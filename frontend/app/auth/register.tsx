import { useState } from 'react';
import { useRouter } from 'expo-router';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import { ShieldAlert, Building2, Phone, Mail, Hash, MapPin, Tag, ChevronRight, ChevronLeft, Check, Plus, X } from 'lucide-react-native';
import { createClient } from '@/lib/supabase';
import { authorityApi } from '@/lib/api';
import Toast from 'react-native-toast-message';

type AuthorityType = "police" | "agency" | "hospital" | "other";

interface FormData {
  email: string;
  password: string;
  authority_type: AuthorityType;
  org_name: string;
  badge_number: string;
  contact_phone: string;
  agency_tour_types: string[];
  jurisdiction_spots: string[];
}

const INITIAL_FORM: FormData = {
  email: "",
  password: "",
  authority_type: "police",
  org_name: "",
  badge_number: "",
  contact_phone: "",
  agency_tour_types: [],
  jurisdiction_spots: [],
};

const STEPS = [
  { id: 1, label: "Account" },
  { id: 2, label: "Organisation" },
  { id: 3, label: "Jurisdiction" },
];

const TOUR_TYPE_OPTIONS = [
  "Pilgrimage",
  "Educational",
  "Adventure",
  "Cultural",
  "Wildlife",
  "Medical",
  "Leisure",
  "Corporate",
];

