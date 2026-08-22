/**
 * TourSafe Battery Types
 * Canonical battery state and policy definitions for the telemetry pipeline.
 */

/**
 * Raw battery information from the device.
 */
export interface BatteryInfo {
  level: number;          // Battery percentage (0-100)
  isCharging: boolean;    // Whether the device is charging
  isLowPowerMode: boolean; // Whether low-power mode is active
}

/**
 * Battery level policy determined from current state.
 * Used by the telemetry pipeline to adapt sampling behavior.
 */
export interface BatteryLevelPolicy {
  policyKey: "normal" | "low" | "critical";
  batteryLevel: number;
  isCharging: boolean;
  isLowPowerMode: boolean;
  gpsFrequencyHz: number;
  imuFrequencyHz: number;
  allowBackground: boolean;
  allowWifiOnly: boolean;
  allowCellularOnly: boolean;
}

/**
 * Battery level thresholds for policy determination.
 * These are configurable per product requirements.
 * Exported as const so they can be used as values.
 */
export const BATTERY_THRESHOLDS = {
  critical: 5,   // Below 5% - critical low battery
  low: 15,       // Below 15% - low battery
  normal: 40,    // Above 40% - normal operation
} as const;

/**
 * Default battery-aware sampling policies.
 * Deterministic and bounded - no ML-driven arbitrary rates.
 * Exported as const so they can be used as values.
 */
export const BATTERY_POLICIES = {
  normal: {
    gpsFrequencyHz: 1.0,
    imuFrequencyHz: 50.0,
    allowBackground: true,
    allowWifiOnly: false,
    allowCellularOnly: true,
  } as const,
  low: {
    gpsFrequencyHz: 0.5,
    imuFrequencyHz: 25.0,
    allowBackground: true,
    allowWifiOnly: false,
    allowCellularOnly: true,
  } as const,
  critical: {
    gpsFrequencyHz: 0.2,
    imuFrequencyHz: 10.0,
    allowBackground: true,
    allowWifiOnly: true,
    allowCellularOnly: false,
  } as const,
} as const;

/**
 * Derive the battery-aware sampling policy from the device's battery state.
 *
 * Inputs:
 *   - batteryLevel: Current battery percentage (0-100)
 *   - isCharging: Whether the device is charging
 *   - isLowPowerMode: Whether low-power mode is active
 *
 * Output: BatteryLevelPolicy with adjusted frequencies and permissions.
 */
export function deriveBatteryPolicy(
  batteryLevel: number,
  isCharging: boolean,
  isLowPowerMode: boolean
): BatteryLevelPolicy {
  let policyKey: "normal" | "low" | "critical" = "normal";

  if (isLowPowerMode) {
    policyKey = "critical";
  } else if (batteryLevel <= BATTERY_THRESHOLDS.critical) {
    policyKey = "critical";
  } else if (batteryLevel <= BATTERY_THRESHOLDS.low) {
    policyKey = "low";
  } else {
    policyKey = "normal";
  }

  const base = BATTERY_POLICIES[policyKey];

  return {
    ...base,
    batteryLevel,
    isCharging,
    isLowPowerMode,
    policyKey,
  };
}