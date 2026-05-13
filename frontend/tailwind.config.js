/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'surface-container-lowest': '#060e20',
        'surface-container-low': '#131b2e',
        'surface-container': '#171f33',
        'surface-container-high': '#222a3d',
        'surface-container-highest': '#2d3449',
        'surface-variant': '#2d3449',
        'surface-bright': '#31394d',
        surface: '#0b1326',
        'surface-dim': '#0b1326',
        background: '#0b1326',
        primary: '#4edea3',
        'primary-container': '#10b981',
        'primary-fixed': '#6ffbbe',
        'primary-fixed-dim': '#4edea3',
        secondary: '#68dba9',
        'secondary-container': '#25a475',
        'secondary-fixed': '#85f8c4',
        'secondary-fixed-dim': '#68dba9',
        tertiary: '#bcc7de',
        'tertiary-container': '#98a3ba',
        'tertiary-fixed': '#d8e3fb',
        'tertiary-fixed-dim': '#bcc7de',
        error: '#ffb4ab',
        'error-container': '#93000a',
        outline: '#86948a',
        'outline-variant': '#3c4a42',
        'on-primary': '#003824',
        'on-primary-container': '#00422b',
        'on-primary-fixed': '#002113',
        'on-primary-fixed-variant': '#005236',
        'on-secondary': '#003825',
        'on-secondary-container': '#00311f',
        'on-secondary-fixed': '#002114',
        'on-secondary-fixed-variant': '#005137',
        'on-tertiary': '#263143',
        'on-tertiary-container': '#2e394c',
        'on-tertiary-fixed': '#111c2d',
        'on-tertiary-fixed-variant': '#3c475a',
        'on-surface': '#dae2fd',
        'on-surface-variant': '#bbcabf',
        'on-background': '#dae2fd',
        'on-error': '#690005',
        'on-error-container': '#ffdad6',
        'inverse-surface': '#dae2fd',
        'inverse-on-surface': '#283044',
        'inverse-primary': '#006c49',
        'surface-tint': '#4edea3'
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        full: '9999px'
      },
      fontFamily: {
        headline: ['Inter', 'sans-serif'],
        display: ['Inter', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        label: ['Inter', 'sans-serif']
      }
    }
  },
  plugins: []
}
