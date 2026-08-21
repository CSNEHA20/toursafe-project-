import { ScrollView, View, Text, StyleSheet } from 'react-native';
import { CalendarDays, MapPin, Route, TimerReset } from 'lucide-react-native';
import { demoItinerary } from '@/lib/demoContent';

export default function Itinerary() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>My Itinerary</Text>
        <Text style={styles.subtitle}>A prototype day-by-day travel plan with safety context</Text>
      </View>

      <View style={styles.summaryCard}>
        <CalendarDays size={18} color="#1a365d" />
        <View style={{ flex: 1 }}>
          <Text style={styles.summaryTitle}>Trip status: Active</Text>
          <Text style={styles.summaryText}>All stops are synced locally for demo mode.</Text>
        </View>
        <Route size={18} color="#0d9488" />
      </View>

      {demoItinerary.map((day) => (
        <View key={day.id} style={styles.dayCard}>
          <View style={styles.dayHeader}>
            <View>
              <Text style={styles.dayDate}>{day.date}</Text>
              <Text style={styles.dayTitle}>{day.title}</Text>
            </View>
            <TimerReset size={18} color="#0d9488" />
          </View>
          {day.steps.map((step) => (
            <View key={step} style={styles.stepRow}>
              <MapPin size={14} color="#1a365d" />
              <Text style={styles.stepText}>{step}</Text>
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 14 },
  header: { marginBottom: 6 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  summaryCard: { backgroundColor: '#fff', borderRadius: 16, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: '#e2e8f0' },
  summaryTitle: { fontSize: 14, fontWeight: '800', color: '#0f172a' },
  summaryText: { marginTop: 3, fontSize: 12, color: 'rgba(100,116,139,0.8)' },
  dayCard: { backgroundColor: '#fff', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#e2e8f0' },
  dayHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  dayDate: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, color: 'rgba(100,116,139,0.7)', fontWeight: '700' },
  dayTitle: { fontSize: 18, fontWeight: '800', color: '#1a365d', marginTop: 2 },
  stepRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderTopWidth: 1, borderTopColor: '#eef2f7' },
  stepText: { color: '#0f172a', flex: 1 },
});
