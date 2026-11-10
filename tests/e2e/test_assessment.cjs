const {
  launchBrowser
} = require('./browser.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  execFileSync
} = require('node:child_process');
const root = process.env.SKILLPROOF_QA_RUN,
  origin = process.env.SKILLPROOF_QA_ORIGIN;
const answerKey = JSON.parse(fs.readFileSync(process.env.SKILLPROOF_QA_ANSWERS, 'utf8'));
const password = 'assessment-browser-test-password';
const stamp = Date.now();
const cases = [];
let browser;
async function account(suffix) {
  const user = {
    email: `assessment-${stamp}-${suffix}@example.invalid`,
    name: `答题测试${suffix}`,
    password
  };
  const response = await fetch(origin + '/api/auth/register', {
    method: 'POST',
    headers: {
      Origin: origin,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(user)
  });
  assert.equal(response.status, 201, 'Isolated account setup: ' + (await response.text()));
  return user;
}
async function login(page, user) {
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
async function start(page, user) {
  await login(page, user);
  await page.getByRole('button', {
    name: '选择该岗位',
    exact: true
  }).click();
  await page.getByRole('button', {
    name: '已选择',
    exact: true
  }).waitFor();
  const response = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/attempts');
  await page.getByRole('button', {
    name: /开始.*测评/
  }).click();
  const r = await response;
  assert.equal(r.status(), 200, await r.text());
  const attempt = await r.json();
  await page.getByRole('heading', {
    name: '能力测评',
    exact: true
  }).waitFor();
  await page.locator('.assessment-options').waitFor();
  assert.equal(attempt.questionCount, 18);
  assert.equal(attempt.questions.length, 18);
  return attempt;
}
async function go(page, index) {
  await page.getByRole('button', {
    name: new RegExp(`^第 ${index + 1} 题，`)
  }).click();
}
function option(page, question, letter) {
  return page.getByRole(question.type === 'single' ? 'radio' : 'checkbox', {
    name: '选项 ' + letter,
    exact: true
  });
}
async function choose(page, attempt, index, letters) {
  await go(page, index);
  const question = attempt.questions[index];
  if (question.type === 'multiple') for (const letter of 'ABCD') await option(page, question, letter).setChecked(letters.includes(letter));else await option(page, question, letters[0]).check();
}
async function fillAll(page, attempt) {
  for (let i = 0; i < attempt.questions.length; i++) await choose(page, attempt, i, answerKey[attempt.questions[i].id]);
}
async function saved(page, attempt) {
  const response = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().endsWith('/answers'));
  await page.getByRole('button', {
    name: '保存答案',
    exact: true
  }).click();
  const r = await response;
  assert.equal(r.status(), 200, await r.text());
  await page.getByText(/当前没有未保存的修改/).waitFor();
  return r.json();
}
async function read(page, attempt) {
  const r = await page.request.get(origin + '/api/attempts/' + attempt.id);
  assert.equal(r.status(), 200);
  return r.json();
}
async function finished(page, attempt) {
  await page.waitForURL('**/reports/' + attempt.id);
  const response = await page.request.get(origin + '/api/reports/' + attempt.id);
  assert.equal(response.status(), 200);
  const report = await response.json();
  assert.equal(report.id, attempt.id);
  assert.equal(report.score, 100);
  assert.equal(report.correctCount, 18);
  return report;
}
async function check(id, name, fn, viewport = {
  width: 1280,
  height: 900
}) {
  const context = await browser.newContext({
    viewport
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
    mode: 'real browser, real backend, isolated 18-question fixture'
  };
  try {
    const user = await account(id);
    const extra = await fn(page, user);
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
  fs.writeFileSync(root + '/results/browser-assessment.json', JSON.stringify({
    cases
  }, null, 2));
  console.log(JSON.stringify({
    id,
    name,
    status: item.status,
    error: item.error
  }));
  await context.close();
  if (item.status === 'fail') throw new Error(item.error);
}
(async () => {
  browser = await launchBrowser();
  await check('ASSESS-UI-01', '创建、单多选、切题、进度、保存刷新与清空恢复', async (page, user) => {
    const attempt = await start(page, user);
    const single = attempt.questions.findIndex(q => q.type === 'single'),
      multiple = attempt.questions.findIndex(q => q.type === 'multiple');
    await choose(page, attempt, single, ['A']);
    await option(page, attempt.questions[single], 'B').check();
    assert.equal(await page.getByRole('radio').count(), 4);
    assert.equal(await page.locator('input[type=radio]:checked').count(), 1);
    await option(page, attempt.questions[single], 'B').isChecked().then(v => assert.equal(v, true));
    await choose(page, attempt, single, answerKey[attempt.questions[single].id]);
    await choose(page, attempt, multiple, ['A', 'C']);
    await option(page, attempt.questions[multiple], 'A').uncheck();
    assert.equal(await page.locator('input[type=checkbox]:checked').count(), 1);
    await option(page, attempt.questions[multiple], 'A').check();
    await go(page, single);
    assert.equal(await option(page, attempt.questions[single], answerKey[attempt.questions[single].id][0]).isChecked(), true);
    assert.equal((await saved(page, attempt)).answeredCount, 2);
    await page.reload();
    await page.locator('.assessment-options').waitFor();
    await go(page, single);
    assert.equal(await option(page, attempt.questions[single], answerKey[attempt.questions[single].id][0]).isChecked(), true);
    await page.getByRole('button', {
      name: '清空本题',
      exact: true
    }).click();
    assert.equal((await saved(page, attempt)).answeredCount, 1);
    await page.reload();
    await page.locator('.assessment-options').waitFor();
    await go(page, single);
    assert.equal(await page.locator('input:checked').count(), 0);
    assert.equal((await read(page, attempt)).answeredCount, 1);
    await page.screenshot({
      path: root + '/evidence/assessment-desktop.png'
    });
  });
  await check('ASSESS-UI-02', '未答完提交被前端拦截，定位首道未答题且保留选择', async (page, user) => {
    const attempt = await start(page, user);
    await choose(page, attempt, 0, ['A']);
    let writes = 0;
    page.on('request', r => {
      if (['PUT', 'POST'].includes(r.method()) && /\/answers$|\/submit$/.test(r.url())) writes++;
    });
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await page.getByRole('alert').filter({
      hasText: '还有 17 题未作答'
    }).waitFor();
    assert.equal(writes, 0);
    assert.match(await page.locator('[aria-current=step]').getAttribute('aria-label'), /^第 2 题/);
    await go(page, 0);
    assert.equal(await option(page, attempt.questions[0], 'A').isChecked(), true);
  });
  await check('ASSESS-UI-03', '保存网络失败保留本地答案，重试后真实保存成功', async (page, user) => {
    const attempt = await start(page, user);
    await choose(page, attempt, 0, ['A']);
    const pattern = '**/api/attempts/' + attempt.id + '/answers';
    await page.route(pattern, route => route.abort('failed'));
    await page.getByRole('button', {
      name: '保存答案',
      exact: true
    }).click();
    await page.getByRole('alert').waitFor();
    assert.equal(await option(page, attempt.questions[0], 'A').isChecked(), true);
    assert.equal((await read(page, attempt)).answeredCount, 0);
    await page.unroute(pattern);
    assert.equal((await saved(page, attempt)).answeredCount, 1);
    return {
      mode: 'browser request abort before save, then real API retry'
    };
  });
  await check('ASSESS-UI-04', '提交请求发送失败后可重试，已保存的18题不丢失', async (page, user) => {
    const attempt = await start(page, user);
    await fillAll(page, attempt);
    const pattern = '**/api/attempts/' + attempt.id + '/submit';
    await page.route(pattern, route => route.abort('failed'));
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await page.getByRole('alert').waitFor();
    const draft = await read(page, attempt);
    assert.equal(draft.status, 'in_progress');
    assert.equal(draft.answeredCount, 18);
    await page.unroute(pattern);
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    await finished(page, attempt);
    return {
      mode: 'browser submission abort before backend processing, then real retry'
    };
  });
  await check('ASSESS-UI-05', '后端提交成功但响应丢失，查询状态恢复并跳转结果入口', async (page, user) => {
    const attempt = await start(page, user);
    await fillAll(page, attempt);
    let submissions = 0,
      status;
    await page.route('**/api/attempts/' + attempt.id + '/submit', async route => {
      submissions++;
      const response = await route.fetch();
      status = response.status();
      await route.abort('failed');
    });
    await page.getByRole('button', {
      name: '提交测评',
      exact: true
    }).click();
    const report = await finished(page, attempt);
    assert.equal(status, 200);
    assert.equal(submissions, 1);
    await page.reload();
    await page.waitForURL('**/reports/' + attempt.id);
    const reread = await page.request.get(origin + '/api/reports/' + attempt.id);
    assert.equal(reread.status(), 200);
    assert.deepEqual(await reread.json(), report);
    return {
      mode: 'real backend commit followed by deliberate loss of its browser response',
      submission_requests: submissions
    };
  });
  await check('ASSESS-UI-06', '提交中禁止重复提交和离开，最终只提交一次', async (page, user) => {
    const attempt = await start(page, user);
    await fillAll(page, attempt);
    let release,
      seen,
      submissions = 0;
    const gate = new Promise(r => release = r),
      arrived = new Promise(r => seen = r);
    await page.route('**/api/attempts/' + attempt.id + '/submit', async route => {
      submissions++;
      seen();
      await gate;
      await route.continue().catch(() => {});
    });
    try {
      await page.getByRole('button', {
        name: '提交测评',
        exact: true
      }).click();
      await arrived;
      const button = page.getByRole('button', {
        name: '提交中…',
        exact: true
      });
      assert.equal(await button.isDisabled(), true);
      await button.evaluate(el => {
        el.click();
        el.click();
      });
      assert.equal(await page.getByRole('button', {
        name: '返回岗位选择',
        exact: true
      }).isDisabled(), true);
      await page.goBack();
      await page.getByRole('alert').filter({
        hasText: '正在保存或提交'
      }).waitFor();
      assert.equal(new URL(page.url()).pathname, '/attempts/' + attempt.id);
    } finally {
      release();
    }
    await finished(page, attempt);
    assert.equal(submissions, 1);
    return {
      mode: 'real submission held in the browser to inspect pending controls',
      submission_requests: submissions
    };
  });
  await check('ASSESS-UI-07', '未保存离开和原生刷新提醒，保存后能离开并恢复同一答卷', async (page, user) => {
    const attempt = await start(page, user);
    await choose(page, attempt, 0, ['A']);
    await page.getByRole('button', {
      name: '返回岗位选择',
      exact: true
    }).click();
    await page.getByRole('alert').filter({
      hasText: '有未保存的答案'
    }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/attempts/' + attempt.id);
    let kind;
    const dialogSeen = page.waitForEvent('dialog', {
      timeout: 5000
    }).then(async dialog => {
      kind = dialog.type();
      await dialog.dismiss();
    });
    await Promise.all([dialogSeen, page.reload({
      timeout: 6000
    }).catch(() => {})]);
    assert.equal(kind, 'beforeunload');
    assert.equal(await option(page, attempt.questions[0], 'A').isChecked(), true);
    await saved(page, attempt);
    await page.getByRole('button', {
      name: '返回岗位选择',
      exact: true
    }).click();
    await page.getByRole('heading', {
      name: '选择目标岗位',
      exact: true
    }).waitFor();
    await page.getByRole('button', {
      name: /开始.*测评/
    }).click();
    await page.waitForURL('**/attempts/' + attempt.id);
    await page.locator('.assessment-options').waitFor();
    assert.equal((await read(page, attempt)).answeredCount, 1);
    return {
      native_dialog: kind
    };
  });
  await check('ASSESS-UI-08', '其他账号无法打开答卷，过期会话刷新后返回登录', async (page, user) => {
    const attempt = await start(page, user);
    await choose(page, attempt, 0, ['A']);
    await saved(page, attempt);
    const other = await account('other');
    await page.getByRole('button', {
      name: '返回岗位选择',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '退出登录',
      exact: true
    }).click();
    await login(page, other);
    const denied = page.waitForResponse(r => r.url().endsWith('/api/attempts/' + attempt.id));
    await page.goto(origin + '/attempts/' + attempt.id);
    assert.equal((await denied).status(), 404);
    await page.getByRole('heading', {
      name: '测评加载失败',
      exact: true
    }).waitFor();
    assert.equal(await page.locator('.assessment-options').count(), 0);
    await page.getByRole('button', {
      name: '返回岗位选择',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '退出登录',
      exact: true
    }).click();
    await login(page, user);
    await page.goto(origin + '/attempts/' + attempt.id);
    await page.locator('.assessment-options').waitFor();
    execFileSync(process.env.SKILLPROOF_QA_PYTHON, ['-c', "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); cur=c.execute('UPDATE sessions SET expires_at=0 WHERE user_id IN (SELECT id FROM users WHERE email=?)',(sys.argv[2].lower(),)); assert cur.rowcount>0, 'No isolated session matched the expiration fixture'; c.commit(); c.close()", process.env.SKILLPROOF_DB_PATH, user.email]);
    await page.reload();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    return {
      mode: 'real cross-account requests; expired session prepared only in isolated database'
    };
  });
  await check('ASSESS-UI-09', '390px答题页面可选择和保存，无横向溢出', async (page, user) => {
    const attempt = await start(page, user);
    await choose(page, attempt, 0, ['A']);
    assert.equal((await saved(page, attempt)).answeredCount, 1);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('.assessment-header').scrollIntoViewIfNeeded();
    await page.screenshot({
      path: root + '/evidence/assessment-mobile.png'
    });
  }, {
    width: 390,
    height: 844
  });
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
