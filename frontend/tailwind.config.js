/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        mist: "#f5f7fb",
        brand: "#5b5ce2",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(31, 41, 55, 0.10)",
      },
    },
  },
  plugins: [],
};
