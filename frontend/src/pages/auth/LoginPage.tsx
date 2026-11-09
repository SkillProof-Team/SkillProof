import { useState, type FormEvent } from 'react'
import { loginUser, type AuthResponse } from '../../api'
import { validateEmail } from '../../authValidation'
import AuthLayout from '../../components/auth/AuthLayout'
import Brand from '../../components/auth/Brand'

type LoginPageProps = {
  navigate: (path: string) => void
  onAuthenticated: (data: AuthResponse) => void
  notice: string
}

export default function LoginPage({ navigate, onAuthenticated, notice }: LoginPageProps) {
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') ?? '').trim().toLowerCase()
    const password = String(form.get('password') ?? '')
    const validationError = validateEmail(email) || (!password ? '请输入密码' : '')
    setError(validationError)
    if (validationError) return

    setIsSubmitting(true)
    try {
      onAuthenticated(await loginUser(email, password))
    } catch (error) {
      setError(error instanceof Error ? error.message : '登录失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="auth-box">
        <div className="mobile-brand"><Brand /></div>
        <p className="form-tag">账号登录</p>
        <h1>欢迎回来</h1>
        <p className="form-desc">登录 SkillProof，继续你的能力测评。</p>
        <form onSubmit={login} noValidate aria-busy={isSubmitting}>
          <label htmlFor="email">邮箱</label>
          <input
            id="email"
            name="email"
            type="email"
            placeholder="name@example.com"
            autoComplete="email"
            required
            disabled={isSubmitting}
          />
          <label htmlFor="password">密码</label>
          <input
            id="password"
            name="password"
            type="password"
            placeholder="请输入密码"
            autoComplete="current-password"
            required
            disabled={isSubmitting}
          />
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '登录中…' : '登录'}
          </button>
        </form>
        {error && <p className="form-message" role="alert">{error}</p>}
        {!error && notice && <p className="form-message" role="status">{notice}</p>}
        <div className="divider"><span>或</span></div>
        <button className="secondary-button" type="button" disabled={isSubmitting} onClick={() => navigate('/register')}>
          注册新账号
        </button>
      </div>
    </AuthLayout>
  )
}
