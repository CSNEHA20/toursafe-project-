import {
  MOCK_ACTIVITY_FEED,
  MOCK_ANALYTICS_SNAPSHOTS,
  MOCK_CONSENT_LOG,
  MOCK_EMERGENCY_CONTACTS,
  MOCK_HEATMAP_POINTS,
  MOCK_NEARBY_PLACES,
  MOCK_TOURISTS,
  MOCK_VERIFICATION_LOG,
  MOCK_ZONE_SUMMARY,
  MOCK_ZONES,
  MOCK_LOGGED_IN_TOURIST,
} from '@/lib/mockData';

export const demoTourist = MOCK_LOGGED_IN_TOURIST;
export const demoTourists = MOCK_TOURISTS.slice(0, 6);
export const demoZones = MOCK_ZONES.slice(0, 8);
export const demoZoneSummary = MOCK_ZONE_SUMMARY;
export const demoActivityFeed = MOCK_ACTIVITY_FEED.slice(0, 8);
export const demoAnalytics = MOCK_ANALYTICS_SNAPSHOTS;
export const demoNearbyPlaces = MOCK_NEARBY_PLACES;
export const demoConsentLog = MOCK_CONSENT_LOG;
export const demoEmergencyContacts = MOCK_EMERGENCY_CONTACTS;
export const demoVerificationLog = MOCK_VERIFICATION_LOG;
export const demoHeatmapPoints = MOCK_HEATMAP_POINTS;

export const demoItinerary = [
  {
    id: 'day-1',
    title: 'Kodaikanal Arrival',
    date: 'Today',
    steps: ['Check-in at hotel', 'Lake walk', 'Boathouse sunset'],
  },
  {
    id: 'day-2',
    title: 'Hill Trail Route',
    date: 'Tomorrow',
    steps: ['Coaker’s Walk', 'Pillar Rocks', 'Early return'],
  },
];
