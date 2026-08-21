import { useMemo, useState } from 'react';
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
import { Mail, Lock, ArrowRight, ShieldAlert, User, Info, Shield, Sparkles } from 'lucide-react-native';
import Toast from 'react-native-toast-message';

type Tab = 'tourist' | 'authority';

const ADMIN_ACCOUNTS = [
  { email: 'admin@toursafe.com', label: 'TourSafe Admin' },
  { email: 'admin@tnpol.gov.in', label: 'TN Police' },
];

export default function LoginPage() {
  const router = useRouter();
  const params = useLocalSearchParams<{ role?: string }>();
  const { width } = useWindowDimensions();
  const isCompact = width < 900;
  const initialTab = params.role === 'tourist' ? 'tourist' : 'authority';

  const [tab, setTab] = useState<Tab>(initialTab);
  const [email, setEmail] = useState(initialTab === 'authority' ? ADMIN_ACCOUNTS[0].email : '');
  const [password, setPassword] = useState(initialTab === 'authority' ? 'admin@123' : '');
  const [loading, setLoading] = useState(false);
  const [otpMode, setOtpMode] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [googleLoading, setGoogleLoading] = useState(false);

  const demoCopy = useMemo(
    () => [
      'Frontend-only prototype',
      'Mock credentials enabled',
      'Authority and client access',
    ],
    []
  );

  function resetMode(nextTab: Tab) {
    setTab(nextTab);
    setOtpMode(false);
    setOtpCode('');
    setEmail(nextTab === 'authority' ? ADMIN_ACCOUNTS[0].email : '');
    setPassword(nextTab === 'authority' ? 'admin@123' : '');
  }

  async function handleGoogleLogin() {
    setGoogleLoading(true);
    Toast.show({
      type: 'info',
      text1: 'Google Sign-in',
      text2: 'This MVP keeps Google sign-in as a visual placeholder for now.',
    });
    setGoogleLoading(false);
  }

  async function handleLogin() {
    setLoading(true);
    try {
      if (tab === 'tourist' && otpMode) {
        // Use backend API for OTP-based tourist login
        const otpEmail = email || 'guest@toursafe.local';
        const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: otpEmail, password: otpCode || '000000' }),
        });
        if (!response.ok) throw new Error('Invalid OTP or credentials');
        const data = await response.json();
        const role = data.user.role;
        router.replace(role === 'tourist' ? '/tourist/(tabs)/dashboard' : '/admin/(tabs)/dashboard');
        return;
      }

      if (tab === 'tourist' && !otpMode) {
        const otpEmail = email || 'guest@toursafe.local';
        const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: otpEmail, password: '000000' }),
        });
        if (!response.ok) throw new Error('OTP send failed');
        setEmail(otpEmail);
        setOtpMode(true);
        Toast.show({
          type: 'success',
          text1: 'OTP Ready',
          text2: 'Enter any 6-digit code for the demo flow.',
        });
        return;
      }

      const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email || ADMIN_ACCOUNTS[0].email, password: password || 'admin@123' }),
      });
      if (!response.ok) throw new Error('Invalid credentials');

      const data = await response.json();
      const role = data.user.role;
      router.replace(role === 'tourist' ? '/tourist/(tabs)/dashboard' : '/admin/(tabs)/dashboard');
    } catch (err: unknown) {
      Toast.show({
        type: 'error',
        text1: 'Login failed',
        text2: err instanceof Error ? err.message : 'Authentication failed',
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={[styles.card, isCompact && styles.cardCompact]}>
        <View style={[styles.leftPane, isCompact && styles.leftPaneCompact]}>
          <View style={styles.logoRow}>
            <View style={styles.logo}>
              <Shield size={24} color="#ffffff" />
            </View>
            <View>
              <Text style={styles.brand}>TourSafe</Text>
              <Text style={styles.brandSub}>Command-ready travel safety</Text>
            </View>
          </View>

          <Text style={styles.heroTitle}>Secure entry for client and authority dashboards.</Text>
          <Text style={styles.heroBody}>
            This is the MVP login layer for the frontend-only TourSafe prototype. Use the tabs to switch between
            client and authority access.
          </Text>

          <View style={styles.demoBox}>
            <View style={styles.demoHeader}>
              <Info size={16} color="#1e40af" />
              <Text style={styles.demoTitle}>Demo login credentials</Text>
            </View>
            {tab === 'authority' ? (
              <>
                {ADMIN_ACCOUNTS.map((account) => (
                  <TouchableOpacity
                    key={account.email}
                    onPress={() => {
                      setEmail(account.email);
                      setPassword('admin@123');
                    }}
                    style={styles.demoRow}
                    activeOpacity={0.85}
                  >
                    <Text style={styles.demoEmail}>{account.email}</Text>
                    <Text style={styles.demoLabel}>{account.label}</Text>
                  </TouchableOpacity>
                ))}
                <Text style={styles.demoPassword}>Password: admin@123</Text>
              </>
            ) : (
              <>
                <Text style={styles.demoPassword}>Client login is OTP-based for the prototype.</Text>
                <Text style={styles.demoPassword}>Enter any email address to continue the demo flow.</Text>
              </>
            )}
          </View>

          <View style={styles.pills}>
            {demoCopy.map((item) => (
              <View key={item} style={styles.pill}>
                <Text style={styles.pillText}>{item}</Text>
              </View>
            ))}
          </View>
        </View>

        <View style={[styles.rightPane, isCompact && styles.rightPaneCompact]}>
          <View style={styles.tabBar}>
            <TouchableOpacity
              onPress={() => resetMode('authority')}
              style={[styles.tab, tab === 'authority' && styles.tabActiveAuthority]}
              activeOpacity={0.9}
            >
              <ShieldAlert size={16} color={tab === 'authority' ? '#1e40af' : '#64748b'} />
              <Text style={[styles.tabText, tab === 'authority' && styles.tabTextActive]}>Authority Login</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => resetMode('tourist')}
              style={[styles.tab, tab === 'tourist' && styles.tabActiveTourist]}
              activeOpacity={0.9}
            >
              <User size={16} color={tab === 'tourist' ? '#0d9488' : '#64748b'} />
              <Text style={[styles.tabText, tab === 'tourist' && styles.tabTextActive]}>Client Login</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.form}>
            <Text style={styles.formTitle}>{tab === 'authority' ? 'Authority Portal' : 'Tourist Access'}</Text>
            <Text style={styles.formSubtitle}>
              {tab === 'authority'
                ? 'Sign in to the command dashboard.'
                : otpMode
                ? 'Enter the OTP for the demo client flow.'
                : 'Enter your email to receive the demo OTP.'}
            </Text>

            {!otpMode && (
              <View style={styles.inputBlock}>
                <Text style={styles.label}>Email Address</Text>
                <View style={styles.inputWrapper}>
                  <Mail size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={email}
                    onChangeText={setEmail}
                    placeholder={tab === 'authority' ? 'admin@toursafe.com' : 'your@email.com'}
                    placeholderTextColor="#94a3b8"
                    autoCapitalize="none"
                    keyboardType="email-address"
                  />
                </View>
              </View>
            )}

            {tab === 'authority' && !otpMode && (
              <View style={styles.inputBlock}>
                <Text style={styles.label}>Password</Text>
                <View style={styles.inputWrapper}>
                  <Lock size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={password}
                    onChangeText={setPassword}
                    placeholder="••••••••"
                    placeholderTextColor="#94a3b8"
                    secureTextEntry
                  />
                </View>
              </View>
            )}

            {tab === 'tourist' && otpMode && (
              <View style={styles.inputBlock}>
                <Text style={styles.label}>One-Time Password</Text>
                <TextInput
                  style={[styles.input, styles.otpInput]}
                  value={otpCode}
                  onChangeText={setOtpCode}
                  placeholder="6-digit code"
                  placeholderTextColor="#94a3b8"
                  maxLength={6}
                  keyboardType="number-pad"
                  textAlign="center"
                />
                <TouchableOpacity onPress={() => setOtpMode(false)}>
                  <Text style={styles.changeEmail}>Change email</Text>
                </TouchableOpacity>
              </View>
            )}

            <TouchableOpacity
              onPress={handleLogin}
              disabled={loading}
              style={[styles.primaryButton, tab === 'authority' ? styles.primaryAuthority : styles.primaryTourist, loading && styles.disabled]}
              activeOpacity={0.9}
            >
              {loading ? (
                <ActivityIndicator color="#ffffff" size="small" />
              ) : (
                <>
                  <Text style={styles.primaryText}>{tab === 'tourist' && !otpMode ? 'Send OTP' : 'Sign In'}</Text>
                  <ArrowRight size={16} color="#ffffff" />
                </>
              )}
            </TouchableOpacity>

            {tab === 'tourist' && (
              <>
                <View style={styles.divider}>
                  <View style={styles.dividerLine} />
                  <Text style={styles.dividerText}>or</Text>
                  <View style={styles.dividerLine} />
                </View>
                <TouchableOpacity
                  onPress={handleGoogleLogin}
                  disabled={googleLoading}
                  style={[styles.secondaryButton, googleLoading && styles.disabled]}
                  activeOpacity={0.9}
                >
                  {googleLoading ? (
                    <ActivityIndicator color="#64748b" size="small" />
                  ) : (
                    <>
                      <Text style={styles.googleGlyph}>G</Text>
                      <Text style={styles.secondaryText}>Continue with Google</Text>
                    </>
                  )}
                </TouchableOpacity>
              </>
            )}

            <View style={styles.footerRow}>
              {tab === 'tourist' && !otpMode ? (
                <Text style={styles.footerText}>
                  New here?{' '}
                  <Text style={styles.footerLink} onPress={() => router.push('/auth/register')}>
                    Create client account
                  </Text>
                </Text>
              ) : (
                <Text style={styles.footerText}>
                  Need authority access?{' '}
                  <Text style={styles.footerLink} onPress={() => resetMode('authority')}>
                    Switch to authority login
                  </Text>
                </Text>
              )}
            </View>

            <View style={styles.secureFooter}>
              <Sparkles size={12} color="#94a3b8" />
              <Text style={styles.secureFooterText}>Secured by demo auth + Polygon DID placeholders</Text>
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
    backgroundColor: '#081a33',
  },
  content: {
    padding: 18,
    minHeight: '100%',
    justifyContent: 'center',
  },
  card: {
    maxWidth: 1160,
    width: '100%',
    alignSelf: 'center',
    borderRadius: 32,
    overflow: 'hidden',
    backgroundColor: '#ffffff',
    flexDirection: 'row',
    shadowColor: '#000',
    shadowOpacity: 0.22,
    shadowRadius: 28,
    shadowOffset: { width: 0, height: 16 },
    elevation: 12,
  },
  cardCompact: {
    flexDirection: 'column',
  },
  leftPane: {
    flex: 1,
    backgroundColor: '#0f274d',
    padding: 28,
    justifyContent: 'space-between',
  },
  leftPaneCompact: {
    minHeight: 360,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    marginBottom: 24,
  },
  logo: {
    width: 52,
    height: 52,
    borderRadius: 16,
    backgroundColor: '#ff7a18',
    alignItems: 'center',
    justifyContent: 'center',
  },
  brand: {
    fontSize: 22,
    fontWeight: '800',
    color: '#ffffff',
  },
  brandSub: {
    marginTop: 2,
    fontSize: 13,
    color: '#cbd5e1',
  },
  heroTitle: {
    fontSize: 32,
    lineHeight: 40,
    fontWeight: '800',
    color: '#ffffff',
    maxWidth: 430,
  },
  heroBody: {
    marginTop: 14,
    fontSize: 14,
    lineHeight: 22,
    color: '#cbd5e1',
    maxWidth: 460,
  },
  demoBox: {
    marginTop: 24,
    borderRadius: 24,
    padding: 18,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.12)',
  },
  demoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  demoTitle: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '800',
  },
  demoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 14,
    paddingVertical: 8,
  },
  demoEmail: {
    color: '#7dd3fc',
    fontSize: 13,
    fontFamily: 'monospace',
  },
  demoLabel: {
    color: '#cbd5e1',
    fontSize: 13,
  },
  demoPassword: {
    color: '#cbd5e1',
    fontSize: 13,
    marginTop: 6,
  },
  pills: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 18,
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: 'rgba(148, 163, 184, 0.12)',
  },
  pillText: {
    color: '#e2e8f0',
    fontSize: 12,
    fontWeight: '600',
  },
  rightPane: {
    flex: 1.05,
    backgroundColor: '#f8fafc',
  },
  rightPaneCompact: {
    minHeight: 520,
  },
  tabBar: {
    flexDirection: 'row',
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 16,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
    backgroundColor: '#ffffff',
  },
  tabActiveAuthority: {
    borderBottomColor: '#1e40af',
    backgroundColor: 'rgba(219, 234, 254, 0.55)',
  },
  tabActiveTourist: {
    borderBottomColor: '#0d9488',
    backgroundColor: 'rgba(204, 251, 241, 0.55)',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#64748b',
  },
  tabTextActive: {
    color: '#0f172a',
  },
  form: {
    padding: 28,
  },
  formTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#0f172a',
  },
  formSubtitle: {
    marginTop: 6,
    marginBottom: 18,
    fontSize: 14,
    color: '#64748b',
    lineHeight: 21,
  },
  inputBlock: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: '#475569',
    marginBottom: 6,
  },
  inputWrapper: {
    position: 'relative',
  },
  inputIcon: {
    position: 'absolute',
    left: 12,
    top: '50%',
    marginTop: -8,
  },
  input: {
    width: '100%',
    paddingLeft: 40,
    paddingRight: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 14,
    fontSize: 14,
    color: '#0f172a',
    backgroundColor: '#ffffff',
  },
  otpInput: {
    letterSpacing: 4,
    fontFamily: 'monospace',
    paddingLeft: 16,
    textAlign: 'center',
  },
  changeEmail: {
    marginTop: 8,
    fontSize: 12,
    fontWeight: '700',
    color: '#0d9488',
  },
  primaryButton: {
    marginTop: 6,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 13,
    borderRadius: 14,
  },
  primaryAuthority: {
    backgroundColor: '#1e40af',
  },
  primaryTourist: {
    backgroundColor: '#0d9488',
  },
  primaryText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#ffffff',
  },
  secondaryButton: {
    marginTop: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    paddingVertical: 13,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    backgroundColor: '#ffffff',
  },
  googleGlyph: {
    fontSize: 18,
    color: '#4285F4',
    fontWeight: '800',
  },
  secondaryText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#475569',
  },
  disabled: {
    opacity: 0.75,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 16,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#e2e8f0',
  },
  dividerText: {
    fontSize: 12,
    color: '#94a3b8',
    fontWeight: '600',
  },
  footerRow: {
    marginTop: 18,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#64748b',
  },
  footerLink: {
    color: '#0d9488',
    fontWeight: '700',
  },
  secureFooter: {
    marginTop: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  secureFooterText: {
    fontSize: 11,
    color: '#94a3b8',
  },
});
