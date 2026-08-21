import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { demoActivityFeed } from '@/lib/demoContent';
import { TriangleAlert, BadgeCheck, ShieldAlert, Clock3 } from 'lucide-react-native';

export default function Incidents() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Incident Feed</Text>
        <Text style={styles.subtitle}>A polished preview of live events and safety updates</Text>
      </View>

      <View style={styles.highlightCard}>
        <TriangleAlert size={20} color="#b45309" />
        <Text style={styles.highlightText}>
          1 active SOS and 3 zone warnings are visible in the demo feed.
        </Text>
      </View>

      {demoActivityFeed.map((item) => (
        <View key={item.text} style={styles.row}>
          <View style={[styles.iconWrap, { backgroundColor: item.color + '22' }]}>
            {item.type === 'sos' ? <ShieldAlert size={16} color={item.color} /> : item.type === 'resolve' ? <BadgeCheck size={16} color={item.color} /> : <TriangleAlert size={16} color={item.color} />}
          </View>
          <View style={styles.rowBody}>
            <Text style={styles.rowTitle}>{item.text}</Text>
            <Text style={styles.rowSub}>{item.sub}</Text>
          </View>
          <Clock3 size={14} color="rgba(100,116,139,0.45)" />
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  highlightCard: { backgroundColor: '#fff7ed', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#fed7aa', flexDirection: 'row', gap: 10, alignItems: 'center' },
  highlightText: { flex: 1, color: '#7c2d12', lineHeight: 20 },
  row: { backgroundColor: '#fff', borderRadius: 16, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  iconWrap: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  rowBody: { flex: 1 },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  rowSub: { fontSize: 12, color: 'rgba(100,116,139,0.8)', marginTop: 4 },
});
