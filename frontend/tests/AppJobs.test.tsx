import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import App from '../src/App'
import type { Catalog } from '../src/api'
import { stubFetch } from './stubFetch'

const catalog: Catalog = {
  dimensions: [{ id: 'programming', name: '程序设计', description: '程序语义与数据结构' }],
  roles: [
    {
      id: 'backend', name: '后端开发', description: '服务端程序与可靠接口',
      enabled: true, weights: { programming: 20 }, topics: { programming: ['队列与先进先出'] },
    },
    {
      id: 'frontend', name: '前端开发', description: '程序设计与网络交互',
      enabled: true, weights: { programming: 25 }, topics: { programming: ['引用与可变对象'] },
    },
    {
      id: 'qa', name: '测试开发', description: '测试方法与工程质量',
      enabled: false, topics: {},
    },
  ],
}

describe('App job selection', () => {
  test('shows the selected role details and sends the chosen role, with creation errors cleared on switch', async () => {
    window.history.replaceState(null, '', '/jobs')
    const user = { id: 'user-1', name: '测试用户', email: 'user@example.com' }
    const shortage = '该岗位知识点的已发布题库中程序设计的medium题不足1道，暂时无法创建测评'
    const fetchMock = stubFetch().mockImplementation(async (url, options) => {
      if (url === '/api/auth/me') return Response.json({ user, csrfToken: 'test-csrf' })
      if (url === '/api/catalog') return Response.json(catalog)
      if (url === '/api/attempts' && options?.method === 'POST') {
        const { roleId } = JSON.parse(String(options.body))
        if (roleId === 'frontend') return Response.json({ detail: shortage }, { status: 503 })
        return Response.json({ detail: '该岗位暂未开放测评' }, { status: 422 })
      }
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)

    const cards = await screen.findAllByRole('article')
    expect(within(cards[2]).getByRole<HTMLButtonElement>('button', { name: '暂未开放' }).disabled).toBe(true)
    fireEvent.click(within(cards[1]).getByRole('button', { name: '选择该岗位' }))
    const selection = within(await screen.findByRole('article', { name: '已选岗位' }))
    expect(selection.getByText('已选择：前端开发')).toBeTruthy()
    expect(selection.getByText('程序设计与网络交互')).toBeTruthy()
    expect(selection.getByText('岗位权重 25%')).toBeTruthy()
    expect(selection.getByText('引用与可变对象')).toBeTruthy()

    fireEvent.click(selection.getByRole('button', { name: '开始 / 继续测评' }))
    expect((await selection.findByRole('alert')).textContent).toBe(shortage)
    expect(fetchMock).toHaveBeenCalledWith('/api/attempts', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ roleId: 'frontend' }),
    }))

    fireEvent.click(within(cards[0]).getByRole('button', { name: '选择该岗位' }))
    await waitFor(() => expect(selection.getByText('已选择：后端开发')).toBeTruthy())
    expect(selection.getByText('服务端程序与可靠接口')).toBeTruthy()
    expect(selection.getByText('队列与先进先出')).toBeTruthy()
    expect(selection.queryByText(/岗位权重/)).toBeNull()
    expect(selection.queryByText('引用与可变对象')).toBeNull()
    expect(selection.queryByRole('alert')).toBeNull()

    fireEvent.click(selection.getByRole('button', { name: '开始 / 继续测评' }))
    expect((await selection.findByRole('alert')).textContent).toBe('该岗位暂未开放测评')
    expect(fetchMock).toHaveBeenCalledWith('/api/attempts', expect.objectContaining({
      method: 'POST', body: JSON.stringify({ roleId: 'backend' }),
    }))
  })
})
