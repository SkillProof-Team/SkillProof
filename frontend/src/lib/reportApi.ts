import type { Report } from '../types/report'

/**
 * 接口基地址。
 * 生产环境由后端同源托管前端，默认留空即可；本地前后端端口不同时，
 * 通过 .env.local 设置 VITE_API_BASE=http://127.0.0.1:8000 即可，无需改代码。
 */
const rawBase: unknown = import.meta.env.VITE_API_BASE
const API_BASE = typeof rawBase === 'string' ? rawBase.replace(/\/+$/, '') : ''

export type ReportErrorKind = 'unauthorized' | 'notFound' | 'conflict' | 'server' | 'network'

export interface ReportLoadError {
  kind: ReportErrorKind
  status: number | null
  message: string
}

export type ReportLoadResult =
  | { ok: true; report: Report }
  | { ok: false; error: ReportLoadError }

const DEFAULT_MESSAGE: Record<ReportErrorKind, string> = {
  unauthorized: '登录状态已失效，请重新登录后再查看测评报告。',
  notFound: '没有找到这份测评报告，可能已被删除，或不属于当前账号。',
  conflict: '这次测评尚未提交，暂时没有可查看的结果。',
  server: '报告加载失败，请稍后重试。',
  network: '网络连接失败，请检查网络后重试。',
}

/** 契约约定错误体为 {detail: string | {message: string}}，取不到时回落到默认文案。 */
function readDetail(payload: unknown): string | null {
  if (typeof payload !== 'object' || payload === null) return null
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (typeof detail === 'object' && detail !== null) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message
  }
  return null
}

function toError(kind: ReportErrorKind, status: number | null, detail: string | null): ReportLoadError {
  return { kind, status, message: detail ?? DEFAULT_MESSAGE[kind] }
}

function isReport(value: unknown): value is Report {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<Report>
  return typeof candidate.id === 'string' && Array.isArray(candidate.dimensions)
}

/**
 * 读取本人已提交测评的报告。
 * 只接受服务端返回的分数，不在前端做任何评分或推断。
 */
export async function fetchReport(
  attemptId: string,
  signal?: AbortSignal,
): Promise<ReportLoadResult> {
  const url = `${API_BASE}/api/reports/${encodeURIComponent(attemptId)}`

  let response: Response
  try {
    response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    // 组件卸载或切换报告时的主动取消，交给调用方忽略。
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    return { ok: false, error: toError('network', null, null) }
  }

  // 非 JSON 响应（例如网关错误页）按空处理，由状态码决定提示文案。
  const payload: unknown = await response.json().catch(() => null)

  if (response.status === 401 || response.status === 403) {
    return { ok: false, error: toError('unauthorized', response.status, readDetail(payload)) }
  }
  if (response.status === 404) {
    return { ok: false, error: toError('notFound', 404, readDetail(payload)) }
  }
  if (response.status === 409) {
    return { ok: false, error: toError('conflict', 409, readDetail(payload)) }
  }
  if (!response.ok) {
    return { ok: false, error: toError('server', response.status, readDetail(payload)) }
  }
  if (!isReport(payload)) {
    return { ok: false, error: toError('server', response.status, '报告数据格式不正确，请稍后重试。') }
  }

  return { ok: true, report: payload }
}
