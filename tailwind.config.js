/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0B1215',
        card: {
          DEFAULT: '#11191D',
          secondary: '#172126',
        },
        'green-primary': '#00C875',
        'green-bright': '#35E89B',
        vygo: {
          bg: '#0B1215',
          card: '#11191D',
          'card-2': '#172126',
          green: '#00C875',
          'green-bright': '#35E89B',
          white: '#F8FAF9',
          secondary: '#94A3B8',
          border: '#253238',
          warning: '#F5A524',
          danger: '#E5484D',
          success: '#16A66A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '20px',
        '4xl': '24px',
      },
      animation: {
        'slide-up': 'slideUp 0.32s cubic-bezier(0.32, 0.72, 0, 1)',
        'fade-in': 'fadeIn 0.2s ease-out',
        'pulse-green': 'pulseGreen 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'dash': 'dash 3s linear infinite',
        'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseGreen: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        dash: {
          to: { strokeDashoffset: '0' },
        },
      },
      boxShadow: {
        'card': '0 2px 12px rgba(0,0,0,0.4)',
        'sheet': '0 -8px 32px rgba(0,0,0,0.6)',
        'green': '0 0 20px rgba(0,200,117,0.25)',
      },
    },
  },
  plugins: [],
}
