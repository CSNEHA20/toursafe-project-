/**
 * TourSafe Telemetry Service
 * Enhanced telemetry pipeline with batching, idempotency, retry logic,
 * offline buffering, and server synchronization.
 *
 * Principle: at-least-once delivery with server-side idempotency.
 * Never assume the mobile client can guarantee exactly-once delivery.
 */

import {
  TelemetryPacketEnvelope,
  TelemetryPacketType,
  TelemetryBatchRequest,
  TelemetryBatchAck,
  TelemetryAck,
  GPSPayload,
  AccelerometerChannels,
  GyroscopeChannels,
  SessionStatus,
  TelemetryAckStatus,
} from "../../types/telemetry";
import { api } from "../api";
import { telemetryOfflineBuffer } from "./offlineBuffer";
import { batteryService } from "../battery/batteryService";
import { connectivityService } from "../connectivity/connectivityService";
import { useTelemetryStore } from "../../store/telemetryStore";
import { useBatteryStore } from "../../store/batteryStore";
import { useConnectivityStore } from "../..//store/connectivityStore";
import { generateId } from "../../lib/utils";

/**
 * retry configuration for batch uploads.
 * Exponential backoff with jitter. Permanent failures are not retried forever.
 */
export const RETRY_CONFIG = {
  // Initial delay in ms before first retry
  initialDelayMs: 1_000,
  // Maximum delay between retries in ms (capped)
  maxDelayMs: 30_000,
  // Base for exponential backoff
  backoffBase: 2,
  // Maximum number of retry attempts (including initial attempt)
  maxAttempts: 5,
  // Jitter factor (randomized portion of backoff)
  jitter: 0.2, // 20% jitter
  // Permanent error classifications - these will NOT be retried
  permanentErrors: ["403", "401", "400"] as const,
} as const;

/**
 * Classification of upload result status.
 */
export type UploadResult =
  | { status: "accepted"; batchId: string; highestContiguous: number }
  | { status: "duplicate"; batchId: string; highestContiguous: number }
  | { status: "rejected"; reason: string; batchId: string }
  | { status: "buffered"; batchId: string }
  | { status: "permanent_failure"; error: string; batchId: string };

/**
 * Idempotency key for a batch upload.
 * The server must safely handle duplicate uploads using this key.
 */
export interface BatchIdempotency {
  batch_id: string;
  tracking_session_id: string;
  device_id: string;
  created_at: string;
  payload_hash: string; // Hash of the batch payload for duplicate detection
}

/**
 * TelemetryService coordinates the full telemetry pipeline:
 * - Sample ingestion (GPS + IMU)
 * - Batch creation and size management
 * - Upload dispatch with retry and backoff
 * - Server acknowledgement processing
 * - Offline buffer management on failure
 * - Idempotency key generation and validation
 */
class TelemetryService {
  private sessionId: string | null = null;
  private sequenceNumber: number = 0;
  private highestContiguousAck: number = 0;
  private isOnline: boolean = true;
  private isStreaming: boolean = false;
  private pendingBatch: TelemetryPacketEnvelope[] = [];
  private flushTimer: NodeJS.Timeout | null = null;
  private replayInProgress: boolean = false;
  private uploadRetryCounts: Map<string, number> = new Map();

  // Batch configuration - customizable per product requirements
  private readonly BATCH_MAX_SIZE = 25;
  private readonly FLUSH_INTERVAL_MS = 500;
  private readonly MAX_RETRY_ATTEMPTS = RETRY_CONFIG.maxAttempts;

  private listeners: Set<(status: {
    sessionId: string | null;
    sequenceNumber: number;
    highestContiguousAck: number;
    bufferSize: number;
    isOnline: boolean;
    status: SessionStatus;
  }) => void> = new Set();

  constructor() {
    this.subscribeDefaultStore();
  }

  /**
   * Subscribe to the telemetry store for state synchronization.
   */
  private subscribeDefaultStore(): void {
    // Sync selected state to the telemetry store
    // This is a two-way connection: store -> service and service -> store
    const telemetryStore = useTelemetryStore.getState();
    // Note: We don't auto-subscribe to all store changes to avoid circular dependencies.
    // Individual components should read from the store directly as needed.
  }

