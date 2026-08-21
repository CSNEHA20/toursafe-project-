import { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking } from 'react-native';
import { useAuthStore } from '@/store/authStore';
import { useSOSStore } from '@/store/sosStore';
import { useAlertStore } from '@/store/alertStore';
import { touristApi } from '@/lib/api';
import type { Tourist } from '@/types';
import RoleSwitch from '@/components/RoleSwitch';
import {
  ShieldAlert,
  MapPin,
  Bell,
  CheckCircle,
  Navigation,
  Wifi,
  Phone,
} from 'lucide-react-native';
import { useRouter } from 'expo-router';

export default function TouristDashboard() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { activeEvents } = useSOSStore();
  const { alerts } = useAlertStore();
  const [tourist, setTourist] = useState<Tourist | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      touristApi.getMe().then((r) => setTourist(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const myAlerts = alerts.slice(0, 5);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      <RoleSwitch currentRole="tourist" />
      {/* Welcome banner */}
      <View style={styles.welcomeBanner}>
        <View style={styles.welcomeContent}>
          <View>
            <Text style={styles.welcomeSubtitle}>Welcome back,</Text>
            <Text style={styles.welcomeTitle}>
              {user?.full_name ?? "Tourist"}
            </Text>
            <View style={styles.locationRow}>
              <MapPin size={16} color="rgba(255, 255, 255, 0.7)" />
              <Text style={styles.locationText}>
                {tourist?.current_zone ?? "Location updating…"}
              </Text>
            </View>
          </View>
          <TouchableOpacity
            onPress={() => router.push("/tourist/(tabs)/sos")}
            style={styles.sosButton}
          >
            <ShieldAlert size={28} color="#fff" />
            <Text style={styles.sosButtonText}>SOS</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Status grid */}
      <View style={styles.statusGrid}>
        <StatusCard
          icon={<CheckCircle size={20} color="#10b981" />}
          label="Safety Status"
          value={tourist?.status === "safe" ? "Safe" : tourist?.status ?? "Unknown"}
          sub="Position shared"
          loading={loading}
        />
        <StatusCard
          icon={<Bell size={20} color="#FF9933" />}
          label="Active Alerts"
          value={String(myAlerts.length)}
          sub="In your zone"
          loading={loading}
        />
        <StatusCard
          icon={<Navigation size={20} color="#0d9488" />}
          label="Current Zone"
          value={tourist?.current_zone ?? "—"}
          sub="Geofence active"
          loading={loading}
        />
        <StatusCard
          icon={<Wifi size={20} color="#1a365d" />}
          label="Connectivity"
          value="Online"
          sub="Real-time tracking"
          loading={loading}
        />
      </View>

      {/* Recent alerts */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.cardTitle}>Recent Alerts</Text>
          <TouchableOpacity onPress={() => router.push("/tourist/(tabs)/incidents")}>
            <Text style={styles.viewAllText}>View all</Text>
          </TouchableOpacity>
        </View>
        {myAlerts.length === 0 ? (
          <View style={styles.emptyState}>
            <Bell size={32} color="rgba(100, 116, 139, 0.3)" />
            <Text style={styles.emptyText}>No active alerts</Text>
          </View>
        ) : (
          <View style={styles.alertsList}>
            {myAlerts.map((alert) => (
              <View key={alert.id} style={styles.alertItem}>
                <View style={[styles.alertDot, { backgroundColor: getSeverityColor(alert.severity) }]} />
                <View style={styles.alertContent}>
                  <Text style={styles.alertTitle}>{alert.title}</Text>
                  <Text style={styles.alertTime}>{formatRelativeTime(alert.created_at)}</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* Emergency contacts */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Emergency Contacts</Text>
        <View style={styles.contactsGrid}>
          {[
            { label: "Police", number: "100", color: "#1a365d" },
            { label: "Ambulance", number: "108", color: "#dc2626" },
            { label: "Fire", number: "101", color: "#f97316" },
            { label: "Tourist Helpline", number: "1800-111-363", color: "#0d9488" },
            { label: "Women Helpline", number: "1091", color: "#9333ea" },
            { label: "National Emergency", number: "112", color: "#10b981" },
          ].map((c) => (
            <TouchableOpacity
              key={c.label}
              onPress={() => Linking.openURL(`tel:${c.number}`)}
              style={[styles.contactCard, { backgroundColor: c.color }]}
            >
              <Phone size={16} color="#fff" />
              <View>
                <Text style={styles.contactLabel}>{c.label}</Text>
                <Text style={styles.contactNumber}>{c.number}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

function StatusCard({
  icon,
  label,
  value,
  sub,
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  loading: boolean;
}) {
  if (loading) {
    return (
      <View style={[styles.statusCard, styles.skeleton]}>
        <View style={styles.skeletonContent} />
      </View>
    );
  }
  return (
    <View style={styles.statusCard}>
      <View style={styles.statusIcon}>{icon}</View>
      <View>
        <Text style={styles.statusLabel}>{label}</Text>
        <Text style={styles.statusValue}>{value}</Text>
        <Text style={styles.statusSub}>{sub}</Text>
      </View>
    </View>
  );
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return '#ef4444';
    case 'high':
      return '#f97316';
    case 'medium':
      return '#eab308';
    case 'low':
      return '#22c55e';
    default:
      return '#94a3b8';
  }
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f1f5f9',
  },
  scrollContent: {
    padding: 16,
  },
  welcomeBanner: {
    backgroundColor: '#1a365d',
    borderRadius: 16,
    padding: 24,
    marginBottom: 16,
  },
  welcomeContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  welcomeSubtitle: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 14,
  },
  welcomeTitle: {
    color: '#fff',
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 4,
  },
  locationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
  },
  locationText: {
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 14,
  },
  sosButton: {
    backgroundColor: '#ef4444',
    borderRadius: 12,
    paddingHorizontal: 32,
    paddingVertical: 16,
    alignItems: 'center',
    gap: 8,
  },
  sosButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  statusGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  statusCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 16,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    width: '48%',
  },
  skeleton: {
    height: 96,
  },
  skeletonContent: {
    flex: 1,
    backgroundColor: '#e2e8f0',
    borderRadius: 8,
  },
  statusIcon: {
    padding: 8,
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
  },
  statusLabel: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.6)',
  },
  statusValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1a365d',
    marginTop: 2,
  },
  statusSub: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.5)',
    marginTop: 2,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1a365d',
  },
  viewAllText: {
    fontSize: 12,
    color: '#0d9488',
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 32,
  },
  emptyText: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.4)',
    marginTop: 8,
  },
  alertsList: {
    gap: 8,
  },
  alertItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(203, 213, 225, 0.5)',
  },
  alertDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 2,
  },
  alertContent: {
    flex: 1,
  },
  alertTitle: {
    fontSize: 12,
    fontWeight: '500',
    color: '#1a365d',
  },
  alertTime: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.5)',
    marginTop: 2,
  },
  contactsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  contactCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    width: '48%',
  },
  contactLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
  },
  contactNumber: {
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.8)',
  },
});
