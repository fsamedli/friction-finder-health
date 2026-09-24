/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#1B3A4B', soft: '#3E5A69', mute: '#6B7F8A' },
        paper: { DEFAULT: '#FAF8F3', deep: '#F2EEE4', card: '#FFFEFB' },
        teal: { DEFAULT: '#1F8FA8', soft: '#D6ECF1', deep: '#146C80' },
        rust: { DEFAULT: '#C8553D', soft: '#F6DED7', deep: '#9E3F2B' },
        mist: '#B9C6CC',
        line: '#E3DFD5',
        amber: { DEFAULT: '#C9962B', soft: '#F5EACF' },
        moss: { DEFAULT: '#4F7F5E', soft: '#DCEADF' },
      },
      fontFamily: {
        serif: ['Fraunces', 'Georgia', 'serif'],
        sans: ['"Source Sans 3"', 'Calibri', '"Segoe UI"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 rgba(27,58,75,0.04), 0 8px 24px -12px rgba(27,58,75,0.18)',
        lift: '0 2px 0 rgba(27,58,75,0.05), 0 18px 40px -18px rgba(27,58,75,0.35)',
      },
      keyframes: {
        rise: { '0%': { opacity: 0, transform: 'translateY(10px)' }, '100%': { opacity: 1, transform: 'none' } },
        draw: { '0%': { strokeDashoffset: 400 }, '100%': { strokeDashoffset: 0 } },
        pulseRing: { '0%': { boxShadow: '0 0 0 0 rgba(200,85,61,0.45)' }, '100%': { boxShadow: '0 0 0 10px rgba(200,85,61,0)' } },
      },
      animation: {
        rise: 'rise .55s cubic-bezier(.2,.7,.2,1) both',
        pulseRing: 'pulseRing 1.8s ease-out infinite',
      },
    },
  },
  plugins: [],
}