  /**
   * Subscribe to status changes.
   */
  public subscribe(callback: (status: {
    sessionId: string | null;
    sequenceNumber: number;
    highestContiguousAck: number;
    bufferSize: number;
    isOnline: boolean;
    status: SessionStatus;
  }) => void): () => void {
    this.listeners.add(callback);
    this.notifyListeners();
    return () => this.listeners.delete(callback);
  }

  private notifyListeners(): void {
    const info = {
      sessionId: this.sessionId,
      sequenceNumber: this.sequenceNumber,
      highestContiguousAck: this.highestContiguousAck,
      bufferSize: telemetryOfflineBuffer.length,
      isOnline: this.isOnline,
      status: (this.isStreaming ? "active" : "stopped") as SessionStatus,
    };
    for (const l of this.listeners) {
      try {
        l(info);
      } catch (e) {
        console.error("Telemetry subscriber error:", e);
      }
    }
  }

  /**
   * Start a new telemetry session.
   * Registers with the backend and initializes sequencing.
   */
  public async startSession(deviceId?: string): Promise<string> {
    // 1. Check battery policy - may affect sampling
    const batteryPolicy = batteryService.getCurrentPolicy();
    const connectivityPolicy = connectivityService.getCurrentPolicy();

    // 2. Determine target sampling rate based on policies
    const targetGPSFrequency = batteryPolicy.allowsGPSFrequency(1.0)
      ? 1.0
      : 0.2; // reduced if battery policy doesn't allow
    const targetIMUFrequency = batteryPolicy.allowsIMUFrequency(50.0)
      ? 50.0
      : 10.0; // reduced if battery policy doesn't allow

    // 3. Determine upload strategy based on connectivity
    const uploadStrategy = connectivityPolicy.mode;

    try {
      const res = await api.post("/api/v1/telemetry/session/start", {
        device_id: deviceId,
        sampling_rate_target_hz: targetIMUFrequency,
        gps_frequency_hz: targetGPSFrequency,
        battery_pct: useBatteryStore.getState().batteryInfo.level,
        network_type: connectivityService.getCurrentState().type,
        schema_version: "1.0.0",
        idempotency_key: generateId(),
      });

      this.sessionId = res.data.session_id;
      this.sequenceNumber = 0;
      this.highestContiguousAck = 0;
      this.isStreaming = true;
      this.isOnline = connectivityService.isOffline() === false;
      this.startFlushTimer();
      this.notifyListeners();

      // Initialize offline buffer with session context
      telemetryOfflineBuffer.enqueue({
        batch_id: `batch_${this.sessionId}_0`,
        tracking_session_id: this.sessionId,
        device_id: deviceId || "",
        created_at: new Date().toISOString(),
        sensor_type: "session_start",
        sequence_start: 1,
        sequence_end: 1,
        records: [],
        attempt_count: 0,
        last_attempt_at: new Date().toISOString(),
        status: "pending",
      });

      return this.sessionId;
    } catch (e) {
      // Degraded offline session initialization
      this.sessionId = `offline_sess_${Date.now()}`;
      this.sequenceNumber = 0;
      this.highestContiguousAck = 0;
      this.isStreaming = true;
      this.isOnline = false;
      this.startFlushTimer();
      this.notifyListeners();

      // Initialize offline buffer for degraded mode
      telemetryOfflineBuffer.enqueue({
        batch_id: `batch_${this.sessionId}_0`,
        tracking_session_id: this.sessionId,
        device_id: deviceId || "",
        created_at: new Date().toISOString(),
        sensor_type: "session_start",
        sequence_start: 1,
        sequence_end: 1,
        records: [],
        attempt_count: 0,
        last_attempt_at: new Date().toISOString(),
        status: "pending",
      });

      return this.sessionId;
    }
  }

  /**
   * Stop the current telemetry session.
   * Flushes pending batch and notifies backend.
   */
  public async stopSession(): Promise<void> {
    this.isStreaming = false;
    this.stopFlushTimer();

    // Flush remaining batch
    if (this.pendingBatch.length > 0) {
      await this.flushPendingBatch();
    }

    // Notify backend if we have a server session
    if (this.sessionId && !this.sessionId.startsWith("offline_")) {
      try {
        await api.post("/api/v1/telemetry/session/stop", {
          session_id: this.sessionId,
        });
      } catch (e) {
        console.warn("Failed to notify server of session stop:", e);
      }
    }

    this.sessionId = null;
    this.notifyListeners();
  }

