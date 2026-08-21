/**
 * TourSafe - Frontend Telemetry Client
 * Coordinates GPS + IMU sampling, envelope creation, monotonic sequence tracking,
 * batch dispatching, server acknowledgement processing, and offline buffer replay.
 */

import { api } from '../api';
import {
  TelemetryPacketEnvelope,
  TelemetryPacketType,
  TelemetryAck,
  TelemetryBatchAck,
  TelemetryBatchRequest,
  GPSPayload,
  AccelerometerChannels,
  GyroscopeChannels,
  SessionStatus,
} from '../../types/telemetry';
import { telemetryOfflineBuffer } from './offlineBuffer';

export type TelemetryStatusCallback = (status: {
  sessionId: string | null;
  sequenceNumber: number;
  highestContiguousAck: number;
  bufferSize: number;
  isOnline: boolean;
  status: SessionStatus;
}) => void;

class TelemetryClient {
  private sessionId: string | null = null;
  private sequenceNumber: number = 0;
  private highestContiguousAck: number = 0;
  private isOnline: boolean = true;
  private isStreaming: boolean = false;
  private pendingBatch: TelemetryPacketEnvelope[] = [];
  private flushTimer: NodeJS.Timeout | null = null;
  private replayInProgress: boolean = false;
  private listeners: Set<TelemetryStatusCallback> = new Set();

  private readonly BATCH_MAX_SIZE = 25;
  private readonly FLUSH_INTERVAL_MS = 500;

  public subscribe(callback: TelemetryStatusCallback): () => void {
    this.listeners.add(callback);
    this.notifyListeners();
    return () => this.listeners.delete(callback);
  }

  private notifyListeners() {
    const info = {
      sessionId: this.sessionId,
      sequenceNumber: this.sequenceNumber,
      highestContiguousAck: this.highestContiguousAck,
      bufferSize: telemetryOfflineBuffer.length,
      isOnline: this.isOnline,
      status: (this.isStreaming ? 'active' : 'stopped') as SessionStatus,
    };
    for (const l of this.listeners) {
      try {
        l(info);
      } catch (e) {
        console.error('Telemetry subscriber error:', e);
      }
    }
  }

  public async startSession(deviceId?: string): Promise<string> {
    try {
      const res = await api.post('/api/v1/telemetry/session/start', {
        device_id: deviceId,
        sampling_rate_target_hz: 50.0,
      });
      this.sessionId = res.data.session_id;
      this.sequenceNumber = 0;
      this.highestContiguousAck = 0;
      this.isStreaming = true;
      this.isOnline = true;
      this.startFlushTimer();
      this.notifyListeners();
      return this.sessionId!;
    } catch (e) {
      // Degraded offline session initialization
      this.sessionId = `offline_sess_${Date.now()}`;
      this.sequenceNumber = 0;
      this.highestContiguousAck = 0;
      this.isStreaming = true;
      this.isOnline = false;
      this.startFlushTimer();
      this.notifyListeners();
      return this.sessionId;
    }
  }

  public async stopSession(): Promise<void> {
    this.isStreaming = false;
    this.stopFlushTimer();

    // Flush remaining buffer
    if (this.pendingBatch.length > 0) {
      await this.flushPendingBatch();
    }

    if (this.sessionId && !this.sessionId.startsWith('offline_')) {
      try {
        await api.post('/api/v1/telemetry/session/stop', {
          session_id: this.sessionId,
        });
      } catch (e) {
        console.warn('Failed to notify server of session stop:', e);
      }
    }

    this.sessionId = null;
    this.notifyListeners();
  }

  /**
   * Ingests a new IMU sample, creates canonical envelope, and queues for transmission.
   */
  public pushIMUSample(
    accel: AccelerometerChannels,
    gyro: GyroscopeChannels,
    gps?: GPSPayload | null,
    isBackground: boolean = false
  ): string {
    if (!this.sessionId || !this.isStreaming) {
      return '';
    }

    this.sequenceNumber += 1;
    const packetId = `pkt_${this.sessionId}_${this.sequenceNumber}_${Date.now()}`;
    const packetType: TelemetryPacketType = gps ? 'telemetry.sample' : 'imu.sample';

    const envelope: TelemetryPacketEnvelope = {
      packet_id: packetId,
      packet_type: packetType,
      session_id: this.sessionId,
      sequence_number: this.sequenceNumber,
      timestamp: new Date().toISOString(),
      is_background: isBackground,
      payload: {
        accelerometer: accel,
        gyroscope: gyro,
        latitude: gps?.latitude,
        longitude: gps?.longitude,
        altitude: gps?.altitude,
        accuracy: gps?.accuracy,
        speed: gps?.speed,
        heading: gps?.heading,
      },
    };

    this.pendingBatch.push(envelope);
    if (this.pendingBatch.length >= this.BATCH_MAX_SIZE) {
      this.flushPendingBatch();
    }

    return packetId;
  }

