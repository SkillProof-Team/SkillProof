/** 六个知识维度的固定标识，与 docs/design/api.md 中的岗位能力树保持一致。 */
export type DimensionId =
  | 'programming'
  | 'algorithms'
  | 'database'
  | 'network'
  | 'os'
  | 'software'

/** 单个维度的得分，字段与 T07 / PR #27 的报告快照契约一致。 */
export interface ReportDimension {
  id: DimensionId | string
  name: string
  score: number
  correct: number
  total: number
}

/** 测评报告，所有评分字段均由服务端快照提供，前端不重复计算。 */
export interface Report {
  id: string
  roleId: string
  roleName: string
  createdAt: string
  submittedAt: string
  modelVersion: string
  /** 按题目难度 1 / 2 / 5 加权后的综合分。 */
  score: number
  correctCount: number
  questionCount: number
  dimensions: ReportDimension[]
  /** 后端按未舍入维度分升序、固定维度顺序处理并列后的薄弱维度。 */
  weakDimensions: ReportDimension[]
}
