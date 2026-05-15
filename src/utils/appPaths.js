const KNOWN_BASE_PATHS = ['/hireflow-live']

export function appBasePath() {
  const pathname = window.location.pathname || '/'
  const match = KNOWN_BASE_PATHS.find((base) => pathname === base || pathname.startsWith(`${base}/`))
  return match || ''
}

export function appPath(path = '/') {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${appBasePath()}${normalizedPath}`
}

export function isAppPath(path) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return window.location.pathname === appPath(normalizedPath)
}

export function appWsUrl(path = '/ws') {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const isLocalHost = ['127.0.0.1', 'localhost'].includes(window.location.hostname)
  if (isLocalHost) {
    return `${protocol}//${window.location.hostname}:8771${normalizedPath}`
  }
  return `${protocol}//${window.location.host}${appPath(normalizedPath)}`
}
