import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking, Modal, TextInput, ActivityIndicator } from 'react-native';
import { useSOSStore } from '@/store/sosStore';
import { sosApi } from '@/lib/api';
import { ShieldAlert, Phone, CheckCircle, X, Clock, MapPin, AlertTriangle, RefreshCw, Send } from 'lucide-react-native';
import * as Location from 'expo-location';
import Toast from 'react-native-toast-message';

export default function SOSPage() {
  const {
    sosStatus,
    countdownSeconds,
    activeIncidentId,
    activeSosId,
    offlinePendingPayload,
    startCountdown,
    cancelCountdown,
    decrementCountdown,
    setSosStatus,
    setActiveIncidentId,
    setActiveSosId,
    setOfflinePendingPayload,
    resetSOS,
  } = useSOSStore();

  const [location, setLocation] = useState<{ lat: number; lng: number; accuracy?: number } | null>(null);
  const [locationDenied, setLocationDenied] = useState(false);
  const [sending, setSending] = useState(false);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelling, setCancelling] = useState(false);

  // Get GPS location on mount
  useEffect(() => {
    (async () => {
      try {
        const { status } = await Location.requestForegroundPermissionsAsync();
        if (status === 'granted') {
          const loc = await Location.getCurrentPositionAsync({});
          setLocation({
            lat: loc.coords.latitude,
            lng: loc.coords.longitude,
            accuracy: loc.coords.accuracy ?? undefined,
          });
        } else {
          setLocationDenied(true);
        }
      } catch (err) {
        console.warn("Location error:", err);
      }
    })();
  }, []);

  // Check for active SOS on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await sosApi.getActive();
        if (res?.data?.active_sos) {
          const active = res.data.active_sos;
          setActiveSosId(active.sos_id);
          setActiveIncidentId(active.incident_id);
          setSosStatus(active.status === "RESOLVED" ? "resolved" : "triggered");
        }
      } catch (e) {
        // Offline or unauthenticated
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

  async function dispatchSOS(isRetry = false) {
    setSending(true);
    const requestId = offlinePendingPayload?.client_request_id || `sos_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const payload = {
      client_request_id: requestId,
      latitude: location?.lat ?? 0,
      longitude: location?.lng ?? 0,
      accuracy: location?.accuracy,
      reason: "Emergency SOS triggered by tourist from mobile app",
    };

    try {
      const res = await sosApi.trigger(payload);
      const data = res.data;
      setActiveSosId(data.sos_id);
      setActiveIncidentId(data.incident_id);
      setOfflinePendingPayload(null);
      setSosStatus("triggered");
      Toast.show({
        type: 'success',
        text1: 'Emergency SOS Transmitted',
        text2: 'TourSafe Command Center has been alerted.',
      });
    } catch (err: any) {
      console.warn("SOS transmission error, queuing offline payload:", err);
      setOfflinePendingPayload(payload);
      setSosStatus("pending_transmission");
      Toast.show({
        type: 'error',
        text1: 'Network Offline - SOS Queued',
        text2: 'Will retry automatically when connection restores.',
      });
    } finally {
      setSending(false);
    }
  }

  async function handleCancelSOS() {
    if (!activeSosId || !cancelReason.trim()) {
      Toast.show({
        type: 'error',
        text1: 'Reason Required',
        text2: 'Please provide a reason to cancel the SOS.',
      });
      return;
    }

    setCancelling(true);
    try {
      await sosApi.cancel(activeSosId, cancelReason.trim());
      Toast.show({
        type: 'success',
        text1: 'SOS Cancelled',
        text2: 'Your emergency request has been withdrawn.',
      });
      resetSOS();
      setCancelModalVisible(false);
      setCancelReason('');
    } catch (e: any) {
      Toast.show({
        type: 'error',
        text1: 'Cancellation Failed',
        text2: e.response?.data?.detail || 'Unable to cancel SOS.',
      });
    } finally {
      setCancelling(false);
    }
  }

  return (
    <View style={styles.container}>
      {/* Background pulse rings for SOS active state */}
      {(sosStatus === "triggered" || sosStatus === "countdown" || sosStatus === "pending_transmission") && (
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
              Transmitting in {countdownSeconds}s…
            </Text>
            <Text style={styles.cancelHint}>Tap Cancel below to abort</Text>
          </View>
        )}
        {sosStatus === "pending_transmission" && (
          <View style={styles.statusBanner}>
            <View style={[styles.activeBadge, { backgroundColor: 'rgba(234, 179, 8, 0.2)', borderColor: '#eab308' }]}>
              <RefreshCw size={16} color="#eab308" />
              <Text style={[styles.activeBadgeText, { color: '#eab308' }]}>OFFLINE - PENDING TRANSMISSION</Text>
            </View>
            <Text style={styles.statusText}>
              SOS stored locally. Tap Retry to transmit to command center.
            </Text>
          </View>
        )}
        {sosStatus === "triggered" && (
          <View style={styles.statusBanner}>
            <View style={styles.activeBadge}>
              <AlertTriangle size={16} color="#f87171" />
              <Text style={styles.activeBadgeText}>SOS ACTIVE</Text>
            </View>
            <Text style={styles.statusText}>
              TourSafe Command Center notified. Response is being coordinated.
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
            (sosStatus === "triggered" || sosStatus === "pending_transmission") && styles.sosButtonActive,
          ]}
        >
          {sending ? (
            <ActivityIndicator size="large" color="#fff" />
          ) : sosStatus === "countdown" ? (
            <>
              <Text style={styles.countdownNumber}>{countdownSeconds}</Text>
              <Text style={styles.countdownLabel}>TRANSMITTING</Text>
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

        {/* Cancel countdown button */}
        {sosStatus === "countdown" && (
          <TouchableOpacity onPress={cancelCountdown} style={styles.cancelButton}>
            <X size={16} color="rgba(255, 255, 255, 0.6)" />
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
        )}

        {/* Offline retry button */}
        {sosStatus === "pending_transmission" && (
          <TouchableOpacity onPress={() => dispatchSOS(true)} style={[styles.cancelButton, { borderColor: '#eab308' }]}>
            <RefreshCw size={16} color="#eab308" />
            <Text style={[styles.cancelButtonText, { color: '#eab308' }]}>Retry Transmission</Text>
          </TouchableOpacity>
        )}

        {/* Cancel active SOS button */}
        {sosStatus === "triggered" && activeSosId && (
          <TouchableOpacity onPress={() => setCancelModalVisible(true)} style={styles.cancelActiveButton}>
            <X size={16} color="#f87171" />
            <Text style={styles.cancelActiveText}>Cancel SOS (I am safe)</Text>
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

        {/* Active SOS status card */}
        {activeIncidentId && sosStatus === "triggered" && (
          <View style={styles.activeSOSCard}>
            <View style={styles.sosRefRow}>
              <Clock size={16} color="rgba(255, 255, 255, 0.5)" />
              <Text style={styles.sosRefText}>
                Incident Reference: {activeIncidentId}
              </Text>
            </View>
            <Text style={styles.sosStatusText}>
              Status: <Text style={styles.sosStatusValue}>COORDINATING ASSISTANCE</Text>
            </Text>
          </View>
        )}
      </View>

      {/* Cancellation Modal */}
      <Modal visible={cancelModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Cancel SOS Request</Text>
            <Text style={styles.modalSubtitle}>
              Please explain why you wish to cancel this emergency request:
            </Text>
            <TextInput
              style={styles.modalInput}
              placeholder="e.g., Accidental tap, situation resolved, safe with guide..."
              placeholderTextColor="#9ca3af"
              value={cancelReason}
              onChangeText={setCancelReason}
              multiline
              numberOfLines={3}
            />
            <View style={styles.modalActions}>
              <TouchableOpacity
                onPress={() => setCancelModalVisible(false)}
                style={styles.modalBtnCancel}
                disabled={cancelling}
              >
                <Text style={styles.modalBtnTextCancel}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={handleCancelSOS}
                style={styles.modalBtnSubmit}
                disabled={cancelling || !cancelReason.trim()}
              >
                {cancelling ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.modalBtnTextSubmit}>Confirm Cancellation</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
    textAlign: 'center',
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
    opacity: 0.85,
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
  cancelActiveButton: {
    marginTop: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.4)',
    borderRadius: 999,
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  cancelActiveText: {
    color: '#f87171',
    fontSize: 14,
    fontWeight: '600',
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 28,
  },
  locationText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 12,
  },
  emergencyGrid: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 32,
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
    marginTop: 20,
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
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: '#1e293b',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#334155',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#f8fafc',
    marginBottom: 8,
  },
  modalSubtitle: {
    fontSize: 13,
    color: '#94a3b8',
    marginBottom: 16,
  },
  modalInput: {
    backgroundColor: '#0f172a',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    color: '#f8fafc',
    padding: 12,
    fontSize: 14,
    textAlignVertical: 'top',
    marginBottom: 20,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
  },
  modalBtnCancel: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#334155',
  },
  modalBtnTextCancel: {
    color: '#e2e8f0',
    fontSize: 14,
    fontWeight: '500',
  },
  modalBtnSubmit: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#ef4444',
  },
  modalBtnTextSubmit: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
});
