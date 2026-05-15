import { createApp } from 'vue'
import App from './App.vue'
import SpeakerTestPage from './SpeakerTestPage.vue'
import './styles.css'
import { isAppPath } from './utils/appPaths'

const RootComponent = isAppPath('/speaker-test')
  ? SpeakerTestPage
  : App

createApp(RootComponent).mount('#app')
