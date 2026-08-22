import React, { useMemo, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  useWindowDimensions,
} from 'react-native';
import {
  Mail,
  Lock,
  ArrowRight,
  Shield,
  ShieldAlert,
  User,
  Users,
  Building2,
  CheckCircle2,
  FileCheck,
  Fingerprint,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { useAuthStore } from '@/store/authStore';

type RoleTab = 'authority' | 'responder' | 'tourist';

const PRESET_ACCOUNTS = {
  authority: [
    { email: 'admin@toursafe.com', label: 'Command Administrator' },
    { email: 'admin@tnpol.gov.in', label: 'State Police Command' },
  ],
  responder: [
    { email: 'unit1@tnpol.gov.in', label: 'Tactical Unit 1 (Patrol)' },
    { email: 'medic1@toursafe.in', label: 'Emergency Medical Unit' },
  ],
  tourist: [
    { email: 'priya.sharma@gmail.com', label: 'Verified Tourist Profile' },
    { email: 'tourist@toursafe.in', label: 'Standard Traveler Profile' },
  ],
};

export default function LoginPage() {
  const router = useRouter();
  const params = useLocalSearchParams<{ role?: string }>();
  const { width } = useWindowDimensions();
  const isCompact = width < 900;

  const initialTab: RoleTab =
    params.role === 'tourist'
      ? 'tourist'
      : params.role === 'responder'
      ? 'responder'
      : 'authority';

  const [tab, setTab] = useState<RoleTab>(initialTab);
  const [email, setEmail] = useState(PRESET_ACCOUNTS[initialTab][0].email);
  const [password, setPassword] = useState('admin@123');
  const [loading, setLoading] = useState(false);

  const { login } = useAuthStore();

  function selectTab(nextTab: RoleTab) {
    setTab(nextTab);
    setEmail(PRESET_ACCOUNTS[nextTab][0].email);
    setPassword('admin@123');
  }

  async function handleLogin() {
    if (!email || !password) {
      Toast.show({
        type: 'error',
        text1: 'Validation Error',
        text2: 'Please provide both email and password.',
      });
      return;
    }

    setLoading(true);
    try {
      const success = await login(email.trim(), password);
      if (success) {
        const user = useAuthStore.getState().user;
        const role = user?.role || tab;
        Toast.show({
          type: 'success',
          text1: 'Authentication Verified',
          text2: `Welcome, ${user?.full_name || user?.email || 'User'}`,
        });

        if (role === 'authority' || role === 'admin') {
          router.replace('/admin/(tabs)/dashboard');
        } else if (role === 'responder') {
          router.replace('/responder');
        } else {
          router.replace('/tourist/(tabs)/dashboard');
        }
      }
    } catch (err: unknown) {
      Toast.show({
        type: 'error',
        text1: 'Login Failed',
        text2: err instanceof Error ? err.message : 'Invalid credentials or connection error',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={[styles.card, isCompact && styles.cardCompact]}>
        {/* Left Side: Brand, Identity & Security Badges */}
        <View style={[styles.leftPane, isCompact && styles.leftPaneCompact]}>
          <View>
            <View style={styles.logoRow}>
              <View style={styles.logo}>
                <Shield size={26} color="#ffffff" />
              </View>
              <View>
                <Text style={styles.brand}>TourSafe</Text>
                <Text style={styles.brandSub}>Government Safety & Command Infrastructure</Text>
              </View>
            </View>

            <Text style={styles.heroTitle}>Authoritative Access to National Safety Network</Text>
            <Text style={styles.heroBody}>
              Encrypted gateway connecting emergency dispatch operators, tactical field units, and verified travelers.
              Protected under DPDP Act 2023 and zero-trust access control protocols.
            </Text>

            <View style={styles.credentialHelperBox}>
              <Text style={styles.helperTitle}>Quick Access Profiles</Text>
              <View style={styles.helperChips}>
                {PRESET_ACCOUNTS[tab].map((acc) => (
                  <TouchableOpacity
                    key={acc.email}
                    style={[styles.helperChip, email === acc.email && styles.helperChipActive]}
                    onPress={() => {
                      setEmail(acc.email);
                      setPassword('admin@123');
                    }}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.helperChipText, email === acc.email && styles.helperChipTextActive]}>
                      {acc.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </View>

          <View style={styles.securityFooter}>
            <View style={styles.securityItem}>
              <Lock size={14} color="#94A3B8" />
              <Text style={styles.securityText}>TLS 1.3 / AES-256 Bit Encryption</Text>
            </View>
            <View style={styles.securityItem}>
              <Fingerprint size={14} color="#94A3B8" />
              <Text style={styles.securityText}>Cryptographically Verified Sessions</Text>
            </View>
          </View>
        </View>

        {/* Right Side: Role Selector & Login Form */}
        <View style={[styles.rightPane, isCompact && styles.rightPaneCompact]}>
          {/* Tab Selector */}
          <View style={styles.tabBar}>
            <TouchableOpacity
              onPress={() => selectTab('authority')}
              style={[styles.tab, tab === 'authority' && styles.tabActiveAuthority]}
              activeOpacity={0.85}
              accessibilityRole="tab"
              accessibilityState={{ selected: tab === 'authority' }}
            >
              <Building2 size={16} color={tab === 'authority' ? '#1A3C6E' : '#64748B'} />
              <Text style={[styles.tabText, tab === 'authority' && styles.tabTextActiveAuthority]}>
                Authority
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => selectTab('responder')}
              style={[styles.tab, tab === 'responder' && styles.tabActiveResponder]}
              activeOpacity={0.85}
              accessibilityRole="tab"
              accessibilityState={{ selected: tab === 'responder' }}
            >
              <Users size={16} color={tab === 'responder' ? '#C2410C' : '#64748B'} />
              <Text style={[styles.tabText, tab === 'responder' && styles.tabTextActiveResponder]}>
                Responder
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => selectTab('tourist')}
              style={[styles.tab, tab === 'tourist' && styles.tabActiveTourist]}
              activeOpacity={0.85}
              accessibilityRole="tab"
              accessibilityState={{ selected: tab === 'tourist' }}
            >
              <User size={16} color={tab === 'tourist' ? '#046A38' : '#64748B'} />
              <Text style={[styles.tabText, tab === 'tourist' && styles.tabTextActiveTourist]}>
                Tourist
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.formContainer}>
            <Text style={styles.formTitle}>
              {tab === 'authority'
                ? 'Authority Command Login'
                : tab === 'responder'
                ? 'Field Responder Authentication'
                : 'Tourist Companion Sign In'}
            </Text>
            <Text style={styles.formSubtitle}>
              {tab === 'authority'
                ? 'Access central dispatch, safety zones, and AI intelligence.'
                : tab === 'responder'
                ? 'Access tactical mission queue and GPS routing.'
                : 'Access travel safety dashboard, SOS, and digital ID.'}
            </Text>

            <View style={styles.inputBlock}>
              <Text style={styles.label}>Email Address</Text>
              <View style={styles.inputWrapper}>
                <Mail size={16} color="#94A3B8" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={email}
                  onChangeText={setEmail}
                  placeholder="operator@toursafe.gov.in"
                  placeholderTextColor="#94A3B8"
                  autoCapitalize="none"
                  keyboardType="email-address"
                  accessibilityLabel="Email Address Input"
                />
              </View>
            </View>

            <View style={styles.inputBlock}>
              <Text style={styles.label}>Password / Access Key</Text>
              <View style={styles.inputWrapper}>
                <Lock size={16} color="#94A3B8" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  value={password}
                  onChangeText={setPassword}
                  placeholder="••••••••"
                  placeholderTextColor="#94A3B8"
                  secureTextEntry
                  accessibilityLabel="Password Input"
                />
              </View>
            </View>

            <TouchableOpacity
              onPress={handleLogin}
              disabled={loading}
              style={[
                styles.submitButton,
                tab === 'authority'
                  ? styles.submitAuthority
                  : tab === 'responder'
                  ? styles.submitResponder
                  : styles.submitTourist,
                loading && styles.submitDisabled,
              ]}
              activeOpacity={0.88}
              accessibilityRole="button"
              accessibilityLabel="Sign in to TourSafe"
            >
              {loading ? (
                <ActivityIndicator color="#ffffff" size="small" />
              ) : (
                <>
                  <Text style={styles.submitButtonText}>Authenticate & Enter</Text>
                  <ArrowRight size={16} color="#ffffff" />
                </>
              )}
            </TouchableOpacity>

            <View style={styles.registerRow}>
              <Text style={styles.registerPrompt}>Need a new registration? </Text>
              <TouchableOpacity onPress={() => router.push('/auth/register')}>
                <Text style={styles.registerLink}>Register Authority Profile</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.homeReturnRow}>
              <TouchableOpacity onPress={() => router.replace('/')}>
                <Text style={styles.homeReturnText}>← Back to TourSafe Portal</Text>
              </TouchableOpacity>
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
    backgroundColor: '#0B132B',
  },
  content: {
    padding: 20,
    minHeight: '100%',
    justifyContent: 'center',
  },
  card: {
    maxWidth: 1100,
    width: '100%',
    alignSelf: 'center',
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: '#ffffff',
    flexDirection: 'row',
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 16 },
    elevation: 14,
  },
  cardCompact: {
    flexDirection: 'column',
  },
  leftPane: {
    flex: 1,
    backgroundColor: '#1C2541',
    padding: 36,
    justifyContent: 'space-between',
  },
  leftPaneCompact: {
    padding: 24,
    minHeight: 280,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginBottom: 28,
  },
  logo: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#1A3C6E',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  brand: {
    fontSize: 22,
    fontWeight: '800',
    color: '#ffffff',
    letterSpacing: -0.4,
  },
  brandSub: {
    marginTop: 2,
    fontSize: 12,
    color: '#94A3B8',
  },
  heroTitle: {
    fontSize: 26,
    lineHeight: 34,
    fontWeight: '800',
    color: '#ffffff',
    letterSpacing: -0.4,
    marginBottom: 12,
  },
  heroBody: {
    fontSize: 13,
    lineHeight: 20,
    color: '#CBD5E1',
    marginBottom: 24,
  },
  credentialHelperBox: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 14,
    padding: 14,
    marginBottom: 20,
  },
  helperTitle: {
    fontSize: 11,
    fontWeight: '700',
    color: '#94A3B8',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 10,
  },
  helperChips: {
    gap: 8,
  },
  helperChip: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.12)',
  },
  helperChipActive: {
    backgroundColor: '#1A3C6E',
    borderColor: '#3B82F6',
  },
  helperChipText: {
    fontSize: 12,
    color: '#CBD5E1',
  },
  helperChipTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  securityFooter: {
    gap: 8,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  securityItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  securityText: {
    fontSize: 11,
    color: '#94A3B8',
  },
  rightPane: {
    flex: 1.1,
    backgroundColor: '#ffffff',
    padding: 36,
  },
  rightPaneCompact: {
    padding: 24,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#F1F5F9',
    borderRadius: 12,
    padding: 4,
    marginBottom: 28,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 8,
  },
  tabActiveAuthority: {
    backgroundColor: '#ffffff',
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  tabActiveResponder: {
    backgroundColor: '#ffffff',
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  tabActiveTourist: {
    backgroundColor: '#ffffff',
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 3,
    shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
  },
  tabTextActiveAuthority: {
    color: '#1A3C6E',
    fontWeight: '700',
  },
  tabTextActiveResponder: {
    color: '#C2410C',
    fontWeight: '700',
  },
  tabTextActiveTourist: {
    color: '#046A38',
    fontWeight: '700',
  },
  formContainer: {
    gap: 16,
  },
  formTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0F172A',
    letterSpacing: -0.3,
  },
  formSubtitle: {
    fontSize: 13,
    color: '#64748B',
    marginBottom: 8,
  },
  inputBlock: {
    gap: 6,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#334155',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: '#CBD5E1',
    borderRadius: 10,
    paddingHorizontal: 12,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    paddingVertical: 11,
    fontSize: 14,
    color: '#0F172A',
  },
  submitButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 13,
    borderRadius: 10,
    marginTop: 8,
  },
  submitAuthority: {
    backgroundColor: '#1A3C6E',
  },
  submitResponder: {
    backgroundColor: '#FF6B00',
  },
  submitTourist: {
    backgroundColor: '#046A38',
  },
  submitDisabled: {
    opacity: 0.65,
  },
  submitButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  registerRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
  },
  registerPrompt: {
    fontSize: 12,
    color: '#64748B',
  },
  registerLink: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1A3C6E',
  },
  homeReturnRow: {
    alignItems: 'center',
    marginTop: 6,
  },
  homeReturnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
  },
});
