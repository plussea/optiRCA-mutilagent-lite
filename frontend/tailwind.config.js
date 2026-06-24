/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#e5eefc",
        mist: "#08111f",
        brand: "#7c8cff",
        abyss: "#08111f",
        panel: "#0d1829",
        cyanline: "#38d5ff",
      },
      boxShadow: {
        soft: "0 24px 70px rgba(0, 0, 0, 0.35)",
        glow: "0 0 36px rgba(56, 213, 255, 0.18)",
      },
    },
  },
  plugins: [],
};
