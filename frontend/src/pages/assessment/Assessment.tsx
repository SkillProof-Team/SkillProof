import { useEffect, useRef, useState } from 'react'
import { ApiError, getAttempt, saveAnswers, submitAttempt } from '../../api'
import type { Answers, Attempt, Question } from './types'
import './assessment.css'

type AssessmentProps = {
  attemptId: string
  onResult: (id: string) => void
  onBack: () => void
  registerNavigationGuard: (guard: (() => boolean) | null) => void
}

function sameAnswers(questions: Question[], left: Answers, right: Answers) {
  return questions.every((question) => {
    const a = left[question.id] ?? []
    const b = right[question.id] ?? []
    return a.length === b.length && a.every((id) => b.includes(id))
  })
}

function Assessment(props: AssessmentProps) {
  return <AssessmentContent key={props.attemptId} {...props} />
}

function AssessmentContent({ attemptId, onResult, onBack, registerNavigationGuard }: AssessmentProps) {
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Answers>({})
  const [attempt, setAttempt] = useState<Attempt | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const pending = useRef(false)
  const request = useRef<AbortController | null>(null)
  const resultShown = useRef(false)
  const questions = attempt?.questions ?? []
  const total = questions.length
  const index = Math.max(0, Math.min(current, total - 1))
  const question = questions[index]
  const selected = question ? answers[question.id] ?? [] : []
  const answered = questions.filter((item) => (answers[item.id]?.length ?? 0) > 0).length
  const progress = total > 0 ? Math.round((answered / total) * 100) : 0
  const saved = questions.filter((item) => (attempt?.answers[item.id]?.length ?? 0) > 0).length
  const changed = attempt ? !sameAnswers(questions, answers, attempt.answers) : false
  const submitted = attempt?.status === 'submitted'
  const busy = saving || submitting

  useEffect(() => {
    const controller = new AbortController()
    request.current = controller
    getAttempt(attemptId, controller.signal).then((data) => {
      if (controller.signal.aborted) return
      setAttempt(data)
      setAnswers(data.answers)
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        setError(error instanceof Error ? error.message : '加载测评失败，请重试')
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [attemptId, retry])

  useEffect(() => {
    if ((!changed && !busy) || submitted) return
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warnBeforeUnload)
    return () => window.removeEventListener('beforeunload', warnBeforeUnload)
  }, [changed, busy, submitted])

  useEffect(() => {
    registerNavigationGuard(() => {
      if (pending.current) {
        setError('正在保存或提交，请等待完成后再离开。')
        return false
      }
      if (changed && !submitted) {
        setError('有未保存的答案，请先保存后再离开。')
        return false
      }
      return true
    })
    return () => registerNavigationGuard(null)
  }, [changed, submitted, registerNavigationGuard])

  useEffect(() => {
    if (!submitted || !attempt || resultShown.current) return
    resultShown.current = true
    onResult(attempt.id)
  }, [submitted, attempt, onResult])

  function reload() {
    setLoading(true)
    setError('')
    setRetry((value) => value + 1)
  }

  function chooseOption(optionId: string) {
    if (!question || submitted || pending.current) return
    setError('')

    setAnswers((prev) => {
      const old = prev[question.id] ?? []
      let next: string[]

      if (question.type === 'single') {
        next = [optionId]
      } else if (old.includes(optionId)) {
        next = old.filter((id) => id !== optionId)
      } else {
        next = [...old, optionId]
      }

      return { ...prev, [question.id]: next }
    })
  }

  async function storeAnswers(signal?: AbortSignal) {
    if (!attempt) return null
    // 空数组也要发送，服务器才会清除该题原来保存的答案。
    const choices = Object.fromEntries(questions.map((item) => [item.id, answers[item.id] ?? []]))
    const data = await saveAnswers(attempt.id, choices, signal)
    if (signal?.aborted) return null
    if (data.roleId !== attempt.roleId || data.questions.length !== total
      || data.questions.some((item) => !questions.some((question) => question.id === item.id))) {
      throw new Error('服务器返回的题目与当前测评不一致，请重新进入测评')
    }
    if (data.status === 'submitted') throw new Error('测评已经提交，不能再保存答案')
    if (!sameAnswers(questions, choices, data.answers)) {
      throw new Error('服务器尚未确认全部答案，请重新保存')
    }
    setAttempt(data)
    return data
  }

  async function save() {
    if (!attempt || !question || submitted || pending.current) return
    const signal = request.current?.signal
    pending.current = true
    setSaving(true)
    setError('')
    try {
      await storeAnswers(signal)
    } catch (error) {
      if (signal?.aborted || (error instanceof ApiError && error.status === 401)) return
      if (error instanceof ApiError && error.status === 409) {
        const latest = await getAttempt(attempt.id, signal).catch(() => null)
        if (signal?.aborted) return
        if (latest?.status === 'submitted') {
          setAttempt(latest)
          setAnswers(latest.answers)
          return
        }
      }
      setError(error instanceof Error ? error.message : '保存答案失败，请重试')
    } finally {
      pending.current = false
      if (!signal?.aborted) setSaving(false)
    }
  }

  async function submit() {
    if (!attempt || !question || submitted || pending.current) return
    const missing = questions.findIndex((item) => !(answers[item.id]?.length))
    if (missing !== -1) {
      setCurrent(missing)
      setError(`还有 ${total - answered} 题未作答，请先完成第 ${missing + 1} 题`)
      return
    }
    const signal = request.current?.signal
    pending.current = true
    setSubmitting(true)
    setError('')
    try {
      const data = await storeAnswers(signal)
      if (!data || signal?.aborted) return
      await submitAttempt(data.id, signal)
      if (!signal?.aborted) setAttempt({ ...data, status: 'submitted' })
    } catch (error) {
      if (signal?.aborted || (error instanceof ApiError && error.status === 401)) return
      // 请求中断时服务器可能已经提交成功，再查询一次确认状态。
      const latest = await getAttempt(attempt.id, signal).catch(() => null)
      if (signal?.aborted) return
      if (latest?.status === 'submitted') {
        setAttempt(latest)
        setAnswers(latest.answers)
        return
      }
      if (!signal?.aborted) setError(error instanceof Error ? error.message : '提交测评失败，请重试')
    } finally {
      pending.current = false
      if (!signal?.aborted) setSubmitting(false)
    }
  }

  return (
    <main className="assessment">
      <header className="assessment-header">
        <button type="button" disabled={busy} onClick={onBack}>返回岗位选择</button>
        <h1>能力测评</h1>
        <p>按题目提示选择答案，可通过题号检查和修改。</p>
        {attempt && <p>当前岗位：{attempt.roleName}</p>}
      </header>

      {error && <p className="assessment-error" role="alert">{error}</p>}

      {loading ? (
        <section className="assessment-panel assessment-empty" role="status">正在加载测评…</section>
      ) : !question ? (
        <section className="assessment-panel assessment-empty" role="status">
          <h2>{error ? '测评加载失败' : attempt ? '暂无测评题目' : '尚未加载测评'}</h2>
          <p>{attempt ? '接口未返回题目，暂时无法作答或提交。' : '请重试加载，或返回岗位选择。'}</p>
          <button type="button" onClick={reload}>重新加载</button>
        </section>
      ) : (
        <>
          <section className="assessment-panel assessment-progress" aria-label="答题进度">
            <div aria-live="polite">
              <span>已作答 {answered} / {total} 题</span>
              <span>{progress}%</span>
            </div>
            <progress aria-label="已作答题数" value={answered} max={total} />
            <p>服务器已保存 {saved} / {total} 题；{changed ? '当前有未保存的修改，离开前请保存。' : '当前没有未保存的修改。'}</p>
          </section>

          <div className="assessment-layout">
            <section className="assessment-panel assessment-question" aria-label="当前题目">
              <div className="assessment-meta">
                <span>第 {index + 1} / {total} 题</span>
                <span>{question.type === 'single' ? '单选题' : '多选题'}</span>
              </div>
              <h2 className="assessment-title">{question.stem}</h2>
              <fieldset className="assessment-options" key={question.id} disabled={busy || submitted}>
                <legend>
                  {question.type === 'single' ? '请选择一个选项' : '可选择多个选项'}
                </legend>
                {question.options.map((option) => (
                  <label
                    className={`assessment-option${selected.includes(option.id) ? ' selected' : ''}`}
                    key={option.id}
                  >
                    <input
                      type={question.type === 'single' ? 'radio' : 'checkbox'}
                      name={`question-${question.id}`}
                      value={option.id}
                      checked={selected.includes(option.id)}
                      onChange={() => chooseOption(option.id)}
                    />
                    <span>{option.text}</span>
                  </label>
                ))}
              </fieldset>
              <div className="assessment-actions">
                <button
                  type="button"
                  disabled={busy || submitted || selected.length === 0}
                  onClick={() => {
                    if (pending.current) return
                    setAnswers((prev) => ({ ...prev, [question.id]: [] }))
                    setError('')
                  }}
                >
                  清空本题
                </button>
              </div>
            </section>

            <aside className="assessment-panel assessment-card" aria-label="答题卡">
              <h2>答题卡</h2>
              <nav className="assessment-numbers" aria-label="题号导航">
                {questions.map((item, position) => {
                  const done = (answers[item.id]?.length ?? 0) > 0

                  return (
                    <button
                      type="button"
                      key={item.id}
                      className={`${done ? 'answered' : ''}${position === index ? ' current' : ''}`}
                      aria-label={`第 ${position + 1} 题，${done ? '已作答' : '未作答'}`}
                      aria-current={position === index ? 'step' : undefined}
                      onClick={() => setCurrent(position)}
                    >
                      {position + 1}
                    </button>
                  )
                })}
              </nav>
              <p>紫色底为已作答，紫色边框为当前题。</p>
              <p>还有 {total - answered} 题未作答。</p>
            </aside>
          </div>
        </>
      )}

      <div className="assessment-actions">
        <button
          type="button"
          disabled={loading || !question || index === 0}
          onClick={() => setCurrent(index - 1)}
        >
          上一题
        </button>
        <button
          type="button"
          disabled={loading || !question || index === total - 1}
          onClick={() => setCurrent(index + 1)}
        >
          下一题
        </button>
      </div>

      <section className="assessment-panel assessment-submit" aria-label="提交测评">
        <div>
          <h2>提交测评</h2>
          <p id="assessment-submit-note" role="status">
            {submitted
              ? '测评已提交，答案不可再修改。'
              : submitting ? '正在保存答案并提交测评…'
              : saving ? '正在保存答案…'
              : question ? `还有 ${total - answered} 题未作答。提交前会先保存全部答案。`
              : '题目加载完成后才可保存和提交。'}
          </p>
        </div>
        <div className="assessment-actions">
          <button type="button" disabled={loading || !question || busy || submitted || !changed} onClick={save} aria-describedby="assessment-submit-note">
            {saving ? '保存中…' : '保存答案'}
          </button>
          <button type="button" disabled={loading || !question || busy || submitted} onClick={submit} aria-describedby="assessment-submit-note">
            {submitting ? '提交中…' : '提交测评'}
          </button>
        </div>
      </section>
    </main>
  )
}

export default Assessment
