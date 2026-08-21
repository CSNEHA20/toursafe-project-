import { ScrollView, View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { UserRound, HeartPulse, Shield, BellRing, LogOut } from 'lucide-react-native';
import { demoConsentLog, demoEmergencyContacts, demoTourist } from '@/lib/demoContent';
import { useAuthStore } from '@/store/authStore';

export default function Profile() {
  const { signOut } = useAuthStore();

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={styles.avatar}>
          <UserRound size={32} color="#fff" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.name}>{demoTourist.full_name}</Text>
          <Text style={styles.subtitle}>{demoTourist.email}</Text>
          <Text style={styles.subtitle}>{demoTourist.current_zone_name}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Health snapshot</Text>
        <View style={styles.grid}>
          <Stat label="Blood Group" value={demoTourist.blood_type ?? 'O+'} icon={<HeartPulse size={16} color="#ef4444" />} />
          <Stat label="Tracking" value="Enabled" icon={<Shield size={16} color="#0d9488" />} />
          <Stat label="Alerts" value="3 active" icon={<BellRing size={16} color="#b45309" />} />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Emergency contacts</Text>
        {demoEmergencyContacts.local.slice(0, 4).map((contact) => (
          <View key={contact.name} style={styles.row}>
            <Text style={styles.rowTitle}>{contact.name}</Text>
            <Text style={styles.rowMeta}>{contact.phone}</Text>
          </View>
        ))}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Consent log</Text>
        {demoConsentLog.slice(0, 4).map((item) => (
          <View key={item.type} style={styles.row}>
            <Text style={styles.rowTitle}>{item.type}</Text>
            <Text style={styles.rowMeta}>{item.action}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity onPress={() => signOut()} style={styles.logoutButton}>
        <LogOut size={16} color="#fff" />
        <Text style={styles.logoutText}>Reset demo session</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function Stat({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <View style={styles.stat}>
      {icon}
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  hero: { backgroundColor: '#1a365d', borderRadius: 20, padding: 16, flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: { width: 72, height: 72, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.15)', alignItems: 'center', justifyContent: 'center' },
  name: { color: '#fff', fontSize: 22, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.7)', marginTop: 4 },
  section: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  grid: { flexDirection: 'row', gap: 10, flexWrap: 'wrap' },
  stat: { flex: 1, minWidth: '30%', backgroundColor: '#f8fafc', borderRadius: 14, padding: 12, borderWidth: 1, borderColor: '#e2e8f0', gap: 6 },
  statLabel: { fontSize: 11, color: 'rgba(100,116,139,0.7)', textTransform: 'uppercase', fontWeight: '700' },
  statValue: { fontSize: 14, fontWeight: '800', color: '#0f172a' },
  row: { paddingVertical: 10, borderTopWidth: 1, borderTopColor: '#eef2f7' },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowMeta: { marginTop: 4, color: 'rgba(100,116,139,0.8)' },
  logoutButton: { backgroundColor: '#0f172a', borderRadius: 14, paddingVertical: 14, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 },
  logoutText: { color: '#fff', fontWeight: '800' },
});
