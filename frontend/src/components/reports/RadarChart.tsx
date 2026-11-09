import type { ReportDimension } from '../../types/report'
import { scoreText, shortDimensionName } from '../../lib/reportUtils'

const CENTER = 180
const RADIUS = 104
const LABEL_RADIUS = 136
const GRID_SCALES = [0.25, 0.5, 0.75, 1]

interface RadarChartProps {
  dimensions: ReportDimension[]
}

/** 六维雷达图：使用内联 SVG 绘制，不引入第三方图表库，便于按需调整与无障碍标注。 */
export function RadarChart({ dimensions }: RadarChartProps) {
  const count = dimensions.length
  if (count === 0) return null

  const pointAt = (index: number, scale: number): [number, number] => {
    const angle = (index * 2 * Math.PI) / count - Math.PI / 2
    return [
      CENTER + Math.cos(angle) * RADIUS * scale,
      CENTER + Math.sin(angle) * RADIUS * scale,
    ]
  }

  const toPoints = (values: number[]): string =>
    values
      .map((value, index) => pointAt(index, Math.max(0, Math.min(100, value)) / 100).join(','))
      .join(' ')

  const label = dimensions.map((item) => `${item.name} ${scoreText(item.score)} 分`).join('，')

  return (
    <figure className="result-radar">
      <svg
        className="result-radar__svg"
        viewBox="0 0 360 360"
        role="img"
        aria-label={`六维知识表现：${label}`}
      >
        {GRID_SCALES.map((scale) => (
          <polygon
            key={scale}
            className="result-radar__grid"
            points={dimensions.map((_, index) => pointAt(index, scale).join(',')).join(' ')}
          />
        ))}

        {dimensions.map((dimension, index) => {
          const [x, y] = pointAt(index, 1)
          const [labelX, labelY] = pointAt(index, LABEL_RADIUS / RADIUS)
          const anchor = Math.abs(labelX - CENTER) < 8 ? 'middle' : labelX > CENTER ? 'start' : 'end'
          return (
            <g key={dimension.id}>
              <line className="result-radar__axis" x1={CENTER} y1={CENTER} x2={x} y2={y} />
              <text
                className="result-radar__label"
                x={labelX}
                y={labelY}
                textAnchor={anchor}
                dominantBaseline="middle"
              >
                {shortDimensionName(dimension)}
              </text>
            </g>
          )
        })}

        <polygon className="result-radar__area" points={toPoints(dimensions.map((item) => item.score))} />

        {dimensions.map((dimension, index) => {
          const [x, y] = pointAt(index, Math.max(0, Math.min(100, dimension.score)) / 100)
          return <circle key={dimension.id} className="result-radar__dot" cx={x} cy={y} r={4} />
        })}
      </svg>
      <figcaption className="result-radar__caption">
        各维度满分 100 分，维度分 = 该维度答对题数 ÷ 该维度题数 × 100。
      </figcaption>
    </figure>
  )
}
