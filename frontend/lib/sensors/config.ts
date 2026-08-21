/**
 * TourSafe IMU Sensor Acquisition Configuration
 * Single source of truth for sampling target, synchronization tolerances,
 * buffer sizing, and sensor quality classification thresholds.
 */

export const IMU_CONFIG = {
  /**
   * Target hardware sampling interval in milliseconds.
   * 20 ms interval = 50 Hz target sampling frequency.
   * Note: This is an OS target, not guaranteed hardware delivery.
   */
  SAMPLE_INTERVAL_MS: 20,

  /**
   * Target sampling frequency in Hz.
   */
  TARGET_FREQUENCY_HZ: 50,

  /**
   * Maximum allowed timestamp divergence (in ms) to consider
   * an Accelerometer sample and a Gyroscope sample synchronized.
   */
  SYNC_TOLERANCE_MS: 25,

  /**
   * Maximum capacity of the bounded in-memory sliding buffer.
   * 250 samples @ 50 Hz = exactly 5.0 seconds of recent telemetry.
   */
  BUFFER_MAX_CAPACITY: 250,

  /**
   * Inter-sample delivery delay (in ms) above which a delivery gap is recorded.
   * 50 ms represents 2.5x the nominal 20 ms target interval.
   */
  GAP_THRESHOLD_MS: 50,

  /**
   * Minimum frequency (Hz) for "excellent" quality rating.
   */
  QUALITY_EXCELLENT_MIN_HZ: 45,

  /**
   * Minimum frequency (Hz) for "good" quality rating.
   */
  QUALITY_GOOD_MIN_HZ: 35,

  /**
   * Minimum frequency (Hz) for "degraded" quality rating.
   */
  QUALITY_DEGRADED_MIN_HZ: 20,

  /**
   * Maximum jitter (ms) for "excellent" quality rating.
   */
  QUALITY_EXCELLENT_MAX_JITTER_MS: 6,

  /**
   * Maximum jitter (ms) for "good" quality rating.
   */
  QUALITY_GOOD_MAX_JITTER_MS: 15,

  /**
   * Maximum accelerometer-gyroscope sync offset (ms) for "excellent" rating.
   */
  QUALITY_EXCELLENT_MAX_SYNC_DELTA_MS: 10,

  /**
   * Maximum accelerometer-gyroscope sync offset (ms) for "good" rating.
   */
  QUALITY_GOOD_MAX_SYNC_DELTA_MS: 25,

  /**
   * Earth gravity acceleration constant in m/s^2.
   * Expo sensors return accelerometer values in units of 'g' (1g ≈ 9.80665 m/s^2).
   */
  GRAVITY_EARTH_MPS2: 9.80665,
} as const;