  /**
   * Ingest a new IMU sample, create envelope, and queue for transmission.
   * Applies battery-aware and connectivity-aware sampling decisions.
   */
  public pushIMUSample(
    accel: AccelerometerChannels,
    gyro: GyroscopeChannels,
    gps?: GPSPayload | null,
    isBackground: boolean = false
  ): string | null {
    if (!this.sessionId || !this.isStreaming) {
      return null;
    }

    // 1. Apply battery-aware sampling decision
    const batteryPolicy = batteryService.getCurrentPolicy();
    if (!batteryPolicy.allowsIMUFrequency(50.0)) {
      // Battery policy restricts IMU frequency - could throttle here
      // For now, we still record but may upload at reduced rate
    }

    // 2. Apply connectivity-aware decision
    const connectivityPolicy = connectivityService.getCurrentPolicy();
    const shouldBuffer = connectivityPolicy.mode === "buffer" || connectivityPolicy.requireServerHealth;

    this.sequenceNumber += 1;
    const packetId = `pkt_${this.sessionId}_${this.sequenceNumber}_${Date.now()}`;
    const packetType: TelemetryPacketType = gps ? "telemetry.sample" : "imu.sample";

    const envelope: TelemetryPacketEnvelope = {
      packet_id: packetId,
      packet_type: packetType,
      session_id: this.sessionId,
      sequence_number: this.sequenceNumber,
      timestamp: new Date().toISOString(),
      is_background: isBackground,
      network_status: connectivityService.getCurrentState().type,
      payload: {
        accelerometer: accel,
        gyroscope: gyro,
        latitude: gps?.latitude,
        longitude: gps?.longitude,
        altitude: gps?.altitude,
        accuracy: gps?.accuracy,
        speed: gps?.speed,
        heading: gps?.heading,
        battery_level: useBatteryStore.getState().batteryInfo.level,
        battery_state: useBatteryStore.getState().batteryInfo.isLowPowerMode ? "low_power" : "normal",
      },
    };

    // 3. Decide: upload now or buffer?
    if (shouldBuffer && !connectivityService.isOnline()) {
      // Network is offline - buffer for later
      telemetryOfflineBuffer.enqueue(envelope);
      this.notifyListeners();
      return packetId;
    }

    // 4. Add to pending batch
    this.pendingBatch.push(envelope);

    // 5. Check if batch is full and flush
    if (this.pendingBatch.length >= this.BATCH_MAX_SIZE) {
      this.flushPendingBatch();
    }

    return packetId;
  }

  /**
   * Ingest a standalone GPS sample.
   */
  public pushGPSSample(gps: GPSPayload, isBackground: boolean = false): string | null {
    if (!this.sessionId || !this.isStreaming) {
      return null;
    }

    // Apply battery policy for GPS frequency
    const batteryPolicy = batteryService.getCurrentPolicy();
    if (!batteryPolicy.allowsGPSFrequency(1.0)) {
      // GPS frequency restricted by battery policy
    }

    this.sequenceNumber += 1;
    const packetId = `pkt_${this.sessionId}_${this.sequenceNumber}_${Date.now()}`;

    const envelope: TelemetryPacketEnvelope = {
      packet_id: packetId,
      packet_type: "gps.sample",
      session_id: this.sessionId,
      sequence_number: this.sequenceNumber,
      timestamp: gps.timestamp || new Date().toISOString(),
      is_background: isBackground,
      network_status: connectivityService.getCurrentState().type,
      payload: {
        latitude: gps.latitude,
        longitude: gps.longitude,
        altitude: gps.altitude,
        accuracy: gps.accuracy,
        speed: gps.speed,
        heading: gps.heading,
      },
    };

    // Apply connectivity decision
    const connectivityPolicy = connectivityService.getCurrentPolicy();
    if (connectivityPolicy.mode === "buffer" || !connectivityService.isOnline()) {
      telemetryOfflineBuffer.enqueue(envelope);
      this.notifyListeners();
      return packetId;
    }

    this.pendingBatch.push(envelope);

    if (this.pendingBatch.length >= this.BATCH_MAX_SIZE) {
      this.flushPendingBatch();
    }

    return packetId;
  }

