import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { demoActivityFeed } from '@/lib/demoContent';
import { BellRing, ShieldAlert, BadgeCheck } from 'lucide-react-native';

export default function AdminAlerts() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Alerts</Text>
        <Text style={styles.subtitle}>Command-center style incident inbox for the prototype</Text>
      </View>

      <View style={styles.topCard}>
        <ShieldAlert size={20} color="#ef4444" />
        <Text style={styles.topText}>Priority routing: one SOS, two warnings, and one resolved case.</Text>
      </View>

      {demoActivityFeed.map((item) => (
        <View key={item.text} style={styles.row}>
          <View style={[styles.iconWrap, { backgroundColor: item.color + '22' }]}>
            {item.type === 'resolve' ? <BadgeCheck size={16} color={item.color} /> : <BellRing size={16} color={item.color} />}
          </View>
          <View style={styles.rowBody}>
            <Text style={styles.rowTitle}>{item.text}</Text>
            <Text style={styles.rowMeta}>{item.sub}</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  topCard: { backgroundColor: '#fff1f2', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#fecdd3', flexDirection: 'row', gap: 10, alignItems: 'center' },
  topText: { flex: 1, color: '#881337', lineHeight: 20 },
  row: { backgroundColor: '#fff', borderRadius: 16, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  iconWrap: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  rowBody: { flex: 1 },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowMeta: { marginTop: 4, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
});
