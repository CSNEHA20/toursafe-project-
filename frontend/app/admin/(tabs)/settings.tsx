import { ScrollView, View, Text, StyleSheet, Switch } from 'react-native';
import { useEffect, useState } from 'react';
import { ShieldCheck, BellRing, DatabaseZap, LockKeyhole } from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';
import Toast from 'react-native-toast-message';

export default function AdminSettings() {
  const { user, isAuthenticated, signOut, accessToken } = useAuthStore();
  const [alerts, setAlerts] = useState(true);
  const [offline, setOffline] = useState(true);
  const [audit, setAudit] = useState(true);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [authorityProfile, setAuthorityProfile] = useState<any>(null);

  useEffect(() => {
    async function loadData() {
      if (!isAuthenticated || !user || (user.role !== 'authority' && user.role !== 'admin')) {
        return;
      }

      setLoadingProfile(true);
      try {
        const res = await fetch(`${process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/authority/me`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        if (res.ok) {
          const data = await res.json();
          setAuthorityProfile(data);
        }
      } catch (err: any) {
        console.error('Authority profile load error:', err);
      } finally {
        setLoadingProfile(false);
      }
    }

    loadData();
  }, [isAuthenticated, accessToken, user?.role]);

  const getStatusColor = (status?: string) => {
    if (status === 'verified') return '#0d9488';
    if (status === 'rejected') return '#ef4444';
    return '#f59e0b';
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.subtitle}>Prototype controls for the authority demo</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Authority profile</Text>
        {authorityProfile ? (
          <View>
            <Text style={styles.profileField}>
              Name: {authorityProfile.full_name}
            </Text>
            <Text style={styles.profileField}>
              Organization: {authorityProfile.organization_name || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              Designation: {authorityProfile.designation || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              Phone: {authorityProfile.phone || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              Office Phone: {authorityProfile.office_phone || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              Address: {authorityProfile.address || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              License Number: {authorityProfile.license_number || 'Not set'}
            </Text>
            <Text style={styles.profileField}>
              Verification Status:{' '}
              <Text style={{ color: getStatusColor(authorityProfile.verification_status), fontWeight: '600' }}>
                {authorityProfile.verification_status || 'pending'}
              </Text>
            </Text>
          </View>
        ) : (
          <Text style={styles.noProfile}>Loading profile...</Text>
        )}
      </View>

      <SettingRow icon={<ShieldCheck size={18} color="#1a365d" />} label="Demo security mode" value="Enabled" />
      <SettingToggle icon={<BellRing size={18} color="#0d9488" />} label="Alert sound" enabled={alerts} onChange={setAlerts} />
      <SettingToggle icon={<DatabaseZap size={18} color="#b45309" />} label="Offline-first cache" enabled={offline} onChange={setOffline} />
      <SettingToggle icon={<LockKeyhole size={18} color="#ef4444" />} label="Audit trail logging" enabled={audit} onChange={setAudit} />

      <View style={styles.footerCard}>
        <Text style={styles.footerTitle}>Future backend switchovers</Text>
        <Text style={styles.footerText}>
          These toggles are visual only right now. Later they can map to real config, APIs, and permissions.
        </Text>
      </View>
    </ScrollView>
  );
}

function SettingRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.row}>
      <View style={styles.rowIcon}>{icon}</View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
      </View>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

function SettingToggle({
  icon,
  label,
  enabled,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  enabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowIcon}>{icon}</View>
      <Text style={[styles.rowLabel, { flex: 1 }]}>{label}</Text>
      <Switch value={enabled} onValueChange={onChange} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  row: { backgroundColor: '#fff', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#e2e8f0', flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowIcon: { width: 36, height: 36, borderRadius: 12, backgroundColor: '#f8fafc', alignItems: 'center', justifyContent: 'center' },
  rowLabel: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowValue: { fontSize: 12, fontWeight: '800', color: '#0d9488' },
  footerCard: { backgroundColor: '#1a365d', borderRadius: 18, padding: 16, marginTop: 6 },
  footerTitle: { color: '#fff', fontSize: 16, fontWeight: '800', marginBottom: 8 },
  footerText: { color: 'rgba(255,255,255,0.75)', lineHeight: 20 },
  section: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  profileField: { marginBottom: 8, color: '#0f172a', fontSize: 14 },
  noProfile: { padding: 20, color: '#64748b', fontStyle: 'italic' },
});