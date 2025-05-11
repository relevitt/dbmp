/** @type {import('tailwindcss').Config} */

module.exports = {
  content: ["*.{html,js}"],
  safelist: [
    "grid-cols-1",
    "grid-cols-2",
    "grid-cols-3",
    "grid-cols-4",
    "grid-cols-5",
    "grid-cols-6",
    "grid-cols-7",
    "grid-cols-8",
    "grid-cols-9",
    "grid-cols-10",
    "grid-cols-11",
    "grid-cols-12",
    "grid-cols-13",
    "grid-cols-14",
    "grid-cols-15",
  ],
  theme: {
    fontFamily: {
      sans: ["Liberation", "serif"],
      arial: ["Arial", "sans"],
      verdana: ["Verdana", "sans"],
      tahoma: ["Tahoma", "sans"],
      helvetica: ["Helvetica", "sans"],
      courier: ["Courier", "monospace"],
      monaco: ["Monaco", "monospace"],
    },
    extend: {
      colors: { gray: { 350: "#b0b7c3" } },
    },
    keyframes: {
      bounceEqualizer: {
        "0%, 100%": { height: "5px" },
        "50%": { height: "12px" },
      },
    },
    animation: {
      "bounce-eq": "bounceEqualizer 0.6s infinite ease-in-out",
    },
  },
  plugins: [],
};
