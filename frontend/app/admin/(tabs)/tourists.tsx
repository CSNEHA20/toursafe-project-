import { ScrollView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useEffect, useState } from 'react';
import { UserRound, MapPin, ShieldAlert } from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';

export default function AdminTourists() {
  const { user, isAuthenticated, signOut, accessToken } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [tourists, setTourists] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    let mounted = true;

    if (!isAuthenticated || !user || user.role !== 'admin') {
      setLoading(false);
      setError('Admin access required');
      return;
    }

    async function loadData() {
      setLoading(true);
      setError(null);

      try {
        const url = new URL(
          `${process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/authority/tourists?page=1&per_page=50`
        );
        if (search) {
          url.searchParams.set('search', search);
        }
        if (statusFilter !== 'all') {
          url.searchParams.set('status', statusFilter);
        }

        const res = await fetch(url.toString(), {
          method: 'GET',
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error?.message || 'Failed to load tourists');
        }

        const data = await res.json();
        setTourists(data.items || []);
        setPage(data.page || 1);
      } catch (err: any) {
        console.error('Admin tourists load error:', err);
        setError(err.message || 'Failed to load tourists data');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    return () => { mounted = false; };
  }, [isAuthenticated, accessToken, user?.role, search, statusFilter]);

  if (!isAuthenticated || !user || user.role !== 'admin') {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Tourists</Text>
          <Text style={styles.subtitle}>Admin access required</Text>
        </View>
        <Text style={styles.errorText}>Admin privileges needed</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>Tourists</Text>
        <Text style={styles.subtitle}>A compact roster view for the command demo</Text>
      </View>

      <View style={styles.toolbar}>
        <View style={styles.searchBox}>
          <Text style={styles.searchLabel}>Search</Text>
          <Text style={styles.searchInputPlaceholder}>Search tourists...</Text>
        </View>
        <View style={styles.filterPillsRow}>
          {(['all', 'sos', 'warning', 'alert'] as const).map((filter) => {
            const isActive = statusFilter === filter;
            return (
              <TouchableOpacity
                key={filter}
                style={[styles.filterPill, isActive && styles.filterPillActive]}
                onPress={() => setStatusFilter(filter)}
              >
                <Text style={[styles.filterText, isActive && styles.filterTextActive]}>
                  {filter.toUpperCase()}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="large" color="#1a365d" />}

      {!loading && tourists.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No tourists found</Text>
          {search ? <Text style={styles.emptyHint}>Try adjusting the search filter</Text> : null}
        </View>
      ) : (
        tourists.map((tourist: any) => (
          <TouchableOpacity
            key={tourist.id}
            style={styles.card}
            onPress={() => {}}
          >
            <View style={styles.avatar}>
              <UserRound size={18} color="#1a365d" />
            </View>
            <View style={styles.body}>
              <Text style={styles.name}>{tourist.full_name}</Text>
              <Text style={styles.meta}>
                {tourist.nationality} · {tourist.kyc_status ?? 'pending'} KYC
              </Text>
              <View style={styles.metaRow}>
                <MapPin size={12} color="#0d9488" />
                <Text style={styles.meta}>{tourist.current_zone_id ?? 'Unknown zone'}</Text>
              </View>
            </View>
            <View style={styles.statusPill}>
              <ShieldAlert
                size={12}
                color={
                  tourist.kyc_status === 'verified'
                    ? '#0d9488'
                    : tourist.kyc_status === 'rejected'
                    ? '#ef4444'
                    : tourist.kyc_status === 'submitted'
                    ? '#f59e0b'
                    : '#0d9488'
                }
              />
              <Text style={styles.statusText}>
                {tourist.kyc_status?.toUpperCase() ?? 'UNKNOWN'}
              </Text>
            </View>
          </TouchableOpacity>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 12 },
  header: { marginBottom: 4 },
  title: { fontSize: 24, fontWeight: '800', color: '#1a365d' },
  subtitle: { marginTop: 6, color: 'rgba(100,116,139,0.75)', lineHeight: 20 },
  toolbar: { marginBottom: 12, gap: 8 },
  searchBox: { flex: 1 },
  searchLabel: { fontSize: 12, color: '#64748b', marginBottom: 4, fontWeight: '600' },
  searchInputPlaceholder: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: '#64748b',
  },
  filterPillsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  filterPill: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  filterPillActive: {
    backgroundColor: '#1a365d',
    borderColor: '#1a365d',
  },
  filterText: {
    color: '#64748b',
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  filterTextActive: {
    color: '#ffffff',
  },
  errorBox: { backgroundColor: '#fef3c7', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#eab308', margin: 8 },
  errorText: { color: '#92400e', fontSize: 13 },
  emptyState: { padding: 40, alignItems: 'center', justifyContent: 'center' },
  emptyText: { fontSize: 18, color: '#64748b', marginBottom: 8 },
  emptyHint: { color: '#94a3b8', fontStyle: 'italic' },
  card: { backgroundColor: '#fff', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: '#e2e8f0', flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 42, height: 42, borderRadius: 14, backgroundColor: '#dbeafe', alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1 },
  name: { fontSize: 14, fontWeight: '800', color: '#0f172a' },
  meta: { fontSize: 12, color: 'rgba(100,116,139,0.8)', marginTop: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  statusPill: { alignItems: 'center', justifyContent: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 999, backgroundColor: '#f8fafc', borderWidth: 1, borderColor: '#e2e8f0' },
  statusText: { fontSize: 11, fontWeight: '800', color: '#1a365d' },
});