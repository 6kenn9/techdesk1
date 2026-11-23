const TOKEN_KEY = 'techdesk-token'
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(value) {
  try { localStorage.setItem(TOKEN_KEY, value); sessionStorage.removeItem(TOKEN_KEY) }
  catch { try { sessionStorage.setItem(TOKEN_KEY, value) } catch {} }
}
export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY) } catch {}
  try { sessionStorage.removeItem(TOKEN_KEY) } catch {}
}
export function watchToken() {
  window.addEventListener('storage', event => { if (event.key === TOKEN_KEY) location.reload() })
}

export async function api(path, { method = 'GET', data, blob = false } = {}) {
  const token = getToken()
  const headers = token ? { Authorization: 'Bearer ' + token } : {}
  const form = data instanceof FormData
  if (data !== undefined && !form) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetch('/api' + path, { method, headers, body: data === undefined ? undefined : form ? data : JSON.stringify(data) })
  } catch {
    throw new Error('Не вдалося з’єднатися із сервісом. Спробуйте ще раз.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    if (response.status === 401 && token && token === getToken() && !path.startsWith('/auth/login') && !path.startsWith('/auth/google')) {
      clearToken()
      window.dispatchEvent(new Event('techdesk-expired'))
    }
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Операцію не виконано. Спробуйте ще раз.')
  }
  return blob ? response.blob() : response.json()
}

export function query(values) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== '' && value !== false && value != null) params.set(key, value)
  }
  return params.size ? '?' + params : ''
}

export async function download(path, name) {
  const url = URL.createObjectURL(await api(path, { blob: true }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
