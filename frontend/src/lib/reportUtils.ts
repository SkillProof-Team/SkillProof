import type { DimensionId, ReportDimension } from '../types/report'

/** 固定展示顺序：接口返回的数组顺序不作为图表与表格的排列依据。 */
export const DIMENSION_ORDER: DimensionId[] = [
  'programming',
  'algorithms',
  'database',
  'network',
  'os',
  'software',
]

/** 维度名过长时用于图表轴标签的短名。 */
const SHORT_NAME: Record<string, string> = {
  programming: '程序设计',
  algorithms: '算法',
  database: '数据库',
  network: '网络',
  os: '操作系统',
  software: '软件工程',
}

export function shortDimensionName(dimension: ReportDimension): string {
  return SHORT_NAME[dimension.id] ?? dimension.name
}

/** 按固定顺序排列维度，未知维度追加在末尾，保证六个维度不会因接口顺序变化而错位。 */
export function orderDimensions(dimensions: ReportDimension[]): ReportDimension[] {
  const known = DIMENSION_ORDER.map((id) => dimensions.find((item) => item.id === id)).filter(
    (item): item is ReportDimension => Boolean(item),
  )
  const rest = dimensions.filter((item) => !DIMENSION_ORDER.includes(item.id as DimensionId))
  return [...known, ...rest]
}

/** 分数展示：后端最多保留两位小数，前端不再降低精度。 */
export function scoreText(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

/** 比较两个维度的未舍入答对率，避免使用展示分数造成错误并列。 */
export function compareDimensionRatios(
  a: Pick<ReportDimension, 'correct' | 'total'>,
  b: Pick<ReportDimension, 'correct' | 'total'>,
): number {
  return a.correct * b.total - b.correct * a.total
}

/** 时间展示：统一按本地时区显示到分钟，后端返回 UTC ISO 字符串。 */
export function dateText(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * 取需要展示的薄弱项。
 * 输入顺序由后端契约保证：未舍入维度分升序，并列按固定维度顺序。
 * 默认取前 limit 项；如果第 limit 项与紧随其后的项同分，把并列项一并纳入。
 * 全部六项都并列时最多返回六项，不会无限扩展。
 */
export function selectWeakDimensions(
  weakDimensions: ReportDimension[],
  limit = 3,
): ReportDimension[] {
  if (weakDimensions.length <= limit) return weakDimensions

  const cutoff = weakDimensions[limit - 1]
  let end = limit
  while (
    end < weakDimensions.length &&
    compareDimensionRatios(weakDimensions[end], cutoff) === 0
  ) {
    end += 1
  }
  return weakDimensions.slice(0, end)
}

/** 并列项显示同一个名次：用于列表编号，避免同分项被编成 3、4、5。 */
export function rankLabels(items: ReportDimension[]): number[] {
  return items.reduce<number[]>((acc, item, index) => {
    const previous = items[index - 1]
    const tiedWithPrevious =
      previous !== undefined && compareDimensionRatios(previous, item) === 0
    acc.push(tiedWithPrevious ? acc[index - 1] : index + 1)
    return acc
  }, [])
}
