import { ScrollView, View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { Copy, ShieldCheck, Fingerprint, HeartPulse, UserRound } from 'lucide-react-native';
import { demoTourist } from '@/lib/demoContent';
import Toast from 'react-native-toast-message';

export default function DigitalID() {
  const qrValue = `did:polygon:mumbai:${demoTourist.did_mock_id ?? 'tour-safe-demo'}|${demoTourist.full_name}`;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <View style={styles.header}>
          <View style={styles.badge}>
            <ShieldCheck size={18} color="#0d9488" />
          </View>
          <View>
            <Text style={styles.title}>Digital ID</Text>
            <Text style={styles.subtitle}>Frontend-only identity card for quick demos</Text>
          </View>
        </View>

        <View style={styles.profileBlock}>
          <View style={styles.avatar}>
            <UserRound size={28} color="#1a365d" />
          </View>
          <View style={styles.profileText}>
            <Text style={styles.name}>{demoTourist.full_name}</Text>
            <Text style={styles.meta}>{demoTourist.nationality} traveler</Text>
            <Text style={styles.meta}>{demoTourist.did_uri}</Text>
          </View>
        </View>

        <View style={styles.qrFrame}>
          <QRCode value={qrValue} size={190} backgroundColor="#fff" color="#1a365d" />
        </View>

        <View style={styles.infoGrid}>
          <InfoChip icon={<Fingerprint size={16} color="#0d9488" />} label="DID" value={demoTourist.did_mock_id ?? 'Pending'} />
          <InfoChip icon={<HeartPulse size={16} color="#ef4444" />} label="Blood Group" value={demoTourist.blood_type ?? 'O+'} />
          <InfoChip icon={<ShieldCheck size={16} color="#1a365d" />} label="Status" value="Verified" />
        </View>

        <TouchableOpacity
          style={styles.button}
          onPress={() =>
            Toast.show({
              type: 'success',
              text1: 'QR payload copied',
              text2: 'The demo identity payload is ready for sharing.',
            })
          }
        >
          <Copy size={16} color="#fff" />
          <Text style={styles.buttonText}>Copy emergency QR payload</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function InfoChip({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <View style={styles.chip}>
      <View style={styles.chipIcon}>{icon}</View>
      <Text style={styles.chipLabel}>{label}</Text>
      <Text style={styles.chipValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16 },
  card: { backgroundColor: '#fff', borderRadius: 20, padding: 18, borderWidth: 1, borderColor: '#e2e8f0' },
  header: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  badge: { width: 42, height: 42, borderRadius: 12, backgroundColor: '#ecfeff', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 22, fontWeight: '800', color: '#1a365d' },
  subtitle: { fontSize: 13, color: 'rgba(100,116,139,0.7)', marginTop: 3 },
  profileBlock: { flexDirection: 'row', gap: 12, alignItems: 'center', marginTop: 18, padding: 14, borderRadius: 16, backgroundColor: '#f8fafc' },
  avatar: { width: 64, height: 64, borderRadius: 20, backgroundColor: '#dbeafe', alignItems: 'center', justifyContent: 'center' },
  profileText: { flex: 1, gap: 4 },
  name: { fontSize: 18, fontWeight: '800', color: '#0f172a' },
  meta: { fontSize: 12, color: 'rgba(100,116,139,0.85)' },
  qrFrame: { marginTop: 18, alignItems: 'center', padding: 18, borderRadius: 18, borderWidth: 1, borderColor: '#dbeafe', backgroundColor: '#eff6ff' },
  infoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 16 },
  chip: { flex: 1, minWidth: '30%', backgroundColor: '#f8fafc', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  chipIcon: { marginBottom: 8 },
  chipLabel: { fontSize: 11, textTransform: 'uppercase', color: 'rgba(100,116,139,0.65)', fontWeight: '700' },
  chipValue: { fontSize: 13, fontWeight: '800', color: '#1a365d', marginTop: 4 },
  button: { marginTop: 18, backgroundColor: '#1a365d', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 14 },
  buttonText: { color: '#fff', fontWeight: '700' },
});
