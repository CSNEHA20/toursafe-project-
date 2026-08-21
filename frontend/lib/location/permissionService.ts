/**
 * TourSafe Location Permission Service
 * Manages foreground and background location permissions across Web, Android, and iOS.
 */

import * as Location from "expo-location";
import { Platform } from "react-native";
import type { LocationPermissionState } from "@/types/location";

class LocationPermissionService {
  private foregroundState: LocationPermissionState = "unknown";
  private backgroundState: LocationPermissionState = "unknown";
  private isRequesting = false;

  public getForegroundState(): LocationPermissionState {
    return this.foregroundState;
  }

  public getBackgroundState(): LocationPermissionState {
    return this.backgroundState;
  }

  /**
   * Check current foreground and background permission status without prompting user.
   */
  public async checkPermissions(): Promise<{
    foreground: LocationPermissionState;
    background: LocationPermissionState;
  }> {
    try {
      if (Platform.OS === "web" && typeof navigator === "undefined") {
        this.foregroundState = "unavailable";
        this.backgroundState = "unavailable";
        return { foreground: "unavailable", background: "unavailable" };
      }

      const fgStatus = await Location.getForegroundPermissionsAsync();
      this.foregroundState = this.normalizePermissionStatus(fgStatus);

      if (Platform.OS !== "web" && this.foregroundState === "granted") {
        try {
          const bgStatus = await Location.getBackgroundPermissionsAsync();
          this.backgroundState = this.normalizePermissionStatus(bgStatus);
        } catch {
          this.backgroundState = "unavailable";
        }
      } else {
        this.backgroundState = Platform.OS === "web" ? "unavailable" : "unknown";
      }

      return {
        foreground: this.foregroundState,
        background: this.backgroundState,
      };
    } catch (error) {
      console.warn("[PermissionService] Error checking permissions:", error);
      this.foregroundState = "unavailable";
      this.backgroundState = "unavailable";
      return { foreground: "unavailable", background: "unavailable" };
    }
  }

  /**
   * Explicitly request foreground location permission.
   */
  public async requestForegroundPermission(): Promise<LocationPermissionState> {
    if (this.isRequesting) return this.foregroundState;
    this.isRequesting = true;

    try {
      // Check if location services are enabled on device
      const isServicesEnabled = await Location.hasServicesEnabledAsync();
      if (!isServicesEnabled) {
        this.foregroundState = "unavailable";
        this.isRequesting = false;
        return "unavailable";
      }

      const result = await Location.requestForegroundPermissionsAsync();
      this.foregroundState = this.normalizePermissionStatus(result);
      return this.foregroundState;
    } catch (error) {
      console.error("[PermissionService] Foreground permission request failed:", error);
      this.foregroundState = "denied";
      return "denied";
    } finally {
      this.isRequesting = false;
    }
  }

  /**
   * Request background location permission (only if foreground is already granted).
   */
  public async requestBackgroundPermission(): Promise<LocationPermissionState> {
    if (Platform.OS === "web") {
      this.backgroundState = "unavailable";
      return "unavailable";
    }

    if (this.foregroundState !== "granted") {
      const fg = await this.requestForegroundPermission();
      if (fg !== "granted") {
        this.backgroundState = "denied";
        return "denied";
      }
    }

    try {
      const result = await Location.requestBackgroundPermissionsAsync();
      this.backgroundState = this.normalizePermissionStatus(result);
      return this.backgroundState;
    } catch (error) {
      console.warn("[PermissionService] Background permission not available:", error);
      this.backgroundState = "unavailable";
      return "unavailable";
    }
  }

  private normalizePermissionStatus(
    permissionResponse: Location.LocationPermissionResponse
  ): LocationPermissionState {
    if (permissionResponse.granted) {
      return "granted";
    }
    if (permissionResponse.canAskAgain === false) {
      return "blocked";
    }
    if (permissionResponse.status === Location.PermissionStatus.DENIED) {
      return "denied";
    }
    return "unknown";
  }
}

export const locationPermissionService = new LocationPermissionService();
