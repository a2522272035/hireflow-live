import { createApp } from 'vue'
import App from './App.vue'
import SpeakerTestPage from './SpeakerTestPage.vue'
import './styles.css'

const RootComponent = window.location.pathname === '/speaker-test'
  ? SpeakerTestPage
  : App

createApp(RootComponent).mount('#app')
