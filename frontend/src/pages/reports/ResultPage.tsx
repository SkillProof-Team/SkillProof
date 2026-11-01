import { useEffect, useState } from 'react'
import { RadarChart } from '../../components/reports/RadarChart'
import { DimensionBars } from '../../components/reports/DimensionBars'
import { fetchReport } from '../../lib/reportApi'
import type { ReportLoadError } from '../../lib/reportApi'
import { dateText, deriveWeakDimensions, orderDimensions, scoreText } from '../../lib/reportUtils'
import type { Report } from '../../types/report'
import '../../styles/report.css'

type PageState =
  | { status: 'loading' }
  | { status: 'ready'; report: Report }
  | { status: 'error'; error: ReportLoadError }

const ERROR_TITLE: Record<ReportLoadError['kind'], string> = {
  unauthorized: '需要登录后查看',
  notFound: '没有找到这份报告',
  conflict: '这次测评还没有结果',
  server: '报告加载失败',
  network: '网络连接失败',
}

interface ResultPageProps {
  attemptId: string
}

export function ResultPage({ attemptId }: ResultPageProps) {
  const [state, setState] = useState<PageState>({ status: 'loading' })
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    fetchReport(attemptId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return
        setState(
          result.ok
            ? { status: 'ready', report: result.report }
            : { status: 'error', error: result.error },
        )
      })
      .catch(() => {
        // 主动取消（切换报告或组件卸载）不更新界面。
      })

    return () => controller.abort()
  }, [attemptId, reloadToken])

  /** 重试时先回到加载态，再触发一次请求。 */
  const handleRetry = () => {
    setState({ status: 'loading' })
    setReloadToken((value) => value + 1)
  }

  if (state.status === 'loading') {
    return (
      <main className="result-page" aria-busy="true">
        <p className="result-state__hint">正在加载测评报告…</p>
        <div className="result-skeleton result-skeleton--title" />
        <div className="result-skeleton" />
        <div className="result-skeleton result-skeleton--chart" />
      </main>
    )
  }

  if (state.status === 'error') {
    const { error } = state
    const retryable = error.kind === 'network' || error.kind === 'server'
    return (
      <main className="result-page">
        <div className="result-state" role="alert">
          <h1 className="result-state__title">{ERROR_TITLE[error.kind]}</h1>
          <p className="result-state__message">{error.message}</p>
          {error.kind === 'unauthorized' && (
            <p className="result-state__hint">请返回登录页重新登录后，再打开这份测评报告。</p>
          )}
          {retryable && (
            <button type="button" className="result-state__action" onClick={handleRetry}>
              重新加载
            </button>
          )}
        </div>
      </main>
    )
  }

  const { report } = state
  const dimensions = orderDimensions(report.dimensions)

  if (dimensions.length === 0) {
    return (
      <main className="result-page">
        <div className="result-state" role="alert">
          <h1 className="result-state__title">报告数据不完整</h1>
          <p className="result-state__message">
            这份报告没有返回知识维度得分，暂时无法生成能力画像，请稍后重试或联系管理员。
          </p>
        </div>
      </main>
    )
  }

  const weakItems = deriveWeakDimensions(dimensions).slice(0, 3)
  const hasPriority = weakItems.every((item) => item.fromPriority)
  const allFullScore = dimensions.every((item) => item.score >= 100)
  const hasVersion = Boolean(report.blueprintVersion || report.modelVersion)

  return (
    <main className="result-page">
      <header className="result-header">
        <p className="result-header__eyebrow">测评报告</p>
        <h1 className="result-header__title">{report.roleName} · 能力画像</h1>
        <p className="result-header__meta">
          提交时间 {dateText(report.submittedAt)}
          {hasVersion && (
            <>
              {' · '}蓝图 {report.blueprintVersion ?? '—'}
              {' · '}权重模型 {report.modelVersion ?? '—'}
            </>
          )}
        </p>
      </header>

      <section className="result-stat-band" aria-label="总分概览">
        <div className="result-stat">
          <span className="result-stat__label">综合分</span>
          <strong className="result-stat__value">{scoreText(report.score)}</strong>
          <span className="result-stat__note">
            {report.score === undefined ? '综合分待接口返回' : '岗位加权分，0–100，不设及格线'}
          </span>
        </div>
        <div className="result-stat">
          <span className="result-stat__label">正确题数</span>
          <strong className="result-stat__value">
            {report.correctCount !== undefined && report.questionCount !== undefined
              ? `${report.correctCount} / ${report.questionCount}`
              : '—'}
          </strong>
          <span className="result-stat__note">多选题按正确选项集合完整计分</span>
        </div>
        <div className="result-stat">
          <span className="result-stat__label">本次重复题</span>
          <strong className="result-stat__value">
            {report.reusedQuestionCount !== undefined ? `${report.reusedQuestionCount} 道` : '—'}
          </strong>
          <span className="result-stat__note">曾作答的题目可能带来记忆效应</span>
        </div>
      </section>

      <p className="result-notice">
        本页只描述本次抽取题目的作答表现，不代表完整工程能力、岗位胜任力或就业概率。
      </p>

      <section className="result-section" aria-labelledby="result-charts-title">
        <h2 className="result-section__title" id="result-charts-title">
          六维知识表现
        </h2>
        <div className="result-charts">
          <RadarChart dimensions={dimensions} />
          <DimensionBars dimensions={dimensions} />
        </div>
      </section>

      <section className="result-section" aria-labelledby="result-weak-title">
        <h2 className="result-section__title" id="result-weak-title">
          薄弱维度与优先提升方向
        </h2>
        {allFullScore ? (
          <p className="result-empty">六个维度均为满分，本次没有需要优先补强的维度。</p>
        ) : (
          <ol className="result-weak">
            {weakItems.map((item, index) => (
              <li className="result-weak__item" key={item.dimension.id}>
                <span className="result-weak__rank" aria-hidden="true">
                  {index + 1}
                </span>
                <div className="result-weak__body">
                  <p className="result-weak__name">
                    {item.dimension.name}
                    <span className="result-weak__score">维度分 {scoreText(item.dimension.score)}</span>
                    {item.tied && <span className="result-weak__tie">并列</span>}
                  </p>
                  <p className="result-weak__detail">
                    {item.dimension.correct !== undefined && item.dimension.total !== undefined
                      ? `答对 ${item.dimension.correct} / ${item.dimension.total} 题，建议优先复习该维度的知识点与错题解析。`
                      : '建议优先复习该维度的知识点与错题解析。'}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="result-hint">
          {hasPriority
            ? '排序依据：岗位权重 ×（1 − 维度分 ÷ 100），数值越大越需要优先提升；并列时按固定维度顺序排列。该值只用于排序，不代表学习效果或所需时间。'
            : '当前接口未返回岗位权重与优先级值，暂按维度分升序排列；待评分接口补充 priority 后改为按岗位权重计算。'}
        </p>
      </section>

      <section className="result-section" aria-labelledby="result-table-title">
        <h2 className="result-section__title" id="result-table-title">
          维度得分明细
        </h2>
        <div className="result-table-wrap">
          <table className="result-table">
            <caption className="result-visually-hidden">六个知识维度的答对数、维度分、岗位权重与学习优先级值</caption>
            <thead>
              <tr>
                <th scope="col">知识维度</th>
                <th scope="col">答对 / 题数</th>
                <th scope="col">维度分</th>
                <th scope="col">岗位权重</th>
                <th scope="col">学习优先级值</th>
              </tr>
            </thead>
            <tbody>
              {dimensions.map((dimension) => (
                <tr key={dimension.id}>
                  <th scope="row">{dimension.name}</th>
                  <td>
                    {dimension.correct !== undefined && dimension.total !== undefined
                      ? `${dimension.correct} / ${dimension.total}`
                      : '—'}
                  </td>
                  <td>{scoreText(dimension.score)}</td>
                  <td>{dimension.weight !== undefined ? `${dimension.weight}%` : '—'}</td>
                  <td>{scoreText(dimension.priority)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="result-table-hint">表格可左右滑动查看完整列</p>
      </section>

      {report.limitations && report.limitations.length > 0 && (
        <section className="result-section" aria-labelledby="result-limitations-title">
          <h2 className="result-section__title" id="result-limitations-title">
            解释边界
          </h2>
          <ul className="result-limitations">
            {report.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  )
}
