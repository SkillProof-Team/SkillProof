import { useEffect, useRef, useState } from 'react'
import { create_attempt, get_attempt, save_answers, submit_attempt } from '../../api'
import type { Answers, Attempt, Question } from './types'
import './assessment.css'

type Assessment_props = {
  role_id?: string
  attempt_id?: string
  on_result?: (id: string) => void
}

function same_answers(questions: Question[], left: Answers, right: Answers) {
  return questions.every((question) => {
    const a = left[question.id] ?? []
    const b = right[question.id] ?? []
    return a.length === b.length && a.every((id) => b.includes(id))
  })
}

function Assessment(props: Assessment_props) {
  return <Assessment_content key={`${props.attempt_id ?? ''}:${props.role_id ?? ''}`} {...props} />
}

function Assessment_content({ role_id, attempt_id, on_result }: Assessment_props) {
  const [current, set_current] = useState(0)
  const [answers, set_answers] = useState<Answers>({})
  const [attempt, set_attempt] = useState<Attempt | null>(null)
  const [loading, set_loading] = useState(Boolean(role_id || attempt_id))
  const [saving, set_saving] = useState(false)
  const [submitting, set_submitting] = useState(false)
  const [error, set_error] = useState('')
  const [retry, set_retry] = useState(0)
  const pending = useRef(false)
  const request = useRef<AbortController | null>(null)
  const questions = attempt?.questions ?? []
  const total = questions.length
  const index = Math.max(0, Math.min(current, total - 1))
  const question = questions[index]
  const selected = question ? answers[question.id] ?? [] : []
  const answered = questions.filter((item) => (answers[item.id]?.length ?? 0) > 0).length
  const progress = total > 0 ? Math.round((answered / total) * 100) : 0
  const saved = questions.filter((item) => (attempt?.answers[item.id]?.length ?? 0) > 0).length
  const changed = attempt ? !same_answers(questions, answers, attempt.answers) : false
  const submitted = attempt?.status === 'submitted'
  const busy = saving || submitting

  useEffect(() => {
    if (!attempt_id && !role_id) return
    const controller = new AbortController()
    request.current = controller
    const load = attempt_id
      ? get_attempt(attempt_id, controller.signal)
      : create_attempt(role_id!, controller.signal)

    load.then((data) => {
      if (controller.signal.aborted) return
      set_attempt(data)
      set_answers(data.answers)
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        set_error(error instanceof Error ? error.message : '加载测评失败，请重试')
      }
    }).finally(() => {
      if (!controller.signal.aborted) set_loading(false)
    })
    return () => controller.abort()
  }, [attempt_id, role_id, retry])

  function reload() {
    set_loading(true)
    set_error('')
    set_retry((value) => value + 1)
  }

  function choose_option(option_id: string) {
    if (!question || submitted || pending.current) return
    set_error('')

    set_answers((prev) => {
      const old = prev[question.id] ?? []
      let next: string[]

      if (question.type === 'single') {
        next = [option_id]
      } else if (old.includes(option_id)) {
        next = old.filter((id) => id !== option_id)
      } else {
        next = [...old, option_id]
      }

      return { ...prev, [question.id]: next }
    })
  }

  async function store_answers(signal?: AbortSignal) {
    if (!attempt) return null
    // 空数组也要发送，服务器才会清除该题原来保存的答案。
    const choices = Object.fromEntries(questions.map((item) => [item.id, answers[item.id] ?? []]))
    const data = await save_answers(attempt.id, choices, signal)
    if (signal?.aborted) return null
    if (data.roleId !== attempt.roleId || data.questions.length !== total
      || data.questions.some((item) => !questions.some((question) => question.id === item.id))) {
      throw new Error('服务器返回的题目与当前测评不一致，请重新进入测评')
    }
    if (data.status === 'submitted') throw new Error('测评已经提交，不能再保存答案')
    if (!same_answers(questions, choices, data.answers)) {
      throw new Error('服务器尚未确认全部答案，请重新保存')
    }
    set_attempt(data)
    return data
  }

  async function save() {
    if (!question || submitted || pending.current) return
    const signal = request.current?.signal
    pending.current = true
    set_saving(true)
    set_error('')
    try {
      await store_answers(signal)
    } catch (error) {
      if (!signal?.aborted) set_error(error instanceof Error ? error.message : '保存答案失败，请重试')
    } finally {
      pending.current = false
      if (!signal?.aborted) set_saving(false)
    }
  }

  async function submit() {
    if (!attempt || !question || submitted || pending.current) return
    const missing = questions.findIndex((item) => !(answers[item.id]?.length))
    if (missing !== -1) {
      set_current(missing)
      set_error(`还有 ${total - answered} 题未作答，请先完成第 ${missing + 1} 题`)
      return
    }
    const signal = request.current?.signal
    pending.current = true
    set_submitting(true)
    set_error('')
    try {
      const data = await store_answers(signal)
      if (!data || signal?.aborted) return
      await submit_attempt(data.id, signal)
      if (!signal?.aborted) set_attempt({ ...data, status: 'submitted' })
    } catch (error) {
      if (signal?.aborted) return
      // 请求中断时服务器可能已经提交成功，再查询一次确认状态。
      const latest = await get_attempt(attempt.id, signal).catch(() => null)
      if (signal?.aborted) return
      if (latest?.status === 'submitted') {
        set_attempt(latest)
        set_answers(latest.answers)
        return
      }
      if (!signal?.aborted) set_error(error instanceof Error ? error.message : '提交测评失败，请重试')
    } finally {
      pending.current = false
      if (!signal?.aborted) set_submitting(false)
    }
  }

  return (
    <main className="assessment">
      <header className="assessment-header">
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
          <p>{attempt ? '接口未返回题目，暂时无法作答或提交。' : '需要岗位 ID 创建测评，或测评 ID 恢复答题。'}</p>
          {(role_id || attempt_id) && <button type="button" onClick={reload}>重新加载</button>}
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
                      onChange={() => choose_option(option.id)}
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
                    set_answers((prev) => ({ ...prev, [question.id]: [] }))
                    set_error('')
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
                      onClick={() => set_current(position)}
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
          onClick={() => set_current(index - 1)}
        >
          上一题
        </button>
        <button
          type="button"
          disabled={loading || !question || index === total - 1}
          onClick={() => set_current(index + 1)}
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
          {submitted && !on_result && <p>结果页尚未接入。</p>}
        </div>
        <div className="assessment-actions">
          <button type="button" disabled={loading || !question || busy || submitted || !changed} onClick={save} aria-describedby="assessment-submit-note">
            {saving ? '保存中…' : '保存答案'}
          </button>
          <button type="button" disabled={loading || !question || busy || submitted} onClick={submit} aria-describedby="assessment-submit-note">
            {submitting ? '提交中…' : '提交测评'}
          </button>
          {submitted && on_result && attempt && (
            <button type="button" onClick={() => on_result(attempt.id)}>查看结果</button>
          )}
        </div>
      </section>
    </main>
  )
}

export default Assessment
