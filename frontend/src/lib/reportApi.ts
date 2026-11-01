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

/** 契约第 6 节规定报告恰好包含六个固定维度，缺项时图表会静默少画一条轴，因此在此拦下。 */
const REQUIRED_DIMENSIONS = ['programming', 'algorithms', 'database', 'network', 'os', 'software']

function isScore(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
}

function isOptionalCount(value: unknown): boolean {
  return value === undefined || (typeof value === 'number' && Number.isInteger(value) && value >= 0)
}

function isDimension(value: unknown): boolean {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  if (typeof item.id !== 'string' || !item.id.trim()) return false
  if (typeof item.name !== 'string' || !item.name.trim()) return false
  if (!isScore(item.score)) return false
  if (!isOptionalCount(item.correct) || !isOptionalCount(item.total)) return false
  if (item.weight !== undefined && (typeof item.weight !== 'number' || !Number.isFinite(item.weight))) {
    return false
  }
  if (item.priority !== undefined && (typeof item.priority !== 'number' || !Number.isFinite(item.priority))) {
    return false
  }
  // 答对数不能超过该维度题数，避免「答对 5 / 3 题」这类矛盾数据进入页面。
  if (typeof item.correct === 'number' && typeof item.total === 'number' && item.correct > item.total) {
    return false
  }
  return true
}

/**
 * 校验报告响应。
 * 只接受契约必填字段与合法的可选取值；扩展字段缺失是允许的（页面按「待接口返回」降级），
 * 但字段存在时类型和范围必须合法，否则整份报告按格式错误处理，不用残缺数据渲染图表。
 */
function isReport(value: unknown): value is Report {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Record<string, unknown>

  if (typeof candidate.id !== 'string' || !candidate.id.trim()) return false
  if (typeof candidate.roleId !== 'string' || !candidate.roleId.trim()) return false
  if (typeof candidate.roleName !== 'string' || !candidate.roleName.trim()) return false
  if (typeof candidate.submittedAt !== 'string' || !candidate.submittedAt.trim()) return false
  if (candidate.score !== undefined && !isScore(candidate.score)) return false
  if (!isOptionalCount(candidate.correctCount) || !isOptionalCount(candidate.questionCount)) {
    return false
  }
  if (
    typeof candidate.correctCount === 'number' &&
    typeof candidate.questionCount === 'number' &&
    candidate.correctCount > candidate.questionCount
  ) {
    return false
  }
  if (candidate.limitations !== undefined) {
    if (
      !Array.isArray(candidate.limitations) ||
      candidate.limitations.some((item) => typeof item !== 'string')
    ) {
      return false
    }
  }

  const { dimensions } = candidate
  if (!Array.isArray(dimensions) || dimensions.length !== REQUIRED_DIMENSIONS.length) return false
  if (!dimensions.every(isDimension)) return false

  const ids = dimensions.map((item) => (item as { id: string }).id)
  if (new Set(ids).size !== ids.length) return false
  return REQUIRED_DIMENSIONS.every((id) => ids.includes(id))
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
