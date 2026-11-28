import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { PopulationComparison } from '../src/components/reports/PopulationComparison'
import { DIMENSION_ORDER } from '../src/lib/reportUtils'
import { stubFetch } from './stubFetch'

test('switches reference mode, preserves individual data, shows signed differences and sample source', async () => {
  stubFetch().mockResolvedValueOnce(Response.json({ roleId: 'backend', sampleCount: 2,
    vector: Object.fromEntries(DIMENSION_ORDER.map((id) => [id, 50])), weight: 0, source: 'samples' }))
  const dimensions = DIMENSION_ORDER.map((id, i) => ({ id, name: id, score: i === 0 ? 60 : i === 1 ? 40 : 50, correct: 1, total: 2 }))
  render(<PopulationComparison roleId="backend" dimensions={dimensions} />)
  fireEvent.click(screen.getByRole('button', { name: '切换为群体对比' }))
  expect(await screen.findByText(/有效样本数：2/)).toBeTruthy()
  expect(screen.getByText('+10')).toBeTruthy()
  expect(screen.getByText('-10')).toBeTruthy()
  expect(screen.getByText(/仅由真实样本计算的均值/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '切换为个人画像' }))
  expect(screen.queryByRole('table')).toBeNull()
})

test('handles failure and retry without hiding the individual chart', async () => {
  stubFetch().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(Response.json({
    roleId: 'backend', sampleCount: 0, vector: Object.fromEntries(DIMENSION_ORDER.map((id) => [id, 50])), weight: 0, source: 'preset',
  }))
  render(<PopulationComparison roleId="backend" dimensions={[]} />)
  fireEvent.click(screen.getByRole('button', { name: '切换为群体对比' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  expect(await screen.findByText(/预设基准/)).toBeTruthy()
})
