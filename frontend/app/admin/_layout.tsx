import { Tabs } from 'expo-router';

export default function AdminLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen
        name="(tabs)"
        options={{ tabBarStyle: { display: 'none' } }}
      />
    </Tabs>
  );
}