  /**
   * Ingests a standalone GPS sample.
   */
  public pushGPSSample(gps: GPSPayload, isBackground: boolean = false): string {
    if (!this.sessionId || !this.isStreaming) {
      return '';
    }

    this.sequenceNumber += 1;
    const packetId = `pkt_${this.sessionId}_${this.sequenceNumber}_${Date.now()}`;

    const envelope: TelemetryPacketEnvelope = {
      packet_id: packetId,
      packet_type: 'gps.sample',
      session_id: this.sessionId,
      sequence_number: this.sequenceNumber,
      timestamp: gps.timestamp || new Date().toISOString(),
      is_background: isBackground,
      payload: {
        latitude: gps.latitude,
        longitude: gps.longitude,
        altitude: gps.altitude,
        accuracy: gps.accuracy,
        speed: gps.speed,
        heading: gps.heading,
      },
    };

    this.pendingBatch.push(envelope);
    this.flushPendingBatch();
    return packetId;
  }

  private startFlushTimer() {
    if (this.flushTimer) return;
    this.flushTimer = setInterval(() => {
      if (this.pendingBatch.length > 0) {
        this.flushPendingBatch();
      }
      if (this.isOnline && telemetryOfflineBuffer.length > 0 && !this.replayInProgress) {
        this.replayOfflineBuffer();
      }
    }, this.FLUSH_INTERVAL_MS);
  }

  private stopFlushTimer() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
  }

  private async flushPendingBatch(): Promise<void> {
    if (this.pendingBatch.length === 0 || !this.sessionId) {
      return;
    }

    const batchToSend = [...this.pendingBatch];
    this.pendingBatch = [];

    if (!this.isOnline) {
      // Directly buffer offline
      telemetryOfflineBuffer.enqueueBatch(batchToSend);
      this.notifyListeners();
      return;
    }

    try {
      const payload: TelemetryBatchRequest = {
        session_id: this.sessionId,
        packets: batchToSend,
      };

      const res = await api.post<TelemetryBatchAck>('/api/v1/telemetry/batch', payload);
      const ack = res.data;

      if (ack && ack.highest_contiguous_sequence > this.highestContiguousAck) {
        this.highestContiguousAck = ack.highest_contiguous_sequence;
      }
      this.isOnline = true;
      this.notifyListeners();
    } catch (err) {
      console.warn('Telemetry batch transmission failed, redirecting to offline buffer:', err);
      this.isOnline = false;
      telemetryOfflineBuffer.enqueueBatch(batchToSend);
      this.notifyListeners();
    }
  }

  /**
   * Replays stored offline buffer packets to the server upon reconnection.
   */
  public async replayOfflineBuffer(): Promise<void> {
    if (this.replayInProgress || telemetryOfflineBuffer.length === 0) {
      return;
    }

    this.replayInProgress = true;
    try {
      while (telemetryOfflineBuffer.length > 0) {
        const batch = telemetryOfflineBuffer.peekBatch(50);
        if (batch.length === 0) break;

        const sessionId = batch[0].session_id;
        const payload: TelemetryBatchRequest = {
          session_id: sessionId,
          packets: batch,
        };

        const res = await api.post<TelemetryBatchAck>('/api/v1/telemetry/batch', payload);
        const ack = res.data;

        if (ack) {
          telemetryOfflineBuffer.removeAcknowledged(sessionId, ack.highest_contiguous_sequence);
          if (ack.highest_contiguous_sequence > this.highestContiguousAck) {
            this.highestContiguousAck = ack.highest_contiguous_sequence;
          }
        } else {
          telemetryOfflineBuffer.removePacketIds(batch.map((b) => b.packet_id));
        }

        this.isOnline = true;
        this.notifyListeners();
      }
    } catch (e) {
      console.warn('Offline buffer replay interrupted:', e);
      this.isOnline = false;
    } finally {
      this.replayInProgress = false;
      this.notifyListeners();
    }
  }

  public getSessionInfo() {
    return {
      sessionId: this.sessionId,
      sequenceNumber: this.sequenceNumber,
      highestContiguousAck: this.highestContiguousAck,
      isOnline: this.isOnline,
      isStreaming: this.isStreaming,
      offlineBufferSize: telemetryOfflineBuffer.length,
    };
  }
}

export const telemetryClient = new TelemetryClient();