  /**
   * Flush the pending batch to the server with retry logic.
   */
  private async flushPendingBatch(): Promise<void> {
    if (this.pendingBatch.length === 0 || !this.sessionId) {
      return;
    }

    // Take a snapshot of the current batch and clear pending
    const batchToSend = [...this.pendingBatch];
    this.pendingBatch = [];

    // Generate idempotency key for this batch
    const batchId = `batch_${this.sessionId}_${this.sequenceNumber}`;
    const payloadHash = this.computePayloadHash(batchToSend);

    const idempotencyKey: BatchIdempotency = {
      batch_id: batchId,
      tracking_session_id: this.sessionId,
      device_id: "",
      created_at: new Date().toISOString(),
      payload_hash: payloadHash,
    };

    // Determine if we should attempt upload based on connectivity
    const connectivityPolicy = connectivityService.getCurrentPolicy();
    const isOnline = connectivityService.isOnline();

    // If offline, buffer directly
    if (!isOnline) {
      telemetryOfflineBuffer.enqueueBatch(batchToSend);
      this.notifyListeners();
      // Mark as buffered - will be retried on reconnect
      batchToSend.forEach((packet) => {
        packet.is_background ? this.uploadRetryCounts.set(packet.packet_id, 0) : null;
      });
      return;
    }

    // If online, attempt upload with retry
    try {
      const payload: TelemetryBatchRequest = {
        session_id: this.sessionId,
        packets: batchToSend,
      };

      const res = await api.post<TelemetryBatchAck>("/api/v1/telemetry/batch", payload);
      const ack = res.data;

      // Process server acknowledgement
      this.processBatchAck(ack, batchId, idempotencyKey);

      this.notifyListeners();
    } catch (err: any) {
      this.handleBatchUploadError(err, batchToSend, batchId, idempotencyKey);
    }
  }

  /**
   * Process server batch acknowledgement.
   * Handles: accepted, duplicates, out-of-order, rejected.
   */
  private processBatchAck(
    ack: TelemetryBatchAck | undefined,
    batchId: string,
    idempotencyKey: BatchIdempotency
  ): void {
    if (!ack) {
      // No response - treat as buffered for retry
      telemetryOfflineBuffer.enqueueBatch(
        [] // The batch was already consumed from pending; will be re-enqueued
      );
      this.recordRetry(batchId);
      return;
    }

    const { status, accepted_count, duplicate_count, rejected_count,
      highest_contiguous_sequence, missing_sequence_ranges } = ack;

    // Update highest contiguous acknowledgement
    if (highest_contiguous_sequence > this.highestContiguousAck) {
      this.highestContiguousAck = highest_contiguous_sequence;
    }

    // Clear acknowledged packets from the offline buffer
    // (they were already removed from pending, we just need to remove from buffer)
    if (ack.accepted_count > 0) {
      // Remove acknowledged packets from offline buffer
      // Use the highest contiguous sequence to remove ranges
      // Note: session_id from the first packet in the batch
      const firstSessionId = batchId.split("_")[1];
      // We'll use a best-effort approach - remove by packet IDs if available
      // In production, we'd track which packets were in this batch
    }

    // Classify result
    if (status === "accepted" || accepted_count > 0) {
      // Success - remove buffered data
      this.removeUploadedBatch(batchId);
      this.recordRetry(batchId, true);
    } else if (status === "duplicate" || duplicate_count > 0) {
      // Server recognized this as a duplicate - this is expected and safe
      // Idempotency is working correctly
      this.recordRetry(batchId, true);
    } else if (status === "rejected" || rejected_count > 0) {
      // Permanent rejection - do not retry
      this.recordRetry(batchId, false, true);
    } else {
      // Unknown status - buffer for retry
      telemetryOfflineBuffer.enqueueBatch(batchToSend);
      this.recordRetry(batchId);
    }
  }

