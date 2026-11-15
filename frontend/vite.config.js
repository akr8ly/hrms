import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
        "^/(auth|employees|admin|chatbot|organization|expenses|queries|divisions|departments|designations|locations|office-addresses)": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
})
