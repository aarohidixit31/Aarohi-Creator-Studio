const API = import.meta.env.VITE_API_URL || ''

export function getToken() {
  return localStorage.getItem('admin_token')
}

export function setToken(token) {
  localStorage.setItem('admin_token', token)
}

export function clearToken() {
  localStorage.removeItem('admin_token')
}

export async function authFetch(path, options = {}) {
  const token = getToken()
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  })
  if (res.status === 401) {
    clearToken()
    window.location.href = '/admin/login'
    throw new Error('Unauthorized')
  }
  return res
}

export async function apiError(response, fallback = 'Something went wrong. Please try again.') {
  const body = await response.json().catch(() => null)
  if (typeof body?.detail === 'string') return body.detail
  if (Array.isArray(body?.detail)) {
    return body.detail
      .map((item) => item?.msg)
      .filter(Boolean)
      .join(' · ') || fallback
  }
  if (typeof body?.message === 'string') return body.message
  return response.status >= 500
    ? 'The server could not complete this request. Please try again shortly.'
    : fallback
}

export { API }