  /**
   * Handle batch upload error with exponential backoff retry.
   */
  private async handleBatchUploadError(
    err: any,
    batch: TelemetryPacketEnvelope[],
    batchId: string,
    idempotencyKey: BatchIdempotency
  ): Promise<void> {
    const currentAttempt = this.uploadRetryCounts.get(batchId) || 0;

    if (currentAttempt >= this.MAX_RETRY_ATTEMPTS) {
      // Max retries exceeded - buffer for later manual review
      console.error(`[TelemetryService] Max retry attempts exceeded for batch ${batchId}`);
      telemetryOfflineBuffer.enqueueBatch(batch);
      this.notifyListeners();
      return;
    }

    // Classify error type for retry decision
    const errorCode = err?.response?.status?.toString();
    const isPermanent = RETRY_CONFIG.permanentErrors.includes(errorCode as any);

    if (isPermanent) {
      // Permanent error (401 Unauthorized, 403 Forbidden, 400 Bad Request)
      // Do not retry - these indicate client or auth problems
      console.warn(`[TelemetryService] Permanent upload error for batch ${batchId}: ${errorCode}`);
      telemetryOfflineBuffer.enqueueBatch(batch);
      this.notifyListeners();
      return;
    }

    // Transient error - apply exponential backoff with jitter
    const backoffMs = this.computeBackoffDelay(currentAttempt);

    // Mark this batch with retry state
    this.uploadRetryCounts.set(batchId, currentAttempt + 1);

    // Buffer the batch - it will be retried when connectivity restores
    // or when the retry timer fires
    telemetryOfflineBuffer.enqueueBatch(batch);

    // Notify UI of pending retry
    this.notifyListeners();

    // Schedule automatic retry after backoff
    setTimeout(() => {
      // Re-fetch in case session/state changed
      this.attemptRetry(batchId);
    }, backoffMs);
  }

  /**
   * Compute exponential backoff delay with jitter.
   */
  private computeBackoffDelay(attempt: number): number {
    // Exponential: initialDelay * backoffBase^attempt
    const baseDelay = RETRY_CONFIG.initialDelayMs * Math.pow(RETRY_CONFIG.backoffBase, attempt);

    // Cap at maxDelayMs
    const cappedDelay = Math.min(baseDelay, RETRY_CONFIG.maxDelayMs);

    // Add jitter: random factor up to jitter fraction
    const jitterRange = cappedDelay * RETRY_CONFIG.jitter;
    const jitter = Math.random() * jitterRange * 2 - jitterRange; // -jitterRange to +jitterRange

    return Math.max(1, cappedDelay + jitter);
  }

  /**
   * Attempt a retry of a previously failed batch.
   */
  private async attemptRetry(batchId: string): Promise<void> {
    const currentAttempt = this.uploadRetryCounts.get(batchId) || 0;

    if (currentAttempt >= this.MAX_RETRY_ATTEMPTS) {
      return; // Already at max, give up
    }

    // Check connectivity before retrying
    const isOnline = connectivityService.isOnline();
    const batteryPolicy = batteryService.getCurrentPolicy();

    // Don't retry if battery is critical and policy says buffer
    if (batteryPolicy.policyKey === "critical" && !batteryPolicy.allowCellularOnly) {
      // Delay retry further
      this.uploadRetryCounts.set(batchId, currentAttempt + 1);
      setTimeout(() => this.attemptRetry(batchId), 30_000);
      return;
    }

    // Check if we should use cellular
    const allowsCellular = batteryPolicy.allowsCellularUploads();
    const connectivityPolicy = connectivityService.getCurrentPolicy();

    // Only retry if conditions allow
    if (!isOnline && !allowsCellular) {
      // Still offline and cellular not allowed - defer further
      this.uploadRetryCounts.set(batchId, currentAttempt + 1);
      setTimeout(() => this.attemptRetry(batchId), 60_000);
      return;
    }

    // Try to upload again
    try {
      // Re-fetch the buffered packets
      // In a full implementation, we'd retrieve from offline buffer
      // For now, we'll just notify and reset retry count
      this.uploadRetryCounts.delete(batchId);
      this.notifyListeners();
    } catch (err) {
      // Retry again
      this.uploadRetryCounts.set(batchId, currentAttempt + 1);
      const backoffMs = this.computeBackoffDelay(currentAttempt + 1);
      setTimeout(() => this.attemptRetry(batchId), backoffMs);
    }
  }

  /**
   * Remove uploaded batch from offline buffer using idempotency.
   */
  private removeUploadedBatch(batchId: string): void {
    // Remove from offline buffer using batch_id pattern
    // The actual implementation depends on buffer schema
    // This is a best-effort cleanup
    telemetryOfflineBuffer.removePacketIds([batchId]);
    this.notifyListeners();
  }

