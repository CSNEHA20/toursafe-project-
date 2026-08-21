import { ScrollView, View, Text, StyleSheet, TouchableOpacity, Platform } from 'react-native';
import { MapPin, Navigation, ShieldAlert, Clock3, TriangleAlert, Layers3 } from 'lucide-react-native';
import { demoNearbyPlaces, demoTourist } from '@/lib/demoContent';
import { useRouter } from 'expo-router';
import RealMap from '@/components/RealMap';

const touristRoute = [
  { latitude: 10.2381, longitude: 77.4892 },
  { latitude: 10.2274, longitude: 77.4803 },
  { latitude: 10.2194, longitude: 77.4721 },
  { latitude: 10.205, longitude: 77.465 },
];

export default function TouristMap() {
  const router = useRouter();
  const center = { latitude: 10.205, longitude: 77.465, latitudeDelta: 0.08, longitudeDelta: 0.08 };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View>
            <Text style={styles.kicker}>Live travel zone</Text>
            <Text style={styles.title}>{demoTourist.current_zone_name}</Text>
            <Text style={styles.subtitle}>Real map view with route, markers, and nearby safety anchors</Text>
          </View>
          <TouchableOpacity onPress={() => router.push('/tourist/(tabs)/sos')} style={styles.sosButton}>
            <ShieldAlert size={18} color="#fff" />
            <Text style={styles.sosText}>SOS</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.mapFrame}>
          <View style={styles.mapHeader}>
            <View style={styles.mapChip}>
              <Navigation size={14} color="#0d9488" />
              <Text style={styles.mapChipText}>GPS locked</Text>
            </View>
            <View style={styles.mapChip}>
              <Clock3 size={14} color="#1a365d" />
              <Text style={styles.mapChipText}>Last update 28 sec ago</Text>
            </View>
            <View style={styles.mapChip}>
              <Layers3 size={14} color="#475569" />
              <Text style={styles.mapChipText}>{Platform.OS === 'web' ? 'OpenStreetMap' : 'Native map'}</Text>
            </View>
          </View>

          <RealMap
            region={center}
            route={touristRoute}
            markers={[
              { ...touristRoute[0], title: 'Start point', color: '#0d9488' },
              { ...touristRoute[touristRoute.length - 1], title: 'Current position', color: '#ef4444' },
              { latitude: 10.214, longitude: 77.482, title: 'Safe exit', color: '#f59e0b' },
            ]}
            overlayTitle="Kodaikanal Lake zone"
            overlayText="The live map is powered by a real map layer with route markers and a tracked path."
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Nearby places</Text>
        {demoNearbyPlaces.map((place) => (
          <View key={place.name} style={styles.placeRow}>
            <View
              style={[
                styles.placeBadge,
                place.type === 'danger' && styles.dangerBadge,
                place.type === 'warning' && styles.warningBadge,
                place.type === 'safe' && styles.safeBadge,
              ]}
            >
              <MapPin size={14} color={place.type === 'danger' ? '#fff' : '#1a365d'} />
            </View>
            <View style={styles.placeBody}>
              <Text style={styles.placeName}>{place.name}</Text>
              <Text style={styles.placeMeta}>{place.distance}</Text>
            </View>
            <Text style={styles.placeType}>{place.type.toUpperCase()}</Text>
          </View>
        ))}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Route intelligence</Text>
        <View style={styles.alertCard}>
          <TriangleAlert size={18} color="#b45309" />
          <Text style={styles.alertText}>
            Avoid the Guna Caves corridor after 17:00. The route follows a safer lake-side exit in the prototype.
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f1f5f9' },
  content: { padding: 16, gap: 16 },
  hero: { backgroundColor: '#1a365d', borderRadius: 20, padding: 16 },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  kicker: { color: 'rgba(255,255,255,0.6)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1 },
  title: { color: '#fff', fontSize: 22, fontWeight: '800', marginTop: 4 },
  subtitle: { color: 'rgba(255,255,255,0.72)', marginTop: 6, lineHeight: 20, maxWidth: 300 },
  sosButton: {
    backgroundColor: '#ef4444',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sosText: { color: '#fff', fontWeight: '700' },
  mapFrame: { marginTop: 16, backgroundColor: '#fff', borderRadius: 18, padding: 12 },
  mapHeader: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  mapChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#eff6ff',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  mapChipText: { fontSize: 11, color: '#1a365d', fontWeight: '600' },
  section: { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#e2e8f0' },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#1a365d', marginBottom: 12 },
  placeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eef2f7',
  },
  placeBadge: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#e2e8f0',
  },
  dangerBadge: { backgroundColor: '#ef4444' },
  warningBadge: { backgroundColor: '#f59e0b' },
  safeBadge: { backgroundColor: '#10b981' },
  placeBody: { flex: 1 },
  placeName: { fontSize: 14, fontWeight: '700', color: '#0f172a' },
  placeMeta: { fontSize: 12, color: 'rgba(100,116,139,0.75)', marginTop: 2 },
  placeType: { fontSize: 11, fontWeight: '800', color: '#64748b' },
  alertCard: {
    backgroundColor: '#fff7ed',
    borderRadius: 14,
    padding: 14,
    flexDirection: 'row',
    gap: 10,
    borderWidth: 1,
    borderColor: '#fed7aa',
  },
  alertText: { flex: 1, color: '#7c2d12', lineHeight: 20 },
});
