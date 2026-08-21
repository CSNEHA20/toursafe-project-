/**
 * TourSafe Simulation Engine
 * Self-contained prototype simulation of all core safety features.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

// ─── DID / Blockchain ────────────────────────────────────────────────────────

/** Generate a pseudo-SHA256-style hex string for prototype DID. */
function pseudoHash(input: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
    h >>>= 0;
  }
  // Expand to 64-char hex to simulate SHA-256 length
  const base = h.toString(16).padStart(8, "0");
  const seeds = [input.length, input.charCodeAt(0) ?? 42, h % 997];
  const parts = Array.from({ length: 8 }, (_, i) => {
    const s = seeds[i % seeds.length] ^ (i * 0xdeadbeef);
    return (((h ^ s) >>> 0) * (i + 1)).toString(16).slice(-8).padStart(8, "0");
  });
  return parts.join("").slice(0, 64);
}

export interface DIDRecord {
  did_address: string;       // 0x-prefixed 40-char hex
  ipfs_hash: string;         // Qm... style hash
  polygon_tx: string;        // 0x transaction hash
  created_at: string;
  network: string;
  encrypted_medical: EncryptedMedical;
}

export interface EncryptedMedical {
  ciphertext: string;
  blood_type: string;        // visible only after emergency access
  allergies: string[];
  emergency_contact: string;
  emergency_phone: string;
}

export interface TravelerProfile {
  id: string;
  name: string;
  nationality: string;
  passport: string;
}

export function generateDID(profile: TravelerProfile): DIDRecord {
  const seed = `${profile.id}:${profile.passport}:${profile.name}`;
  const hash = pseudoHash(seed);
  const ipfsSeed = pseudoHash(seed + "ipfs");
  const txSeed = pseudoHash(seed + "tx");

  return {
    did_address: `0x${hash.slice(0, 40)}`,
    ipfs_hash: `Qm${btoa(ipfsSeed).replace(/[^a-zA-Z0-9]/g, "").slice(0, 44)}`,
    polygon_tx: `0x${txSeed}`,
    created_at: new Date().toISOString(),
    network: "Polygon PoS",
    encrypted_medical: {
      ciphertext: btoa(JSON.stringify({
        blood_type: "O+",
        allergies: ["Penicillin", "Shellfish"],
        emergency_contact: profile.name.split(" ")[0] + "'s Family",
        emergency_phone: "+91-98765-43210",
      })),
      blood_type: "O+",
      allergies: ["Penicillin", "Shellfish"],
      emergency_contact: profile.name.split(" ")[0] + "'s Family",
      emergency_phone: "+91-98765-43210",
    },
  };
}

/** Simulate on-chain verification delay */
export async function verifyDIDOnChain(did_address: string): Promise<boolean> {
  await delay(2200);
  return did_address.startsWith("0x") && did_address.length >= 42;
}

/** Simulate emergency medical record decryption */
export async function emergencyDecryptMedical(
  ciphertext: string
): Promise<EncryptedMedical["blood_type"] extends string ? EncryptedMedical : never> {
  await delay(1500);
  try {
    return JSON.parse(atob(ciphertext));
  } catch {
    return { blood_type: "A+", allergies: ["None on record"], emergency_contact: "N/A", emergency_phone: "112" } as never;
  }
}

// ─── IMU / Anomaly Detection ─────────────────────────────────────────────────

export interface IMUSample {
  ts: number;       // epoch ms
  x: number;        // g-force X
  y: number;        // g-force Y
  z: number;        // g-force Z
  magnitude: number;
  lat: number;
  lng: number;
}

export type AnomalyType = "fall" | "crash" | "inactivity" | "normal";

export interface AnomalyResult {
  type: AnomalyType;
  confidence: number;    // 0–1
  threshold: number;
  sample: IMUSample;
  message: string;
}

const FALL_THRESHOLD = 3.2;        // g
const CRASH_THRESHOLD = 4.5;       // g
const INACTIVITY_SECS = 20;        // seconds

let _lastMotion = Date.now();
let _imuBuffer: IMUSample[] = [];

