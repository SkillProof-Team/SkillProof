export type User = {
  id: string
  email: string
  name: string
}

export type AuthResponse = {
  user: User
  csrfToken: string
}

export type Role = {
  id: string
  name: string
  description: string
  enabled: boolean
  topics: Record<string, string[]>
}

export type Catalog = {
  roles: Role[]
  dimensions: { id: string; name: string; description: string }[]
}

let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type RequestOptions = RequestInit & { authenticated?: boolean }

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { authenticated = false, ...requestOptions } = options
  const headers = new Headers(requestOptions.headers)
  const method = requestOptions.method ?? 'GET'

  if (requestOptions.body) headers.set('Content-Type', 'application/json')
  if (authenticated && !['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) {
    if (!csrfToken) throw new ApiError(403, '登录信息不完整，请刷新页面后重试')
    headers.set('X-CSRF-Token', csrfToken)
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...requestOptions,
      headers,
      credentials: 'include',
    })
  } catch (error) {
    if (requestOptions.signal?.aborted) throw error
    throw new ApiError(0, '无法连接服务器，请检查网络后重试')
  }

  if (response.status === 401 && authenticated) {
    setCsrfToken(null)
    window.dispatchEvent(new Event('session-expired'))
  }

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = data?.detail
    const message = typeof detail === 'string' ? detail : detail?.message
    throw new ApiError(response.status,
      typeof message === 'string' && message.trim() ? message : `请求失败（${response.status}），请稍后重试`)
  }
  if (data === null) throw new ApiError(response.status, '服务器响应格式不正确，请稍后重试')
  return data as T
}

async function authRequest(path: string, options?: RequestOptions) {
  const data = await apiRequest<AuthResponse>(path, options)
  if (!data.user?.id || typeof data.csrfToken !== 'string' || !data.csrfToken) {
    throw new ApiError(200, '服务器返回的登录信息不完整，请稍后重试')
  }
  return data
}

export function registerUser(email: string, name: string, password: string) {
  return authRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, name, password }),
  })
}

export function loginUser(email: string, password: string) {
  return authRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function getCurrentUser(signal?: AbortSignal, authenticated = true) {
  return authRequest('/auth/me', { signal, authenticated })
}

export function logoutUser() {
  return apiRequest<{ ok: boolean }>('/auth/logout', { method: 'POST', authenticated: true })
}

export async function getCatalog(signal?: AbortSignal) {
  const data = await apiRequest<Catalog>('/catalog', { signal })
  if (!Array.isArray(data.roles) || !Array.isArray(data.dimensions)) {
    throw new ApiError(200, '服务器返回的岗位信息不完整，请稍后重试')
  }
  return data
}
