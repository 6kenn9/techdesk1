export async function api(path, { method = 'GET', data, blob = false } = {}) {
  const token = sessionStorage.getItem('techdesk-token')
  const headers = token ? { Authorization: 'Bearer ' + token } : {}
  if (data !== undefined) headers['Content-Type'] = 'application/json'
  let response
  try {
    response = await fetch('/api' + path, { method, headers, body: data === undefined ? undefined : JSON.stringify(data) })
  } catch {
    throw new Error('Не вдалося з’єднатися із сервісом. Спробуйте ще раз.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    if (response.status === 401 && token && token === sessionStorage.getItem('techdesk-token') && !path.startsWith('/auth/login')) {
      sessionStorage.removeItem('techdesk-token')
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
