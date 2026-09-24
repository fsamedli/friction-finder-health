/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#F5F6F8',
        surface: '#FFFFFF',
        border: { DEFAULT: '#E4E7EC', strong: '#D0D5DD' },
        fg: { DEFAULT: '#101828', soft: '#344054', mute: '#525E70', faint: '#667085' },  // mute and faint meet WCAG AA (≥ 4.5:1) on white and canvas
        side: { DEFAULT: '#0B1B2B', hover: '#13283D', active: '#1B3550', line: '#1E3348', fg: '#C9D4E0', mute: '#7D8FA3' },
        brand: { DEFAULT: '#0E8A7E', 50: '#E7F6F4', 100: '#C9ECE7', 500: '#12A594', 600: '#0E8A7E', 700: '#0B6E65', 900: '#08433E' },
        crit: { DEFAULT: '#D92D20', 50: '#FEF3F2', 100: '#FEE4E2', 700: '#B42318' },
        warn: { DEFAULT: '#CA8504', 50: '#FEFBE8', 100: '#FEF7C3', 700: '#854A0E' },
        act: { DEFAULT: '#C4501E', 50: '#FDF1EC', 100: '#F9DCCF', 700: '#9C3A12' },
        ok: { DEFAULT: '#079455', 50: '#ECFDF3', 100: '#D1FADF', 700: '#067647' },
        info: { DEFAULT: '#2E6BE6', 50: '#EFF4FF', 100: '#D1E0FF', 700: '#1D4ED8' },
        ai: { DEFAULT: '#6941C6', 50: '#F4F3FF', 100: '#EBE9FE', 700: '#5925DC' },
      },
      fontFamily: {
        sans: ['Geist', '"Source Sans 3"', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      boxShadow: {
        xs: '0 1px 2px rgba(16,24,40,0.05)',
        card: '0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)',
        pop: '0 12px 24px -6px rgba(16,24,40,0.14), 0 4px 8px -2px rgba(16,24,40,0.06)',
        ring: '0 0 0 4px rgba(14,138,126,0.14)',
      },
      keyframes: {
        in: { '0%': { opacity: 0, transform: 'translateY(4px)' }, '100%': { opacity: 1, transform: 'none' } },
        pulse2: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.35 } },
        slide: { '0%': { transform: 'translateX(100%)' }, '100%': { transform: 'none' } },
      },
      animation: { in: 'in .28s ease-out both', pulse2: 'pulse2 1.6s ease-in-out infinite', slide: 'slide .25s ease-out both' },
    },
  },
  plugins: [],
}
