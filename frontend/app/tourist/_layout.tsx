import { Stack } from 'expo-router';

export default function TouristLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="onboarding" />
      <Stack.Screen name="splash" />
    </Stack>
  );
}
