const {
  launchBrowser
} = require('./browser.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const root = process.env.SKILLPROOF_QA_RUN,
  origin = process.env.SKILLPROOF_QA_ORIGIN;
const password = 'report-browser-test-password';
const stamp = Date.now();
const owner = {
  email: `report-${stamp}@example.invalid`,
  name: '结果验收用户',
  password
};
const key = JSON.parse(fs.readFileSync(process.env.SKILLPROOF_QA_ANSWERS, 'utf8'));
const correctIds = new Set(['programming-easy-1', 'programming-easy-2', 'programming-medium', 'algorithms-easy-1', 'database-easy-1', 'database-easy-2', 'network-medium', 'software-medium']);
const mixed = Object.fromEntries(Object.entries(key).map(([id, answer]) => [id, correctIds.has(id) ? answer : id.endsWith('medium') ? ['B', 'D'] : ['D']]));
const names = ['程序设计', '算法基础', '数据库', '计算机网络', '操作系统', '软件工程'];
const scores = [100, 33.33, 66.67, 33.33, 0, 33.33],
  counts = [3, 1, 2, 1, 0, 1];
const cases = [];
let browser, baseReport;
async function ready(page) {
  await page.getByRole('heading', {
    name: '后端开发 · 能力画像',
    exact: true
  }).waitFor();
}
async function login(page, user = owner) {
  await page.goto(origin + '/login');
  await page.getByRole('heading', {
    name: '欢迎回来',
    exact: true
  }).waitFor();
  await page.getByLabel('邮箱', {
    exact: true
  }).fill(user.email);
  await page.getByLabel('密码', {
    exact: true
  }).fill(password);
  await page.getByRole('button', {
    name: '登录',
    exact: true
  }).click();
  await page.getByRole('heading', {
    name: '选择目标岗位',
    exact: true
  }).waitFor();
}
async function openReport(page) {
  await login(page);
  await page.goto(origin + '/reports/' + baseReport.id);
}
async function validateMixed(page) {
  await ready(page);
  const values = await page.locator('.result-stat__value').allTextContents();
  assert.equal(values[0].trim(), '45.83');
  assert.equal(values[1].replace(/\s/g, ''), '8/18');
  const rows = await page.locator('.result-table tbody tr').evaluateAll(xs => xs.map(row => ({
    name: row.querySelector('th').textContent.trim(),
    cells: [...row.querySelectorAll('td')].map(x => x.textContent.trim())
  })));
  assert.equal(rows.length, 6);
  for (let i = 0; i < 6; i++) {
    assert.equal(rows[i].name, names[i]);
    assert.equal(rows[i].cells[0].replace(/\s/g, ''), counts[i] + '/3');
    assert.equal(Number(rows[i].cells[1]), scores[i]);
  }
  assert.deepEqual((await page.locator('.result-bars__value').allTextContents()).map(Number), scores);
  assert.deepEqual(await page.locator('.result-bars__fill').evaluateAll(xs => xs.map(x => parseFloat(x.style.width))), scores);
  const radar = await page.getByRole('img', {
    name: /六维知识表现/
  }).getAttribute('aria-label');
  for (let i = 0; i < 6; i++) assert.ok(radar.includes(names[i] + ' ' + scores[i]));
  assert.equal(await page.locator('.result-radar__dot').count(), 6);
  assert.deepEqual(await page.locator('.result-weak__name').evaluateAll(xs => xs.map(x => x.childNodes[0].textContent.trim())), ['操作系统', '算法基础', '计算机网络', '软件工程']);
  assert.deepEqual((await page.locator('.result-weak__rank').allTextContents()).map(x => x.trim()), ['1', '2', '2', '2']);
  assert.match(await page.locator('.result-notice').innerText(), /不代表.*岗位胜任力/);
}
async function newReport(page, allCorrect) {
  const auth = await (await page.request.get(origin + '/api/auth/me')).json();
  const headers = {
    Origin: origin,
    'X-CSRF-Token': auth.csrfToken
  };
  let response = await page.request.post(origin + '/api/attempts', {
    headers,
    data: {
      roleId: 'backend'
    }
  });
  assert.equal(response.status(), 200);
  const attempt = await response.json();
  const answers = Object.fromEntries(attempt.questions.map(q => [q.id, allCorrect ? key[q.id] : q.type === 'multiple' ? ['B', 'D'] : ['D']]));
  response = await page.request.put(origin + '/api/attempts/' + attempt.id + '/answers', {
    headers,
    data: {
      answers,
      expectedVersion: attempt.answersVersion
    }
  });
  assert.equal(response.status(), 200);
  response = await page.request.post(origin + '/api/attempts/' + attempt.id + '/submit', {
    headers
  });
  assert.equal(response.status(), 200);
  return response.json();
}
async function check(id, name, fn, mobile = false) {
  const context = await browser.newContext({
    viewport: mobile ? {
      width: 390,
      height: 844
    } : {
      width: 1280,
      height: 900
    },
    timezoneId: 'Asia/Shanghai',
    locale: 'zh-CN'
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  const errors = [],
    consoleErrors = [],
    apiResponses = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('response', r => {
    if (r.url().includes('/api/')) apiResponses.push({
      path: new URL(r.url()).pathname,
      status: r.status()
    });
  });
  const item = {
    id,
    name,
    status: 'pass',
    mode: 'real services and isolated test bank'
  };
  try {
    const extra = await fn(page);
    if (extra) Object.assign(item, extra);
    assert.deepEqual(errors, []);
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
  } catch (e) {
    item.status = 'fail';
    item.error = e.message;
    await page.screenshot({
      path: root + '/evidence/' + id + '-failure.png'
    }).catch(() => {});
  }
  item.url = page.url();
  item.pageErrors = errors;
  item.consoleErrors = consoleErrors;
  item.apiResponses = apiResponses;
  cases.push(item);
  fs.writeFileSync(root + '/results/browser-result.json', JSON.stringify({
    cases
  }, null, 2));
  console.log(JSON.stringify({
    id,
    name,
    status: item.status,
    error: item.error
  }));
  await context.close();
}
(async () => {
  browser = await launchBrowser();
  await check('RESULT-UI-01', '真实页面注册到答题、保存刷新、提交及45.83分结果图表', async page => {
    await page.goto(origin + '/register');
    await page.getByRole('heading', {
      name: '创建账号',
      exact: true
    }).waitFor();
    await page.getByLabel('邮箱', {
      exact: true
    }).fill(owner.email);
    await page.getByLabel('姓名', {
      exact: true
    }).fill(owner.name);
    await page.getByLabel('密码', {
      exact: true
    }).fill(password);
    await page.getByRole('button', {
      name: '注册',
      exact: true
    }).click();
    await page.getByRole('heading', {
      name: '选择目标岗位',
      exact: true
    }).waitFor();
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '已选择',
      exact: true
    }).waitFor();
    const creation = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/attempts');
    await page.getByRole('button', {
      name: /开始.*测评/
    }).click();
    const response = await creation;
    assert.equal(response.status(), 200);
    const attempt = await response.json();
    await page.locator('.assessment-options').waitFor();
    async function answer(index) {
      const q = attempt.questions[index];
      await page.getByRole('button', {
        name: new RegExp(`^第 ${index + 1} 题，`)
      }).click();
      for (const letter of mixed[q.id]) await page.getByRole(q.type === 'single' ? 'radio' : 'checkbox', {
        name: '选项 ' + letter,
        exact: true
      }).check();
    }
    for (let i = 0; i < 17; i++) await answer(i);
    const saving = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith('/answers'));
    await page.getByRole('button', {
      name: '保存答案',
      exact: true
    }).click();
    assert.equal((await saving).status(), 200);
    await page.getByText(/当前没有未保存的修改/).waitFor();
    await page.reload();
    await page.locator('.assessment-options').waitFor();
    await page.getByText(/服务器已保存 17 \/ 18 题/).waitFor();
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await page.getByRole('alert').filter({
      hasText: '还有 1 题未作答'
    }).waitFor();
    await answer(17);
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await page.waitForURL('**/reports/' + attempt.id);
    const reportResponse = await page.request.get(origin + '/api/reports/' + attempt.id);
    assert.equal(reportResponse.status(), 200);
    const report = await reportResponse.json();
    assert.equal(report.score, 45.83);
    assert.equal(report.correctCount, 8);
    assert.equal(report.questionCount, 18);
    assert.deepEqual(report.dimensions.map(d => d.score), scores);
    await validateMixed(page);
    baseReport = report;
    fs.writeFileSync(root + '/results/real-report.json', JSON.stringify(report, null, 2));
    await page.screenshot({
      path: root + '/evidence/result-desktop.png'
    });
  });
  if (!baseReport) throw Error('Real-flow baseline failed; dependent report checks were not executed.');
  await check('RESULT-UI-02', '报告直接打开和刷新后数据一致', async page => {
    await openReport(page);
    await validateMixed(page);
    await page.reload();
    await validateMixed(page);
    const r = await page.request.get(origin + '/api/reports/' + baseReport.id);
    assert.deepEqual(await r.json(), baseReport);
  });
  await check('RESULT-UI-03', '真实跨账号访问报告返回404且不展示图表', async page => {
    const other = {
      email: `report-other-${stamp}@example.invalid`,
      name: '其他结果用户',
      password
    };
    const r = await fetch(origin + '/api/auth/register', {
      method: 'POST',
      headers: {
        Origin: origin,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(other)
    });
    assert.equal(r.status, 201);
    await login(page, other);
    const denied = page.waitForResponse(r => r.url().endsWith('/api/reports/' + baseReport.id));
    await page.goto(origin + '/reports/' + baseReport.id);
    assert.equal((await denied).status(), 404);
    await page.getByRole('heading', {
      name: '没有找到这份报告',
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.result-radar__svg').count(), 0);
  });
  await check('RESULT-UI-04', '本人未提交测评查询结果返回409并明确提示', async page => {
    await login(page);
    const auth = await (await page.request.get(origin + '/api/auth/me')).json();
    const r = await page.request.post(origin + '/api/attempts', {
      headers: {
        Origin: origin,
        'X-CSRF-Token': auth.csrfToken
      },
      data: {
        roleId: 'backend'
      }
    });
    assert.equal(r.status(), 200);
    const attempt = await r.json();
    const waiting = page.waitForResponse(r => r.url().endsWith('/api/reports/' + attempt.id));
    await page.goto(origin + '/reports/' + attempt.id);
    assert.equal((await waiting).status(), 409);
    await page.getByRole('heading', {
      name: '这次测评还没有结果',
      exact: true
    }).waitFor();
  });
  await check('RESULT-UI-05', '访客直接访问报告路由进入登录页', async page => {
    await page.goto(origin + '/reports/' + baseReport.id);
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/login');
  });
  await check('RESULT-UI-06', '报告加载中有明确提示，完成后显示真实图表', async page => {
    await login(page);
    let release;
    const gate = new Promise(r => release = r);
    await page.route('**/api/reports/**', async route => {
      await gate;
      await route.continue().catch(() => {});
    });
    try {
      await page.goto(origin + '/reports/' + baseReport.id);
      await page.getByText('正在加载测评报告…', {
        exact: true
      }).waitFor();
      assert.equal(await page.locator('.result-radar__svg').count(), 0);
    } finally {
      release();
    }
    await validateMixed(page);
    return {
      mode: 'controlled delay of the real report request'
    };
  });
  await check('RESULT-UI-07', '报告503错误提示和真实重试恢复', async page => {
    await login(page);
    await page.route('**/api/reports/**', route => route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: '测试服务暂不可用'
      })
    }));
    await page.goto(origin + '/reports/' + baseReport.id);
    await page.getByRole('heading', {
      name: '报告加载失败',
      exact: true
    }).waitFor();
    await page.unroute('**/api/reports/**');
    await page.getByRole('button', {
      name: '重新加载',
      exact: true
    }).click();
    await validateMixed(page);
    return {
      mode: 'explicit 503 response injection followed by a real request'
    };
  });
  await check('RESULT-UI-08', '报告网络失败提示和真实重试恢复', async page => {
    await login(page);
    await page.route('**/api/reports/**', route => route.abort('failed'));
    await page.goto(origin + '/reports/' + baseReport.id);
    await page.getByRole('heading', {
      name: '网络连接失败',
      exact: true
    }).waitFor();
    await page.unroute('**/api/reports/**');
    await page.getByRole('button', {
      name: '重新加载',
      exact: true
    }).click();
    await validateMixed(page);
    return {
      mode: 'explicit browser request abort followed by a real request'
    };
  });
  await check('RESULT-UI-09', '报告请求401和403分别提示且不显示图表', async page => {
    await login(page);
    let code = 401;
    await page.route('**/api/reports/**', route => route.fulfill({
      status: code,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: '测试权限错误'
      })
    }));
    await page.goto(origin + '/reports/' + baseReport.id);
    await page.getByRole('heading', {
      name: '需要登录后查看',
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.result-radar__svg').count(), 0);
    code = 403;
    await page.reload();
    await page.getByRole('heading', {
      name: '无权查看这份报告',
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.result-radar__svg').count(), 0);
    return {
      mode: 'explicit 401/403 response injection for the report component'
    };
  });
  await check('RESULT-UI-10', '报告维度顺序变化时仍按ID正确显示图表和明细', async page => {
    await login(page);
    const shuffled = structuredClone(baseReport);
    shuffled.dimensions.reverse();
    await page.route('**/api/reports/**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(shuffled)
    }));
    await page.goto(origin + '/reports/' + baseReport.id);
    await validateMixed(page);
    return {
      mode: 'controlled reordering of the verified real report payload'
    };
  });
  await check('RESULT-UI-11', '缺维度、分数越界、汇总矛盾及薄弱项乱序不进入图表', async page => {
    await login(page);
    const examples = [];
    let data = structuredClone(baseReport);
    data.dimensions.pop();
    examples.push(data);
    data = structuredClone(baseReport);
    data.dimensions[0].score = 120;
    examples.push(data);
    data = structuredClone(baseReport);
    data.correctCount = 99;
    examples.push(data);
    data = structuredClone(baseReport);
    data.weakDimensions.reverse();
    examples.push(data);
    let payload;
    await page.route('**/api/reports/**', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload)
    }));
    for (payload of examples) {
      await page.goto(origin + '/reports/' + baseReport.id);
      await page.getByRole('heading', {
        name: '报告加载失败',
        exact: true
      }).waitFor();
      assert.match(await page.getByRole('alert').innerText(), /格式|完整/);
      assert.equal(await page.locator('.result-radar__svg').count(), 0);
    }
    return {
      mode: 'four explicitly malformed report payloads; one grouped data-validation scenario'
    };
  });
  await check('RESULT-UI-12', '真实全对报告显示100分且无薄弱项', async page => {
    await login(page);
    const report = await newReport(page, true);
    assert.equal(report.score, 100);
    assert.equal(report.correctCount, 18);
    await page.goto(origin + '/reports/' + report.id);
    await ready(page);
    assert.equal((await page.locator('.result-stat__value').first().innerText()).trim(), '100');
    assert.equal((await page.locator('.result-stat__value').nth(1).innerText()).replace(/\s/g, ''), '18/18');
    await page.getByText('六个维度均为满分，本次没有需要优先补强的维度。', {
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.result-weak__item').count(), 0);
  });
  await check('RESULT-UI-13', '真实全错报告显示0分，六维并列全部列出', async page => {
    await login(page);
    const report = await newReport(page, false);
    assert.equal(report.score, 0);
    assert.equal(report.correctCount, 0);
    await page.goto(origin + '/reports/' + report.id);
    await ready(page);
    assert.equal((await page.locator('.result-stat__value').first().innerText()).trim(), '0');
    assert.equal((await page.locator('.result-stat__value').nth(1).innerText()).replace(/\s/g, ''), '0/18');
    assert.equal(await page.locator('.result-weak__item').count(), 6);
    assert.deepEqual((await page.locator('.result-weak__rank').allTextContents()).map(x => x.trim()), ['1', '1', '1', '1', '1', '1']);
  });
  await check('RESULT-UI-14', '390px真实结果页数值、图表和布局可用', async page => {
    await openReport(page);
    await validateMixed(page);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({
      path: root + '/evidence/result-mobile.png'
    });
    await page.locator('.result-charts').scrollIntoViewIfNeeded();
    await page.screenshot({
      path: root + '/evidence/result-mobile-charts.png'
    });
  }, true);
  const summary = {
    total: cases.length,
    pass: cases.filter(c => c.status === 'pass').length,
    fail: cases.filter(c => c.status === 'fail').length
  };
  fs.writeFileSync(root + '/results/summary.json', JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({
    summary
  }));
  await browser.close();
  if (summary.fail) process.exitCode = 1;
})().catch(async e => {
  console.error(e.stack);
  fs.writeFileSync(root + '/results/summary.json', JSON.stringify({
    total: cases.length,
    pass: cases.filter(c => c.status === 'pass').length,
    fail: cases.filter(c => c.status === 'fail').length
  }));
  if (browser) await browser.close();
  process.exitCode = 1;
});
