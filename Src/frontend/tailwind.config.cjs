/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./Src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        newsreader: ['Newsreader', 'serif'],
      },
    },
  },
  plugins: [],
}