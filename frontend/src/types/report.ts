/** 六个知识维度的固定标识，与 docs/design/api.md 中的岗位能力树保持一致。 */
export type DimensionId =
  | 'programming'
  | 'algorithms'
  | 'database'
  | 'network'
  | 'os'
  | 'software'

/**
 * 单个维度的得分。
 * correct / total / weight / priority 属于 T07 待确认的契约扩展字段，
 * 后端返回前一律视为可选，缺失时页面按「不可用」处理，不使用本地假数据补齐。
 */
export interface ReportDimension {
  id: DimensionId | string
  name: string
  score: number
  correct?: number
  total?: number
  weight?: number
  priority?: number
}

/**
 * 测评报告。必填字段以 docs/design/api.md 第 6 节为准，
 * 其余字段为 Issue #11 中提出、等待 T07 确认的扩展字段。
 */
export interface Report {
  id: string
  roleId: string
  roleName: string
  submittedAt: string
  dimensions: ReportDimension[]
  /** 综合分：按岗位权重加权，保留一位小数显示。 */
  score?: number
  correctCount?: number
  questionCount?: number
  blueprintVersion?: string
  modelVersion?: string
  reusedQuestionCount?: number
  limitations?: string[]
}
