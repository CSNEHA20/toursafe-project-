import { useRouter } from 'expo-router';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  useWindowDimensions,
} from 'react-native';
import {
  ArrowRight,
  Bell,
  Building2,
  Calendar,
  CheckCircle2,
  CircleAlert,
  FileBadge2,
  MapPinned,
  Menu,
  ScanQrCode,
  Shield,
  ShieldAlert,
  Smartphone,
  User,
  Waves,
} from 'lucide-react-native';

const clientScreens = [
  { no: '01', title: 'Splash / Welcome', icon: Shield, note: 'TourSafe' },
  { no: '02', title: 'Home Dashboard', icon: Smartphone, note: 'Safety status' },
  { no: '03', title: 'Live Location', icon: MapPinned, note: 'Route tracking' },
  { no: '04', title: 'SOS Emergency', icon: ShieldAlert, note: 'Press and hold' },
  { no: '05', title: 'Digital ID', icon: ScanQrCode, note: 'Blockchain verified' },
  { no: '06', title: 'Profile & Settings', icon: User, note: 'Privacy controls' },
  { no: '07', title: 'Alert History', icon: Bell, note: 'Recent incidents' },
];

const authorityHighlights = [
  { label: 'Active tourists', value: '247', icon: User, tint: '#0f766e' },
  { label: 'Live alerts', value: '12', icon: Bell, tint: '#f97316' },
  { label: 'SOS today', value: '3', icon: CircleAlert, tint: '#ef4444' },
  { label: 'Avg response', value: '7.2 min', icon: Calendar, tint: '#1d4ed8' },
];

const alertRows = [
  ['Critical', 'SOS triggered by Priya Sharma', 'Coaker’s Walk Ridge Trail'],
  ['High', 'High anomaly score (0.71) detected', 'Guna Caves (Devil’s Kitchen)'],
  ['High', 'Tourist Meena Das entered restricted zone', 'Berijam Lake Forest Reserve'],
  ['Low', 'Tourist Vikram Singh device battery low', 'Vattakanal & Dolphin’s Nose'],
];

const quickActions = [
  { title: 'Broadcast Message', icon: Waves },
  { title: 'Create Alert', icon: Bell },
  { title: 'Generate E-FIR', icon: FileBadge2 },
  { title: 'Export Report', icon: Shield },
];

