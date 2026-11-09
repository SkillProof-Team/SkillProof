import type { ReportDimension } from '../../types/report'
import { scoreText } from '../../lib/reportUtils'

interface DimensionBarsProps {
  dimensions: ReportDimension[]
}

/** 六维条形图：作为雷达图的数值补充，窄屏下可读性更好。 */
export function DimensionBars({ dimensions }: DimensionBarsProps) {
  if (dimensions.length === 0) return null

  return (
    <div className="result-bars">
      {dimensions.map((dimension) => {
        const value = Math.max(0, Math.min(100, dimension.score))
        return (
          <div className="result-bars__row" key={dimension.id}>
            <span className="result-bars__name">{dimension.name}</span>
            <span
              className="result-bars__track"
              role="meter"
              aria-label={`${dimension.name} 维度分`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(value * 10) / 10}
            >
              <span className="result-bars__fill" style={{ width: `${value}%` }} />
            </span>
            <span className="result-bars__value">{scoreText(dimension.score)}</span>
          </div>
        )
      })}
    </div>
  )
}
