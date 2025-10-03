import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import UnoCSS from 'unocss/vite'
import { presetUno, presetIcons, presetWebFonts, presetAttributify } from 'unocss'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    UnoCSS({
      presets: [
        presetUno(),
        presetAttributify(),
        presetIcons({
          scale: 1.2,
          cdn: 'https://esm.sh/'
        }),
        presetWebFonts({
          fonts: {
            sans: 'Inter:400,500,600,700',
            mono: 'Fira Code:400,500',
          },
        }),
      ],
      shortcuts: {
        'btn': 'py-2 px-4 font-semibold rounded-lg shadow-md transition-colors duration-200',
        'btn-primary': 'bg-blue-500 text-white hover:bg-blue-700',
        'btn-danger': 'bg-red-500 text-white hover:bg-red-700',
        'btn-success': 'bg-green-500 text-white hover:bg-green-700',
        'btn-warning': 'bg-yellow-500 text-white hover:bg-yellow-700',
        'card': 'bg-white p-4 rounded-lg shadow-md',
        'card-hover': 'bg-white p-4 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-200',
        'input': 'border rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500',
        'badge': 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        'badge-success': 'bg-green-100 text-green-800',
        'badge-error': 'bg-red-100 text-red-800',
        'badge-warning': 'bg-yellow-100 text-yellow-800',
        'badge-info': 'bg-blue-100 text-blue-800',
      },
      theme: {
        colors: {
          primary: {
            50: '#f0f9ff',
            100: '#e0f2fe',
            200: '#bae6fd',
            300: '#7dd3fc',
            400: '#38bdf8',
            500: '#0ea5e9',
            600: '#0284c7',
            700: '#0369a1',
            800: '#075985',
            900: '#0c4a6e',
            950: '#082f49',
          },
        },
      },
    }),
  ],
  server: {
    port: 5186,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true
      }
    }
  }
})
