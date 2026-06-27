/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#f3f5f9",
        surface: "#ffffff",
        tint: "#f7f9fc",
        border: "#e6eaf1",
        "border-2": "#eef1f6",
        text: "#0f172a",
        "text-2": "#334155",
        muted: "#64748b",
        "muted-2": "#94a3b8",

        primary: {
          DEFAULT: "#2f80ed",
          ink: "#1d4ed8",
          soft: "#e9f1ff",
        },
        teal: {
          DEFAULT: "#10b981",
          ink: "#065f46",
          soft: "#d1fae5",
        },
        amber: {
          DEFAULT: "#f59e0b",
          ink: "#92400e",
          soft: "#fef3c7",
        },
        violet: {
          DEFAULT: "#8b5cf6",
          ink: "#5b21b6",
          soft: "#ede9fe",
        },
        danger: {
          DEFAULT: "#ef4444",
          ink: "#991b1b",
          soft: "#fee2e2",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      fontSize: {
        xs: ["11.5px", "1.4"],
        sm: ["12.5px", "1.4"],
        base: ["14px", "1.5"],
        md: ["15px", "1.4"],
        lg: ["18px", "1.3"],
        xl: ["22px", "1.2"],
        "2xl": ["24px", "1.15"],
        "3xl": ["28px", "1.1"],
      },
      borderRadius: {
        xs: "6px",
        sm: "10px",
        DEFAULT: "12px",
        md: "12px",
        lg: "14px",
        xl: "16px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.04)",
        soft: "0 4px 12px rgba(15,23,42,0.06), 0 8px 24px rgba(15,23,42,0.05)",
        brand: "0 4px 12px -2px rgba(16,185,129,0.4)",
      },
      transitionDuration: {
        150: "150ms",
      },
    },
  },
  plugins: [],
};
