/**
 * TourSafe Tourist Tabs Navigation Layout
 * Primary navigation for the mobile safety companion.
 */

import { Tabs } from "expo-router";
import { View, StyleSheet } from "react-native";
import {
  ShieldCheck,
  Compass,
  MapPin,
  ShieldAlert,
  FileText,
  CreditCard,
  User,
  Activity,
} from "lucide-react-native";
import { useAuthStore } from "@/store/authStore";
import { useEffect } from "react";

export default function TouristTabsLayout() {
  const { initializeAuth } = useAuthStore();

  useEffect(() => {
    initializeAuth();
  }, []);

  return (
    <View style={styles.container}>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarStyle: styles.tabBar,
          tabBarActiveTintColor: "#FF9933",
          tabBarInactiveTintColor: "#94A3B8",
          tabBarLabelStyle: styles.tabBarLabel,
        }}
      >
        <Tabs.Screen
          name="dashboard"
          options={{
            title: "Home",
            tabBarIcon: ({ color }) => <ShieldCheck size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="itinerary"
          options={{
            title: "Trips",
            tabBarIcon: ({ color }) => <Compass size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="map"
          options={{
            title: "Map",
            tabBarIcon: ({ color }) => <MapPin size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="safety"
          options={{
            title: "Safety",
            tabBarIcon: ({ color }) => <Activity size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="sos"
          options={{
            title: "SOS",
            tabBarIcon: ({ color }) => <ShieldAlert size={20} color="#EF4444" />,
            tabBarActiveTintColor: "#EF4444",
          }}
        />
        <Tabs.Screen
          name="incidents"
          options={{
            title: "Incident",
            tabBarIcon: ({ color }) => <FileText size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="digital-id"
          options={{
            title: "Digital ID",
            tabBarIcon: ({ color }) => <CreditCard size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: "Profile",
            tabBarIcon: ({ color }) => <User size={20} color={color} />,
          }}
        />
      </Tabs>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0B132B",
  },
  tabBar: {
    backgroundColor: "#0F172A",
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.08)",
    paddingBottom: 6,
    paddingTop: 6,
    height: 58,
  },
  tabBarLabel: {
    fontSize: 10,
    fontWeight: "600",
  },
});
