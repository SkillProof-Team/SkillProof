import type { ReactNode } from 'react'
import AuthLeft from './AuthLeft'
import '../../styles/auth.css'

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-page">
      <AuthLeft />
      <section className="right-panel">{children}</section>
    </main>
  )
}
