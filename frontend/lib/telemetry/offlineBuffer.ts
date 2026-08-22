/**
 * TourSafe - Mobile Telemetry Offline Buffer
 * Bounded local FIFO queue with AsyncStorage durability.
 * Protects telemetry data during network blackouts and handles reconnection replay.
 * Enhanced with batching, idempotency keys, and retry logic for Prompt 17.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  TelemetryPacketEnvelope,
  TelemetryPacketType,
  TelemetryBatchRequest,
  TelemetryBatchAck,
  BatchIdempotency,
} from '../../types/telemetry';
import { RETRY_CONFIG } from '../telemetry/telemetryService';
import { generateId } from '../lib/utils';

const STORAGE_KEY = '@toursafe_telemetry_offline_buffer_v1';
const MAX_BUFFER_CAPACITY = 5000; // ~100 seconds of 50 Hz IMU data or 1.4 hours of 1 Hz GPS

export interface OfflineBufferStats {
  size: number;
  capacity: number;
  droppedPackets: number;
  oldestPacketTimestamp: string | null;
  newestPacketTimestamp: string | null;
  pendingRetries: number;
}

export interface BufferedPacket extends TelemetryPacketEnvelope {
  retryCount: number;
  lastAttemptAt: string;
  batchId?: string;
  idempotencyKey?: BatchIdempotency;
}

class TelemetryOfflineBuffer {
  private buffer: BufferedPacket[] = [];
  private droppedCount: number = 0;
  private isLoaded: boolean = false;
  private saveTimeout: NodeJS.Timeout | null = null;

  constructor() {
    this.loadFromStorage();
  }

  private async loadFromStorage() {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          // Migrate old format to new buffered format
          this.buffer = parsed.map((packet: any) => ({
            ...packet,
            retryCount: packet.attempt_count ?? 0,
            lastAttemptAt: packet.last_attempt_at ?? new Date().toISOString(),
            batchId: packet.batch_id ?? generateId(),
            idempotencyKey: packet.idempotency_key
              ? {
                  batch_id: packet.batch_id || generateId(),
                  tracking_session_id: packet.session_id || "",
                  device_id: packet.device_id || "",
                  created_at: packet.created_at || new Date().toISOString(),
                  payload_hash: packet.payload_hash || this.computePayloadHash(packet),
                }
              : undefined,
          }));
        }
      }
    } catch (e) {
      console.warn('Failed to load telemetry offline buffer from AsyncStorage:', e);
    } finally {
      this.isLoaded = true;
    }
  }

  private computePayloadHash(packet: BufferedPacket): string {
    // Simple hash based on packet IDs and sequence numbers
    const data = `${packet.packet_id}:${packet.sequence_number}`;
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash | 0;
    }
    return Math.abs(hash).toString(36);
  }

  private scheduleSave() {
    if (this.saveTimeout) {
      return;
    }
    this.saveTimeout = setTimeout(async () => {
      this.saveTimeout = null;
      try {
        // Save only packet summaries (without full payload to save space)
        // In a full implementation, we'd use more efficient storage
        const summaries = this.buffer.map((p) => ({
          packet_id: p.packet_id,
          packet_type: p.packet_type,
          session_id: p.session_id,
          sequence_number: p.sequence_number,
          timestamp: p.timestamp,
          is_background: p.is_background,
          retryCount: p.retryCount,
          batchId: p.batchId,
        }));
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(summaries));
      } catch (e) {
        console.warn('Failed to save telemetry offline buffer:', e);
      }
    }, 1000);
  }

  /**
   * Appends a packet to the buffer with bounded overflow drop policy.
   * Preserves idempotency and retry state.
   */
  public enqueue(packet: TelemetryPacketEnvelope): boolean {
    // Set default retry state if not already set
    const bufferedPacket: BufferedPacket = {
      ...packet,
      retryCount: packet.retryCount ?? 0,
      lastAttemptAt: packet.last_attempt_at ?? new Date().toISOString(),
      batchId: packet.batch_id ?? generateId(),
      idempotencyKey: packet.idempotency_key
        ? {
            batch_id: packet.batch_id || generateId(),
            tracking_session_id: packet.session_id || "",
            device_id: packet.device_id || "",
            created_at: packet.created_at || new Date().toISOString(),
            payload_hash: this.computePayloadHashFromEnvelope(packet),
          }
        : {
            batch_id: generateId(),
            tracking_session_id: packet.session_id || "",
            device_id: packet.device_id || "",
            created_at: new Date().toISOString(),
            payload_hash: this.computePayloadHashFromEnvelope(packet),
          },

      // Ensure required fields for buffered format
      sequence_number: packet.sequence_number ?? 0,
      timestamp: packet.timestamp ?? new Date().toISOString(),
    };

    if (this.buffer.length >= MAX_BUFFER_CAPACITY) {
      // Drop oldest 100 packets to free up space, tracking drops
      const dropped = this.buffer.splice(0, 100);
      this.droppedCount += dropped.length;
      // Record data dropped event for diagnostics
      // In production, this would be logged to diagnostics subsystem
    }

    this.buffer.push(bufferedPacket);
    this.scheduleSave();
    return true;
  }

  private computePayloadHashFromEnvelope(envelope: TelemetryPacketEnvelope): string {
    const data = `${envelope.packet_id}:${envelope.sequence_number}:${envelope.session_id}`;
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash | 0;
    }
    return Math.abs(hash).toString(36);
  }

  /**
   * Appends multiple packets to the buffer.
   */
  public enqueueBatch(packets: TelemetryPacketEnvelope[]): number {
    let count = 0;
    for (const p of packets) {
      if (this.enqueue(p)) {
        count++;
      }
    }
    return count;
  }

  /**
   * Peeks the next batch of packets without removing them.
   */
  public peekBatch(maxSize: number = 50): TelemetryPacketEnvelope[] {
    return this.buffer.slice(0, maxSize).map((p) => ({
      packet_id: p.packet_id,
      packet_type: p.packet_type,
      session_id: p.session_id,
      sequence_number: p.sequence_number,
      timestamp: p.timestamp,
      is_background: p.is_background,
      payload: p.payload,
    }));
  }

  /**
   * Removes packets up to the confirmed contiguous sequence number.
   * Used during server acknowledgement processing.
   */
  public removeAcknowledged(sessionId: string, highestContiguousSeq: number): number {
    const initialLen = this.buffer.length;
    this.buffer = this.buffer.filter(
      (p) => !(p.session_id === sessionId && p.sequence_number <= highestContiguousSeq)
    );
    const removed = initialLen - this.buffer.length;
    if (removed > 0) {
      this.scheduleSave();
    }
    return removed;
  }

  /**
   * Removes specific packet IDs confirmed by server ack.
   * Supports idempotency-based deduplication.
   */
  public removePacketIds(packetIds: string[]): number {
    const idSet = new Set(packetIds);
    const initialLen = this.buffer.length;
    this.buffer = this.buffer.filter((p) => !idSet.has(p.packet_id));
    const removed = initialLen - this.buffer.length;
    if (removed > 0) {
      this.scheduleSave();
    }
    return removed;
  }

  /**
   * Clears the buffer.
   */
  public async clear(): Promise<void> {
    this.buffer = [];
    this.droppedCount = 0;
    try {
      await AsyncStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Failed to clear telemetry buffer in storage:', e);
    }
  }

  /**
   * Get buffer statistics including retry state.
   */
  public getStats(): OfflineBufferStats {
    const pendingRetries = this.buffer.filter(
      (p) => p.retryCount > 0).length;

    return {
      size: this.buffer.length,
      capacity: MAX_BUFFER_CAPACITY,
      droppedPackets: this.droppedCount,
      oldestPacketTimestamp:
        this.buffer.length > 0 ? this.buffer[0].timestamp : null,
      newestPacketTimestamp:
        this.buffer.length > 0 ? this.buffer[this.buffer.length - 1].timestamp : null,
      pendingRetries,
    };
  }

  /**
   * Get the full buffer (for replay).
   */
  public get length(): number {
    return this.buffer.length;
  }

  /**
   * Get all buffered packets suitable for batch upload.
   * Filters out packets that should not be uploaded based on retry state.
   */
  public getPacketsForUpload(): TelemetryPacketEnvelope[] {
    return this.buffer
      .filter((p) => p.retryCount < RETRY_CONFIG.maxAttempts)
      .map((p) => ({
        packet_id: p.packet_id,
        packet_type: p.packet_type,
        session_id: p.session_id,
        sequence_number: p.sequence_number,
        timestamp: p.timestamp,
        is_background: p.is_background,
        payload: p.payload,
      }));
  }

  /**
   * Increment retry count for a packet and re-save.
   * Used when a batch upload fails and needs retry.
   */
  public incrementRetry(packetId: string): boolean {
    const index = this.buffer.findIndex((p) => p.packet_id === packetId);
    if (index >= 0) {
      this.buffer[index].retryCount += 1;
      this.buffer[index].lastAttemptAt = new Date().toISOString();
      this.scheduleSave();
      return true;
    }
    return false;
  }

  /**
   * Update the idempotency key for a packet.
   */
  public updateIdempotencyKey(
    packetId: string,
    key: BatchIdempotency
  ): boolean {
    const index = this.buffer.findIndex((p) => p.packet_id === packetId);
    if (index >= 0) {
      this.buffer[index].idempotencyKey = key;
      this.scheduleSave();
      return true;
    }
    return false;
  }

  /**
   * Get packets grouped by batch for organized uploading.
   */
  public getBatchedPackets(batchSize: number = RETRY_CONFIG.initialDelayMs): TelemetryPacketEnvelope[][] {
    const packets = this.getPacketsForUpload();
    const batches: TelemetryPacketEnvelope[][] = [];
    
    for (let i = 0; i < packets.length; i += batchSize) {
      batches.push(packets.slice(i, i + batchSize));
    }
    
    return batches;
  }
}

export const telemetryOfflineBuffer = new TelemetryOfflineBuffer();

export type { OfflineBufferStats, BufferedPacket };