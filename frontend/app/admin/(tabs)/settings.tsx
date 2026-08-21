import { ScrollView, View, Text, StyleSheet, Switch } from 'react-native';
import { useState } from 'react';
import { ShieldCheck, BellRing, DatabaseZap, LockKeyhole } from 'lucide-react-native';

export default function AdminSettings() {
  const [alerts, setAlerts] = useState(true);
  const [offline, setOffline] = useState(true);
  const [audit, setAudit] = useState(true);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Settings</Text>
        <Text style={styles.subtitle}>Prototype controls for the authority demo</Text>
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
});
