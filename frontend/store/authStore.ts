import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { AuthUser } from "@/types";
import Toast from "react-native-toast-message";
import { realtimeClient } from "@/lib/realtimeClient";
import { initRealtimeEventDispatcher } from "@/lib/eventDispatcher";

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  setUser: (user: AuthUser | null) => void;
  setLoading: (loading: boolean) => void;
  signOut: () => Promise<void>;
  logout: () => Promise<void>;
  isAuthority: () => boolean;
  isTourist: () => boolean;
  initializeAuth: () => Promise<void>;
  login: (email: string, password: string) => Promise<boolean>;
  refreshSession: () => Promise<boolean>;
}

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: true,
      isAuthenticated: false,
      setUser: (user) => set({ user }),
      setLoading: (isLoading) => set({ isLoading }),
      signOut: async () => {
        try {
          await AsyncStorage.removeItem("toursafe-auth");
        } catch (e) {
          // Ignore errors during sign out
        }
        realtimeClient.disconnect();
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
      logout: async () => {
        await get().signOut();
      },

      isAuthority: () => {
        const role = get().user?.role;
        return role === "authority" || role === "admin" || role === "responder";
      },
      isTourist: () => get().user?.role === "tourist",
      initializeAuth: async () => {
        set({ isLoading: true });
        try {
          const stored = await AsyncStorage.getItem("toursafe-auth");
          if (stored) {
            const { user, accessToken, refreshToken } = JSON.parse(stored);
            // Validate that the stored user has required fields
            if (user && user.email && user.role) {
              set({
                user,
                accessToken,
                refreshToken,
                isAuthenticated: true,
              });
              initRealtimeEventDispatcher();
              if (accessToken) {
                realtimeClient.connect(accessToken);
              }
            } else {
              await AsyncStorage.removeItem("toursafe-auth");
              realtimeClient.disconnect();
              set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
            }
          } else {
            realtimeClient.disconnect();
            set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
          }
        } catch (error) {
          await AsyncStorage.removeItem("toursafe-auth");
          realtimeClient.disconnect();
          set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
        } finally {
          set({ isLoading: false });
        }
      },
      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Login failed");
          }

          const data = await response.json();
          
          const { access_token, refresh_token, user } = data;
          
          // Store tokens and user securely
          await AsyncStorage.setItem("toursafe-auth", JSON.stringify({
            user: {
              id: user.id,
              email: user.email,
              role: user.role,
              full_name: user.full_name,
            },
            accessToken: access_token,
            refreshToken: refresh_token,
          }));

          set({
            user: {
              id: user.id,
              email: user.email,
              role: user.role,
              full_name: user.full_name,
            },
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
          });

          initRealtimeEventDispatcher();
          realtimeClient.connect(access_token);

          return true;
        } catch (error: any) {
          Toast.show({
            type: "error",
            text1: "Login failed",
            text2: error.message,
          });
          return false;
        } finally {
          set({ isLoading: false });
        }
      },
      refreshSession: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          await AsyncStorage.removeItem("toursafe-auth");
          set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
          return false;
        }

        try {
          const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Session refresh failed");
          }

          const data = await response.json();
          const { access_token: newAccessToken, refresh_token: newRefreshToken } = data;

          await AsyncStorage.setItem("toursafe-auth", JSON.stringify({
            user: get().user,
            accessToken: newAccessToken,
            refreshToken: newRefreshToken,
          }));

          set({
            accessToken: newAccessToken,
            refreshToken: newRefreshToken,
          });

          return true;
        } catch (error: any) {
          await AsyncStorage.removeItem("toursafe-auth");
          set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
          return false;
        }
      },
    }),
    {
      name: "toursafe-auth",
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);