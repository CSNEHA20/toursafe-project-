import "react-native-url-polyfill/auto";
import AsyncStorage from "@react-native-async-storage/async-storage";

// Supabase client - configured for development only.
// Production authentication is handled by the FastAPI backend.
// This client is retained for backward compatibility and optional demo features.

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

// Mock auth is now explicitly opt-in via EXPO_PUBLIC_USE_MOCK=false
// Production default: FastAPI backend authentication
// Mock mode: only enabled when EXPO_PUBLIC_USE_MOCK=true explicitly set

type MockUser = {
  id: string;
  email: string;
  app_metadata: { role: string };
  user_metadata: { role: string; full_name?: string };
};

type MockSession = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  expires_at: number;
  user: MockUser;
};

type MockAuthRecord = {
  user: MockUser | null;
  session: MockSession | null;
  pendingOtpEmail?: string;
};

async function readMockAuth(): Promise<MockAuthRecord> {
  const raw = await AsyncStorage.getItem("toursafe-mock-auth");
  if (!raw) {
    return { user: null, session: null };
  }

  try {
    return JSON.parse(raw) as MockAuthRecord;
  } catch {
    return { user: null, session: null };
  }
}

async function writeMockAuth(record: MockAuthRecord) {
  await AsyncStorage.setItem("toursafe-mock-auth", JSON.stringify(record));
}

function buildMockUser(email: string, role: string, fullName = ""): MockUser {
  const safeRole = role || "tourist";
  const id = `mock-${safeRole}-${email.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  return {
    id,
    email,
    app_metadata: { role: safeRole },
    user_metadata: { role: safeRole, full_name: fullName },
  };
}

function buildMockSession(user: MockUser): MockSession {
  const expiresAt = Math.floor(Date.now() / 1000) + 60 * 60;
  return {
    access_token: `mock-access-${user.id}`,
    refresh_token: `mock-refresh-${user.id}`,
    token_type: "bearer",
    expires_in: 60 * 60,
    expires_at: expiresAt,
    user,
  };
}

function createMockSupabaseClient() {
  return {
    auth: {
      async signInWithPassword({ email }: { email: string; password: string }) {
        const role =
          email.toLowerCase().includes("admin") || email.toLowerCase().includes("authority")
            ? "authority"
            : "tourist";
        const user = buildMockUser(email, role);
        const session = buildMockSession(user);
        await writeMockAuth({ user, session });
        return { data: { user, session }, error: null };
      },
      async signInWithOtp({ email }: { email: string }) {
        const existing = await readMockAuth();
        await writeMockAuth({ ...existing, pendingOtpEmail: email });
        return { data: { user: null, session: null }, error: null };
      },
      async verifyOtp({ email }: { email: string; token: string; type: string }) {
        const user = buildMockUser(email, "tourist");
        const session = buildMockSession(user);
        await writeMockAuth({ user, session });
        return { data: { user, session }, error: null };
      },
      async signUp({
        email,
        options,
      }: {
        email: string;
        password: string;
        options?: { data?: Record<string, unknown> };
      }) {
        const role = options?.data?.role ?? "tourist";
        const user = buildMockUser(email, String(role), String(options?.data?.full_name ?? ""));
        const session = buildMockSession(user);
        await writeMockAuth({ user, session });
        return { data: { user, session }, error: null };
      },
      async updateUser({ data }: { data: Record<string, unknown> }) {
        const current = await readMockAuth();
        const currentEmail = current.user?.email ?? "demo@toursafe.local";
        const currentRole = String(data.role ?? current.user?.app_metadata.role ?? "tourist");
        const user = buildMockUser(
          currentEmail,
          currentRole,
          String(data.full_name ?? current.user?.user_metadata.full_name ?? "")
        );
        const session = buildMockSession(user);
        await writeMockAuth({ user, session });
        return { data: { user }, error: null };
      },
      async refreshSession() {
        const current = await readMockAuth();
        if (current.user && current.session) {
          const session = buildMockSession(current.user);
          await writeMockAuth({ ...current, session });
          return { data: { session }, error: null };
        }
        return { data: { session: null }, error: null };
      },
      async getSession() {
        const current = await readMockAuth();
        return { data: { session: current.session }, error: null };
      },
      async getUser() {
        const current = await readMockAuth();
        return { data: { user: current.user }, error: null };
      },
      async signOut() {
        await writeMockAuth({ user: null, session: null });
        return { error: null };
      },
    },
    channel(): any {
      return {
        on(_type: string, _filter: unknown, _callback: (...args: any[]) => void) {
          return this;
        },
        subscribe() {
          return { unsubscribe() {} };
        },
      };
    },
  } as const;
}

// Primary client: Supabase if configured, otherwise backend auth is used.
// Mock client is only available explicitly via EXPO_PUBLIC_USE_MOCK=true
export function createClient() {
  if (isSupabaseConfigured) {
    try {
      return createSupabaseClient(supabaseUrl!, supabaseAnonKey!, {
        auth: {
          storage: AsyncStorage,
          autoRefreshToken: true,
          persistSession: true,
          detectSessionInUrl: false,
        },
      });
    } catch {
      // Fall through to indicate Supabase not available
    }
  }

  // Supabase not configured - production path uses FastAPI backend auth
  // Mock client only available if explicitly enabled
  if (process.env.EXPO_PUBLIC_USE_MOCK === "true") {
    return createMockSupabaseClient();
  }

  // Return null if neither Supabase nor mock is configured
  // App should use FastAPI backend authentication instead
  return null as any;
}

// Export null client when Supabase/mock not available
// Auth is expected to come from FastAPI backend
export const supabase = createClient();

export function isMockAuthActive(): boolean {
  return process.env.EXPO_PUBLIC_USE_MOCK === "true";
}

// Helper: get auth token from FastAPI backend session
// This should be used by API clients instead of Supabase auth
export async function getBackendAuthToken(): Promise<string | null> {
  if (!isSupabaseConfigured && process.env.EXPO_PUBLIC_USE_MOCK !== "true") {
    // Production: authenticate via FastAPI
    // Token should be managed by the auth store / API client
    return null;
  }
  const client = createClient();
  if (!client) return null;
  const {
    data: { session },
  } = await client.auth.getSession();
  return session?.access_token ?? null;
}