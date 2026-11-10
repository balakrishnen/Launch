import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { installReviewShim } from './review'
async function boot() {
  if (import.meta.env.VITE_REVIEW === '1') { const data = await fetch('data.json').then(r => r.json()); installReviewShim(data) }
  createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
}
boot()