/** Generate a realistic IMU sample (random walk with occasional spikes). */
export function generateIMUSample(
  baseLat = 10.2381,
  baseLng = 77.4892,
  forceAnomaly?: "fall" | "crash"
): IMUSample {
  const ts = Date.now();
  let x: number, y: number, z: number;

  if (forceAnomaly === "crash") {
    x = (Math.random() - 0.5) * 10 + 5;
    y = (Math.random() - 0.5) * 10 - 3;
    z = (Math.random() - 0.5) * 8 + 2;
  } else if (forceAnomaly === "fall") {
    x = (Math.random() - 0.5) * 8 + 3;
    y = (Math.random() - 0.5) * 8;
    z = (Math.random() - 0.5) * 6 + 1;
  } else {
    // normal walking: ~1g with slight noise
    x = (Math.random() - 0.5) * 0.6 + 0.05;
    y = (Math.random() - 0.5) * 0.6 + 0.05;
    z = (Math.random() - 0.5) * 0.4 + 0.98;
    if (Math.random() < 0.03) {
      // rare small bump
      x += (Math.random() - 0.5) * 1.5;
      z += (Math.random() - 0.5) * 1.5;
    }
  }

  const magnitude = Math.sqrt(x * x + y * y + z * z);
  _lastMotion = ts;

  return {
    ts,
    x: +x.toFixed(3),
    y: +y.toFixed(3),
    z: +z.toFixed(3),
    magnitude: +magnitude.toFixed(3),
    lat: baseLat + (Math.random() - 0.5) * 0.0002,
    lng: baseLng + (Math.random() - 0.5) * 0.0002,
  };
}

/** Push sample into sliding window and run detection logic. */
export function detectAnomaly(sample: IMUSample): AnomalyResult {
  _imuBuffer.push(sample);
  if (_imuBuffer.length > 50) _imuBuffer.shift();

  const now = Date.now();
  const inactiveSecs = (now - _lastMotion) / 1000;

  if (sample.magnitude >= CRASH_THRESHOLD) {
    return {
      type: "crash",
      confidence: Math.min(0.99, (sample.magnitude - CRASH_THRESHOLD) / 3 + 0.7),
      threshold: CRASH_THRESHOLD,
      sample,
      message: `High-impact event detected (${sample.magnitude.toFixed(2)}g) — possible vehicle crash`,
    };
  }

  if (sample.magnitude >= FALL_THRESHOLD) {
    return {
      type: "fall",
      confidence: Math.min(0.95, (sample.magnitude - FALL_THRESHOLD) / 2 + 0.6),
      threshold: FALL_THRESHOLD,
      sample,
      message: `Sudden acceleration spike (${sample.magnitude.toFixed(2)}g) — possible fall detected`,
    };
  }

  if (inactiveSecs >= INACTIVITY_SECS && _imuBuffer.length > 5) {
    const recent = _imuBuffer.slice(-5);
    const avgMag = recent.reduce((s, r) => s + r.magnitude, 0) / recent.length;
    if (avgMag < 0.3) {
      return {
        type: "inactivity",
        confidence: Math.min(0.85, inactiveSecs / 120),
        threshold: INACTIVITY_SECS,
        sample,
        message: `Prolonged inactivity detected (${Math.round(inactiveSecs)}s) — tourist may need assistance`,
      };
    }
  }

  return {
    type: "normal",
    confidence: 1 - Math.min(0.8, sample.magnitude / FALL_THRESHOLD),
    threshold: FALL_THRESHOLD,
    sample,
    message: "Normal movement pattern",
  };
}

export function getIMUBuffer(): IMUSample[] {
  return [..._imuBuffer];
}

// ─── Offline Queue ────────────────────────────────────────────────────────────
// React Native has no `localStorage`; the queue lives in memory and is mirrored
// to AsyncStorage (fire-and-forget) so it survives app restarts.

const QUEUE_KEY = "toursafe_offline_queue";

export interface TelemetryPacket {
  id: string;
  ts: number;
  encrypted: string;
  lat: number;
  lng: number;
  type: "gps" | "imu" | "sos" | "anomaly";
  flushed: boolean;
}

