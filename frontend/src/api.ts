import type { Answers, AssessmentResult, Attempt } from './pages/assessment/types'

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
  const timeout = AbortSignal.timeout(30000)
  try {
    response = await fetch(`/api${path}`, {
      ...requestOptions,
      headers,
      credentials: 'include',
      signal: requestOptions.signal ? AbortSignal.any([requestOptions.signal, timeout]) : timeout,
    })
  } catch (error) {
    if (requestOptions.signal?.aborted) throw error
    if (timeout.aborted) throw new ApiError(0, '请求超时，请稍后重试')
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

function hasText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function checkAttempt(data: Attempt, id?: string) {
  const message = '服务器返回的测评数据不完整或格式不正确，请稍后重试'
  if (!data || !hasText(data.id) || (id !== undefined && data.id !== id)
    || !hasText(data.roleId) || !hasText(data.roleName)
    || !['in_progress', 'submitted'].includes(data.status)
    || !Array.isArray(data.questions) || !data.answers
    || typeof data.answers !== 'object' || Array.isArray(data.answers)) {
    throw new ApiError(200, message)
  }

  const validQuestions = data.questions.every((question) => (
    question && hasText(question.id) && hasText(question.dimension) && hasText(question.stem)
    && ['single', 'multiple'].includes(question.type)
    && Array.isArray(question.options) && question.options.length > 0
    && question.options.every((option) => option && hasText(option.id) && hasText(option.text))
    && new Set(question.options.map((option) => option.id)).size === question.options.length
  ))
  if (!validQuestions || new Set(data.questions.map((question) => question.id)).size !== data.questions.length) {
    throw new ApiError(200, message)
  }

  const validAnswers = Object.entries(data.answers).every(([questionId, choices]) => {
    const question = data.questions.find((item) => item.id === questionId)
    return question && Array.isArray(choices)
      && (question.type !== 'single' || choices.length <= 1)
      && choices.every((choice) => typeof choice === 'string' && question.options.some((option) => option.id === choice))
      && new Set(choices).size === choices.length
  })
  if (!validAnswers || data.questionCount !== data.questions.length
    || data.answeredCount !== Object.values(data.answers).filter((choices) => choices.length > 0).length) {
    throw new ApiError(200, message)
  }
  return {
    ...data,
    answers: Object.fromEntries(data.questions.map((question) => [
      question.id, Object.hasOwn(data.answers, question.id) ? data.answers[question.id] : [],
    ])),
  }
}

export async function createAttempt(roleId: string, signal?: AbortSignal) {
  const data = checkAttempt(await apiRequest<Attempt>('/attempts', {
    method: 'POST',
    authenticated: true,
    body: JSON.stringify({ roleId }),
    signal,
  }))
  if (data.roleId !== roleId) throw new ApiError(200, '服务器返回的测评岗位不一致，请重试')
  return data
}

export async function getAttempt(id: string, signal?: AbortSignal) {
  return checkAttempt(await apiRequest<Attempt>(`/attempts/${encodeURIComponent(id)}`, {
    authenticated: true,
    signal,
  }), id)
}

export async function saveAnswers(id: string, answers: Answers, signal?: AbortSignal) {
  return checkAttempt(await apiRequest<Attempt>(`/attempts/${encodeURIComponent(id)}/answers`, {
    method: 'PUT',
    authenticated: true,
    body: JSON.stringify({ answers }),
    signal,
  }), id)
}

export async function submitAttempt(id: string, signal?: AbortSignal) {
  const data = await apiRequest<AssessmentResult>(`/attempts/${encodeURIComponent(id)}/submit`, {
    method: 'POST',
    authenticated: true,
    signal,
  })
  const dimensions = ['programming', 'algorithms', 'database', 'network', 'os', 'software']
  if (!data || data.id !== id || !hasText(data.roleId) || !hasText(data.roleName)
    || !hasText(data.submittedAt) || Number.isNaN(Date.parse(data.submittedAt))
    || !Array.isArray(data.dimensions) || data.dimensions.length !== dimensions.length
    || !data.dimensions.every((item) => item && dimensions.includes(item.id) && hasText(item.name)
      && typeof item.score === 'number' && Number.isFinite(item.score) && item.score >= 0 && item.score <= 100)
    || new Set(data.dimensions.map((item) => item.id)).size !== dimensions.length) {
    throw new ApiError(200, '服务器返回的提交结果格式不正确，请重试确认测评状态')
  }
  return data
}
