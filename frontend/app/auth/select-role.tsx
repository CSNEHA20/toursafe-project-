import { useState } from 'react';
import { useRouter } from 'expo-router';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { ShieldAlert, User, Building2, Loader2 } from 'lucide-react-native';
import { createClient } from '@/lib/supabase';
import Toast from 'react-native-toast-message';

export default function SelectRolePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);

  async function choose(role: "tourist" | "authority") {
    setSaving(true);
    try {
      if (role === "tourist") {
        router.replace("/tourist/(tabs)/dashboard");
      } else {
        router.replace("/admin/(tabs)/dashboard");
      }
    } catch (err: unknown) {
      Toast.show({
        type: 'error',
        text1: 'Error',
        text2: err instanceof Error ? err.message : "Failed to set role",
      });
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        {/* Logo */}
        <View style={styles.logoContainer}>
          <View style={styles.logo}>
            <ShieldAlert size={28} color="#FF9933" />
          </View>
        </View>
        <Text style={styles.title}>Who are you?</Text>
        <Text style={styles.subtitle}>
          Choose how you'll be using TourSafe. This sets your access level.
        </Text>

        <View style={styles.optionsContainer}>
          <TouchableOpacity
            disabled={saving}
            onPress={() => choose("tourist")}
            style={[styles.optionButton, saving && styles.optionButtonDisabled]}
          >
            <View style={styles.optionIcon}>
              <User size={20} color="#0d9488" />
            </View>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>Tourist / Traveller</Text>
              <Text style={styles.optionDescription}>Track my trip, SOS, digital ID</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity
            disabled={saving}
            onPress={() => choose("authority")}
            style={[styles.optionButton, saving && styles.optionButtonDisabled]}
          >
            <View style={styles.optionIcon}>
              <Building2 size={20} color="#1a365d" />
            </View>
            <View style={styles.optionText}>
              <Text style={styles.optionTitle}>Authority / Organisation</Text>
              <Text style={styles.optionDescription}>Police, travel agency, hospital</Text>
            </View>
          </TouchableOpacity>
        </View>

        {saving && (
          <View style={styles.loadingContainer}>
            <Loader2 size={14} color="#64748b" />
            <Text style={styles.loadingText}>Setting up your account…</Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 8,
    padding: 32,
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  logoContainer: {
    marginBottom: 16,
  },
  logo: {
    width: 56,
    height: 56,
    backgroundColor: '#1a365d',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1a365d',
    marginBottom: 4,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: 'rgba(100, 116, 139, 0.6)',
    marginBottom: 24,
    textAlign: 'center',
  },
  optionsContainer: {
    width: '100%',
    gap: 12,
  },
  optionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#cbd5e1',
    backgroundColor: '#fff',
  },
  optionButtonDisabled: {
    opacity: 0.6,
  },
  optionIcon: {
    width: 40,
    height: 40,
    backgroundColor: 'rgba(13, 148, 136, 0.1)',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionText: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1a365d',
  },
  optionDescription: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.5)',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
  },
  loadingText: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.5)',
  },
});
