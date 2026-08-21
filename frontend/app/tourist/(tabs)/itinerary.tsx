import { ScrollView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { CalendarDays, MapPin, Route, TimerReset } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import Toast from 'react-native-toast-message';

export default function Itinerary() {
  const { user, isAuthenticated, refreshSession, accessToken } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [itineraries, setItineraries] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<string | null>('none');

  useEffect(() => {
    let mounted = true;

    if (!isAuthenticated || !user) {
      setLoading(false);
      setError(null);
      return;
    }

    async function loadData() {
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/itinerary`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.error?.message || 'Failed to load itinerary');
        }

        const data = await res.json();
        setItineraries(data.items || []);
      } catch (err: any) {
        console.error('Itinerary load error:', err);
        setError(err.message || 'Failed to load itinerary data');
        setErrorType('network');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    return () => { mounted = false; };
  }, [isAuthenticated, accessToken]);

  if (!isAuthenticated || !user) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>My Itinerary</Text>
        </View>
        <Text style={styles.errorText}>Please log in to view your itinerary</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>My Itinerary</Text>
        <Text style={styles.subtitle}>Your planned travel schedule and safety waypoints</Text>
      </View>

      <View style={styles.summaryCard}>
        <CalendarDays size={18} color="#1a365d" />
        <View style={{ flex: 1 }}>
          <Text style={styles.summaryTitle}>Trip status: active</Text>
          <Text style={styles.summaryText}>({itineraries.length} itinerary entries loaded)</Text>
        </View>
        <Route size={18} color="#0d9488" />
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="large" color="#1a365d" />}

      {itineraries.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No itineraries yet</Text>
          <Text style={styles.emptyHint}>Add your first itinerary using the + button</Text>
        </View>
      ) : (
        itineraries.map((day: any, index: number) => (
          <View key={day.itinerary_id || index} style={styles.dayCard}>
            <View style={styles.dayHeader}>
              <View>
                <Text style={styles.dayDate}>{day.start_date ? new Date(day.start_date).toLocaleDateString() : 'No date'}</Text>
                <Text style={styles.dayTitle}>{day.title}</Text>
              </View>
              <TimerReset size={18} color="#0d9488" />
            </View>
            {day.entries && day.entries.length > 0 ? (
              day.entries.map((step: any, i: number) => (
                <View key={i} style={styles.stepRow}>
                  <MapPin size={14} color="#1a365d" />
                  <Text style={styles.stepText}>{step.spot_name || step.name || 'Step ' + (i + 1)}</Text>
                </View>
              ))
            ) : (
              <View style={styles.stepRow}>
                <MapPin size={14} color="#1a365d" />
                <Text style={styles.stepText}>No stops added</Text>
              </View>
            )}
          </View>
        ))
      )}
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
  emptyState: { padding: 40, alignItems: 'center', justifyContent: 'center' },
  emptyText: { fontSize: 18, color: '#64748b', marginBottom: 8 },
  emptyHint: { color: '#94a3b8', fontStyle: 'italic' },
  errorBox: { backgroundColor: '#fef3c7', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#eab308', margin: 12 },
  errorText: { color: '#92400e', fontSize: 14 },
});