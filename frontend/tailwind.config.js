/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        emerald: {
          400: 'rgb(var(--color-primary) / <alpha-value>)',
          500: 'rgb(var(--color-primary) / <alpha-value>)',
          600: 'rgb(var(--color-primary-dark) / <alpha-value>)',
          900: '#064E3B',
        },
        gray: {
          300: 'rgb(var(--color-gray-300) / <alpha-value>)',
          400: 'rgb(var(--color-gray-400) / <alpha-value>)',
          500: 'rgb(var(--color-gray-500) / <alpha-value>)',
          600: 'rgb(var(--color-gray-600) / <alpha-value>)',
          700: 'rgb(var(--color-gray-700) / <alpha-value>)',
          800: 'rgb(var(--color-gray-800) / <alpha-value>)',
          900: 'rgb(var(--color-gray-900) / <alpha-value>)',
          950: 'rgb(var(--color-gray-950) / <alpha-value>)',
        },
      },
      borderRadius: {
        base: 'var(--radius-base)',
      },
    },
  },
  plugins: [],
};
