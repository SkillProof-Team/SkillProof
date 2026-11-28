# #67 岗位群体参考

每个岗位按用户选择 `submitted_at DESC, created_at DESC, id DESC` 的最新有效报告。损坏报告不入样本，回退至该用户上一条有效报告。六维必须齐全、无重复且分数为有限的 0–100 数值。没有样本时使用预设值（默认六维 50，虚拟权重 0），这是产品基准，并非真实统计。

提交测评时在同一事务更新当前用户向量及岗位汇总。查询时也重新核对快照，以覆盖旧数据、删除或损坏快照变化。SQLite 写事务保证同次统计使用一致快照。目前查询重建为线性扫描，适合课程数据规模，后续大规模部署可改为增量更新。

## 接口

- 登录用户：`GET /api/roles/{roleId}/population`
- 管理员：`PUT /api/admin/roles/{roleId}/population`，携带现有会话的 `X-CSRF-Token`。
- 配置体：`{"preset":{"programming":50,"algorithms":50,"database":50,"network":50,"os":50,"software":50},"weight":0}`。
- 权重支持 0–1000000 的有限数。配置持久化，更新后立即重新计算。
- 查询只返回 roleId、sampleCount、vector、preset、weight、source、updatedAt，无个人标识或答题数据。
- source：preset（无真实样本）、weighted（含虚拟样本）、samples（真实样本均值）。每个岗位独立，群体包含本人，每用户每岗位只占一份权重。

## 前端

结果页默认个人模式，按钮切换双曲线与六维对比明细。紫色实线为当前查看报告，橙色虚线为当前岗位群体参考。差值为本次报告分数减群体值，旧报告仍比较当前群体。显示样本数和基准来源。失败时保留个人结果并允许重试，组件卸载取消请求。

## 验证命令

`PYTHONPATH=backend:backend/tests python -m unittest discover -s backend/tests`

`cd frontend && npm run lint && npm run build && npm test`

管理员配置目前通过受保护 API 完成，不新增管理员管理界面。
