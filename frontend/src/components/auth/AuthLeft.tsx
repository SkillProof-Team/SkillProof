import Brand from './Brand'

export default function AuthLeft() {
  return (
    <aside className="left-panel">
      <header className="left-header">
        <Brand />
        <span className="alpha-tag">ALPHA</span>
      </header>
      <div className="left-content">
        <h1>从测评开始，<br />看清你的<span>能力结构。</span></h1>
        <p className="left-desc">
          基于岗位知识体系的能力测评，<br />
          帮助你发现优势与不足，找到下一步的学习方向。
        </p>
      </div>
    </aside>
  )
}
