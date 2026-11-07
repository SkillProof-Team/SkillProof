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

/** 分数展示：内部保留全精度，仅在显示时四舍五入到一位小数。 */
export function scoreText(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  const rounded = Math.round(value * 10) / 10
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)
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

export interface WeakDimension {
  dimension: ReportDimension
  /** 排序键：越大表示越需要优先提升。 */
  rank: number
  /** 是否使用后端返回的 priority；false 表示按维度分升序的临时口径。 */
  fromPriority: boolean
  /** 与相邻项排序键相同，即并列。 */
  tied: boolean
}

/**
 * 薄弱项排序。
 * 优先使用后端返回的 priority = 岗位权重 × (1 − 维度分 / 100)，降序排列；
 * 接口未返回 priority 时退回维度分升序，并在页面注明当前口径。
 * 并列时保持 DIMENSION_ORDER 的固定顺序，避免同一份报告每次排序结果不同。
 */
export function deriveWeakDimensions(dimensions: ReportDimension[]): WeakDimension[] {
  const ordered = orderDimensions(dimensions)
  const fromPriority = ordered.every((item) => typeof item.priority === 'number')
  const scored = ordered.map((dimension, index) => ({
    dimension,
    index,
    rank: fromPriority ? (dimension.priority as number) : 100 - dimension.score,
  }))

  scored.sort((a, b) => {
    if (b.rank !== a.rank) return b.rank - a.rank
    return a.index - b.index
  })

  return scored.map((item, index) => {
    const previous = scored[index - 1]
    const next = scored[index + 1]
    const tied =
      (previous !== undefined && previous.rank === item.rank) ||
      (next !== undefined && next.rank === item.rank)
    return { dimension: item.dimension, rank: item.rank, fromPriority, tied }
  })
}

/**
 * 取需要展示的薄弱项。
 * 默认取前 limit 项；如果第 limit 项与紧随其后的项排序键相同（并列），
 * 把并列项一并纳入，避免「页面上标了并列、却只显示到第三名」的矛盾。
 * 全部六项都并列时最多返回六项，不会无限扩展。
 */
export function selectWeakDimensions(dimensions: ReportDimension[], limit = 3): WeakDimension[] {
  const all = deriveWeakDimensions(dimensions)
  if (all.length <= limit) return all

  const cutoff = all[limit - 1].rank
  let end = limit
  while (end < all.length && all[end].rank === cutoff) {
    end += 1
  }
  return all.slice(0, end)
}

/** 并列项显示同一个名次：用于列表编号，避免同分项被编成 3、4、5。 */
export function rankLabels(items: WeakDimension[]): number[] {
  return items.reduce<number[]>((acc, item, index) => {
    const previous = items[index - 1]
    const tiedWithPrevious = previous !== undefined && previous.rank === item.rank
    acc.push(tiedWithPrevious ? acc[index - 1] : index + 1)
    return acc
  }, [])
}