export default function Index() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isCompact = width < 1100;

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.page}>
        <View style={styles.header}>
          <View style={styles.brandRow}>
            <View style={styles.brandMark}>
              <Shield size={20} color="#fff" />
            </View>
            <View>
              <Text style={styles.brandTitle}>TourSafe</Text>
              <Text style={styles.brandSubtitle}>Traveler Safety & Emergency Companion</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.headerButton} onPress={() => router.push('/auth/login')}>
            <Text style={styles.headerButtonText}>Open Demo Login</Text>
            <ArrowRight size={15} color="#0f172a" />
          </TouchableOpacity>
        </View>

        <View style={styles.heroCard}>
          <View style={styles.heroText}>
            <Text style={styles.heroKicker}>Client Mobile App (Tourist)</Text>
            <Text style={styles.heroTitle}>A premium safety-first travel app prototype.</Text>
            <Text style={styles.heroBody}>
              Frontend-only MVP for tourists and command teams — polished for a B2G-style product demo, with
              client, authority, SOS, identity, and live monitoring flows.
            </Text>
            <View style={styles.heroButtons}>
              <TouchableOpacity
                style={[styles.primaryButton, styles.primaryBlue]}
                onPress={() => router.push('/auth/login?role=tourist')}
              >
                <Text style={styles.primaryButtonText}>Client Login</Text>
                <ArrowRight size={16} color="#fff" />
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.primaryButton, styles.primaryDark]}
                onPress={() => router.push('/auth/login?role=authority')}
              >
                <Text style={styles.primaryButtonText}>Authority Login</Text>
                <ArrowRight size={16} color="#fff" />
              </TouchableOpacity>
            </View>
          </View>

          <View style={styles.heroBadge}>
            <ShieldAlert size={28} color="#1e40af" />
            <Text style={styles.heroBadgeTitle}>Demo credentials</Text>
            <Text style={styles.heroBadgeLine}>Authority: admin@toursafe.com / admin@123</Text>
            <Text style={styles.heroBadgeLine}>Alt authority: admin@tnpol.gov.in / admin@123</Text>
            <Text style={styles.heroBadgeLine}>Client: any email + demo OTP</Text>
          </View>
        </View>

        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>CLIENT MOBILE APP (TOURIST)</Text>
            <Text style={styles.sectionSubtitle}>Traveler Safety & Emergency Companion</Text>
          </View>
        </View>

        <View style={[styles.clientGrid, isCompact && styles.clientGridCompact]}>
          {clientScreens.map((screen, index) => {
            const Icon = screen.icon;
            return (
              <View key={screen.no} style={styles.phoneFrame}>
                <View style={styles.phoneStatus}>
                  <Text style={styles.phoneTime}>9:41</Text>
                  <Menu size={13} color="#0f172a" />
                </View>
                <View style={styles.phoneTop}>
                  <Icon size={28} color={index === 3 ? '#fff' : '#475569'} />
                </View>
                <Text style={styles.phoneTitle}>{screen.title}</Text>
                <Text style={styles.phoneNote}>{screen.note}</Text>
                <View style={styles.phoneArt}>
                  {index === 0 && (
                    <View style={styles.splashArt}>
                      <View style={styles.mountainA} />
                      <View style={styles.mountainB} />
                      <View style={styles.mountainC} />
                      <View style={styles.pathLine} />
                    </View>
                  )}
                  {index === 1 && (
                    <View style={styles.dashboardArt}>
                      <View style={styles.statusCard}>
                        <CheckCircle2 size={18} color="#64748b" />
                        <View style={{ flex: 1 }}>
                          <Text style={styles.statusLabel}>Safety Status</Text>
                          <Text style={styles.statusValue}>Safe</Text>
                        </View>
                      </View>
                      <View style={styles.gridRow}>
                        <View style={styles.gridTile}>
                          <User size={16} color="#0f172a" />
                          <Text style={styles.gridText}>Share Location</Text>
                        </View>
                        <View style={styles.gridTile}>
                          <ShieldAlert size={16} color="#0f172a" />
                          <Text style={styles.gridText}>SOS Emergency</Text>
                        </View>
                      </View>
                    </View>
                  )}
                  {index === 2 && (
                    <View style={styles.mapArt}>
                      <View style={styles.routeLine} />
                      <View style={styles.routePin} />
                      <View style={styles.routeEnd} />
                    </View>
                  )}
                  {index === 3 && (
                    <View style={styles.sosArt}>
                      <View style={styles.sosRing}>
                        <Text style={styles.sosText}>SOS</Text>
                      </View>
                    </View>
                  )}
                  {index === 4 && (
                    <View style={styles.idArt}>
                      <View style={styles.qrBox}>
                        <View style={styles.qrGrid}>
                          {Array.from({ length: 25 }).map((_, cellIndex) => {
                            const filled = [0, 1, 2, 5, 7, 8, 10, 12, 13, 15, 18, 20, 22, 24].includes(cellIndex);
                            return <View key={cellIndex} style={[styles.qrCell, filled && styles.qrCellFilled]} />;
                          })}
                        </View>
                      </View>
                    </View>
                  )}
                  {index === 5 && (
                    <View style={styles.profileArt}>
                      <View style={styles.avatarCircle}>
                        <Text style={styles.avatarLetter}>V</Text>
                      </View>
                      <View style={styles.profileLine} />
                      <View style={styles.profileLineShort} />
                      <View style={styles.toggleLine} />
                    </View>
                  )}
                  {index === 6 && (
                    <View style={styles.alertArt}>
                      {['Critical', 'High', 'High', 'Low'].map((tag) => (
                        <View key={tag} style={styles.alertChip}>
                          <Text style={styles.alertChipText}>{tag}</Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
                <Text style={styles.phoneCaption}>
                  {screen.no}. {screen.title}
                </Text>
              </View>
            );
          })}
        </View>

        <View style={styles.sectionHeader}>
          <View>
            <Text style={styles.sectionTitle}>AUTHORITY DASHBOARD (B2G PORTAL)</Text>
            <Text style={styles.sectionSubtitle}>Real-time Monitoring & Incident Management</Text>
          </View>
        </View>

        <View style={[styles.authorityLayout, isCompact && styles.authorityLayoutCompact]}>
          <View style={styles.loginCard}>
            <View style={styles.loginLogo}>
              <Shield size={34} color="#0f172a" />
            </View>
            <Text style={styles.loginTitle}>TourSafe</Text>
            <Text style={styles.loginSubtitle}>Authority Portal</Text>
            <View style={styles.loginFields}>
              <Text style={styles.inputLabel}>Email</Text>
              <View style={styles.fakeInput}>
                <Text style={styles.fakeInputText}>admin@toursafe.in</Text>
              </View>
              <Text style={styles.inputLabel}>Password</Text>
              <View style={styles.fakeInput}>
                <Text style={styles.fakeInputText}>••••••••••</Text>
              </View>
              <TouchableOpacity style={styles.loginButton} onPress={() => router.push('/auth/login?role=authority')}>
                <Text style={styles.loginButtonText}>Login</Text>
              </TouchableOpacity>
              <Text style={styles.loginFoot}>Secure Government Access</Text>
            </View>
          </View>

          <View style={styles.dashboardCard}>
            <View style={styles.dashboardTop}>
              <View>
                <Text style={styles.dashboardTitle}>Dashboard</Text>
                <Text style={styles.dashboardSubtitle}>Real-time overview of tourist safety operations</Text>
              </View>
              <View style={styles.livePill}>
                <View style={styles.liveDot} />
                <Text style={styles.liveText}>Live</Text>
                <Text style={styles.clockText}>21:17:59</Text>
              </View>
            </View>

            <View style={styles.metricRow}>
              {authorityHighlights.map((item) => {
                const Icon = item.icon;
                return (
                  <View key={item.label} style={styles.metricCard}>
                    <View style={[styles.metricIcon, { backgroundColor: `${item.tint}15` }]}>
                      <Icon size={16} color={item.tint} />
                    </View>
                    <Text style={styles.metricLabel}>{item.label}</Text>
                    <Text style={styles.metricValue}>{item.value}</Text>
                  </View>
                );
              })}
            </View>

            <View style={styles.dashboardBottom}>
              <View style={styles.alertPanel}>
                <View style={styles.panelHeader}>
                  <Text style={styles.panelTitle}>Recent Alerts</Text>
                  <Text style={styles.panelLink}>View All</Text>
                </View>
                {alertRows.map(([severity, title, zone]) => (
                  <View key={title} style={styles.alertRow}>
                    <Text style={[styles.severityBadge, severity === 'Critical' ? styles.critical : styles.high]}>
                      {severity}
                    </Text>
                    <View style={styles.alertTextCol}>
                      <Text style={styles.alertTitle}>{title}</Text>
                      <Text style={styles.alertZone}>{zone}</Text>
                    </View>
                    <Text style={styles.alertTime}>2 min ago</Text>
                  </View>
                ))}
              </View>

              <View style={styles.mapPanel}>
                <View style={styles.panelHeader}>
                  <Text style={styles.panelTitle}>Zone Overview</Text>
                  <Text style={styles.panelLink}>View Full Map</Text>
                </View>
                <View style={styles.mapPreview}>
                  <View style={styles.mapGlowA} />
                  <View style={styles.mapGlowB} />
                  <View style={styles.mapMarkerGreen}>
                    <Text style={styles.mapMarkerValue}>47</Text>
                  </View>
                  <View style={styles.mapMarkerOrange}>
                    <Text style={styles.mapMarkerValue}>16</Text>
                  </View>
                  <View style={styles.mapMarkerRed}>
                    <Text style={styles.mapMarkerValue}>3</Text>
                  </View>
                </View>
              </View>
            </View>

            <View style={styles.quickPanel}>
              <View style={styles.panelHeader}>
                <Text style={styles.panelTitle}>Quick Actions</Text>
              </View>
              <View style={styles.quickRow}>
                {quickActions.map((action) => {
                  const Icon = action.icon;
                  return (
                    <View key={action.title} style={styles.quickCard}>
                      <View style={styles.quickIcon}>
                        <Icon size={16} color="#0f172a" />
                      </View>
                      <Text style={styles.quickTitle}>{action.title}</Text>
                    </View>
                  );
                })}
              </View>
            </View>
          </View>

          <View style={styles.sidePanel}>
            <View style={styles.sideHeader}>
              <Text style={styles.sideHeaderTitle}>Alerts</Text>
              <Text style={styles.sideHeaderSub}>SOS</Text>
            </View>
            <View style={styles.sideList}>
              {alertRows.map(([severity, title, zone]) => (
                <View key={`${title}-${zone}`} style={styles.sideAlert}>
                  <Text style={[styles.sideSeverity, severity === 'Critical' ? styles.critical : styles.high]}>
                    {severity}
                  </Text>
                  <Text style={styles.sideTitle}>{title}</Text>
                  <Text style={styles.sideZone}>{zone}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#f4f6fb',
  },
  content: {
    padding: 18,
  },
  page: {
    maxWidth: 1520,
    alignSelf: 'center',
    width: '100%',
    gap: 18,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  brandMark: {
    width: 42,
    height: 42,
    borderRadius: 13,
    backgroundColor: '#f97316',
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
  },
  brandSubtitle: {
    fontSize: 12,
    color: '#64748b',
  },
  headerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#dbe3ef',
  },
  headerButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a',
  },
  heroCard: {
    backgroundColor: '#ffffff',
    borderRadius: 28,
    padding: 28,
    borderWidth: 1,
    borderColor: '#dbe3ef',
    flexDirection: 'row',
    gap: 20,
    alignItems: 'stretch',
  },
  heroText: {
    flex: 1,
  },
  heroKicker: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.1,
    color: '#1e40af',
    textTransform: 'uppercase',
  },
  heroTitle: {
    marginTop: 10,
    fontSize: 32,
    lineHeight: 40,
    fontWeight: '800',
    color: '#0f172a',
    maxWidth: 760,
  },
  heroBody: {
    marginTop: 12,
    fontSize: 15,
    lineHeight: 23,
    color: '#5b6474',
    maxWidth: 760,
  },
  heroButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
    flexWrap: 'wrap',
  },
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 14,
  },
  primaryBlue: {
    backgroundColor: '#1e40af',
  },
  primaryDark: {
    backgroundColor: '#0f274d',
  },
  primaryButtonText: {
    fontSize: 13,
    fontWeight: '800',
    color: '#ffffff',
  },
  heroBadge: {
    width: 340,
    borderRadius: 24,
    padding: 22,
    backgroundColor: '#f8fbff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    justifyContent: 'center',
  },
  heroBadgeTitle: {
    marginTop: 12,
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
  },
  heroBadgeLine: {
    marginTop: 7,
    fontSize: 13,
    color: '#475569',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    paddingTop: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: 0.3,
  },
  sectionSubtitle: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  clientGrid: {
    flexDirection: 'row',
    gap: 16,
    flexWrap: 'wrap',
  },
  clientGridCompact: {
    justifyContent: 'center',
  },
  phoneFrame: {
    width: 200,
    minHeight: 410,
    borderRadius: 26,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#cfd8e6',
    padding: 12,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 12 },
    elevation: 4,
  },
  phoneStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  phoneTime: {
    fontSize: 9,
    fontWeight: '700',
    color: '#0f172a',
  },
  phoneTop: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 68,
    marginTop: 8,
  },
  phoneTitle: {
    textAlign: 'center',
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
  },
  phoneNote: {
    textAlign: 'center',
    fontSize: 10,
    color: '#64748b',
    marginTop: 4,
  },
  phoneArt: {
    marginTop: 12,
    flex: 1,
    borderRadius: 18,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 10,
  },
  phoneCaption: {
    marginTop: 10,
    textAlign: 'center',
    fontSize: 11,
    fontWeight: '700',
    color: '#0f172a',
  },
  splashArt: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: 8,
  },
  mountainA: {
    position: 'absolute',
    bottom: 34,
    width: 120,
    height: 48,
    borderTopLeftRadius: 90,
    borderTopRightRadius: 90,
    backgroundColor: 'rgba(148, 163, 184, 0.16)',
  },
  mountainB: {
    position: 'absolute',
    bottom: 22,
    left: 16,
    width: 60,
    height: 32,
    borderTopLeftRadius: 40,
    borderTopRightRadius: 40,
    backgroundColor: 'rgba(148, 163, 184, 0.24)',
  },
  mountainC: {
    position: 'absolute',
    bottom: 22,
    right: 16,
    width: 60,
    height: 32,
    borderTopLeftRadius: 40,
    borderTopRightRadius: 40,
    backgroundColor: 'rgba(148, 163, 184, 0.24)',
  },
  pathLine: {
    position: 'absolute',
    bottom: 20,
    width: 64,
    height: 2,
    backgroundColor: 'rgba(15, 23, 42, 0.12)',
  },
  dashboardArt: {
    width: '100%',
    gap: 10,
  },
  statusCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusLabel: {
    fontSize: 9,
    color: '#64748b',
  },
  statusValue: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0f172a',
  },
  gridRow: {
    flexDirection: 'row',
    gap: 8,
  },
  gridTile: {
    flex: 1,
    borderRadius: 12,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 10,
    gap: 6,
    alignItems: 'center',
  },
  gridText: {
    fontSize: 9,
    color: '#334155',
    fontWeight: '700',
    textAlign: 'center',
  },
  mapArt: {
    width: '100%',
    height: 220,
    borderRadius: 16,
    backgroundColor: '#0b1120',
    position: 'relative',
  },
  routeLine: {
    position: 'absolute',
    left: 26,
    top: 48,
    width: 120,
    height: 2,
    backgroundColor: '#94a3b8',
    transform: [{ rotate: '-36deg' }],
  },
  routePin: {
    position: 'absolute',
    left: 68,
    top: 84,
    width: 16,
    height: 16,
    borderRadius: 999,
    backgroundColor: '#1e40af',
    borderWidth: 3,
    borderColor: '#e2e8f0',
  },
  routeEnd: {
    position: 'absolute',
    right: 24,
    bottom: 22,
    width: 18,
    height: 18,
    borderRadius: 999,
    backgroundColor: '#f97316',
    borderWidth: 3,
    borderColor: '#fde68a',
  },
  sosArt: {
    width: '100%',
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#475569',
    borderRadius: 18,
  },
  sosRing: {
    width: 88,
    height: 88,
    borderRadius: 999,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 12,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  sosText: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
  },
  idArt: {
    width: '100%',
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  qrBox: {
    width: 104,
    height: 104,
    borderRadius: 16,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    padding: 12,
  },
  qrGrid: {
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 3,
    alignContent: 'flex-start',
  },
  qrCell: {
    width: 12,
    height: 12,
    borderRadius: 2,
    backgroundColor: '#dbe3ef',
  },
  qrCellFilled: {
    backgroundColor: '#0f172a',
  },
  profileArt: {
    width: '100%',
    alignItems: 'center',
    gap: 12,
  },
  avatarCircle: {
    width: 54,
    height: 54,
    borderRadius: 999,
    backgroundColor: '#cbd5e1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarLetter: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0f172a',
  },
  profileLine: {
    width: '78%',
    height: 12,
    borderRadius: 999,
    backgroundColor: '#e2e8f0',
  },
  profileLineShort: {
    width: '56%',
    height: 10,
    borderRadius: 999,
    backgroundColor: '#e2e8f0',
  },
  toggleLine: {
    width: '88%',
    height: 78,
    borderRadius: 16,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  alertArt: {
    width: '100%',
    gap: 8,
  },
  alertChip: {
    paddingVertical: 9,
    borderRadius: 12,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    alignItems: 'center',
  },
  alertChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
  },
  authorityLayout: {
    flexDirection: 'row',
    gap: 16,
    alignItems: 'stretch',
  },
  authorityLayoutCompact: {
    flexDirection: 'column',
  },
  loginCard: {
    width: 240,
    borderRadius: 22,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 18,
    alignItems: 'center',
  },
  loginLogo: {
    width: 78,
    height: 78,
    borderRadius: 22,
    backgroundColor: '#eff6ff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loginTitle: {
    marginTop: 14,
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
  },
  loginSubtitle: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 14,
  },
  loginFields: {
    width: '100%',
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#64748b',
    marginBottom: 6,
  },
  fakeInput: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#dbe3ef',
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
  },
  fakeInputText: {
    fontSize: 12,
    color: '#334155',
  },
  loginButton: {
    borderRadius: 8,
    backgroundColor: '#475569',
    paddingVertical: 12,
    alignItems: 'center',
  },
  loginButtonText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '800',
  },
  loginFoot: {
    marginTop: 10,
    fontSize: 11,
    textAlign: 'center',
    color: '#94a3b8',
  },
  dashboardCard: {
    flex: 1,
    borderRadius: 22,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 18,
  },
  dashboardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  dashboardTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0f172a',
  },
  dashboardSubtitle: {
    fontSize: 12,
    color: '#64748b',
  },
  livePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  liveDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: '#16a34a',
  },
  liveText: {
    fontSize: 12,
    fontWeight: '800',
    color: '#16a34a',
  },
  clockText: {
    marginLeft: 4,
    fontSize: 11,
    color: '#64748b',
  },
  metricRow: {
    flexDirection: 'row',
    gap: 12,
    flexWrap: 'wrap',
  },
  metricCard: {
    flex: 1,
    minWidth: 160,
    borderRadius: 16,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 14,
    gap: 4,
  },
  metricIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 2,
  },
  metricLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#64748b',
    textTransform: 'uppercase',
  },
  metricValue: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0f172a',
  },
  dashboardBottom: {
    marginTop: 12,
    flexDirection: 'row',
    gap: 12,
  },
  alertPanel: {
    flex: 1.2,
    borderRadius: 16,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 14,
  },
  mapPanel: {
    flex: 1,
    borderRadius: 16,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 14,
  },
  panelHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  panelTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#0f172a',
  },
  panelLink: {
    fontSize: 11,
    color: '#0f766e',
    fontWeight: '700',
  },
  alertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    gap: 10,
  },
  severityBadge: {
    minWidth: 62,
    textAlign: 'center',
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    color: '#fff',
    fontSize: 11,
    fontWeight: '800',
  },
  critical: {
    backgroundColor: '#dc2626',
  },
  high: {
    backgroundColor: '#f97316',
  },
  alertTextCol: {
    flex: 1,
  },
  alertTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
  },
  alertZone: {
    marginTop: 2,
    fontSize: 11,
    color: '#64748b',
  },
  alertTime: {
    fontSize: 10,
    color: '#94a3b8',
  },
  mapPreview: {
    flex: 1,
    minHeight: 240,
    borderRadius: 16,
    backgroundColor: '#e5e7eb',
    position: 'relative',
    overflow: 'hidden',
  },
  mapGlowA: {
    position: 'absolute',
    top: 26,
    left: 24,
    width: 72,
    height: 72,
    borderRadius: 999,
    backgroundColor: 'rgba(34, 197, 94, 0.26)',
  },
  mapGlowB: {
    position: 'absolute',
    top: 100,
    right: 54,
    width: 84,
    height: 84,
    borderRadius: 999,
    backgroundColor: 'rgba(249, 115, 22, 0.25)',
  },
  mapMarkerGreen: {
    position: 'absolute',
    left: 30,
    top: 38,
    width: 54,
    height: 54,
    borderRadius: 999,
    backgroundColor: '#16a34a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapMarkerOrange: {
    position: 'absolute',
    right: 58,
    top: 112,
    width: 54,
    height: 54,
    borderRadius: 999,
    backgroundColor: '#f59e0b',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapMarkerRed: {
    position: 'absolute',
    left: 100,
    bottom: 48,
    width: 48,
    height: 48,
    borderRadius: 999,
    backgroundColor: '#dc2626',
    alignItems: 'center',
    justifyContent: 'center',
  },
  mapMarkerValue: {
    fontSize: 13,
    color: '#fff',
    fontWeight: '800',
  },
  quickPanel: {
    marginTop: 12,
    borderRadius: 16,
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    padding: 14,
  },
  quickRow: {
    flexDirection: 'row',
    gap: 10,
    flexWrap: 'wrap',
  },
  quickCard: {
    flex: 1,
    minWidth: 130,
    borderRadius: 14,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 12,
    alignItems: 'center',
    gap: 8,
  },
  quickIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0f172a',
    textAlign: 'center',
  },
  sidePanel: {
    width: 280,
    borderRadius: 22,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#dbe3ef',
    padding: 16,
  },
  sideHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  sideHeaderTitle: {
    fontSize: 14,
    fontWeight: '800',
    color: '#0f172a',
  },
  sideHeaderSub: {
    fontSize: 14,
    fontWeight: '800',
    color: '#1e40af',
  },
  sideList: {
    gap: 10,
  },
  sideAlert: {
    borderRadius: 14,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    backgroundColor: '#f8fafc',
  },
  sideSeverity: {
    alignSelf: 'flex-start',
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 4,
    marginBottom: 8,
  },
  sideTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0f172a',
  },
  sideZone: {
    marginTop: 4,
    fontSize: 11,
    color: '#64748b',
  },
});
