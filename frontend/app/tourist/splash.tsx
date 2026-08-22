/**
 * TourSafe Splash Screen
 * Initializes the mobile application, checks authentication token and session validity,
 * restores safe local state, and routes to Onboarding, Login, or Home Dashboard.
 */

import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator, Animated } from "react-native";
import { useRouter } from "expo-router";
import { Shield, Sparkles, CheckCircle2 } from "lucide-react-native";
import { useAuthStore } from "@/store/authStore";
import { touristApi } from "@/lib/api";
import { initRealtimeEventDispatcher } from "@/lib/eventDispatcher";
import { realtimeClient } from "@/lib/realtimeClient";
import AsyncStorage from "@react-native-async-storage/async-storage";

export default function SplashScreen() {
  const router = useRouter();
  const { accessToken, user, initializeAuth } = useAuthStore();
  const [initStatus, setInitStatus] = useState("Initializing TourSafe security layers…");
  const [scaleAnim] = useState(new Animated.Value(0.85));
  const [fadeAnim] = useState(new Animated.Value(0));

  useEffect(() => {
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 6,
        tension: 40,
        useNativeDriver: true,
      }),
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      }),
    ]).start();

    bootstrapApp();
  }, []);

  async function bootstrapApp() {
    try {
      setInitStatus("Checking stored session…");
      await initializeAuth();

      // Check onboarding state
      const hasCompletedOnboarding = await AsyncStorage.getItem("@toursafe_onboarding_completed");

      const store = useAuthStore.getState();
      if (store.accessToken && store.user) {
        setInitStatus("Verifying identity profile…");
        try {
          // Initialize WebSocket
          realtimeClient.connect(store.accessToken);
          initRealtimeEventDispatcher();

          // Warm cache
          await touristApi.getMe();
          router.replace("/tourist/(tabs)/dashboard");
          return;
        } catch (authErr) {
          console.warn("[Splash] Profile verification failed, refreshing session...");
        }
      }

      if (!hasCompletedOnboarding) {
        setInitStatus("Welcome to TourSafe");
        router.replace("/tourist/onboarding" as any);
      } else {
        router.replace("/auth/login?role=tourist");
      }
    } catch (err) {
      console.warn("[Splash] Bootstrapping failed:", err);
      router.replace("/auth/login?role=tourist");
    }
  }

  return (
    <View style={styles.container}>
      <Animated.View
        style={[
          styles.content,
          {
            opacity: fadeAnim,
            transform: [{ scale: scaleAnim }],
          },
        ]}
      >
        <View style={styles.logoBadge}>
          <Shield size={48} color="#FF9933" />
        </View>

        <Text style={styles.brandTitle}>TourSafe</Text>
        <Text style={styles.brandSubtitle}>Traveler Safety & Emergency Companion</Text>

        <View style={styles.statusBox}>
          <ActivityIndicator size="small" color="#0d9488" style={{ marginRight: 8 }} />
          <Text style={styles.statusText}>{initStatus}</Text>
        </View>

        <View style={styles.footerNote}>
          <Sparkles size={14} color="#64748b" />
          <Text style={styles.footerText}>B2G Government & Tourism Safety Network</Text>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  content: {
    alignItems: "center",
    width: "100%",
    maxWidth: 380,
  },
  logoBadge: {
    width: 96,
    height: 96,
    borderRadius: 28,
    backgroundColor: "rgba(255, 153, 51, 0.12)",
    borderWidth: 2,
    borderColor: "rgba(255, 153, 51, 0.4)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },
  brandTitle: {
    fontSize: 32,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: 0.5,
  },
  brandSubtitle: {
    fontSize: 14,
    color: "#94A3B8",
    marginTop: 6,
    textAlign: "center",
    fontWeight: "500",
  },
  statusBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(30, 41, 59, 0.7)",
    borderRadius: 20,
    paddingVertical: 10,
    paddingHorizontal: 18,
    marginTop: 40,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
  },
  statusText: {
    fontSize: 13,
    color: "#E2E8F0",
    fontWeight: "500",
  },
  footerNote: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    position: "absolute",
    bottom: -140,
  },
  footerText: {
    fontSize: 11,
    color: "#64748B",
    fontWeight: "500",
  },
});
