import { useEffect, useState } from 'react'
import { apiRequest } from '../../api'
import type { ReportDimension } from '../../types/report'
import { DIMENSION_ORDER, scoreText } from '../../lib/reportUtils'
import { RadarChart } from './RadarChart'

type Population = {
  roleId: string
  sampleCount: number
  source: 'preset' | 'weighted' | 'samples'
  vector: Record<string, number>
  weight: number
}

export function PopulationComparison({ roleId, dimensions }: {
  roleId: string; dimensions: ReportDimension[]
}) {
  const [compare, setCompare] = useState(false)
  const [reload, setReload] = useState(0)
  const [state, setState] = useState<{ roleId: string; data?: Population; error?: string }>()
  useEffect(() => {
    const controller = new AbortController()
    apiRequest<Population>(`/roles/${encodeURIComponent(roleId)}/population`, {
      signal: controller.signal, authenticated: true,
    }).then((data) => {
      if (controller.signal.aborted) return
      if (data.roleId !== roleId || !Number.isInteger(data.sampleCount) || data.sampleCount < 0 ||
        !['preset', 'weighted', 'samples'].includes(data.source) ||
        !data.vector || DIMENSION_ORDER.some((id) => !Number.isFinite(data.vector[id]) ||
          data.vector[id] < 0 || data.vector[id] > 100)) throw new Error('群体数据格式无效')
      setState({ roleId, data })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ roleId, error: error instanceof Error ? error.message : '加载失败' })
    })
    return () => controller.abort()
  }, [roleId, reload])
  const data = state?.roleId === roleId ? state.data : undefined
  return <div>
    <button type="button" className="result-state__action" aria-pressed={compare}
      onClick={() => setCompare(!compare)}>{compare ? '切换为个人画像' : '切换为群体对比'}</button>
    <RadarChart dimensions={dimensions} reference={compare && data ? data.vector : undefined} />
    {compare && !data && (state?.roleId === roleId && state.error
      ? <p role="alert">{state.error} <button onClick={() => { setState(undefined); setReload(reload + 1) }}>重试</button></p>
      : <p role="status">正在加载同岗位群体参考…</p>)}
    {compare && data && <>
      <p>有效样本数：{data.sampleCount}。{data.source === 'preset' ? '预设基准（暂无有效用户）'
        : data.source === 'weighted' ? `含预设权重的群体参考值（虚拟样本权重 ${data.weight}）` : '仅由真实样本计算的均值'}。</p>
      <p>紫色实线为本次个人结果，橙色虚线为同岗位群体参考。每名用户仅计入最新有效结果，群体包含本人。差值不代表岗位胜任力。</p>
      <div className="result-table-wrap"><table className="result-table">
        <caption>个人与同岗位群体六维对比</caption>
        <thead><tr><th>维度</th><th>个人得分</th><th>群体参考</th><th>差值（个人减群体）</th></tr></thead>
        <tbody>{dimensions.map((d) => {
          const delta = d.score - data.vector[d.id]
          return <tr key={d.id}><th scope="row">{d.name}</th><td>{scoreText(d.score)}</td>
            <td>{scoreText(data.vector[d.id])}</td><td>{delta > 0 ? '+' : ''}{scoreText(delta)}</td></tr>
        })}</tbody>
      </table></div>
    </>}
  </div>
}
