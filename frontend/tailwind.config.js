/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        forge: {
          50:  '#f0f4ff',
          100: '#e0eaff',
          200: '#c4d4ff',
          300: '#9db5fe',
          400: '#7490fc',
          500: '#5a6ef8',
          600: '#4550ed',
          700: '#3a40d3',
          800: '#3036aa',
          900: '#2d3286',
          950: '#1c1f54',
        },
        accent: {
          400: '#f472b6',
          500: '#ec4899',
          600: '#db2777',
        },
        surface: {
          900: '#0d0e1a',
          800: '#13152a',
          700: '#1a1d38',
          600: '#252848',
          500: '#333660',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      backgroundImage: {
        'checkerboard': `repeating-conic-gradient(#3a3d5c 0% 25%, #252848 0% 50%)`,
        'gradient-forge': 'linear-gradient(135deg, #5a6ef8 0%, #ec4899 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.4s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(16px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
