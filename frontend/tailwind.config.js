/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:         "#0A0A0F",
        surface:    "#141420",
        "surface-2":"#1E1E2E",
        border:     "#2D2D3D",
        primary:    "#E8E8F0",
        muted:      "#7777AA",
        accent:     "#6C63FF",
        "accent-hover": "#7B74FF",
        success:    "#22C55E",
        warning:    "#F59E0B",
        error:      "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        glow:    "0 4px 24px rgba(108, 99, 255, 0.2)",
        "glow-sm": "0 2px 12px rgba(108, 99, 255, 0.15)",
        card:    "0 1px 3px rgba(0,0,0,0.5)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in":    "fadeIn 0.3s ease-in-out",
        "slide-up":   "slideUp 0.3s ease-out",
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { transform: "translateY(8px)", opacity: 0 }, to: { transform: "translateY(0)", opacity: 1 } },
      },
    },
  },
  plugins: [],
}
