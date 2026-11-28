import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  createAttempt,
  getAttempt,
  getCatalog,
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
  saveAnswers,
  setCsrfToken,
  submitAttempt,
} from '../../src/api'
import { fetchHistory } from '../../src/lib/historyApi'
import { buildComparison } from '../../src/lib/historyUtils'
import { fetchRecommendations, fetchReport } from '../../src/lib/reportApi'
import type { Answers } from '../../src/pages/assessment/types'
import { fetchWrongQuestions, fetchWrongDetail, saveMastery, submitPractice } from '../../src/lib/wrongbookApi'

const nativeFetch = globalThis.fetch.bind(globalThis)
const apiBase = import.meta.env.VITE_API_BASE

function updateCookieJar(jar: Map<string, string>, headers: Headers) {
  const rawCookies = typeof headers.getSetCookie === 'function' ? headers.getSetCookie() : []
  for (const rawCookie of rawCookies) {
    const segments = rawCookie.split(';').map((part) => part.trim())
    const [nameValue, ...attrs] = segments
    if (!nameValue) continue
    const eqIndex = nameValue.indexOf('=')
    if (eqIndex <= 0) continue
    const name = nameValue.slice(0, eqIndex).trim()
    const value = nameValue.slice(eqIndex + 1).trim()
    const maxAgeZero = attrs.some((attr) => attr.toLowerCase() === 'max-age=0')
    if (maxAgeZero || value === '' || value === '""') {
      jar.delete(name)
    } else {
      jar.set(name, value)
    }
  }
}

function installLiveBrowserFetch(baseUrl: string) {
  const cookies = new Map<string, string>()

  const liveFetch: typeof fetch = async (input, init) => {
    const rawUrl = typeof input === 'string'
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url
    const targetUrl = rawUrl.startsWith('/') ? `${baseUrl}${rawUrl}` : rawUrl

    const { signal, ...restInit } = init ?? {}
    if (signal?.aborted) {
      throw new DOMException('The operation was aborted.', 'AbortError')
    }

    const headers = new Headers(init?.headers)
    if (!headers.has('Origin')) {
      headers.set('Origin', baseUrl)
    }
    if (init?.credentials === 'include' && cookies.size > 0) {
      headers.set(
        'Cookie',
        Array.from(cookies.entries())
          .map(([name, value]) => `${name}=${value}`)
          .join('; '),
      )
    }

    const fetchPromise = nativeFetch(targetUrl, { ...restInit, headers })
    const response = signal
      ? await new Promise<Response>((resolve, reject) => {
          const onAbort = () => {
            reject(new DOMException('The operation was aborted.', 'AbortError'))
          }
          signal.addEventListener('abort', onAbort, { once: true })
          fetchPromise.then(
            (res) => {
              signal.removeEventListener('abort', onAbort)
              resolve(res)
            },
            (err) => {
              signal.removeEventListener('abort', onAbort)
              reject(err)
            },
          )
        })
      : await fetchPromise

    updateCookieJar(cookies, response.headers)
    return response
  }

  vi.stubGlobal('fetch', liveFetch)
  return cookies
}

function requireApiBase(): string {
  if (typeof apiBase !== 'string' || !apiBase.trim()) {
    throw new Error('VITE_API_BASE must be set to the running backend URL')
  }
  return apiBase.replace(/\/+$/, '')
}

async function completeAttempt(roleId = 'backend') {
  const created = await createAttempt(roleId)
  const reloaded = await getAttempt(created.id)
  expect(reloaded.id).toBe(created.id)

  const answers: Answers = Object.fromEntries(
    reloaded.questions.map((question) => [question.id, [question.options[0].id]]),
  )
  const saved = await saveAnswers(reloaded.id, answers, reloaded.answersVersion)
  expect(saved.answersVersion).toBe(reloaded.answersVersion + 1)
  expect(saved.answeredCount).toBe(reloaded.questionCount)

  const submitted = await submitAttempt(saved.id)
  expect(submitted.id).toBe(saved.id)
  expect(submitted.dimensions).toHaveLength(6)
  return { reloaded, saved, submitted }
}

afterEach(() => {
  setCsrfToken(null)
})

