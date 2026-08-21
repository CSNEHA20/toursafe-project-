import { ScrollView, View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { UserRound, HeartPulse, Shield, BellRing, LogOut } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/authStore';
import { toast } from 'react-native-toast-message';

export default function Profile() {
  const { user, signOut, isAuthenticated } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [tourist, setTourist] = useState<any>(null);
  const [kycStatus, setKycStatus] = useState('pending');
  const [profileCompleteness, setProfileCompleteness] = useState(0);
  const [medical, setMedical] = useState<any>(null);
  const [emergencyContacts, setEmergencyContacts] = useState<any[]>([]);
  const [itineraries, setItineraries] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<string | null>('none');

  useEffect(() => {
    let mounted = true;

    if (!isAuthenticated || !user) {
      setLoading(false);
      setError(null);
      setErrorType('none');
      return;
    }

    async function loadData() {
      setLoading(true);
      setError(null);

      try {
        // Get tourist profile
        const profileRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (!profileRes.ok) {
          const errData = await profileRes.json();
          throw new Error(errData.error?.message || 'Failed to load profile');
        }

        const profileData = await profileRes.json();
        setTourist(profileData);

        // Get KYC status
        const kycRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/kyc`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (kycRes.ok) {
          const kycData = await kycRes.json();
          setKycStatus(kycData.status || 'pending');
        }

        // Get profile status
        const statusRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/status`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (statusRes.ok) {
          const statusData = await statusRes.json();
          setProfileCompleteness(statusData.profile_completeness || 0);
        }

        // Get medical profile
        const medicalRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/medical`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (medicalRes.ok) {
          const medicalData = await medicalRes.json();
          setMedical(medicalData);
        } else if (medicalRes.status === 404) {
          // No medical profile yet - that's OK
          setMedical({ blood_group: '', allergies: [], medical_conditions: [], medications: [] });
        }

        // Get emergency contacts
        const contactsRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/emergency-contacts`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (contactsRes.ok) {
          const contactsData = await contactsRes.json();
          setEmergencyContacts(contactsData.items || []);
        }

        // Get itineraries
        const itineraryRes = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/tourists/me/itinerary`, {
          method: 'GET',
          headers: { Authorization: `Bearer ${user.accessToken}` },
        });

        if (itineraryRes.ok) {
          const itineraryData = await itineraryRes.json();
          setItineraries(itineraryData.items || []);
        }

      } catch (err: any) {
        console.error('Profile load error:', err);
        setError(err.message || 'Failed to load profile data');
        setErrorType('network');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    return () => { mounted = false; }
  }, [isAuthenticated, user?.accessToken]);

  if (!isAuthenticated || !user) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <View style={styles.avatar}>
            <UserRound size={32} color="#fff" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.name}>Loading...</Text>
          </View>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={styles.avatar}>
          <UserRound size={32} color="#fff" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.name}>{user.full_name || 'Tourist'}</Text>
          <Text style={styles.subtitle}>{user.email}</Text>
          <Text style={styles.subtitle}>{tourist?.current_zone_name || ''}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Health snapshot</Text>
        <View style={styles.grid}>
          <Stat label="Blood Group" value={medical?.blood_group ?? 'Not set'} icon={<HeartPulse size={16} color="#ef4444" />} />
          <Stat label="Tracking" value="Enabled" icon={<Shield size={16} color="#0d9488" />} />
          <Stat label="Alerts" value="3 active" icon={<BellRing size={16} color="#b45309" />} />
        </View>
      </View>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {loading && <ActivityIndicator size="large" animated />}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>KYC Status</Text>
        <View style={styles.kycStatus}>
          <Text style={styles.kycLabel}>{kycStatus}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Profile Completeness</Text>
        <View style={styles.progressBar}>
          <Text style={styles.percentage}>{profileCompleteness}%</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Emergency contacts</Text>
        {emergencyContacts.length === 0 ? (
          <Text style={styles.noContacts}>No emergency contacts added</Text>
        ) : (
          emergencyContacts.map((contact: any, index: number) => (
            <View key={contact.emergency_contact_id || index} style={styles.contactRow}>
              <Text style={styles.contactName}>{contact.name}</Text>
              <Text style={styles.contactPhone}>{contact.phone}</Text>
              {contact.relationship && <Text style={styles.contactRelation}>({contact.relationship})</Text>}
            </View>
          ))
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Itinerary</Text>
        {itineraries.length === 0 ? (
          <Text style={styles.noItinerary}>No itineraries added</Text>
        ) : (
          itineraries.map((itinerary: any, index: number) => (
            <View key={itinerary.itinerary_id || index} style={styles.itineraryCard}>
              <Text style={styles.itineraryTitle}>{itinerary.title}</Text>
              <Text style={styles.itineraryMeta}>
                {itinerary.destination || 'No destination'} · 
                {itinerary.start_date ? new Date(itinerary.start_date).toLocaleDateString() : 'No dates'}
              </Text>
            </View>
          ))
        )}
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
  errorBox: { backgroundColor: '#fef3c7', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#eab308', margin: 12 },
  errorText: { color: '#92400e', fontSize: 14 },
  progressBar: { marginTop: 8 },
  percentage: { fontSize: 18, fontWeight: '700', color: '#0f172a' },
  kycStatus: { marginTop: 8 },
  kycLabel: { fontSize: 14, color: '#0d9488', fontWeight: '600' },
  noContacts: { padding: 16, color: '#64748b', fontStyle: 'italic' },
  noItinerary: { padding: 16, color: '#64748b', fontStyle: 'italic' },
  contactRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#e2e8f7' },
  contactName: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  contactPhone: { marginTop: 2, color: '#334155', fontSize: 13 },
  contactRelation: { marginTop: 2, color: '#64748b', fontSize: 11, fontStyle: 'italic' },
  logoutButton: { backgroundColor: '#0f172a', borderRadius: 14, paddingVertical: 14, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 8 },
  logoutText: { color: '#fff', fontWeight: '800' },
});