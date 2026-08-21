/**
 * TourSafe Location Quality & Telemetry Metrics Calculator
 * Calculates measurable GPS metrics: accuracy, observed frequency (Hz), intervals, and staleness.
 */

import type { LocationQualityMetrics, LocationQualityState, LocationSample } from "@/types/location";

const MAX_HISTORY_WINDOW = 30; // 30 samples window for rolling statistics

export class QualityCalculator {
  private samples: { timestampMs: number; accuracy: number | null }[] = [];

  public reset() {
    this.samples = [];
  }

  public recordSample(sample: LocationSample): LocationQualityMetrics {
    const tsMs = new Date(sample.timestamp).getTime();
    this.samples.push({
      timestampMs: tsMs,
      accuracy: sample.accuracy ?? null,
    });

    if (this.samples.length > MAX_HISTORY_WINDOW) {
      this.samples.shift();
    }

    return this.getMetrics();
  }

  public getMetrics(): LocationQualityMetrics {
    const count = this.samples.length;
    const now = Date.now();

    if (count === 0) {
      return {
        qualityState: "unavailable",
        sampleCount: 0,
        observedFrequencyHz: 0,
        averageIntervalMs: 0,
        minIntervalMs: 0,
        maxIntervalMs: 0,
        currentAccuracyMeters: null,
        staleDurationSeconds: 0,
        lastUpdateTimestamp: null,
      };
    }

    const latest = this.samples[count - 1];
    const staleDurationSeconds = Math.max(0, Math.round((now - latest.timestampMs) / 1000));

    if (count === 1) {
      const qState: LocationQualityState =
        staleDurationSeconds > 15
          ? "stale"
          : (latest.accuracy ?? 100) <= 15
          ? "good"
          : "degraded";

      return {
        qualityState: qState,
        sampleCount: 1,
        observedFrequencyHz: 1.0,
        averageIntervalMs: 1000,
        minIntervalMs: 1000,
        maxIntervalMs: 1000,
        currentAccuracyMeters: latest.accuracy,
        staleDurationSeconds,
        lastUpdateTimestamp: new Date(latest.timestampMs).toISOString(),
      };
    }

    // Calculate intervals
    const intervals: number[] = [];
    for (let i = 1; i < count; i++) {
      const diff = Math.max(1, this.samples[i].timestampMs - this.samples[i - 1].timestampMs);
      intervals.push(diff);
    }

    const sumIntervals = intervals.reduce((a, b) => a + b, 0);
    const avgIntervalMs = Math.round(sumIntervals / intervals.length);
    const minIntervalMs = Math.min(...intervals);
    const maxIntervalMs = Math.max(...intervals);
    const observedFrequencyHz = avgIntervalMs > 0 ? Number((1000 / avgIntervalMs).toFixed(2)) : 0;

    const currentAcc = latest.accuracy;

    // Quality State classification based on measurable physical properties
    let qualityState: LocationQualityState = "unavailable";
    if (staleDurationSeconds > 15) {
      qualityState = "stale";
    } else if (currentAcc !== null) {
      if (currentAcc <= 10 && avgIntervalMs <= 3000) {
        qualityState = "excellent";
      } else if (currentAcc <= 25 && avgIntervalMs <= 8000) {
        qualityState = "good";
      } else if (currentAcc <= 50 && avgIntervalMs <= 15000) {
        qualityState = "degraded";
      } else {
        qualityState = "poor";
      }
    } else {
      qualityState = "degraded";
    }

    return {
      qualityState,
      sampleCount: count,
      observedFrequencyHz,
      averageIntervalMs: avgIntervalMs,
      minIntervalMs,
      maxIntervalMs,
      currentAccuracyMeters: currentAcc,
      staleDurationSeconds,
      lastUpdateTimestamp: new Date(latest.timestampMs).toISOString(),
    };
  }
}
