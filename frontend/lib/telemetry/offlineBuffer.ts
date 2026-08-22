/**
 * TourSafe - Mobile Telemetry Offline Buffer
 * Bounded local FIFO queue with AsyncStorage durability.
 * Protects telemetry data during network blackouts and handles reconnection replay.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  TelemetryPacketEnvelope,
  BatchIdempotency,
} from '@/types/telemetry';

const STORAGE_KEY = '@toursafe_telemetry_offline_buffer_v1';
const MAX_BUFFER_CAPACITY = 5000;

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
  private saveTimeout: any = null;

  constructor() {
    this.loadFromStorage();
  }

  public get length(): number {
    return this.buffer.length;
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
    } catch {
      // Ignore load error
    } finally {
      this.isLoaded = true;
    }
  }

  private scheduleSave() {
    if (this.saveTimeout) clearTimeout(this.saveTimeout);
    this.saveTimeout = setTimeout(async () => {
      try {
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(this.buffer.slice(0, MAX_BUFFER_CAPACITY)));
      } catch {
        // Storage full
      }
    }, 1000);
  }

  public enqueue(packet: TelemetryPacketEnvelope): boolean {
    if (this.buffer.length >= MAX_BUFFER_CAPACITY) {
      this.buffer.shift();
      this.droppedCount++;
    }

    const buffered: BufferedPacket = {
      ...packet,
      retryCount: 0,
      lastAttemptAt: new Date().toISOString(),
    };

    this.buffer.push(buffered);
    this.scheduleSave();
    return true;
  }

  public enqueueBatch(packets: TelemetryPacketEnvelope[]): void {
    packets.forEach((p) => this.enqueue(p));
  }

  public peekBatch(count: number = 50): BufferedPacket[] {
    return this.buffer.slice(0, count);
  }

  public removeBatch(packetIds: string[]): void {
    const idSet = new Set(packetIds);
    this.buffer = this.buffer.filter((p) => !idSet.has(p.packet_id));
    this.scheduleSave();
  }

  public removePacketIds(packetIds: string[]): void {
    this.removeBatch(packetIds);
  }

  public removeAcknowledged(sequenceNumber: number, sessionId?: string): void {
    this.buffer = this.buffer.filter((p) => p.sequence_number > sequenceNumber);
    this.scheduleSave();
  }

  public clear(): void {
    this.buffer = [];
    this.scheduleSave();
  }

  public getStats(): OfflineBufferStats {
    return {
      size: this.buffer.length,
      capacity: MAX_BUFFER_CAPACITY,
      droppedPackets: this.droppedCount,
      oldestPacketTimestamp: this.buffer[0]?.timestamp || null,
      newestPacketTimestamp: this.buffer[this.buffer.length - 1]?.timestamp || null,
      pendingRetries: this.buffer.length,
    };
  }
}

export const telemetryOfflineBuffer = new TelemetryOfflineBuffer();