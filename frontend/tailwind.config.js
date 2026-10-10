/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        industrial: {
          950: "#090d16",
          900: "#0f172a",
          850: "#141e33",
          800: "#1e293b",
          700: "#334155",
          600: "#475569",
        },
        cyber: {
          cyan: "#00f0ff",
          blue: "#38bdf8",
          amber: "#f59e0b",
          orange: "#f97316",
          emerald: "#10b981",
          crimson: "#ef4444",
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
};
