import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, createAttempt, getCurrentUser, logoutUser, setCsrfToken, type AuthResponse, type User } from './api'
import AuthLayout from './components/auth/AuthLayout'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import JobSelectionPage from './pages/jobs/JobSelectionPage'
import Assessment from './pages/assessment/Assessment'
import { ResultPage } from './pages/reports/ResultPage'

const ATTEMPT_PATH = /^\/attempts\/([^/]+)\/?$/
const REPORT_PATH = /^\/reports\/([^/]+)\/?$/

function authenticatedPath(path: string) {
  return ATTEMPT_PATH.test(path) || REPORT_PATH.test(path) ? path : '/jobs'
}

function decodeReportId(value: string): string | null {
  try {
    const decoded = decodeURIComponent(value)
    return decoded.trim() ? decoded : null
  } catch {
    return null
  }
}

function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [user, setUser] = useState<User | null>(null)
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const [sessionRetry, setSessionRetry] = useState(0)
  const [message, setMessage] = useState('')
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [accountError, setAccountError] = useState('')
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null)
  const [isStarting, setIsStarting] = useState(false)
  const creationRequest = useRef<AbortController | null>(null)
  const navigationGuard = useRef<(() => boolean) | null>(null)
  const historyIndex = useRef<number>(window.history.state?.skillproofIndex ?? 0)
  const restoringHistory = useRef(false)

  const clearSession = useCallback((notice: string) => {
    creationRequest.current?.abort()
    creationRequest.current = null
    setIsStarting(false)
    setCsrfToken(null)
    setUser(null)
    setSelectedRoleId(null)
    setMessage(notice)
    setAccountError('')
    setPath('/login')
  }, [])

  useEffect(() => {
    window.history.replaceState({ ...window.history.state, skillproofIndex: historyIndex.current }, '')
    function updatePath() {
      if (restoringHistory.current) {
        restoringHistory.current = false
        return
      }
      const nextIndex = window.history.state?.skillproofIndex
      if (navigationGuard.current && !navigationGuard.current()) {
        if (typeof nextIndex === 'number' && nextIndex !== historyIndex.current) {
          restoringHistory.current = true
          window.history.go(historyIndex.current - nextIndex)
        } else {
          window.history.replaceState({ skillproofIndex: historyIndex.current }, '', path)
        }
        return
      }
      historyIndex.current = typeof nextIndex === 'number' ? nextIndex : historyIndex.current
      creationRequest.current?.abort()
      creationRequest.current = null
      setIsStarting(false)
      let nextPath = window.location.pathname
      if (!isCheckingSession && !sessionError) {
        nextPath = user ? authenticatedPath(nextPath) : nextPath === '/register' ? '/register' : '/login'
        if (window.location.pathname !== nextPath) window.history.replaceState(window.history.state, '', nextPath)
      }
      setPath(nextPath)
    }

    window.addEventListener('popstate', updatePath)
    return () => window.removeEventListener('popstate', updatePath)
  }, [user, isCheckingSession, sessionError, path])

  useEffect(() => {
    const controller = new AbortController()
    getCurrentUser(controller.signal, false)
      .then((data) => {
        if (controller.signal.aborted) return
        setCsrfToken(data.csrfToken)
        setUser(data.user)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) setMessage('请先登录')
        else setSessionError(error instanceof Error ? error.message : '登录状态查询失败，请重试')
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsCheckingSession(false)
      })
    return () => controller.abort()
  }, [sessionRetry])

  useEffect(() => {
    function handleSessionExpired() {
      clearSession('会话已失效，请重新登录')
    }

    window.addEventListener('session-expired', handleSessionExpired)
    return () => window.removeEventListener('session-expired', handleSessionExpired)
  }, [clearSession])

  const userId = user?.id

  useEffect(() => {
    if (!userId) return
    let controller: AbortController | undefined

    function checkSession() {
      if (document.visibilityState !== 'visible') return
      controller?.abort()
      const request = new AbortController()
      controller = request
      getCurrentUser(request.signal)
        .then((data) => {
          if (request.signal.aborted) return
          setCsrfToken(data.csrfToken)
          setUser(data.user)
          setAccountError('')
        })
        .catch((error: unknown) => {
          if (request.signal.aborted || (error instanceof ApiError && error.status === 401)) return
          setAccountError(error instanceof Error ? error.message : '登录状态查询失败，请重试')
        })
    }

    window.addEventListener('focus', checkSession)
    document.addEventListener('visibilitychange', checkSession)
    return () => {
      controller?.abort()
      window.removeEventListener('focus', checkSession)
      document.removeEventListener('visibilitychange', checkSession)
    }
  }, [userId])

  const page = user ? authenticatedPath(path) : path === '/register' ? '/register' : '/login'

  useEffect(() => {
    if (isCheckingSession || sessionError) return
    if (window.location.pathname !== page) window.history.replaceState(window.history.state, '', page)
  }, [page, isCheckingSession, sessionError])

  function navigate(next: string, replace = false) {
    if (navigationGuard.current && !navigationGuard.current()) return
    if (replace) {
      window.history.replaceState({ skillproofIndex: historyIndex.current }, '', next)
    } else {
      historyIndex.current += 1
      window.history.pushState({ skillproofIndex: historyIndex.current }, '', next)
    }
    setPath(next)
  }

  const registerNavigationGuard = useCallback((guard: (() => boolean) | null) => {
    navigationGuard.current = guard
  }, [])

  function finishLogin(data: AuthResponse) {
    setCsrfToken(data.csrfToken)
    setUser(data.user)
    setMessage('')
    setPath('/jobs')
  }

  async function logout() {
    if (navigationGuard.current && !navigationGuard.current()) return
    setIsLoggingOut(true)
    setAccountError('')
    try {
      await logoutUser()
      clearSession('已退出登录')
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearSession('登录状态已失效，请重新登录')
      } else {
        setAccountError(error instanceof Error ? error.message : '退出失败，请重试')
      }
    } finally {
      setIsLoggingOut(false)
    }
  }

  async function selectRole(roleId: string) {
    setAccountError('')
    try {
      const data = await getCurrentUser()
      setCsrfToken(data.csrfToken)
      setUser(data.user)
      setSelectedRoleId(roleId)
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) {
        setAccountError(error instanceof Error ? error.message : '登录状态查询失败，请重试')
      }
    }
  }

  async function startAssessment() {
    if (!selectedRoleId || creationRequest.current || isLoggingOut) return
    const controller = new AbortController()
    creationRequest.current = controller
    setIsStarting(true)
    setAccountError('')
    try {
      const data = await getCurrentUser(controller.signal)
      if (controller.signal.aborted) return
      setCsrfToken(data.csrfToken)
      setUser(data.user)
      const attempt = await createAttempt(selectedRoleId, controller.signal)
      if (!controller.signal.aborted) navigate(`/attempts/${encodeURIComponent(attempt.id)}`)
    } catch (error) {
      if (!controller.signal.aborted && !(error instanceof ApiError && error.status === 401)) {
        setAccountError(error instanceof Error ? error.message : '创建测评失败，请重试')
      }
    } finally {
      if (creationRequest.current === controller) {
        creationRequest.current = null
        setIsStarting(false)
      }
    }
  }

  function retrySession() {
    setIsCheckingSession(true)
    setSessionError('')
    setSessionRetry(sessionRetry + 1)
  }

  if (isCheckingSession || sessionError) {
    return (
      <AuthLayout>
        <div className="auth-box">
          <h1>SkillProof</h1>
          {isCheckingSession ? (
            <p>正在恢复登录状态…</p>
          ) : (
            <>
              <p className="form-message" role="alert">{sessionError}</p>
              <button className="primary-button" type="button" onClick={retrySession}>重试</button>
            </>
          )}
        </div>
      </AuthLayout>
    )
  }

  if (user) {
    const attemptMatch = ATTEMPT_PATH.exec(page)
    if (attemptMatch) {
      return <Assessment key={`${user.id}:${attemptMatch[1]}`} attemptId={attemptMatch[1]}
        onResult={(id) => navigate(`/reports/${encodeURIComponent(id)}`, true)}
        onBack={() => navigate('/jobs')} registerNavigationGuard={registerNavigationGuard} />
    }
    const reportMatch = REPORT_PATH.exec(page)
    if (reportMatch) {
      const attemptId = decodeReportId(reportMatch[1])
      if (!attemptId) {
        return (
          <main className="result-page">
            <div className="result-state" role="alert">
              <h1 className="result-state__title">报告链接无效</h1>
              <p className="result-state__message">报告地址无法解析，请检查链接后重试。</p>
            </div>
          </main>
        )
      }
      return <ResultPage key={`${user.id}:${attemptId}`} attemptId={attemptId} />
    }
    return (
      <JobSelectionPage
        key={user.id}
        user={user}
        logout={logout}
        isLoggingOut={isLoggingOut}
        accountError={accountError}
        selectedRoleId={selectedRoleId}
        onSelectRole={selectRole}
        onStartAssessment={startAssessment}
        isStarting={isStarting}
      />
    )
  }

  if (page === '/register') return <RegisterPage navigate={navigate} onAuthenticated={finishLogin} />
  return <LoginPage navigate={navigate} onAuthenticated={finishLogin} notice={message} />
}

export default App