describe('API integration', () => {
  it('collects wrong answers, practices and restores mastery without changing the report', async () => {
    installLiveBrowserFetch(requireApiBase())
    const email = `wrongbook-${crypto.randomUUID().slice(0, 8)}@example.invalid`
    const password = 'IntegrationPass123!'
    const registered = await registerUser(email, '错题本集成测试', password)
    setCsrfToken(registered.csrfToken)
    const attempt = await createAttempt('backend')
    const answers: Answers = Object.fromEntries(attempt.questions.map((question) => [
      question.id, [question.options[0].id],
    ]))
    await saveAnswers(attempt.id, answers, attempt.answersVersion)
    await submitAttempt(attempt.id)
    const before = await fetchReport(attempt.id)
    expect(before.ok).toBe(true)
    if (!before.ok) throw new Error('Submitted report is unavailable')
    const wrongCount = before.report.dimensions.reduce((sum, dimension) => sum + dimension.total - dimension.correct, 0)
    expect(wrongCount).toBeGreaterThan(0)
    const query = { roleId: 'backend', dimension: '', topicId: '', status: 'all' as const, offset: 0 }
    const list = await fetchWrongQuestions(query, new AbortController().signal)
    expect(list.total).toBe(wrongCount)
    const item = await fetchWrongDetail(list.items[0].id, new AbortController().signal)
    const requestId = crypto.randomUUID()
    const practiced = await submitPractice(item.id, item.question.correct, requestId)
    expect(practiced.result.isCorrect).toBe(true)
    expect(practiced.item.practiceCount).toBe(1)
    expect((await submitPractice(item.id, item.question.correct, requestId)).item.practiceCount).toBe(1)
    expect((await saveMastery(item.id, true)).mastered).toBe(true)
    await logoutUser()
    const loggedIn = await loginUser(email, password)
    setCsrfToken(loggedIn.csrfToken)
    const restored = await fetchWrongDetail(item.id, new AbortController().signal)
    expect(restored.mastered).toBe(true)
    expect(restored.practiceCount).toBe(1)
    expect((await saveMastery(item.id, false)).mastered).toBe(false)
    expect(await fetchReport(attempt.id)).toEqual(before)
    const other = await registerUser(`other-${crypto.randomUUID().slice(0, 8)}@example.invalid`, '其他测试用户', password)
    setCsrfToken(other.csrfToken)
    expect((await fetchWrongQuestions(query, new AbortController().signal)).items).toEqual([])
    await expect(fetchWrongDetail(item.id, new AbortController().signal)).rejects.toMatchObject({ status: 404 })
  })
  it('creates and reports each open role with the released question bank', async () => {
    installLiveBrowserFetch(requireApiBase())
    const email = `roles-${crypto.randomUUID().slice(0, 8)}@example.invalid`
    const registered = await registerUser(email, '多岗位集成测试', 'IntegrationPass123!')
    setCsrfToken(registered.csrfToken)
    const { roles } = await getCatalog()
    const openRoles = roles.filter((role) => role.enabled)
    expect(openRoles.map((role) => role.id)).toEqual(['backend', 'frontend', 'algorithm', 'qa'])

    const reports = []
    for (const role of openRoles) {
      const { reloaded, submitted } = await completeAttempt(role.id)
      expect(reloaded.questionCount).toBe(18)
      expect(submitted.roleId).toBe(role.id)
      expect(submitted.roleName).toBe(role.name)
      reports.push(submitted)
    }
    const history = await fetchHistory()
    expect(history.ok).toBe(true)
    if (!history.ok) throw new Error('Assessment history is unavailable')
    expect(history.items).toHaveLength(openRoles.length)
    for (const submitted of reports) {
      const result = await fetchReport(submitted.id)
      expect(result).toEqual({ ok: true, report: submitted })
      if (!result.ok) throw new Error('Submitted report is unavailable')
      const { report } = result
      expect(history.items.find((entry) => entry.id === report.id)).toMatchObject({
        roleId: report.roleId, roleName: report.roleName, score: report.score, dimensions: report.dimensions,
      })
    }
  })

  it('loads catalog and surfaces real 401 errors for unauthenticated requests', async () => {
    installLiveBrowserFetch(requireApiBase())

    const catalog = await getCatalog()
    expect(catalog.dimensions).toHaveLength(6)
    expect(catalog.roles.some((role) => role.id === 'backend' && role.enabled)).toBe(true)

    const reportResult = await fetchReport('non-existent-attempt')
    expect(reportResult.ok).toBe(false)
    if (!reportResult.ok) {
      expect(reportResult.error.kind).toBe('unauthorized')
      expect(reportResult.error.status).toBe(401)
    }

    const historyResult = await fetchHistory()
    expect(historyResult.ok).toBe(false)
    if (!historyResult.ok) {
      expect(historyResult.error.kind).toBe('unauthorized')
      expect(historyResult.error.status).toBe(401)
    }

    await expect(loginUser('nobody@example.invalid', 'WrongPass123!')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
    })
  })

  it('completes register, session lookup, CSRF-protected logout, and re-login', async () => {
    const cookies = installLiveBrowserFetch(requireApiBase())
    const suffix = crypto.randomUUID().slice(0, 8)
    const email = `auth-${suffix}@example.invalid`
    const password = 'IntegrationPass123!'

    const registered = await registerUser(email, '集成测试用户', password)
    expect(registered.user.email).toBe(email)
    expect(cookies.size).toBeGreaterThan(0)
    setCsrfToken(registered.csrfToken)

    const current = await getCurrentUser()
    expect(current.user.id).toBe(registered.user.id)
    expect(current.csrfToken).toBe(registered.csrfToken)

    const logoutResult = await logoutUser()
    expect(logoutResult).toEqual({ ok: true })
    expect(cookies.size).toBe(0)

    let sessionExpiredFired = false
    const onExpired = () => {
      sessionExpiredFired = true
    }
    window.addEventListener('session-expired', onExpired, { once: true })
    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiError)
    expect(sessionExpiredFired).toBe(true)

    const loggedIn = await loginUser(email, password)
    expect(loggedIn.user.id).toBe(registered.user.id)
    expect(loggedIn.csrfToken).toBeTruthy()
    setCsrfToken(loggedIn.csrfToken)

    const verified = await getCurrentUser()
    expect(verified.user.id).toBe(registered.user.id)
  })

  it('runs full assessment lifecycle through report and learning recommendations', async () => {
    installLiveBrowserFetch(requireApiBase())
    const suffix = crypto.randomUUID().slice(0, 8)
    const auth = await registerUser(`flow-${suffix}@example.invalid`, '测评测试用户', 'IntegrationPass123!')
    setCsrfToken(auth.csrfToken)

    const { submitted } = await completeAttempt()

    const reportResult = await fetchReport(submitted.id)
    expect(reportResult.ok).toBe(true)
    if (!reportResult.ok) return
    expect(reportResult.report.id).toBe(submitted.id)
    expect(reportResult.report.dimensions).toHaveLength(6)

    const recommendations = await fetchRecommendations(submitted.id, new AbortController().signal)
    expect(Array.isArray(recommendations)).toBe(true)
    if (reportResult.report.weakDimensions.length > 0) {
      expect(recommendations.length).toBeGreaterThan(0)
    }
    for (const item of recommendations) {
      expect(item.resources.length).toBeGreaterThan(0)
    }
  })

  it('lists submitted attempts in history and builds valid retake comparison', async () => {
    installLiveBrowserFetch(requireApiBase())
    const suffix = crypto.randomUUID().slice(0, 8)
    const auth = await registerUser(`history-${suffix}@example.invalid`, '复测测试用户', 'IntegrationPass123!')
    setCsrfToken(auth.csrfToken)

    const first = await completeAttempt()
    const second = await completeAttempt()
    expect(second.submitted.id).not.toBe(first.submitted.id)

    const historyResult = await fetchHistory()
    expect(historyResult.ok).toBe(true)
    if (!historyResult.ok) return
    expect(historyResult.items).toHaveLength(2)

    const comparisonResult = buildComparison(historyResult.items[1], historyResult.items[0])
    expect(comparisonResult.ok).toBe(true)
    if (!comparisonResult.ok) return
    expect(comparisonResult.comparison.dimensions).toHaveLength(6)
    expect(comparisonResult.comparison.diffAllowed).toBe(true)
  })
})