let _queue: TelemetryPacket[] = [];

AsyncStorage.getItem(QUEUE_KEY)
  .then((raw) => {
    if (raw) _queue = JSON.parse(raw);
  })
  .catch(() => {
    _queue = [];
  });

function persistQueue(): void {
  AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(_queue)).catch(() => {});
}

export function enqueuePacket(packet: Omit<TelemetryPacket, "id" | "flushed">): void {
  const full: TelemetryPacket = {
    ...packet,
    id: `pkt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    flushed: false,
  };
  _queue.push(full);
  // Cap at 100 packets
  _queue = _queue.slice(-100);
  persistQueue();
}

export function getQueue(): TelemetryPacket[] {
  return [..._queue];
}

export function getPendingCount(): number {
  return _queue.filter((p) => !p.flushed).length;
}

export async function flushQueue(onProgress?: (flushed: number, total: number) => void): Promise<number> {
  const pending = _queue.filter((p) => !p.flushed);
  let count = 0;

  for (const pkt of pending) {
    await delay(60 + Math.random() * 80); // Simulate network round-trip
    pkt.flushed = true;
    count++;
    onProgress?.(count, pending.length);
  }

  persistQueue();
  return count;
}

export function clearFlushedPackets(): void {
  _queue = _queue.filter((p) => !p.flushed);
  persistQueue();
}

// ─── Shake / Motion Trigger ───────────────────────────────────────────────────

export interface ShakeEvent {
  ts: number;
  magnitude: number;
  triggered: boolean;
}

const SHAKE_THRESHOLD = 25;  // px²/s² device motion threshold
let _shakeHistory: number[] = [];
let _lastShakeAlert = 0;

export function processShakeSample(acceleration: number): ShakeEvent {
  const ts = Date.now();
  _shakeHistory.push(acceleration);
  if (_shakeHistory.length > 20) _shakeHistory.shift();

  const triggered =
    acceleration >= SHAKE_THRESHOLD &&
    ts - _lastShakeAlert > 10_000; // 10s cooldown

  if (triggered) _lastShakeAlert = ts;

  return { ts, magnitude: +acceleration.toFixed(2), triggered };
}

export function resetShakeCooldown(): void {
  _lastShakeAlert = 0;
  _shakeHistory = [];
}

// ─── Real-Time Incident Receiver (WebSocket simulation) ──────────────────────

export type IncidentSeverity = "critical" | "high" | "medium" | "low";

export interface LiveIncident {
  id: string;
  ts: number;
  tourist_name: string;
  tourist_did: string;
  lat: number;
  lng: number;
  severity: IncidentSeverity;
  type: AnomalyType | "sos" | "geofence";
  zone: string;
  message: string;
  status: "incoming" | "acknowledged" | "resolved";
}

const TOURIST_NAMES = [
  "Yuki Tanaka", "Emma Wilson", "Ahmed Al-Rashid", "Sofia Martínez",
  "James O'Brien", "Priya Nair", "Marco Rossi", "Fatima Hassan",
  "Chen Wei", "Anya Petrov",
];
const ZONES = [
  "Guna Caves Area", "Coaker's Walk", "Kodaikanal Lake", "Berijam Reserve",
  "Pillar Rocks", "Bear Shola Falls", "Dolphin's Nose", "Bryant Park",
];
const INCIDENT_TYPES: (AnomalyType | "sos" | "geofence")[] = [
  "fall", "crash", "inactivity", "sos", "geofence",
];

function randomIncident(): LiveIncident {
  const idx = Math.floor(Math.random() * TOURIST_NAMES.length);
  const type = INCIDENT_TYPES[Math.floor(Math.random() * INCIDENT_TYPES.length)];
  const nameSeed = TOURIST_NAMES[idx];
  const did = `0x${pseudoHash(nameSeed + "did").slice(0, 40)}`;
  const severity: IncidentSeverity =
    type === "crash" || type === "sos" ? "critical"
    : type === "fall" ? "high"
    : type === "geofence" ? "medium"
    : "low";

  const messages: Record<typeof type, string> = {
    fall: "Sudden fall detected via IMU accelerometer spike",
    crash: "High-impact collision event — immediate response required",
    inactivity: "Tourist inactive for >20s in remote zone",
    sos: "Manual SOS triggered by tourist",
    geofence: "Tourist entered restricted danger zone",
    normal: "Routine telemetry update",
  };

  return {
    id: `INC-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).slice(2, 5).toUpperCase()}`,
    ts: Date.now(),
    tourist_name: nameSeed,
    tourist_did: did,
    lat: 10.15 + Math.random() * 0.15,
    lng: 77.42 + Math.random() * 0.12,
    severity,
    type,
    zone: ZONES[Math.floor(Math.random() * ZONES.length)],
    message: messages[type],
    status: "incoming",
  };
}

type IncidentCallback = (incident: LiveIncident) => void;
let _wsInterval: ReturnType<typeof setInterval> | null = null;
const _wsListeners: Set<IncidentCallback> = new Set();

export function startIncidentStream(intervalMs = 4000): void {
  if (_wsInterval) return;
  // Immediately emit one on start
  setTimeout(() => {
    const inc = randomIncident();
    _wsListeners.forEach((cb) => cb(inc));
  }, 800);

  _wsInterval = setInterval(() => {
    // 60% chance of emitting an incident each tick
    if (Math.random() < 0.6) {
      const inc = randomIncident();
      _wsListeners.forEach((cb) => cb(inc));
    }
  }, intervalMs);
}

export function stopIncidentStream(): void {
  if (_wsInterval) {
    clearInterval(_wsInterval);
    _wsInterval = null;
  }
}

export function subscribeToIncidents(cb: IncidentCallback): () => void {
  _wsListeners.add(cb);
  return () => _wsListeners.delete(cb);
}

// ─── e-FIR Auto-Generation ────────────────────────────────────────────────────

export interface EFIRPayload {
  fir_number: string;
  generated_at: string;
  tourist_name: string;
  tourist_nationality: string;
  tourist_did: string;
  passport_number: string;
  blood_type: string;
  allergies: string[];
  incident_type: string;
  incident_lat: number;
  incident_lng: number;
  zone: string;
  timestamp: string;
  anomaly_confidence: number;
  imu_magnitude: number;
  justification: string;
  dispatched_to: string[];
  status: "draft" | "dispatched";
}

export async function generateEFIR(incident: LiveIncident): Promise<EFIRPayload> {
  await delay(1800); // Simulate backend processing

  const now = new Date();
  const firNum = `FIR/${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, "0")}/${Math.floor(1000 + Math.random() * 9000)}`;

  return {
    fir_number: firNum,
    generated_at: now.toISOString(),
    tourist_name: incident.tourist_name,
    tourist_nationality: randomNationality(),
    tourist_did: incident.tourist_did,
    passport_number: `P${Math.floor(1000000 + Math.random() * 9000000)}`,
    blood_type: ["A+", "B+", "O+", "AB+", "A-", "O-"][Math.floor(Math.random() * 6)],
    allergies: [["Penicillin"], ["Latex"], ["None"], ["Shellfish", "Nuts"]][Math.floor(Math.random() * 4)],
    incident_type: incident.type.toUpperCase(),
    incident_lat: incident.lat,
    incident_lng: incident.lng,
    zone: incident.zone,
    timestamp: new Date(incident.ts).toISOString(),
    anomaly_confidence: +(0.65 + Math.random() * 0.33).toFixed(2),
    imu_magnitude: +(3.2 + Math.random() * 3).toFixed(2),
    justification: incident.message,
    dispatched_to: ["Kodaikanal Police Station (PS-KDL-001)", "GH Kodaikanal Emergency Dept."],
    status: "draft",
  };
}

function randomNationality() {
  return ["Indian", "Japanese", "British", "American", "German", "French", "Australian"][
    Math.floor(Math.random() * 7)
  ];
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function delay(ms: number): Promise<void> {
  return new Promise((res) => setTimeout(res, ms));
}
