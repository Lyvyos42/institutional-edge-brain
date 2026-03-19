import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#06060f",
        surface: "#0d0d1a",
        border: "#1a1a2e",
        primary: "#00d4ff",
        secondary: "#7c3aed",
        bull: "#00f5a0",
        bear: "#f72585",
        warn: "#ffb703",
        muted: "#4a5568",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
