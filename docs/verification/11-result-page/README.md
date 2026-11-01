# 结果页验证记录（#11）

这些截图用于 [#11 实现能力画像与薄弱项结果页](https://github.com/daybreakju9/SkillProof/issues/11) 的验收，
由前端在真实后端接口联调前，用**仓库外的临时 mock 接口**生成。

- 临时 mock 与截图脚本均放在仓库外，未提交任何示例数据或测试依赖
- 数据只用于验证渲染与异常分支，不代表真实测评结果
- 真实 `GET /api/reports/{id}` 联调后需要重新截取并更新本目录

| 文件 | 验证内容 |
| --- | --- |
| `01-desktop-1280.png` | 桌面 1280px：概览、雷达图、条形图、薄弱项、明细表、解释边界 |
| `02-mobile-390.png` | 手机 390px：单列排列，表格在容器内横向滚动，页面无横向溢出 |
| `03-dark-mode.png` | 深色模式：文字、图表线条与表格边框可读 |
| `04-unauthorized-401.png` | 未登录：提示返回登录页，不提供重试按钮 |
| `05-not-found-404.png` | 结果不存在或无权限：提示检查链接，不提供重试按钮 |
| `06-not-submitted-409.png` | 测评尚未提交 |
| `07-server-error-500.png` | 请求失败：提供「重新加载」重试 |
| `08-missing-fields-fallback.png` | 只返回契约基础字段（无综合分/权重/优先级）时的降级显示 |

复现方式：

```bash
cd frontend
npm run lint
npm run build
# 启动开发服务器后访问 /reports/{id}
```
