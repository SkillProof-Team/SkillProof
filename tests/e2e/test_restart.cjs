const {
  launchBrowser
} = require('./browser.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const root = process.env.SKILLPROOF_QA_RUN,
  origin = process.env.SKILLPROOF_QA_ORIGIN;
const password = 'restart-acceptance-password';
const owner = {
  email: `restart-${Date.now()}@example.invalid`,
  name: '重启验收用户',
  password
};
const key = JSON.parse(fs.readFileSync(process.env.SKILLPROOF_QA_ANSWERS, 'utf8'));
const correctIds = new Set(['programming-easy-1', 'programming-easy-2', 'programming-medium', 'algorithms-easy-1', 'database-easy-1', 'database-easy-2', 'network-medium', 'software-medium']);
const mixed = Object.fromEntries(Object.entries(key).map(([id, answer]) => [id, correctIds.has(id) ? answer : id.endsWith('medium') ? ['B', 'D'] : ['D']]));
const cases = [];
let sequence = 0,
  browser,
  context,
  page,
  attempt,
  report;
const pageErrors = [],
  consoleErrors = [],
  apiResponses = [];
function watch(p) {
  p.setDefaultTimeout(30000);
  p.on('pageerror', e => pageErrors.push(e.message));
  p.on('console', m => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  p.on('response', r => {
    if (r.url().includes('/api/')) apiResponses.push({
      path: new URL(r.url()).pathname,
      status: r.status()
    });
  });
}
async function restart(target) {
  const seq = ++sequence,
    temp = root + '/control-request.tmp';
  fs.writeFileSync(temp, JSON.stringify({
    sequence: seq,
    target
  }));
  fs.renameSync(temp, root + '/control-request.json');
  const deadline = Date.now() + Number(process.env.SKILLPROOF_QA_RESTART_TIMEOUT) * 1000;
  while (Date.now() < deadline) {
    const file = root + '/control-response.json';
    if (fs.existsSync(file)) {
      const ack = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (ack.sequence === seq) {
        assert.equal(ack.ready, true);
        for (const [name, pid] of Object.entries(ack.after)) {
          assert.notEqual(pid, ack.before[name].pid);
          assert.notEqual(ack.before[name].exit_code, null);
        }
        return ack;
      }
    }
    await new Promise(r => setTimeout(r, 100));
  }
  throw Error('Restart acknowledgement timed out');
}
async function login(p, user = owner) {
  await p.goto(origin + '/login');
  await p.getByRole('heading', {
    name: '欢迎回来',
    exact: true
  }).waitFor();
  await p.getByLabel('邮箱', {
    exact: true
  }).fill(user.email);
  await p.getByLabel('密码', {
    exact: true
  }).fill(password);
  await p.getByRole('button', {
    name: '登录',
    exact: true
  }).click();
  await p.getByRole('heading', {
    name: '选择目标岗位',
    exact: true
  }).waitFor();
}
async function validateReport(p) {
  await p.getByRole('heading', {
    name: '后端开发 · 能力画像',
    exact: true
  }).waitFor();
  const values = await p.locator('.result-stat__value').allTextContents();
  assert.equal(values[0].trim(), '45.83');
  assert.equal(values[1].replace(/\s/g, ''), '8/18');
  assert.deepEqual((await p.locator('.result-bars__value').allTextContents()).map(Number), [100, 33.33, 66.67, 33.33, 0, 33.33]);
  assert.equal(await p.locator('.result-radar__dot').count(), 6);
  const response = await p.request.get(origin + '/api/reports/' + attempt.id);
  assert.equal(response.status(), 200);
  assert.deepEqual(await response.json(), report);
}
async function check(id, name, fn) {
  const start = apiResponses.length,
    errors = pageErrors.length,
    consoleStart = consoleErrors.length;
  const item = {
    id,
    name,
    status: 'pass'
  };
  try {
    Object.assign(item, await fn());
    assert.deepEqual(pageErrors.slice(errors), []);
    assert.equal(await page.locator('vite-error-overlay').count(), 0);
  } catch (e) {
    item.status = 'fail';
    item.error = e.message;
    await page.screenshot({
      path: root + '/evidence/' + id + '-failure.png'
    }).catch(() => {});
  }
  item.apiResponses = apiResponses.slice(start);
  item.pageErrors = pageErrors.slice(errors);
  item.consoleErrors = consoleErrors.slice(consoleStart);
  cases.push(item);
  fs.writeFileSync(root + '/results/browser-restart.json', JSON.stringify({
    cases
  }, null, 2));
  console.log(JSON.stringify({
    id,
    status: item.status,
    error: item.error
  }));
  if (item.status !== 'pass') throw Error(id + ' failed: ' + item.error);
}
(async () => {
  browser = await launchBrowser();
  context = await browser.newContext({
    viewport: {
      width: 1280,
      height: 900
    },
    timezoneId: 'Asia/Shanghai',
    locale: 'zh-CN'
  });
  page = await context.newPage();
  watch(page);
  await check('RESTART-UI-01', '后端进程重启后恢复本人身份、17道已保存答案并补齐提交', async () => {
    await page.goto(origin + '/register');
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
    const creation = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/attempts');
    await page.getByRole('button', {
      name: /开始.*测评/
    }).click();
    attempt = await (await creation).json();
    assert.equal(attempt.questions.length, 18);
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
    const saved = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith('/answers'));
    await page.getByRole('button', {
      name: '保存答案',
      exact: true
    }).click();
    assert.equal((await saved).status(), 200);
    await page.getByText(/当前没有未保存的修改/).waitFor();
    const before = await (await page.request.get(origin + '/api/attempts/' + attempt.id)).json();
    assert.equal(Object.keys(before.answers).length, 17);
    const identity = await (await page.request.get(origin + '/api/auth/me')).json();
    const receipt = await restart('api');
    await page.reload();
    await page.locator('.assessment-options').waitFor();
    await page.getByText(/服务器已保存 17 \/ 18 题/).waitFor();
    assert.equal(new URL(page.url()).pathname, '/attempts/' + attempt.id);
    const me = await page.request.get(origin + '/api/auth/me');
    assert.equal(me.status(), 200);
    assert.deepEqual((await me.json()).user, identity.user);
    const after = await page.request.get(origin + '/api/attempts/' + attempt.id);
    assert.equal(after.status(), 200);
    assert.deepEqual(await after.json(), before);
    for (let i = 0; i < 17; i++) {
      const q = attempt.questions[i];
      await page.getByRole('button', {
        name: new RegExp(`^第 ${i + 1} 题，`)
      }).click();
      for (const letter of mixed[q.id]) assert.equal(await page.getByRole(q.type === 'single' ? 'radio' : 'checkbox', {
        name: '选项 ' + letter,
        exact: true
      }).isChecked(), true);
    }
    await answer(17);
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await page.waitForURL('**/reports/' + attempt.id);
    const r = await page.request.get(origin + '/api/reports/' + attempt.id);
    assert.equal(r.status(), 200);
    report = await r.json();
    assert.equal(report.score, 45.83);
    assert.equal(report.correctCount, 8);
    await validateReport(page);
    fs.writeFileSync(root + '/results/report-before-full-restart.json', JSON.stringify(report, null, 2));
    await page.screenshot({
      path: root + '/evidence/restart-saved-then-submitted.png'
    });
    return {
      restart: receipt,
      saved_answers: 17,
      score: report.score
    };
  });
  await check('RESTART-UI-02', '前后端进程全部重启后报告及会话保留，新浏览器登录可查同一报告', async () => {
    const receipt = await restart('all');
    await page.reload();
    await validateReport(page);
    await page.screenshot({
      path: root + '/evidence/restart-report-existing-session.png'
    });
    await context.close();
    context = await browser.newContext({
      viewport: {
        width: 1280,
        height: 900
      },
      timezoneId: 'Asia/Shanghai',
      locale: 'zh-CN'
    });
    page = await context.newPage();
    watch(page);
    await login(page);
    await page.goto(origin + '/reports/' + attempt.id);
    await validateReport(page);
    await page.screenshot({
      path: root + '/evidence/restart-report-new-session.png'
    });
    return {
      restart: receipt,
      report_unchanged: true,
      fresh_context_login: true
    };
  });
  await check('RESTART-UI-03', '重启后其他账号仍无法读取原报告且新测评不继承答案', async () => {
    await context.close();
    context = await browser.newContext({
      viewport: {
        width: 1280,
        height: 900
      },
      timezoneId: 'Asia/Shanghai',
      locale: 'zh-CN'
    });
    page = await context.newPage();
    watch(page);
    await page.goto(origin + '/register');
    await page.getByLabel('邮箱', {
      exact: true
    }).fill('other-' + owner.email);
    await page.getByLabel('姓名', {
      exact: true
    }).fill('重启后其他用户');
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
    const denied = page.waitForResponse(r => r.url().endsWith('/api/reports/' + attempt.id));
    await page.goto(origin + '/reports/' + attempt.id);
    assert.equal((await denied).status(), 404);
    await page.getByRole('heading', {
      name: '没有找到这份报告',
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.result-radar__svg').count(), 0);
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
    const other = await r.json();
    assert.notEqual(other.id, attempt.id);
    assert.deepEqual(other.answers, {});
    return {
      other_report_status: 404,
      other_answers_empty: true
    };
  });
})().catch(e => {
  console.error(e.message);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  const summary = {
    planned: 3,
    total: cases.length,
    pass: cases.filter(x => x.status === 'pass').length,
    fail: cases.filter(x => x.status === 'fail').length,
    not_run: 3 - cases.length
  };
  fs.writeFileSync(root + '/results/summary.json', JSON.stringify(summary, null, 2));
});
