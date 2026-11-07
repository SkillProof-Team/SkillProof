import { useCallback, useEffect, useState } from 'react'
import { ApiError, getCurrentUser, logoutUser, setCsrfToken, type AuthResponse, type User } from './api'
import AuthLayout from './components/auth/AuthLayout'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import JobSelectionPage from './pages/jobs/JobSelectionPage'

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

  const clearSession = useCallback((notice: string) => {
    setCsrfToken(null)
    setUser(null)
    setSelectedRoleId(null)
    setMessage(notice)
    setAccountError('')
    setPath('/login')
  }, [])

  useEffect(() => {
    function updatePath() {
      let nextPath = window.location.pathname
      if (!isCheckingSession && !sessionError) {
        nextPath = user ? '/jobs' : nextPath === '/register' ? '/register' : '/login'
        if (window.location.pathname !== nextPath) window.history.replaceState(null, '', nextPath)
      }
      setPath(nextPath)
    }

    window.addEventListener('popstate', updatePath)
    return () => window.removeEventListener('popstate', updatePath)
  }, [user, isCheckingSession, sessionError])

  useEffect(() => {
    const controller = new AbortController()
    getCurrentUser(controller.signal)
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

  const page = user ? '/jobs' : path === '/register' ? '/register' : '/login'

  useEffect(() => {
    if (isCheckingSession || sessionError) return
    if (window.location.pathname !== page) window.history.replaceState(null, '', page)
  }, [page, isCheckingSession, sessionError])

  function navigate(next: string) {
    window.history.pushState(null, '', next)
    setPath(next)
  }

  function finishLogin(data: AuthResponse) {
    setCsrfToken(data.csrfToken)
    setUser(data.user)
    setMessage('')
    setPath('/jobs')
  }

  async function logout() {
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
    return (
      <JobSelectionPage
        key={user.id}
        user={user}
        logout={logout}
        isLoggingOut={isLoggingOut}
        accountError={accountError}
        selectedRoleId={selectedRoleId}
        onSelectRole={selectRole}
      />
    )
  }

  if (page === '/register') return <RegisterPage navigate={navigate} onAuthenticated={finishLogin} />
  return <LoginPage navigate={navigate} onAuthenticated={finishLogin} notice={message} />
}

export default App
