/**
 * TourSafe - Mobile Telemetry Offline Buffer
 * Bounded local FIFO queue with AsyncStorage durability.
 * Protects telemetry data during network blackouts and handles reconnection replay.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { TelemetryPacketEnvelope } from '../../types/telemetry';

const STORAGE_KEY = '@toursafe_telemetry_offline_buffer_v1';
const MAX_BUFFER_CAPACITY = 5000; // ~100 seconds of 50 Hz IMU data or 1.4 hours of 1 Hz GPS

export interface OfflineBufferStats {
  size: number;
  capacity: number;
  droppedPackets: number;
  oldestPacketTimestamp: string | null;
  newestPacketTimestamp: string | null;
}

class TelemetryOfflineBuffer {
  private buffer: TelemetryPacketEnvelope[] = [];
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
          this.buffer = parsed;
        }
      }
    } catch (e) {
      console.warn('Failed to load telemetry offline buffer from AsyncStorage:', e);
    } finally {
      this.isLoaded = true;
    }
  }

  private scheduleSave() {
    if (this.saveTimeout) {
      return;
    }
    this.saveTimeout = setTimeout(async () => {
      this.saveTimeout = null;
      try {
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(this.buffer.slice(0, 2000)));
      } catch (e) {
        console.warn('Failed to save telemetry offline buffer:', e);
      }
    }, 1000);
  }

  /**
   * Appends a packet to the buffer with bounded overflow drop policy.
   */
  public enqueue(packet: TelemetryPacketEnvelope): boolean {
    if (this.buffer.length >= MAX_BUFFER_CAPACITY) {
      // Drop oldest 100 packets to free up space
      this.buffer.splice(0, 100);
      this.droppedCount += 100;
    }

    this.buffer.push(packet);
    this.scheduleSave();
    return true;
  }

  /**
   * Appends multiple packets to the buffer.
   */
  public enqueueBatch(packets: TelemetryPacketEnvelope[]): number {
    for (const p of packets) {
      this.enqueue(p);
    }
    return packets.length;
  }

  /**
   * Peeks the next batch of packets without removing them.
   */
  public peekBatch(maxSize: number = 50): TelemetryPacketEnvelope[] {
    return this.buffer.slice(0, maxSize);
  }

  /**
   * Removes packets up to the confirmed contiguous sequence number.
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

  public getStats(): OfflineBufferStats {
    return {
      size: this.buffer.length,
      capacity: MAX_BUFFER_CAPACITY,
      droppedPackets: this.droppedCount,
      oldestPacketTimestamp: this.buffer.length > 0 ? this.buffer[0].timestamp : null,
      newestPacketTimestamp:
        this.buffer.length > 0 ? this.buffer[this.buffer.length - 1].timestamp : null,
    };
  }

  public get length(): number {
    return this.buffer.length;
  }
}

export const telemetryOfflineBuffer = new TelemetryOfflineBuffer();
