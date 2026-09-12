/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#FAFBFF',
        card: {
          DEFAULT: '#F0F2FF',
          secondary: '#E5E8FF',
        },
        'green-primary': '#6FA800',
        'green-bright': '#8CC800',
        vygo: {
          bg: '#FAFBFF',
          card: '#F0F2FF',
          'card-2': '#E5E8FF',
          green: '#6FA800',
          'green-bright': '#8CC800',
          white: '#0F1340',
          secondary: '#4A5490',
          border: '#C5CAF0',
          warning: '#C87000',
          danger: '#C42D2D',
          success: '#4E8A00',
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
        'card': '0 2px 12px rgba(15,19,64,0.08)',
        'sheet': '0 -8px 32px rgba(15,19,64,0.14)',
        'green': '0 0 20px rgba(111,168,0,0.25)',
        'phone': '0 0 0 1px rgba(201,232,110,0.15), 0 40px 100px rgba(0,0,0,0.7), 0 0 80px rgba(111,168,0,0.08)',
      },
    },
  },
  plugins: [],
}
