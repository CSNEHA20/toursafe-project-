/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        // ─── TourSafe brand tokens — updated lighter blue palette ───
        "ts-navy": "#2B4C7E",        // Lighter navy blue (from dark #1A3C6E)
        "ts-saffron": "#FF6B00",     // Keep vibrant orange
        "ts-green": "#059669",       // Slightly lighter green
        "ts-teal": "#0891B2",        // Lighter teal/cyan
        "ts-slate": "#64748B",       // Lighter slate gray
        "ts-light": "#F8FAFC",       // Very light background
        "ts-mid": "#E2E8F0",         // Keep as is
        "ts-alert-red": "#DC2626",   // Slightly lighter red
        border: "#CBD5E1",           // Lighter border
        input: "#E2E8F0",
        ring: "#2B4C7E",             // Match lighter navy
        background: "#FFFFFF",       // Pure white background
        foreground: "#1E293B",       // Slightly lighter text
        primary: {
          DEFAULT: "#2B4C7E",        // Lighter navy
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "#0891B2",        // Lighter teal
          foreground: "#ffffff",
        },
        destructive: {
          DEFAULT: "#DC2626",        // Lighter red
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "#F1F5F9",        // Lighter muted background
          foreground: "#64748B",     // Lighter muted text
        },
        accent: {
          DEFAULT: "#0284C7",        // Bright blue accent
          foreground: "#ffffff",
        },
        popover: {
          DEFAULT: "#ffffff",
          foreground: "#1E293B",
        },
        card: {
          DEFAULT: "#ffffff",
          foreground: "#1E293B",
        },
      },
      borderRadius: {
        lg: "12px",
        md: "10px",
        sm: "8px",
      },
      fontFamily: {
        sans: ["Inter_400Regular", "system-ui"],
        mono: ["JetBrainsMono_400Regular", "monospace"],
      },
      // Note: CSS @keyframes animations (sos-pulse, status-blink, slide-in-right)
      // don't exist on native — these are re-implemented with
      // react-native-reanimated in the components that use them
      // (SOS button, status dots, side panels) to preserve the same
      // visual effect. See components/ui/animations.tsx.
    },
  },
  plugins: [],
};
