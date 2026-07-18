/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       '#07071a',
        surface:  '#0d0d24',
        card:     '#12122e',
        'card-h': '#181838',
        border:   '#252550',
        accent:   '#6366f1',
        'accent-bright': '#818cf8',
        'accent-glow':   'rgba(99,102,241,0.35)',
        muted:    '#64648a',
        text:     '#e2e2f0',
        'text-dim': '#9090b8',
      },
      boxShadow: {
        'glow-sm': '0 0 12px rgba(99,102,241,0.25)',
        'glow':    '0 0 24px rgba(99,102,241,0.35)',
        'glow-lg': '0 0 40px rgba(99,102,241,0.45)',
        'tile':    '0 4px 20px rgba(0,0,0,0.5)',
        'tile-h':  '0 8px 32px rgba(0,0,0,0.7)',
      },
      animation: {
        'fade-in':    'fadeIn 0.2s ease',
        'slide-up':   'slideUp 0.25s ease',
        'scale-in':   'scaleIn 0.15s ease',
        'spin-slow':  'spin 3s linear infinite',
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 },                     to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        scaleIn: { from: { opacity: 0, transform: 'scale(0.95)' },      to: { opacity: 1, transform: 'scale(1)' } },
      },
    },
  },
  plugins: [],
}
