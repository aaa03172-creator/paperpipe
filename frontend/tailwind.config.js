/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--pp-font-sans)"],
        mono: ["var(--pp-font-mono)"],
      },
    },
  },
  plugins: [],
};
