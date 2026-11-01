export type Question = {
  id: string
  dimension: string
  stem: string
  type: 'single' | 'multiple'
  options: {
    id: string
    text: string
  }[]
}

export type Answers = Record<string, string[]>

export type Attempt = {
  id: string
  roleId: string
  roleName: string
  status: 'in_progress' | 'submitted'
  questionCount: number
  answeredCount: number
  questions: Question[]
  answers: Answers
}

export type Assessment_result = {
  id: string
  roleId: string
  roleName: string
  submittedAt: string
  dimensions: { id: string; name: string; score: number }[]
}
