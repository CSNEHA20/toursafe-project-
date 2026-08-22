import { Stack } from 'expo-router';

export default function ResponderLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: '#090D16' },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="index" options={{ title: 'Responder Dashboard' }} />
      <Stack.Screen name="incident" options={{ title: 'Incident Response' }} />
      <Stack.Screen name="messages" options={{ title: 'Operational Messages' }} />
      <Stack.Screen name="map" options={{ title: 'Tactical Map' }} />
    </Stack>
  );
}
