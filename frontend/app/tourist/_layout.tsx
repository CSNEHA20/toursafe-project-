import { Tabs } from 'expo-router';
import { ShieldAlert, LayoutDashboard, Map, CreditCard, User, FileText, CalendarDays } from 'lucide-react-native';

export default function TouristLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen
        name="(tabs)"
        options={{ tabBarStyle: { display: 'none' } }}
      />
    </Tabs>
  );
}
