/**
 * TourSafe First-Launch Onboarding Experience
 * Explains what TourSafe does, how location is used, how motion telemetry works,
 * how emergency assistance operates, and what permissions are requested.
 * Reassuring, human language — avoiding raw ML and surveillance terminology.
 */

import React, { useState, useRef } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  useWindowDimensions,
  Animated,
} from "react-native";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  Shield,
  MapPin,
  Activity,
  ShieldAlert,
  Bell,
  CheckCircle2,
  ArrowRight,
  Sparkles,
  Lock,
  HeartHandshake,
} from "lucide-react-native";

const ONBOARDING_SLIDES = [
  {
    id: "companion",
    icon: HeartHandshake,
    tint: "#FF9933",
    badge: "SAFETY COMPANION",
    title: "Travel With Peace of Mind",
    headline: "Your Official Tourist Safety Companion",
    description:
      "TourSafe is built to look out for you throughout your journey. We provide proactive guidance, real-time safety alerts, and instant emergency response wherever your adventures take you.",
    keyPoints: [
      "Not a surveillance dashboard — you are always in control",
      "Clear visibility on what is collected and why",
      "Dedicated to traveler protection and emergency coordination",
    ],
  },
  {
    id: "location",
    icon: MapPin,
    tint: "#0d9488",
    badge: "LOCATION AWARENESS",
    title: "Smart Safety Geofencing",
    headline: "Stay Aware of Monitored Travel Zones",
    description:
      "TourSafe uses your GPS to notify you when you enter tourist support corridors, protected nature reserves, or restricted zones, helping you make informed decisions on the ground.",
    keyPoints: [
      "Automatic alerts for hazardous weather or terrain warnings",
      "Verified tourist waypoints and destination tracking",
      "Pinpoint location dispatch if you ever request assistance",
    ],
  },
  {
    id: "motion",
    icon: Activity,
    tint: "#3b82f6",
    badge: "MOTION TELEMETRY",
    title: "Edge Motion Intelligence",
    headline: "Recognizing Distress When It Matters Most",
    description:
      "Your phone's motion sensors help recognize sudden impacts, falls, or unusual stillness during hikes and excursions. We'll simply check in to ask 'Are you okay?' before taking any action.",
    keyPoints: [
      "Processed efficiently with battery-aware sampling",
      "Works offline during network blackouts and reconnects smoothly",
      "No raw sensor feeds shared publicly",
    ],
  },
  {
    id: "emergency",
    icon: ShieldAlert,
    tint: "#ef4444",
    badge: "EMERGENCY ASSISTANCE",
    title: "One-Touch Emergency SOS",
    headline: "Direct Link to Local First Responders",
    description:
      "If you ever need urgent help, a deliberate press-and-hold SOS immediately alerts the nearest authority command center and coordinates nearby police, medical, or rescue units.",
    keyPoints: [
      "Real-time responder tracking and direct communication",
      "Automatic notification to your trusted emergency contacts",
      "Works reliably even with spotty connectivity",
    ],
  },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [currentStep, setCurrentStep] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const isLastSlide = currentStep === ONBOARDING_SLIDES.length - 1;

  async function handleComplete() {
    await AsyncStorage.setItem("@toursafe_onboarding_completed", "true");
    router.replace("/auth/login?role=tourist");
  }

  function handleNext() {
    if (isLastSlide) {
      handleComplete();
    } else {
      const nextIndex = currentStep + 1;
      setCurrentStep(nextIndex);
      scrollRef.current?.scrollTo({ x: nextIndex * width, animated: true });
    }
  }

  function handleSkip() {
    handleComplete();
  }

  return (
    <View style={styles.container}>
      {/* Top Header */}
      <View style={styles.topBar}>
        <View style={styles.brandRow}>
          <Shield size={22} color="#FF9933" />
          <Text style={styles.brandTitle}>TourSafe</Text>
        </View>
        <TouchableOpacity onPress={handleSkip} style={styles.skipButton}>
          <Text style={styles.skipText}>Skip</Text>
        </TouchableOpacity>
      </View>

      {/* Slides ScrollView */}
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(e) => {
          const index = Math.round(e.nativeEvent.contentOffset.x / width);
          setCurrentStep(index);
        }}
        style={styles.slidesContainer}
      >
        {ONBOARDING_SLIDES.map((slide, idx) => {
          const IconComp = slide.icon;
          return (
            <View key={slide.id} style={[styles.slide, { width }]}>
              <View style={styles.slideCard}>
                <View
                  style={[
                    styles.iconCircle,
                    { backgroundColor: `${slide.tint}18`, borderColor: `${slide.tint}40` },
                  ]}
                >
                  <IconComp size={38} color={slide.tint} />
                </View>

                <View
                  style={[
                    styles.badgePill,
                    { backgroundColor: `${slide.tint}15`, borderColor: `${slide.tint}30` },
                  ]}
                >
                  <Text style={[styles.badgeText, { color: slide.tint }]}>{slide.badge}</Text>
                </View>

                <Text style={styles.slideHeadline}>{slide.headline}</Text>
                <Text style={styles.slideDesc}>{slide.description}</Text>

                <View style={styles.pointsList}>
                  {slide.keyPoints.map((pt, pIdx) => (
                    <View key={pIdx} style={styles.pointRow}>
                      <CheckCircle2 size={16} color={slide.tint} style={{ marginTop: 2 }} />
                      <Text style={styles.pointText}>{pt}</Text>
                    </View>
                  ))}
                </View>
              </View>
            </View>
          );
        })}
      </ScrollView>

      {/* Bottom Controls */}
      <View style={styles.bottomBar}>
        <View style={styles.indicators}>
          {ONBOARDING_SLIDES.map((_, i) => (
            <View
              key={i}
              style={[
                styles.dot,
                currentStep === i ? styles.activeDot : styles.inactiveDot,
              ]}
            />
          ))}
        </View>

        <TouchableOpacity
          style={[styles.primaryButton, isLastSlide && styles.finishButton]}
          onPress={handleNext}
        >
          <Text style={styles.primaryButtonText}>
            {isLastSlide ? "Get Started" : "Continue"}
          </Text>
          <ArrowRight size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
  },
  topBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 54,
    paddingHorizontal: 24,
    paddingBottom: 12,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  brandTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: 0.5,
  },
  skipButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: "rgba(255, 255, 255, 0.08)",
  },
  skipText: {
    fontSize: 13,
    color: "#94A3B8",
    fontWeight: "600",
  },
  slidesContainer: {
    flex: 1,
  },
  slide: {
    paddingHorizontal: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  slideCard: {
    backgroundColor: "rgba(30, 41, 59, 0.6)",
    borderRadius: 24,
    padding: 24,
    width: "100%",
    maxWidth: 420,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.08)",
    alignItems: "center",
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 24,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  badgePill: {
    borderWidth: 1,
    paddingVertical: 4,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginBottom: 12,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  slideHeadline: {
    fontSize: 20,
    fontWeight: "800",
    color: "#FFFFFF",
    textAlign: "center",
    marginBottom: 10,
    lineHeight: 28,
  },
  slideDesc: {
    fontSize: 14,
    color: "#94A3B8",
    textAlign: "center",
    lineHeight: 22,
    marginBottom: 20,
  },
  pointsList: {
    width: "100%",
    gap: 10,
    backgroundColor: "rgba(15, 23, 42, 0.5)",
    padding: 14,
    borderRadius: 14,
  },
  pointRow: {
    flexDirection: "row",
    gap: 10,
    alignItems: "flex-start",
  },
  pointText: {
    flex: 1,
    fontSize: 13,
    color: "#E2E8F0",
    lineHeight: 18,
    fontWeight: "500",
  },
  bottomBar: {
    paddingHorizontal: 24,
    paddingBottom: 40,
    paddingTop: 16,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  indicators: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
  },
  dot: {
    height: 8,
    borderRadius: 4,
  },
  activeDot: {
    width: 24,
    backgroundColor: "#FF9933",
  },
  inactiveDot: {
    width: 8,
    backgroundColor: "rgba(255, 255, 255, 0.2)",
  },
  primaryButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1E40AF",
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 14,
    gap: 8,
  },
  finishButton: {
    backgroundColor: "#0d9488",
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
});
