import React, { useState } from 'react';
import { useRouter } from 'expo-router';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Shield, User, Building2, Users, ArrowRight, Lock } from 'lucide-react-native';
import Toast from 'react-native-toast-message';

export default function SelectRolePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);

  async function choose(role: 'tourist' | 'authority' | 'responder') {
    setSaving(true);
    try {
      if (role === 'tourist') {
        router.replace('/tourist/(tabs)/dashboard');
      } else if (role === 'responder') {
        router.replace('/responder');
      } else {
        router.replace('/admin/(tabs)/dashboard');
      }
    } catch (err: unknown) {
      Toast.show({
        type: 'error',
        text1: 'Navigation Error',
        text2: err instanceof Error ? err.message : 'Failed to navigate to selected workspace',
      });
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <View style={styles.logoContainer}>
          <View style={styles.logo}>
            <Shield size={28} color="#ffffff" />
          </View>
        </View>

        <Text style={styles.title}>Select Workspace Access</Text>
        <Text style={styles.subtitle}>
          Choose your operational role to enter the corresponding TourSafe environment.
        </Text>

        <View style={styles.optionsContainer}>
          {/* Authority */}
          <TouchableOpacity
            disabled={saving}
            onPress={() => choose('authority')}
            style={[styles.optionButton, saving && styles.optionButtonDisabled]}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Authority & Command Center"
          >
            <View style={[styles.optionIcon, { backgroundColor: 'rgba(26, 60, 110, 0.1)' }]}>
              <Building2 size={22} color="#1A3C6E" />
            </View>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>Authority Command Center</Text>
              <Text style={styles.optionDescription}>Incident dispatch, safety zones & AI intelligence</Text>
            </View>
            <ArrowRight size={16} color="#1A3C6E" />
          </TouchableOpacity>

          {/* Responder */}
          <TouchableOpacity
            disabled={saving}
            onPress={() => choose('responder')}
            style={[styles.optionButton, saving && styles.optionButtonDisabled]}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Field Responder Operations"
          >
            <View style={[styles.optionIcon, { backgroundColor: 'rgba(255, 107, 0, 0.1)' }]}>
              <Users size={22} color="#C2410C" />
            </View>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>Field Responder Operations</Text>
              <Text style={styles.optionDescription}>Tactical mission dispatch, GPS navigation & scene triage</Text>
            </View>
            <ArrowRight size={16} color="#C2410C" />
          </TouchableOpacity>

          {/* Tourist */}
          <TouchableOpacity
            disabled={saving}
            onPress={() => choose('tourist')}
            style={[styles.optionButton, saving && styles.optionButtonDisabled]}
            activeOpacity={0.85}
            accessibilityRole="button"
            accessibilityLabel="Tourist & Traveler Safety Companion"
          >
            <View style={[styles.optionIcon, { backgroundColor: 'rgba(4, 106, 56, 0.1)' }]}>
              <User size={22} color="#046A38" />
            </View>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>Tourist Safety Companion</Text>
              <Text style={styles.optionDescription}>Real-time safety radar, Digital ID & 1-touch SOS</Text>
            </View>
            <ArrowRight size={16} color="#046A38" />
          </TouchableOpacity>
        </View>

        {saving && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color="#1A3C6E" />
            <Text style={styles.loadingText}>Initializing workspace session…</Text>
          </View>
        )}

        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.replace('/auth/login')}
        >
          <Text style={styles.backButtonText}>Return to Login</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B132B',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 10,
    padding: 32,
    alignItems: 'center',
    width: '100%',
    maxWidth: 480,
  },
  logoContainer: {
    marginBottom: 16,
  },
  logo: {
    width: 56,
    height: 56,
    backgroundColor: '#1A3C6E',
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0F172A',
    marginBottom: 6,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 13,
    color: '#64748B',
    marginBottom: 24,
    textAlign: 'center',
    lineHeight: 18,
  },
  optionsContainer: {
    width: '100%',
    gap: 12,
  },
  optionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    backgroundColor: '#F8FAFC',
  },
  optionButtonDisabled: {
    opacity: 0.6,
  },
  optionIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionText: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0F172A',
    marginBottom: 2,
  },
  optionDescription: {
    fontSize: 11,
    color: '#64748B',
    lineHeight: 15,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 20,
  },
  loadingText: {
    fontSize: 12,
    color: '#64748B',
  },
  backButton: {
    marginTop: 20,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  backButtonText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748B',
  },
});
