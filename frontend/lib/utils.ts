import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";
import type { AlertSeverity, ZoneType, IncidentStatus, EFIRStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function formatDateTime(date: string | Date): string {
  return format(new Date(date), "dd MMM yyyy, HH:mm");
}

export function formatTime(date: string | Date): string {
  return format(new Date(date), "HH:mm:ss");
}

export function severityColor(severity: AlertSeverity): string {
  const map: Record<AlertSeverity, string> = {
    critical: "text-ts-alert-red bg-red-50 border-ts-alert-red",
    high: "text-ts-saffron bg-orange-50 border-ts-saffron",
    medium: "text-yellow-700 bg-yellow-50 border-yellow-500",
    low: "text-ts-teal bg-teal-50 border-ts-teal",
  };
  return map[severity];
}

export function severityBadgeColor(severity: AlertSeverity): string {
  const map: Record<AlertSeverity, string> = {
    critical: "bg-ts-alert-red text-white",
    high: "bg-ts-saffron text-white",
    medium: "bg-yellow-500 text-white",
    low: "bg-ts-teal text-white",
  };
  return map[severity];
}

export function zoneTypeColor(type: ZoneType): string {
  const map: Record<ZoneType, string> = {
    safe: "#046A38",
    warning: "#D97706",
    danger: "#C53030",
    restricted: "#4A5568",
  };
  return map[type];
}

export function incidentStatusColor(status: IncidentStatus | EFIRStatus): string {
  const map: Record<string, string> = {
    reported: "bg-ts-saffron/10 text-ts-saffron",
    dispatched: "bg-blue-50 text-blue-700",
    in_progress: "bg-purple-50 text-purple-700",
    resolved: "bg-green-50 text-ts-green",
    closed: "bg-ts-mid text-ts-slate",
    draft: "bg-gray-100 text-gray-600",
    submitted: "bg-blue-50 text-blue-700",
    accepted: "bg-purple-50 text-purple-700",
    archived: "bg-ts-mid text-ts-slate",
    under_review: "bg-yellow-50 text-yellow-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}

export function getStatusDot(status: "safe" | "alert" | "sos" | "inactive"): string {
  // Note: "animate-status-blink" was a web CSS keyframe. On native, the blink
  // for the "sos" state is implemented with react-native-reanimated in the
  // component that renders the dot (see components/ui/StatusDot.tsx) since
  // NativeWind can't run arbitrary @keyframes animations.
  const map = {
    safe: "bg-ts-green",
    alert: "bg-ts-saffron",
    sos: "bg-ts-alert-red",
    inactive: "bg-gray-400",
  };
  return map[status];
}

export function formatCoords(lat: number, lng: number): string {
  const latDir = lat >= 0 ? "N" : "S";
  const lngDir = lng >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(5)}° ${latDir}, ${Math.abs(lng).toFixed(5)}° ${lngDir}`;
}

export function kmToMeters(km: number): number {
  return km * 1000;
}

export function haversineDistance(
  lat1: number, lng1: number,
  lat2: number, lng2: number
): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
