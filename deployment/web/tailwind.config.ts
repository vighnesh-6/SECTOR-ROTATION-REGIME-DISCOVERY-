import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--terminal-bg)",
        foreground: "var(--terminal-text-primary)",
        terminal: {
          bg: "var(--terminal-bg)",
          panel: "var(--terminal-panel)",
          secondary: "var(--terminal-secondary)",
          border: "var(--terminal-border)",
          primary: "var(--terminal-text-primary)",
          muted: "var(--terminal-text-secondary)",
        },
        financial: {
          positive: "var(--financial-positive)",
          negative: "var(--financial-negative)",
          neutral: "var(--financial-neutral)",
        },
        sector: {
          auto: "var(--sector-auto)",
          bank: "var(--sector-bank)",
          fmcg: "var(--sector-fmcg)",
          it: "var(--sector-it)",
          metal: "var(--sector-metal)",
          pharma: "var(--sector-pharma)",
          benchmark: "var(--sector-benchmark)",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "Liberation Mono",
          "Courier New",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
export default config;
