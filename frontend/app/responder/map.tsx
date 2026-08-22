import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Dimensions,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { router } from 'expo-router';
import {
  AlertTriangle,
  ArrowLeft,
  Compass,
  Crosshair,
  MapPin,
  Navigation,
  RefreshCw,
  Shield,
  ShieldAlert,
} from 'lucide-react-native';
import { responderApi, incidentApi } from '@/lib/api';
import type { IncidentRecord, ResponderSelfProfile } from '@/types';

const { width, height } = Dimensions.get('window');

export default function ResponderMapScreen() {
  const [profile, setProfile] = useState<ResponderSelfProfile | null>(null);
  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMapData();
    const interval = setInterval(loadMapData, 5000);
    return () => clearInterval(interval);
  }, []);

  async function loadMapData() {
    try {
      const profRes = await responderApi.getMe();
      if (profRes?.data) {
        setProfile(profRes.data);
        if (profRes.data.active_incident) {
          setIncident(profRes.data.active_incident);
        }
      }
    } catch (e: any) {
      console.warn('Failed to load tactical map data:', e);
    } finally {
      setLoading(false);
    }
  }

  const responderLoc = profile?.live_location || profile?.responder?.current_location;
  const incidentLoc = incident?.location_data;

  return (
    <View style={styles.container}>
      {/* Map Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBackBtn} onPress={() => router.back()}>
          <ArrowLeft size={20} color="#F8FAFC" />
        </TouchableOpacity>
        <View style={styles.headerTitleWrap}>
          <Text style={styles.headerTitle}>TACTICAL MAP</Text>
          <Text style={styles.headerSubtitle}>Realtime GPS & Incident Grid</Text>
        </View>
        <TouchableOpacity style={styles.headerBackBtn} onPress={loadMapData}>
          <RefreshCw size={18} color="#94A3B8" />
        </TouchableOpacity>
      </View>

      {/* Simulated Tactical Grid Canvas */}
      <View style={styles.gridCanvas}>
        {/* Tactical Crosshair Background */}
        <View style={styles.gridLineHorizontal} />
        <View style={styles.gridLineVertical} />
        <View style={styles.gridCircleOuter} />
        <View style={styles.gridCircleInner} />

        {/* Responder Location Marker */}
        <View style={styles.responderPinWrap}>
          <View style={styles.responderPulse} />
          <View style={styles.responderPin}>
            <Navigation size={16} color="#FFFFFF" />
          </View>
          <View style={styles.pinLabelBox}>
            <Text style={styles.pinLabelText}>YOU (UNIT)</Text>
          </View>
        </View>

        {/* Incident Target Marker (if active) */}
        {incident && incidentLoc && (
          <View style={styles.incidentPinWrap}>
            <View style={styles.incidentPulse} />
            <View style={styles.incidentPin}>
              <ShieldAlert size={18} color="#FFFFFF" />
            </View>
            <View style={[styles.pinLabelBox, styles.incidentLabelBox]}>
              <Text style={styles.incidentLabelText}>INCIDENT {incident.incident_id}</Text>
            </View>
          </View>
        )}

        {/* Compass Overlay */}
        <View style={styles.compassOverlay}>
          <Compass size={24} color="#38BDF8" />
          <Text style={styles.compassText}>NORTH</Text>
        </View>
      </View>

      {/* Bottom Floating Telemetry Card */}
      <View style={styles.telemetryCard}>
        <View style={styles.telemetryHeader}>
          <View style={styles.telemetryTitleRow}>
            <Crosshair size={16} color="#34D399" />
            <Text style={styles.telemetryTitle}>TACTICAL TELEMETRY</Text>
          </View>
          <View style={styles.fixPill}>
            <Text style={styles.fixPillText}>
              {responderLoc?.quality || 'HIGH ACCURACY'} (±{responderLoc?.accuracy ? Math.round(responderLoc.accuracy) : 10}m)
            </Text>
          </View>
        </View>

        <View style={styles.coordsGrid}>
          <View style={styles.coordItem}>
            <Text style={styles.coordLabel}>MY POSITION</Text>
            <Text style={styles.coordValue}>
              {responderLoc
                ? `${responderLoc.latitude.toFixed(5)}, ${responderLoc.longitude.toFixed(5)}`
                : 'Searching for Fix...'}
            </Text>
          </View>

          {incidentLoc && (
            <View style={styles.coordItem}>
              <Text style={styles.coordLabel}>TARGET POSITION</Text>
              <Text style={styles.coordValue}>
                {incidentLoc.latitude.toFixed(5)}, {incidentLoc.longitude.toFixed(5)}
              </Text>
            </View>
          )}
        </View>

        {incident && (
          <TouchableOpacity
            style={styles.openIncidentBtn}
            onPress={() =>
              router.push({
                pathname: '/responder/incident',
                params: { incident_id: incident.incident_id },
              })
            }
          >
            <ShieldAlert size={16} color="#FFFFFF" />
            <Text style={styles.openIncidentBtnText}>VIEW ACTIVE INCIDENT ACTIONS</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090D16',
  },
  header: {
    paddingTop: 54,
    paddingHorizontal: 16,
    paddingBottom: 14,
    backgroundColor: '#0D1424',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    zIndex: 10,
  },
  headerBackBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#1E293B',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitleWrap: {
    alignItems: 'center',
  },
  headerTitle: {
    color: '#F8FAFC',
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#94A3B8',
    fontSize: 11,
  },
  gridCanvas: {
    flex: 1,
    backgroundColor: '#070A12',
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  gridLineHorizontal: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: '#1E293B40',
  },
  gridLineVertical: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 1,
    backgroundColor: '#1E293B40',
  },
  gridCircleOuter: {
    position: 'absolute',
    width: 320,
    height: 320,
    borderRadius: 160,
    borderWidth: 1,
    borderColor: '#1E293B50',
  },
  gridCircleInner: {
    position: 'absolute',
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 1,
    borderColor: '#33415550',
  },
  compassOverlay: {
    position: 'absolute',
    top: 20,
    right: 20,
    alignItems: 'center',
    backgroundColor: '#0F172A80',
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  compassText: {
    color: '#38BDF8',
    fontSize: 9,
    fontWeight: '800',
    marginTop: 2,
  },
  responderPinWrap: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  responderPulse: {
    position: 'absolute',
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#2563EB30',
  },
  responderPin: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#2563EB',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  pinLabelBox: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#2563EB',
    marginTop: 4,
  },
  pinLabelText: {
    color: '#93C5FD',
    fontSize: 10,
    fontWeight: '800',
  },
  incidentPinWrap: {
    position: 'absolute',
    top: height * 0.22,
    right: width * 0.22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  incidentPulse: {
    position: 'absolute',
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: '#DC262630',
  },
  incidentPin: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#DC2626',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
  },
  incidentLabelBox: {
    borderColor: '#DC2626',
  },
  incidentLabelText: {
    color: '#FCA5A5',
    fontSize: 10,
    fontWeight: '800',
  },
  telemetryCard: {
    backgroundColor: '#0F172A',
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    borderWidth: 1,
    borderColor: '#1E293B',
    padding: 16,
    gap: 12,
  },
  telemetryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  telemetryTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  telemetryTitle: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  fixPill: {
    backgroundColor: '#065F4640',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#10B981',
  },
  fixPillText: {
    color: '#34D399',
    fontSize: 10,
    fontWeight: '700',
  },
  coordsGrid: {
    flexDirection: 'row',
    gap: 10,
  },
  coordItem: {
    flex: 1,
    backgroundColor: '#1E293B60',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#33415550',
  },
  coordLabel: {
    color: '#64748B',
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 2,
  },
  coordValue: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '700',
  },
  openIncidentBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#DC2626',
    paddingVertical: 12,
    borderRadius: 8,
  },
  openIncidentBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
});
