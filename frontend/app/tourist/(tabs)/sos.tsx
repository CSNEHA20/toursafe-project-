import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking } from 'react-native';
import { useSOSStore } from '@/store/sosStore';
import { sosApi } from '@/lib/api';
import { ShieldAlert, Phone, CheckCircle, X, Clock, MapPin, AlertTriangle } from 'lucide-react-native';
import * as Location from 'expo-location';
import Toast from 'react-native-toast-message';

export default function SOSPage() {
  const {
    sosStatus,
    countdownSeconds,
    startCountdown,
    cancelCountdown,
    decrementCountdown,
    activeEvents,
  } = useSOSStore();
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationDenied, setLocationDenied] = useState(false);
  const [sending, setSending] = useState(false);

  // Get GPS location on mount
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status === 'granted') {
        const loc = await Location.getCurrentPositionAsync({});
        setLocation({ lat: loc.coords.latitude, lng: loc.coords.longitude });
      } else {
        setLocationDenied(true);
        Toast.show({
          type: 'error',
          text1: 'Location permission denied',
          text2: 'SOS will be sent without your GPS position.',
        });
      }
    })();
  }, []);

  // Countdown timer
  useEffect(() => {
    if (sosStatus !== "countdown") return;
    if (countdownSeconds <= 0) {
      dispatchSOS();
      return;
    }
    const timer = setTimeout(() => decrementCountdown(), 1000);
    return () => clearTimeout(timer);
  }, [sosStatus, countdownSeconds]);

  function handleSOSPress() {
    if (sosStatus !== "idle") return;
    startCountdown();
  }

  async function dispatchSOS() {
    setSending(true);
    try {
      await sosApi.trigger({
        latitude: location?.lat ?? 0,
        longitude: location?.lng ?? 0,
        description: "Emergency SOS triggered from TourSafe app",
      });
      useSOSStore.getState().setSosStatus("triggered");
    } catch {
      useSOSStore.getState().setSosStatus("idle");
    } finally {
      setSending(false);
    }
  }

  const latestSOS = activeEvents[0];

  return (
    <View style={styles.container}>
      {/* Background pulse rings for SOS active state */}
      {(sosStatus === "triggered" || sosStatus === "countdown") && (
        <View style={styles.pulseContainer}>
          {[1, 2, 3].map((i) => (
            <View
              key={i}
              style={[
                styles.pulseRing,
                {
                  width: 200 + i * 120,
                  height: 200 + i * 120,
                },
              ]}
            />
          ))}
        </View>
      )}

      <View style={styles.content}>
        {/* Status banner */}
        {sosStatus === "idle" && (
          <View style={styles.statusBanner}>
            <Text style={styles.statusText}>Press in case of emergency</Text>
          </View>
        )}
        {sosStatus === "countdown" && (
          <View style={styles.statusBanner}>
            <Text style={styles.countdownText}>
              Dispatching in {countdownSeconds}s…
            </Text>
            <Text style={styles.cancelHint}>Tap Cancel to abort</Text>
          </View>
        )}
        {(sosStatus === "triggered" || sosStatus === "acknowledged") && (
          <View style={styles.statusBanner}>
            <View style={styles.activeBadge}>
              <AlertTriangle size={16} color="#f87171" />
              <Text style={styles.activeBadgeText}>SOS ACTIVE</Text>
            </View>
            <Text style={styles.statusText}>
              {sosStatus === "acknowledged"
                ? "Authorities acknowledged — help is on the way"
                : "Alerting nearby authorities…"}
            </Text>
          </View>
        )}
        {sosStatus === "resolved" && (
          <View style={styles.statusBanner}>
            <CheckCircle size={48} color="#10b981" />
            <Text style={styles.resolvedText}>Incident Resolved</Text>
          </View>
        )}

        {/* MAIN SOS BUTTON */}
        <TouchableOpacity
          onPress={handleSOSPress}
          disabled={sosStatus !== "idle" || sending}
          style={[
            styles.sosButton,
            sosStatus === "idle" && styles.sosButtonIdle,
            sosStatus === "countdown" && styles.sosButtonCountdown,
            (sosStatus === "triggered" || sosStatus === "acknowledged") && styles.sosButtonActive,
          ]}
        >
          {sosStatus === "countdown" ? (
            <>
              <Text style={styles.countdownNumber}>{countdownSeconds}</Text>
              <Text style={styles.countdownLabel}>DISPATCHING</Text>
            </>
          ) : (
            <>
              <ShieldAlert size={64} color="#fff" />
              <Text style={styles.sosText}>SOS</Text>
              <Text style={styles.sosSubtext}>
                {sosStatus === "idle" ? "EMERGENCY" : "ACTIVE"}
              </Text>
            </>
          )}
        </TouchableOpacity>

        {/* Cancel button during countdown */}
        {sosStatus === "countdown" && (
          <TouchableOpacity onPress={cancelCountdown} style={styles.cancelButton}>
            <X size={16} color="rgba(255, 255, 255, 0.6)" />
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
        )}

        {/* Location indicator */}
        {location && (
          <View style={styles.locationRow}>
            <MapPin size={14} color="rgba(255, 255, 255, 0.4)" />
            <Text style={styles.locationText}>
              GPS: {location.lat.toFixed(5)}, {location.lng.toFixed(5)}
            </Text>
          </View>
        )}
        {locationDenied && (
          <View style={styles.locationRow}>
            <MapPin size={14} color="#f87171" />
            <Text style={[styles.locationText, { color: '#f87171' }]}>
              GPS unavailable — location permission denied
            </Text>
          </View>
        )}

        {/* Emergency numbers */}
        <View style={styles.emergencyGrid}>
          {[
            { label: "Police", number: "100" },
            { label: "Ambulance", number: "108" },
            { label: "Emergency", number: "112" },
          ].map((c) => (
            <TouchableOpacity
              key={c.label}
              onPress={() => Linking.openURL(`tel:${c.number}`)}
              style={styles.emergencyCard}
            >
              <Phone size={16} color="rgba(255, 255, 255, 0.5)" />
              <Text style={styles.emergencyNumber}>{c.number}</Text>
              <Text style={styles.emergencyLabel}>{c.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Active SOS status */}
        {latestSOS && sosStatus !== "idle" && (
          <View style={styles.activeSOSCard}>
            <View style={styles.sosRefRow}>
              <Clock size={16} color="rgba(255, 255, 255, 0.5)" />
              <Text style={styles.sosRefText}>
                SOS Reference: {(latestSOS.id ?? latestSOS.incident_id).slice(0, 8).toUpperCase()}
              </Text>
            </View>
            <Text style={styles.sosStatusText}>
              Status: <Text style={styles.sosStatusValue}>{latestSOS.status}</Text>
            </Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a365d',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  pulseContainer: {
    position: 'absolute',
    inset: 0,
    alignItems: 'center',
    justifyContent: 'center',
    pointerEvents: 'none',
  },
  pulseRing: {
    position: 'absolute',
    borderRadius: 999,
    borderWidth: 2,
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  content: {
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  statusBanner: {
    alignItems: 'center',
    marginBottom: 32,
  },
  statusText: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 14,
  },
  countdownText: {
    color: '#f87171',
    fontSize: 18,
    fontWeight: 'bold',
  },
  cancelHint: {
    color: 'rgba(255, 255, 255, 0.5)',
    fontSize: 14,
    marginTop: 4,
  },
  activeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(220, 38, 38, 0.2)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginBottom: 8,
  },
  activeBadgeText: {
    color: '#f87171',
    fontSize: 14,
    fontWeight: '600',
  },
  resolvedText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 8,
  },
  sosButton: {
    width: 224,
    height: 224,
    borderRadius: 112,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 16,
  },
  sosButtonIdle: {
    backgroundColor: '#ef4444',
  },
  sosButtonCountdown: {
    backgroundColor: '#b91c1c',
  },
  sosButtonActive: {
    backgroundColor: '#7f1d1d',
    opacity: 0.8,
  },
  countdownNumber: {
    color: '#fff',
    fontSize: 64,
    fontWeight: '900',
  },
  countdownLabel: {
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 14,
    marginTop: 8,
  },
  sosText: {
    color: '#fff',
    fontSize: 32,
    fontWeight: '900',
    letterSpacing: 4,
  },
  sosSubtext: {
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 12,
    marginTop: 4,
  },
  cancelButton: {
    marginTop: 24,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    borderRadius: 999,
    paddingHorizontal: 24,
    paddingVertical: 10,
  },
  cancelButtonText: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 14,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 32,
  },
  locationText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 12,
  },
  emergencyGrid: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 40,
    width: '100%',
  },
  emergencyCard: {
    flex: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 12,
    padding: 12,
    alignItems: 'center',
  },
  emergencyNumber: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 14,
    fontWeight: 'bold',
    marginTop: 4,
  },
  emergencyLabel: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 12,
    marginTop: 2,
  },
  activeSOSCard: {
    width: '100%',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 12,
    padding: 16,
    marginTop: 24,
  },
  sosRefRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  sosRefText: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 12,
  },
  sosStatusText: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 14,
  },
  sosStatusValue: {
    color: '#FF9933',
    fontWeight: '600',
  },
});
