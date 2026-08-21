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
        // ─── TourSafe brand tokens — unchanged from web app ───
        "ts-navy": "#1A3C6E",
        "ts-saffron": "#FF6B00",
        "ts-green": "#046A38",
        "ts-teal": "#0D7680",
        "ts-slate": "#4A5568",
        "ts-light": "#F7F8FA",
        "ts-mid": "#E2E8F0",
        "ts-alert-red": "#C53030",
        border: "#E2E8F0",
        input: "#E2E8F0",
        ring: "#1A3C6E",
        background: "#F7F8FA",
        foreground: "#1A202C",
        primary: {
          DEFAULT: "#1A3C6E",
          foreground: "#ffffff",
        },
        secondary: {
          DEFAULT: "#0D7680",
          foreground: "#ffffff",
        },
        destructive: {
          DEFAULT: "#C53030",
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "#F7F8FA",
          foreground: "#4A5568",
        },
        accent: {
          DEFAULT: "#FF6B00",
          foreground: "#ffffff",
        },
        popover: {
          DEFAULT: "#ffffff",
          foreground: "#1A202C",
        },
        card: {
          DEFAULT: "#ffffff",
          foreground: "#1A202C",
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
