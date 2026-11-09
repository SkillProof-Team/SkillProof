import { useState, type FormEvent } from 'react'
import { registerUser, type AuthResponse } from '../../api'
import { validateEmail, validateName, validatePassword } from '../../authValidation'
import AuthLayout from '../../components/auth/AuthLayout'
import Brand from '../../components/auth/Brand'

type RegisterPageProps = {
  navigate: (path: string) => void
  onAuthenticated: (data: AuthResponse) => void
}

export default function RegisterPage({ navigate, onAuthenticated }: RegisterPageProps) {
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) return
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') ?? '').trim().toLowerCase()
    const name = String(form.get('name') ?? '').trim()
    const password = String(form.get('password') ?? '')
    const validationError = validateEmail(email) || validateName(name) || validatePassword(password)
    setError(validationError)
    if (validationError) return

    setIsSubmitting(true)
    try {
      onAuthenticated(await registerUser(email, name, password))
    } catch (error) {
      setError(error instanceof Error ? error.message : '注册失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="auth-box">
        <div className="mobile-brand"><Brand /></div>
        <p className="form-tag">账号注册</p>
        <h1>创建账号</h1>
        <p className="form-desc">注册 SkillProof，开始了解你的能力结构。</p>
        <form onSubmit={register} noValidate aria-busy={isSubmitting}>
          <label htmlFor="register-email">邮箱</label>
          <input
            id="register-email"
            name="email"
            type="email"
            placeholder="name@example.com"
            autoComplete="email"
            required
            disabled={isSubmitting}
          />
          <label htmlFor="register-name">姓名</label>
          <input
            id="register-name"
            name="name"
            type="text"
            placeholder="请输入姓名（1–50 个可显示字符）"
            autoComplete="name"
            required
            disabled={isSubmitting}
          />
          <label htmlFor="register-password">密码</label>
          <input
            id="register-password"
            name="password"
            type="password"
            placeholder="请输入 15–128 个字符的密码"
            autoComplete="new-password"
            required
            disabled={isSubmitting}
          />
          <button className="primary-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? '注册中…' : '注册'}
          </button>
        </form>
        {error && <p className="form-message" role="alert">{error}</p>}
        <div className="divider"><span>已有账号？</span></div>
        <button className="secondary-button" type="button" disabled={isSubmitting} onClick={() => navigate('/login')}>
          返回登录
        </button>
      </div>
    </AuthLayout>
  )
}
