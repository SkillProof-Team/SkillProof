import { useEffect, useState } from 'react'
import { getCatalog, type Catalog, type User } from '../../api'
import '../../styles/jobs.css'

type JobSelectionPageProps = {
  user: User
  logout: () => Promise<void>
  isLoggingOut: boolean
  accountError: string
  selectedRoleId: string | null
  onSelectRole: (roleId: string) => Promise<void>
}

export default function JobSelectionPage({
  user, logout, isLoggingOut, accountError, selectedRoleId, onSelectRole,
}: JobSelectionPageProps) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [isSelecting, setIsSelecting] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getCatalog(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setCatalog(data)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setError(error instanceof Error ? error.message : '岗位查询失败，请重试')
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
    return () => controller.abort()
  }, [retryCount])

  function retry() {
    setIsLoading(true)
    setError('')
    setRetryCount(retryCount + 1)
  }

  async function selectRole(roleId: string) {
    if (isSelecting || isLoggingOut) return
    setIsSelecting(true)
    try {
      await onSelectRole(roleId)
    } finally {
      setIsSelecting(false)
    }
  }

  const selectedRole = catalog?.roles.find((role) => role.id === selectedRoleId && role.enabled === true)

  return (
    <main className="jobs-page">
      <div className="jobs-content">
        <p className="jobs-user">你好，{user.name}</p>
        <button className="jobs-back" type="button" disabled={isLoggingOut || isSelecting} onClick={logout}>
          {isLoggingOut ? '退出中…' : '退出登录'}
        </button>
        {accountError && <p role="alert">{accountError}</p>}
        <p className="jobs-tag">SKILLPROOF · ALPHA</p>
        <h1>选择目标岗位</h1>
        <p className="jobs-desc">选择岗位，了解对应的能力评估方向。</p>
        <section aria-label="岗位列表" aria-busy={isLoading}>
          {isLoading && <p role="status">正在加载岗位…</p>}
          {error && (
            <article className="job-card">
              <p role="alert">{error}</p>
              <button type="button" onClick={retry} disabled={isLoading || isLoggingOut}>重新加载</button>
            </article>
          )}
          {!isLoading && !error && catalog && (
            <>
              {catalog.roles.length === 0 && <p role="status">暂无岗位数据，请稍后重新加载。</p>}
              {catalog.roles.length > 0 && !catalog.roles.some((role) => role.enabled === true) && (
                <p role="status">目前暂无开放岗位。</p>
              )}
              {catalog.roles.map((role) => (
                <article className="job-card" key={role.id}>
                  <span className="job-label">{role.enabled === true ? '已开放' : '暂未开放'}</span>
                  <h2>{role.name}</h2>
                  <p>{role.description}</p>
                  <h3>六维能力与知识点</h3>
                  {catalog.dimensions.length === 0 && <p>暂无能力维度数据。</p>}
                  <dl className="job-dimensions">
                    {catalog.dimensions.map((dimension) => (
                      <div key={dimension.id}>
                        <dt>{dimension.name}</dt>
                        <dd>{dimension.description}</dd>
                        <dd>
                          {role.topics?.[dimension.id]?.length
                            ? role.topics[dimension.id].join('、')
                            : '暂无知识点'}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <button
                    type="button"
                    disabled={role.enabled !== true || isLoggingOut || isSelecting}
                    aria-pressed={role.id === selectedRole?.id}
                    onClick={() => selectRole(role.id)}
                  >
                    {role.enabled !== true ? '暂未开放' : isSelecting ? '正在验证登录状态…' : role.id === selectedRole?.id ? '已选择' : '选择该岗位'}
                  </button>
                </article>
              ))}
              {catalog.roles.length === 0 && (
                <button className="jobs-back" type="button" onClick={retry} disabled={isLoggingOut}>重新加载</button>
              )}
              {selectedRole && (
                <article className="job-card" aria-label="已选岗位">
                  <p role="status">已选择：{selectedRole.name}</p>
                  <p id="assessment-note">测评入口尚未接入，当前可以选择岗位，暂时无法开始测评。</p>
                  <button type="button" disabled aria-describedby="assessment-note">开始测评（待开放）</button>
                </article>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  )
}
