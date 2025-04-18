import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'
import { VoiceProvider } from './contexts/VoiceContext'

// TEST LOG REMOVED
// console.log("MAIN.TSX LOADED - VERSION 2");

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MantineProvider defaultColorScheme="auto">
      <VoiceProvider>
        <App />
      </VoiceProvider>
    </MantineProvider>
  </React.StrictMode>,
)
