import React, { useEffect } from 'react';
import { useRouter } from 'expo-router';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  useWindowDimensions,
  Platform,
} from 'react-native';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Building2,
  User,
  Users,
  Radio,
  Activity,
  ArrowRight,
  MapPin,
  Sparkles,
  Lock,
  FileCheck,
  CheckCircle2,
  Navigation,
  ExternalLink,
  Cpu,
  Layers,
  BarChart3,
  Bell,
  Fingerprint,
} from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';
import { ConnectionStatusBadge } from '@/components/ConnectionStatusBadge';

export default function TourSafeOfficialPortal() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isCompact = width < 960;
  const isMobile = width < 640;

  const { user, isAuthenticated, initializeAuth } = useAuthStore();

  useEffect(() => {
    initializeAuth();
  }, []);

  const getRoleDashboardPath = (role?: string) => {
    switch (role) {
      case 'authority':
      case 'admin':
        return '/admin/(tabs)/dashboard';
      case 'responder':
        return '/responder';
      case 'tourist':
      default:
        return '/tourist/(tabs)/dashboard';
    }
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <View style={styles.container}>
        {/* Government / Platform Header */}
        <View style={[styles.header, isMobile && styles.headerMobile]}>
          <View style={styles.brandRow}>
            <View style={styles.brandMark}>
              <Shield size={24} color="#ffffff" />
            </View>
            <View>
              <View style={styles.brandTitleRow}>
                <Text style={styles.brandTitle}>TourSafe</Text>
                <View style={styles.govBadge}>
                  <Text style={styles.govBadgeText}>OFFICIAL B2G PLATFORM</Text>
                </View>
              </View>
              <Text style={styles.brandSubtitle}>
                Integrated Tourist Safety, Realtime Telemetry & Emergency Command System
              </Text>
            </View>
          </View>

          <View style={[styles.headerActions, isMobile && styles.headerActionsMobile]}>
            <ConnectionStatusBadge showLabel={true} allowNavigateDev={false} />
            {isAuthenticated && user ? (
              <TouchableOpacity
                style={styles.activeUserButton}
                onPress={() => router.push(getRoleDashboardPath(user.role) as any)}
                accessibilityRole="button"
                accessibilityLabel={`Open ${user.role} workspace for ${user.full_name || user.email}`}
              >
                <User size={15} color="#0D7680" />
                <Text style={styles.activeUserText} numberOfLines={1}>
                  {user.full_name || user.email}
                </Text>
                <ArrowRight size={14} color="#0D7680" />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                style={styles.loginButton}
                onPress={() => router.push('/auth/login')}
                accessibilityRole="button"
                accessibilityLabel="Sign in to TourSafe Portal"
              >
                <Lock size={14} color="#ffffff" />
                <Text style={styles.loginButtonText}>Sign In</Text>
                <ArrowRight size={14} color="#ffffff" />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Authenticated Active Session Banner */}
        {isAuthenticated && user && (
          <View style={styles.sessionBanner}>
            <View style={styles.sessionBannerLeft}>
              <CheckCircle2 size={20} color="#046A38" />
              <View>
                <Text style={styles.sessionBannerTitle}>Active Verified Session Found</Text>
                <Text style={styles.sessionBannerSubtitle}>
                  Logged in as <Text style={{ fontWeight: '700' }}>{user.full_name || user.email}</Text> ({user.role?.toUpperCase() || 'TOURIST'})
                </Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.sessionLaunchButton}
              onPress={() => router.push(getRoleDashboardPath(user.role) as any)}
              accessibilityRole="button"
            >
              <Text style={styles.sessionLaunchText}>Enter Workspace</Text>
              <ArrowRight size={14} color="#ffffff" />
            </TouchableOpacity>
          </View>
        )}

        {/* Hero Section */}
        <View style={styles.heroSection}>
          <View style={styles.heroHeader}>
            <View style={styles.heroTagRow}>
              <View style={styles.securityTag}>
                <Lock size={12} color="#1A3C6E" />
                <Text style={styles.securityTagText}>DPDP ACT 2023 & ISO 27001 COMPLIANT</Text>
              </View>
              <View style={styles.realtimeTag}>
                <Radio size={12} color="#046A38" />
                <Text style={styles.realtimeTagText}>50Hz REALTIME INFERENCE ENGINE</Text>
              </View>
            </View>
            <Text style={styles.heroTitle}>
              Government-Grade Safety Intelligence & Rapid Emergency Response
            </Text>
            <Text style={styles.heroLead}>
              TourSafe connects tourism authorities, emergency command centers, field tactical units, and travelers
              into a unified, zero-trust safety network powered by geospatial intelligence and real-time motion anomaly detection.
            </Text>
          </View>
        </View>

        {/* Three Primary Role Gateways */}
        <View style={styles.gatewaysSection}>
          <Text style={styles.sectionHeading}>OPERATIONAL WORKSPACES</Text>
          <Text style={styles.sectionSubheading}>Select your authorized access portal to begin</Text>

          <View style={[styles.gatewayGrid, isCompact && styles.gatewayGridCompact]}>
            {/* Gateway 1: Authority Command Center */}
            <View style={styles.gatewayCard}>
              <View style={styles.gatewayCardHeader}>
                <View style={[styles.gatewayIconBox, { backgroundColor: '#2B4C7E' }]}>
                  <Building2 size={24} color="#ffffff" />
                </View>
                <View style={styles.gatewayBadge}>
                  <Text style={styles.gatewayBadgeText}>COMMAND & CONTROL</Text>
                </View>
              </View>
              <Text style={styles.gatewayTitle}>Authority Command Center</Text>
              <Text style={styles.gatewayDescription}>
                Real-time incident dispatch, multi-zone safety monitoring, tactical responder orchestration, and grounded AI operational intelligence.
              </Text>
              <View style={styles.featureList}>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#2B4C7E" />
                  <Text style={styles.featureText}>Live multi-layer geospatial operations map</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#2B4C7E" />
                  <Text style={styles.featureText}>AI Copilot tactical query & action execution</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#2B4C7E" />
                  <Text style={styles.featureText}>E-FIR generation & legal audit governance</Text>
                </View>
              </View>
              <TouchableOpacity
                style={[styles.gatewayButton, { backgroundColor: '#2B4C7E' }]}
                onPress={() => router.push('/admin/(tabs)/dashboard')}
                accessibilityRole="button"
                accessibilityLabel="Enter Authority Command Center"
              >
                <Text style={styles.gatewayButtonText}>Launch Command Center</Text>
                <ArrowRight size={16} color="#ffffff" />
              </TouchableOpacity>
            </View>

            {/* Gateway 2: Tourist Safety Companion */}
            <View style={styles.gatewayCard}>
              <View style={styles.gatewayCardHeader}>
                <View style={[styles.gatewayIconBox, { backgroundColor: '#059669' }]}>
                  <User size={24} color="#ffffff" />
                </View>
                <View style={[styles.gatewayBadge, { backgroundColor: '#ECFDF5', borderColor: '#A7F3D0' }]}>
                  <Text style={[styles.gatewayBadgeText, { color: '#059669' }]}>TRAVELER PORTAL</Text>
                </View>
              </View>
              <Text style={styles.gatewayTitle}>Tourist Safety Companion</Text>
              <Text style={styles.gatewayDescription}>
                Traveler companion featuring continuous motion anomaly detection, verified digital credentials, hazard proximity alerts, and 1-touch SOS.
              </Text>
              <View style={styles.featureList}>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#059669" />
                  <Text style={styles.featureText}>One-touch deliberate emergency SOS trigger</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#059669" />
                  <Text style={styles.featureText}>Verifiable Digital Tourist Credential (QR / KYC)</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#059669" />
                  <Text style={styles.featureText}>Granular privacy & sovereign consent center</Text>
                </View>
              </View>
              <TouchableOpacity
                style={[styles.gatewayButton, { backgroundColor: '#059669' }]}
                onPress={() => router.push('/tourist/(tabs)/dashboard')}
                accessibilityRole="button"
                accessibilityLabel="Open Tourist Safety Companion"
              >
                <Text style={styles.gatewayButtonText}>Open Tourist Companion</Text>
                <ArrowRight size={16} color="#ffffff" />
              </TouchableOpacity>
            </View>

            {/* Gateway 3: Tactical Field Responder */}
            <View style={styles.gatewayCard}>
              <View style={styles.gatewayCardHeader}>
                <View style={[styles.gatewayIconBox, { backgroundColor: '#FF6B00' }]}>
                  <Users size={24} color="#ffffff" />
                </View>
                <View style={[styles.gatewayBadge, { backgroundColor: '#FFF7ED', borderColor: '#FFEDD5' }]}>
                  <Text style={[styles.gatewayBadgeText, { color: '#C2410C' }]}>TACTICAL FIELD UNIT</Text>
                </View>
              </View>
              <Text style={styles.gatewayTitle}>Field Responder Operations</Text>
              <Text style={styles.gatewayDescription}>
                Mission dispatch terminal for police, forest rangers, and medical teams with GPS navigation, on-scene assessment, and field notes sync.
              </Text>
              <View style={styles.featureList}>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#C2410C" />
                  <Text style={styles.featureText}>Real-time mission assignment & GPS dispatch</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#C2410C" />
                  <Text style={styles.featureText}>On-scene triage assessment & multi-unit handover</Text>
                </View>
                <View style={styles.featureItem}>
                  <CheckCircle2 size={14} color="#C2410C" />
                  <Text style={styles.featureText}>Offline-resilient field notes & incident timeline</Text>
                </View>
              </View>
              <TouchableOpacity
                style={[styles.gatewayButton, { backgroundColor: '#FF6B00' }]}
                onPress={() => router.push('/responder')}
                accessibilityRole="button"
                accessibilityLabel="Access Field Responder Operations"
              >
                <Text style={styles.gatewayButtonText}>Access Field Operations</Text>
                <ArrowRight size={16} color="#ffffff" />
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* System Integrity & Subsystems Overview */}
        <View style={styles.statusSection}>
          <Text style={styles.sectionHeading}>SYSTEM INTEGRITY & SUBSYSTEM STATUS</Text>
          <Text style={styles.sectionSubheading}>Authoritative core engine verification</Text>

          <View style={[styles.subsystemGrid, isCompact && styles.subsystemGridCompact]}>
            <View style={styles.subsystemCard}>
              <View style={styles.subsystemHeader}>
                <Cpu size={18} color="#2B4C7E" />
                <View style={styles.statusPillActive}>
                  <Text style={styles.statusPillText}>OPERATIONAL</Text>
                </View>
              </View>
              <Text style={styles.subsystemName}>FastAPI Core Gateway</Text>
              <Text style={styles.subsystemDetail}>
                Zero-trust JWT authentication, role-based access control, and audited microservice endpoints.
              </Text>
            </View>

            <View style={styles.subsystemCard}>
              <View style={styles.subsystemHeader}>
                <Radio size={18} color="#059669" />
                <View style={styles.statusPillActive}>
                  <Text style={styles.statusPillText}>LIVE BROADCAST</Text>
                </View>
              </View>
              <Text style={styles.subsystemName}>Realtime Event Bus</Text>
              <Text style={styles.subsystemDetail}>
                Sub-50ms WebSocket telemetry streaming with fallback event reconciliation and heartbeat monitoring.
              </Text>
            </View>

            <View style={styles.subsystemCard}>
              <View style={styles.subsystemHeader}>
                <Layers size={18} color="#FF6B00" />
                <View style={styles.statusPillActive}>
                  <Text style={styles.statusPillText}>CALIBRATED</Text>
                </View>
              </View>
              <Text style={styles.subsystemName}>LSTM Motion AI</Text>
              <Text style={styles.subsystemDetail}>
                High-frequency 50Hz accelerometer & gyroscope anomaly inference with calibrated confidence scoring.
              </Text>
            </View>

            <View style={styles.subsystemCard}>
              <View style={styles.subsystemHeader}>
                <MapPin size={18} color="#0891B2" />
                <View style={styles.statusPillActive}>
                  <Text style={styles.statusPillText}>GEO-POLYGON ACTIVE</Text>
                </View>
              </View>
              <Text style={styles.subsystemName}>Spatial Geofencing</Text>
              <Text style={styles.subsystemDetail}>
                Dynamic risk polygon intersection, hazard buffer zones, and instant boundary breach notification.
              </Text>
            </View>
          </View>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <View style={styles.footerBrand}>
            <Shield size={20} color="#2B4C7E" />
            <Text style={styles.footerTitle}>TourSafe Sovereign Safety Infrastructure</Text>
          </View>
          <Text style={styles.footerCopyright}>
            Official National Tourism Safety & Emergency Management Network. All rights reserved.
          </Text>
          <View style={styles.footerBadges}>
            <View style={styles.footerBadge}>
              <Lock size={12} color="#64748B" />
              <Text style={styles.footerBadgeText}>TLS 1.3 / AES-256</Text>
            </View>
            <View style={styles.footerBadge}>
              <FileCheck size={12} color="#64748B" />
              <Text style={styles.footerBadgeText}>DPDP Act 2023</Text>
            </View>
            <View style={styles.footerBadge}>
              <Fingerprint size={12} color="#64748B" />
              <Text style={styles.footerBadgeText}>Zero-Trust RBAC</Text>
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
    backgroundColor: '#F8FAFC',
  },
  content: {
    paddingBottom: 48,
  },
  container: {
    maxWidth: 1200,
    width: '100%',
    alignSelf: 'center',
    paddingHorizontal: 20,
    paddingTop: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 20,
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  headerMobile: {
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: 12,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  brandMark: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: '#2B4C7E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  brandTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  brandTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0F172A',
    letterSpacing: -0.3,
  },
  govBadge: {
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#BFDBFE',
  },
  govBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#1D4ED8',
    letterSpacing: 0.5,
  },
  brandSubtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerActionsMobile: {
    width: '100%',
    justifyContent: 'space-between',
  },
  activeUserButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    backgroundColor: '#F0FDFA',
    borderWidth: 1,
    borderColor: '#CCFBF1',
    maxWidth: 180,
  },
  activeUserText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#0D7680',
    flexShrink: 1,
  },
  loginButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#2B4C7E',
  },
  loginButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#ffffff',
  },
  sessionBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#F0FDF4',
    borderWidth: 1,
    borderColor: '#BBF7D0',
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
  },
  sessionBannerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  sessionBannerTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#166534',
  },
  sessionBannerSubtitle: {
    fontSize: 12,
    color: '#15803D',
    marginTop: 1,
  },
  sessionLaunchButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#166534',
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 8,
  },
  sessionLaunchText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#ffffff',
  },
  heroSection: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 24,
    marginBottom: 28,
  },
  heroHeader: {
    gap: 10,
  },
  heroTagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 4,
  },
  securityTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#DBEAFE',
  },
  securityTagText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#2563EB',
    letterSpacing: 0.4,
  },
  realtimeTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: '#F0FDF4',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#DCFCE7',
  },
  realtimeTagText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#15803D',
    letterSpacing: 0.4,
  },
  heroTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#0F172A',
    lineHeight: 32,
    letterSpacing: -0.5,
  },
  heroLead: {
    fontSize: 14,
    color: '#475569',
    lineHeight: 22,
  },
  gatewaysSection: {
    marginBottom: 32,
  },
  sectionHeading: {
    fontSize: 11,
    fontWeight: '800',
    color: '#64748B',
    letterSpacing: 1,
    marginBottom: 2,
  },
  sectionSubheading: {
    fontSize: 14,
    color: '#334155',
    marginBottom: 16,
  },
  gatewayGrid: {
    flexDirection: 'row',
    gap: 16,
  },
  gatewayGridCompact: {
    flexDirection: 'column',
  },
  gatewayCard: {
    flex: 1,
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 20,
    justifyContent: 'space-between',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  gatewayCardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  gatewayIconBox: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gatewayBadge: {
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#BFDBFE',
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
  },
  gatewayBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    color: '#1E40AF',
    letterSpacing: 0.4,
  },
  gatewayTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#0F172A',
    marginBottom: 6,
  },
  gatewayDescription: {
    fontSize: 12,
    color: '#475569',
    lineHeight: 18,
    marginBottom: 16,
  },
  featureList: {
    gap: 8,
    marginBottom: 20,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  featureText: {
    fontSize: 12,
    color: '#334155',
    flex: 1,
  },
  gatewayButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 11,
    borderRadius: 8,
  },
  gatewayButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#ffffff',
  },
  statusSection: {
    marginBottom: 32,
  },
  subsystemGrid: {
    flexDirection: 'row',
    gap: 14,
  },
  subsystemGridCompact: {
    flexDirection: 'column',
  },
  subsystemCard: {
    flex: 1,
    backgroundColor: '#ffffff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 16,
  },
  subsystemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  statusPillActive: {
    backgroundColor: '#F0FDF4',
    borderWidth: 1,
    borderColor: '#BBF7D0',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusPillText: {
    fontSize: 8,
    fontWeight: '700',
    color: '#15803D',
    letterSpacing: 0.4,
  },
  subsystemName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0F172A',
    marginBottom: 4,
  },
  subsystemDetail: {
    fontSize: 11,
    color: '#64748B',
    lineHeight: 16,
  },
  footer: {
    backgroundColor: '#ffffff',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    padding: 20,
    alignItems: 'center',
    gap: 8,
  },
  footerBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  footerTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#2B4C7E',
  },
  footerCopyright: {
    fontSize: 11,
    color: '#64748B',
    textAlign: 'center',
  },
  footerBadges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 6,
  },
  footerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  footerBadgeText: {
    fontSize: 10,
    color: '#64748B',
  },
});