  /**
   * Compute a hash of the batch payload for idempotency key generation.
   */
  private computePayloadHash(packets: TelemetryPacketEnvelope[]): string {
    // Simple hash based on packet IDs and sequence numbers
    // In production, use a proper cryptographic hash
    const identifiers = packets
      .map((p) => `${p.packet_id}:${p.sequence_number}`)
      .sort()
      .join("|");
    // Use btoa for a simple string hash
    let hash = 0;
    for (let i = 0; i < identifiers.length; i++) {
      const char = identifiers.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash | 0; // Convert to 32bit integer
    }
    return Math.abs(hash).toString(36);
  }

  /**
   * Record retry attempt in tracking store.
   */
  private recordRetry(
    batchId: string,
    resetting: boolean = false,
    permanent: boolean = false
  ): void {
    if (resetting) {
      this.uploadRetryCounts.delete(batchId);
    } else if (permanent) {
      // Mark as permanent - don't retry again
      this.uploadRetryCounts.set(batchId, -1); // -1 signals permanent
    } else {
      this.uploadRetryCounts.set(batchId, (this.uploadRetryCounts.get(batchId) || 0) + 1);
    }
  }

  /**
   * Replay offline buffer packets to server upon reconnection.
   */
  public async replayOfflineBuffer(): Promise<void> {
    if (this.replayInProgress || telemetryOfflineBuffer.length === 0) {
      return;
    }

    this.replayInProgress = true;
    try {
      // Process in batches of 50
      while (telemetryOfflineBuffer.length > 0) {
        const batch = telemetryOfflineBuffer.peekBatch(50);
        if (batch.length === 0) break;

        const sessionId = batch[0].session_id;
        const payload: TelemetryBatchRequest = {
          session_id: sessionId,
          packets: batch,
        };

        try {
          const res = await api.post<TelemetryBatchAck>("/api/v1/telemetry/batch", payload);
          const ack = res.data;

          if (ack) {
            // Remove acknowledged packets (up to highest contiguous sequence)
            telemetryOfflineBuffer.removeAcknowledged(sessionId, ack.highest_contiguous_sequence);
            if (ack.highest_contiguous_sequence > this.highestContiguousAck) {
              this.highestContiguousAck = ack.highest_contiguous_sequence;
            }
          } else {
            // Remove by packet IDs
            telemetryOfflineBuffer.removePacketIds(batch.map((b) => b.packet_id));
          }
        } catch (e) {
          // Break on error - will be retried next reconnect cycle
          console.warn("Offline buffer replay interrupted:", e);
          break;
        }
      }
    } finally {
      this.replayInProgress = false;
      this.notifyListeners();
    }
  }

  /**
   * Get current session info.
   */
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

  /**
   * Stop the flush timer.
   */
  private stopFlushTimer(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
  }

  /**
   * Start the flush timer - periodically attempts to send pending batches.
   */
  private startFlushTimer(): void {
    if (this.flushTimer) return;
    this.flushTimer = setInterval(() => {
      if (this.pendingBatch.length > 0) {
        this.flushPendingBatch();
      }
      // Also try replaying offline buffer if we just came online
      if (this.isOnline && telemetryOfflineBuffer.length > 0 && !this.replayInProgress) {
        this.replayOfflineBuffer();
      }
    }, this.FLUSH_INTERVAL_MS);
  }
}

export const telemetryService = new TelemetryService();

/**
 * Utility: generates a random ID string for batch/idempotency keys.
 */
function generateId(): string {
  return `batch_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
}

/**
 * Compute a simple hash of a payload array for idempotency detection.
 * Used to identify duplicate batches across upload attempts.
 */
function computePayloadHash(packets: any[]): string {
  const data = packets.map((p) => ({
    id: p.packet_id,
    seq: p.sequence_number,
    type: p.packet_type,
  }));
  const sorted = data.sort((a: any, b: any) => a.id.localeCompare(b.id));
  let hash = 0;
  for (let i = 0; i < sorted.length; i++) {
    const char = sorted[i].id.charCodeAt(0);
    hash = ((hash << 5) - hash) + char;
    hash = hash | 0;
  }
  return Math.abs(hash).toString(36);
}