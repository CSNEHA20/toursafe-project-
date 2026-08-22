import { Tabs } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { LayoutDashboard, Map, ShieldAlert, Users, BarChart3, FileText, Settings, Cpu } from 'lucide-react-native';
import { useAuthStore } from '@/store/authStore';
import { useEffect } from 'react';

export default function AdminTabsLayout() {
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
          tabBarActiveTintColor: '#FF9933',
          tabBarInactiveTintColor: 'rgba(255, 255, 255, 0.6)',
          tabBarLabelStyle: styles.tabBarLabel,
        }}
      >
        <Tabs.Screen
          name="dashboard"
          options={{
            title: 'Dashboard',
            tabBarIcon: ({ color }) => <LayoutDashboard size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="map"
          options={{
            title: 'Live Map',
            tabBarIcon: ({ color }) => <Map size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="alerts"
          options={{
            title: 'Alerts',
            tabBarIcon: ({ color }) => <ShieldAlert size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="tourists"
          options={{
            title: 'Tourists',
            tabBarIcon: ({ color }) => <Users size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="analytics"
          options={{
            title: 'Analytics',
            tabBarIcon: ({ color }) => <BarChart3 size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="zones"
          options={{
            title: 'Zones',
            tabBarIcon: ({ color }) => <FileText size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="ml-ops"
          options={{
            title: 'ML Ops',
            tabBarIcon: ({ color }) => <Cpu size={20} color={color} />,
          }}
        />
        <Tabs.Screen
          name="settings"
          options={{
            title: 'Settings',
            tabBarIcon: ({ color }) => <Settings size={20} color={color} />,
          }}
        />
      </Tabs>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f1f5f9',
  },
  tabBar: {
    backgroundColor: '#1a365d',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
    paddingBottom: 8,
    paddingTop: 8,
    height: 60,
  },
  tabBarLabel: {
    fontSize: 11,
    fontWeight: '500',
  },
});