export default function AuthorityRegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [spotInput, setSpotInput] = useState("");

  function update<K extends keyof FormData>(field: K, value: FormData[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function canProceed() {
    if (step === 1) return !!(form.email && form.password && form.password.length >= 8);
    if (step === 2) return !!(form.org_name && form.badge_number);
    return true;
  }

  function addSpot() {
    const s = spotInput.trim();
    if (s && !form.jurisdiction_spots.includes(s)) {
      update("jurisdiction_spots", [...form.jurisdiction_spots, s]);
    }
    setSpotInput("");
  }

  function toggleTourType(t: string) {
    if (form.agency_tour_types.includes(t)) {
      update(
        "agency_tour_types",
        form.agency_tour_types.filter((x) => x !== t)
      );
    } else {
      update("agency_tour_types", [...form.agency_tour_types, t]);
    }
  }

  async function handleSubmit() {
    setLoading(true);
    try {
      // Step 1: Register user via FastAPI
      const registerResponse = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          full_name: form.full_name,
          role: "authority",
        }),
      });

      if (!registerResponse.ok) {
        const errorData = await registerResponse.json();
        throw new Error(errorData.detail || "Registration failed");
      }

      const userData = await registerResponse.json();

      // Step 2: Create authority profile via FastAPI
      const authorityResponse = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/api/v1/authority/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userData.user.id,
          full_name: form.full_name,
          organization_name: form.org_name,
          designation: form.designation,
          phone: form.contact_phone,
          office_phone: form.office_phone || "",
          address: form.address || "",
          license_number: form.license_number || "",
        }),
      });

      if (!authorityResponse.ok) {
        const errorData = await authorityResponse.json();
        throw new Error(errorData.detail || "Authority profile creation failed");
      }

      Toast.show({
        type: 'success',
        text1: 'Registration Successful',
        text2: 'Authority account created! Pending verification.',
      });
      router.replace("/admin/(tabs)/dashboard");
    } catch (err: any) {
      Toast.show({
        type: 'error',
        text1: 'Registration Failed',
        text2: err.message || "Registration failed",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.scrollContent}>
      <View style={styles.card}>
        {/* Step bar */}
        <View style={styles.stepBar}>
          {STEPS.map((s) => {
            const done = step > s.id;
            const active = step === s.id;
            return (
              <View key={s.id} style={styles.stepItem}>
                <View style={[
                  styles.stepCircle,
                  active && styles.stepCircleActive,
                  done && styles.stepCircleDone
                ]}>
                  {done ? <Check size={14} color="#fff" /> : <Text style={[
                    styles.stepNumber,
                    active && styles.stepNumberActive,
                    done && styles.stepNumberDone
                  ]}>{s.id}</Text>}
                </View>
                <Text style={[
                  styles.stepLabel,
                  active && styles.stepLabelActive,
                  done && styles.stepLabelDone
                ]}>{s.label}</Text>
              </View>
            );
          })}
        </View>

        <View style={styles.content}>
          <View style={styles.header}>
            <View style={styles.headerIcon}>
              <ShieldAlert size={16} color="#1a365d" />
            </View>
            <View>
              <Text style={styles.headerTitle}>Authority Registration</Text>
              <Text style={styles.headerSubtitle}>Police Station / Travel Agency</Text>
            </View>
          </View>

          {step === 1 && (
            <View style={styles.stepContent}>
              <View style={styles.inputContainer}>
                <Text style={styles.label}>Official Email</Text>
                <View style={styles.inputWrapper}>
                  <Mail size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={form.email}
                    onChangeText={(text) => update("email", text)}
                    placeholder="officer@police.gov.in"
                    placeholderTextColor="#94a3b8"
                    autoCapitalize="none"
                    keyboardType="email-address"
                  />
                </View>
              </View>
              <View style={styles.inputContainer}>
                <Text style={styles.label}>Password (min. 8 chars)</Text>
                <View style={styles.inputWrapper}>
                  <Hash size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={form.password}
                    onChangeText={(text) => update("password", text)}
                    placeholder="••••••••"
                    placeholderTextColor="#94a3b8"
                    secureTextEntry
                  />
                </View>
              </View>
            </View>
          )}

          {step === 2 && (
            <View style={styles.stepContent}>
              <View style={styles.inputContainer}>
                <Text style={styles.label}>Organisation Type</Text>
                <View style={styles.typeGrid}>
                  {[
                    { value: "police", label: "Police Station" },
                    { value: "agency", label: "Travel Agency" },
                    { value: "hospital", label: "Hospital" },
                    { value: "other", label: "Other Authority" },
                  ].map((opt) => (
                    <TouchableOpacity
                      key={opt.value}
                      onPress={() => update("authority_type", opt.value as AuthorityType)}
                      style={[
                        styles.typeButton,
                        form.authority_type === opt.value && styles.typeButtonActive
                      ]}
                    >
                      <Text style={[
                        styles.typeButtonText,
                        form.authority_type === opt.value && styles.typeButtonTextActive
                      ]}>{opt.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              <View style={styles.inputContainer}>
                <Text style={styles.label}>Organisation / Station Name</Text>
                <View style={styles.inputWrapper}>
                  <Building2 size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={form.org_name}
                    onChangeText={(text) => update("org_name", text)}
                    placeholder="Ooty Police Station"
                    placeholderTextColor="#94a3b8"
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <Text style={styles.label}>Badge / Registration Number</Text>
                <View style={styles.inputWrapper}>
                  <Hash size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={form.badge_number}
                    onChangeText={(text) => update("badge_number", text)}
                    placeholder="TN-12345"
                    placeholderTextColor="#94a3b8"
                  />
                </View>
              </View>

              <View style={styles.inputContainer}>
                <Text style={styles.label}>Contact Phone</Text>
                <View style={styles.inputWrapper}>
                  <Phone size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={form.contact_phone}
                    onChangeText={(text) => update("contact_phone", text)}
                    placeholder="+91 90000 00000"
                    placeholderTextColor="#94a3b8"
                    keyboardType="phone-pad"
                  />
                </View>
              </View>

              {form.authority_type === "agency" && (
                <View style={styles.inputContainer}>
                  <Text style={styles.label}>Tour Types Handled</Text>
                  <View style={styles.tourTypesContainer}>
                    {TOUR_TYPE_OPTIONS.map((t) => (
                      <TouchableOpacity
                        key={t}
                        onPress={() => toggleTourType(t)}
                        style={[
                          styles.tourTypeButton,
                          form.agency_tour_types.includes(t) && styles.tourTypeButtonActive
                        ]}
                      >
                        <Text style={[
                          styles.tourTypeButtonText,
                          form.agency_tour_types.includes(t) && styles.tourTypeButtonTextActive
                        ]}>{t}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}
            </View>
          )}

          {step === 3 && (
            <View style={styles.stepContent}>
              <Text style={styles.jurisdictionHint}>
                Register the tourist spots under your jurisdiction. Tourists in these spots will be routed to your authority for monitoring.
              </Text>
              <View style={styles.spotInputContainer}>
                <View style={styles.spotInputWrapper}>
                  <MapPin size={16} color="#94a3b8" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    value={spotInput}
                    onChangeText={setSpotInput}
                    onSubmitEditing={addSpot}
                    placeholder="e.g. Guna Caves, Ooty Lake…"
                    placeholderTextColor="#94a3b8"
                  />
                </View>
                <TouchableOpacity onPress={addSpot} style={styles.addButton}>
                  <Plus size={16} color="#fff" />
                </TouchableOpacity>
              </View>

              <View style={styles.spotsContainer}>
                {form.jurisdiction_spots.map((spot) => (
                  <View key={spot} style={styles.spotTag}>
                    <Tag size={12} color="#1a365d" />
                    <Text style={styles.spotText}>{spot}</Text>
                    <TouchableOpacity
                      onPress={() =>
                        update(
                          "jurisdiction_spots",
                          form.jurisdiction_spots.filter((s) => s !== spot)
                        )
                      }
                      style={styles.removeSpot}
                    >
                      <X size={12} color="#ef4444" />
                    </TouchableOpacity>
                  </View>
                ))}
                {form.jurisdiction_spots.length === 0 && (
                  <Text style={styles.noSpotsText}>
                    No spots added yet. You can add them later too.
                  </Text>
                )}
              </View>
            </View>
          )}

          {/* Nav buttons */}
          <View style={styles.navButtons}>
            {step > 1 && (
              <TouchableOpacity
                onPress={() => setStep((s) => s - 1)}
                style={styles.backButton}
              >
                <ChevronLeft size={16} color="#64748b" />
                <Text style={styles.backButtonText}>Back</Text>
              </TouchableOpacity>
            )}
            {step < STEPS.length ? (
              <TouchableOpacity
                onPress={() => setStep((s) => s + 1)}
                disabled={!canProceed()}
                style={[styles.continueButton, !canProceed() && styles.buttonDisabled]}
              >
                <Text style={styles.continueButtonText}>Continue</Text>
                <ChevronRight size={16} color="#fff" />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                onPress={handleSubmit}
                disabled={loading}
                style={[styles.submitButton, loading && styles.buttonDisabled]}
              >
                {loading ? <ActivityIndicator color="#fff" size="small" /> : <Check size={16} color="#fff" />}
                <Text style={styles.submitButtonText}>Register Authority</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Already have an account?{" "}
            <Text style={styles.footerLink} onPress={() => router.push("/auth/login")}>
              Sign in
            </Text>
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a365d',
  },
  scrollContent: {
    padding: 20,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 8,
  },
  stepBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#cbd5e1',
  },
  stepItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    gap: 4,
  },
  stepCircle: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: '#cbd5e1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepCircleActive: {
    borderColor: '#1a365d',
    backgroundColor: '#1a365d',
  },
  stepCircleDone: {
    borderColor: '#0d9488',
    backgroundColor: '#0d9488',
  },
  stepNumber: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.4)',
  },
  stepNumberActive: {
    color: '#fff',
  },
  stepNumberDone: {
    color: '#fff',
  },
  stepLabel: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.4)',
  },
  stepLabelActive: {
    color: '#1a365d',
  },
  stepLabelDone: {
    color: '#0d9488',
  },
  content: {
    padding: 32,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 20,
  },
  headerIcon: {
    width: 32,
    height: 32,
    backgroundColor: 'rgba(26, 54, 93, 0.1)',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#1a365d',
  },
  headerSubtitle: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.6)',
  },
  stepContent: {
    gap: 16,
  },
  inputContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#64748b',
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
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
    fontSize: 14,
    color: '#1e293b',
  },
  typeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  typeButton: {
    flex: 1,
    minWidth: '45%',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    alignItems: 'center',
  },
  typeButtonActive: {
    borderColor: '#1a365d',
    backgroundColor: '#1a365d',
  },
  typeButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#64748b',
  },
  typeButtonTextActive: {
    color: '#fff',
  },
  tourTypesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tourTypeButton: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#cbd5e1',
  },
  tourTypeButtonActive: {
    backgroundColor: '#0d9488',
    borderColor: '#0d9488',
  },
  tourTypeButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#64748b',
  },
  tourTypeButtonTextActive: {
    color: '#fff',
  },
  jurisdictionHint: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.6)',
    marginBottom: 12,
  },
  spotInputContainer: {
    flexDirection: 'row',
    gap: 8,
  },
  spotInputWrapper: {
    flex: 1,
    position: 'relative',
  },
  addButton: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#1a365d',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  spotsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  spotTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#e2e8f0',
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  spotText: {
    fontSize: 12,
    color: '#1a365d',
  },
  removeSpot: {
    marginLeft: 2,
  },
  noSpotsText: {
    fontSize: 12,
    color: 'rgba(100, 116, 139, 0.4)',
    fontStyle: 'italic',
  },
  navButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
  },
  backButtonText: {
    fontSize: 14,
    color: '#64748b',
  },
  continueButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: '#1a365d',
    paddingVertical: 10,
    borderRadius: 8,
  },
  continueButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  submitButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#0d9488',
    paddingVertical: 10,
    borderRadius: 8,
  },
  submitButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  footer: {
    backgroundColor: 'rgba(226, 232, 240, 0.5)',
    borderTopWidth: 1,
    borderTopColor: '#cbd5e1',
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  footerText: {
    fontSize: 11,
    color: 'rgba(100, 116, 139, 0.5)',
    textAlign: 'center',
  },
  footerLink: {
    color: '#0d9488',
  },
});
