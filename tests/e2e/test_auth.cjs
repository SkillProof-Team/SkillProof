const {
  launchBrowser
} = require('./browser.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {
  execFileSync
} = require('node:child_process');
const root = process.env.SKILLPROOF_QA_RUN;
const origin = process.env.SKILLPROOF_QA_ORIGIN;
const password = 'QA-browser-only-password-2026';
const stamp = Date.now();
const a = {
  email: `qa-a-${stamp}@example.test`,
  name: '浏览器账号A'
};
const b = {
  email: `qa-b-${stamp}@example.test`,
  name: '浏览器账号B'
};
const cases = [];
let browser;
async function visible(page, text) {
  await page.getByText(text, {
    exact: true
  }).waitFor({
    timeout: 30000
  });
}
async function login(page, account = a) {
  await page.goto(origin + '/login');
  await page.getByRole('heading', {
    name: '欢迎回来',
    exact: true
  }).waitFor();
  await page.getByLabel('邮箱', {
    exact: true
  }).fill(account.email);
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
  await visible(page, `你好，${account.name}`);
}
async function check(id, name, fn, options = {}) {
  const context = await browser.newContext({
    viewport: options.viewport || {
      width: 1280,
      height: 900
    }
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  const pageErrors = [],
    consoleErrors = [],
    responses = [];
  page.on('pageerror', e => pageErrors.push(e.message));
  page.on('console', m => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('response', r => {
    if (r.url().includes('/api/')) responses.push({
      path: new URL(r.url()).pathname,
      status: r.status()
    });
  });
  const item = {
    id,
    name,
    mode: 'browser with the checked-out frontend and backend',
    status: 'pass'
  };
  try {
    const extra = await fn(page, context);
    if (extra) Object.assign(item, extra);
    assert.equal(pageErrors.length, 0, 'Unhandled page exception: ' + pageErrors.join(';'));
    assert.equal(await page.locator('vite-error-overlay').count(), 0, 'Vite error overlay');
  } catch (e) {
    item.status = 'fail';
    item.error = e.message;
    item.screenshot = `${root}/evidence/${id}-failure.png`;
    await page.screenshot({
      path: item.screenshot,
      fullPage: false
    }).catch(() => {});
  }
  item.url = page.url();
  item.pageErrors = pageErrors;
  item.consoleErrors = consoleErrors;
  item.apiResponses = responses;
  cases.push(item);
  console.log(JSON.stringify({
    id,
    name,
    status: item.status,
    error: item.error
  }));
  fs.writeFileSync(root + '/results/browser-auth.json', JSON.stringify({
    accounts: [a.email, b.email],
    cases
  }, null, 2));
  await context.close();
  if (item.status === 'fail') throw new Error(item.error);
}
(async () => {
  for (const account of [a, b]) {
    const r = await fetch(origin + '/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: origin
      },
      body: JSON.stringify({
        ...account,
        password
      })
    });
    assert.equal(r.status, 201, 'Test-account setup failed: ' + r.status);
  }
  browser = await launchBrowser();
  await check('AUTH-UI-01', '首次访问、页面身份与未登录保护', async page => {
    await page.goto(origin + '/jobs');
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/login');
    assert.ok((await page.locator('body').innerText()).includes('SkillProof'));
    return {
      title: await page.title()
    };
  });
  await check('AUTH-UI-02', '注册空值与密码14/129字符边界', async page => {
    let submits = 0;
    page.on('request', r => {
      if (r.method() === 'POST' && r.url().endsWith('/auth/register')) submits++;
    });
    await page.goto(origin + '/register');
    await page.getByRole('button', {
      name: '注册',
      exact: true
    }).click();
    await visible(page, '请输入有效的电子邮箱地址');
    await page.getByLabel('邮箱', {
      exact: true
    }).fill('boundary@example.test');
    await page.getByLabel('姓名', {
      exact: true
    }).fill('边界用户');
    for (const n of [14, 129]) {
      await page.getByLabel('密码', {
        exact: true
      }).fill('x'.repeat(n));
      await page.getByRole('button', {
        name: '注册',
        exact: true
      }).click();
      await visible(page, '密码需为 15–128 个字符');
    }
    assert.equal(submits, 0);
  });
  await check('AUTH-UI-03', '真实注册成功并建立浏览器会话', async (page, context) => {
    await page.goto(origin + '/register');
    await page.getByLabel('邮箱', {
      exact: true
    }).fill(`qa-new-${stamp}@example.test`);
    await page.getByLabel('姓名', {
      exact: true
    }).fill('新注册用户');
    await page.getByLabel('密码', {
      exact: true
    }).fill(password);
    await page.getByRole('button', {
      name: '注册',
      exact: true
    }).click();
    await visible(page, '你好，新注册用户');
    assert.ok((await context.cookies()).some(c => c.name === 'skillproof_session' && c.httpOnly && c.sameSite === 'Strict'));
    const screenshot = root + '/evidence/auth-registered-desktop.png';
    await page.screenshot({
      path: screenshot
    });
    return {
      screenshot
    };
  });
  await check('AUTH-UI-04', '重复邮箱注册显示真实后端错误', async page => {
    await page.goto(origin + '/register');
    await page.getByLabel('邮箱', {
      exact: true
    }).fill(a.email.toUpperCase());
    await page.getByLabel('姓名', {
      exact: true
    }).fill('重复');
    await page.getByLabel('密码', {
      exact: true
    }).fill(password);
    await page.getByRole('button', {
      name: '注册',
      exact: true
    }).click();
    await visible(page, '该邮箱已经注册');
    assert.equal(new URL(page.url()).pathname, '/register');
  });
  await check('AUTH-UI-05', '错误密码与不存在账号均无法登录', async page => {
    await page.goto(origin + '/login');
    for (const email of [a.email, `missing-${stamp}@example.test`]) {
      await page.getByLabel('邮箱', {
        exact: true
      }).fill(email);
      await page.getByLabel('密码', {
        exact: true
      }).fill('wrong');
      await page.getByRole('button', {
        name: '登录',
        exact: true
      }).click();
      await visible(page, '邮箱或密码不正确');
    }
    assert.equal(new URL(page.url()).pathname, '/login');
  });
  await check('AUTH-UI-06', '岗位选择与开放限制', async page => {
    await login(page);
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    assert.equal(await page.getByRole('button', {
      name: '暂未开放',
      exact: true
    }).count(), 3);
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '已选择',
      exact: true
    }).waitFor();
    assert.equal(await page.getByRole('button', {
      name: /开始.*测评/
    }).isEnabled(), true);
    const screenshot = root + '/evidence/auth-selected-job.png';
    await page.getByRole('button', {
      name: /开始.*测评/
    }).scrollIntoViewIfNeeded();
    await page.screenshot({
      path: screenshot
    });
    return {
      screenshot
    };
  });
  await check('AUTH-UI-07', '刷新恢复本人身份', async page => {
    await login(page);
    await page.reload();
    await visible(page, `你好，${a.name}`);
    assert.equal(new URL(page.url()).pathname, '/jobs');
  });
  await check('AUTH-UI-08', '退出后刷新与返回不可恢复旧身份', async page => {
    await login(page);
    await page.getByRole('button', {
      name: '退出登录',
      exact: true
    }).click();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    assert.equal((await page.request.get(origin + '/api/auth/me')).status(), 401);
    await page.reload();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    await page.goto(origin + '/jobs');
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
  });
  await check('AUTH-UI-09', '切换账号不串用身份和已选岗位', async page => {
    await login(page);
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '已选择',
      exact: true
    }).waitFor();
    await page.getByRole('button', {
      name: '退出登录',
      exact: true
    }).click();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    await login(page, b);
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    assert.ok(!(await page.locator('body').innerText()).includes(`你好，${a.name}`));
    assert.equal(await page.getByRole('button', {
      name: '已选择',
      exact: true
    }).count(), 0);
    assert.equal(await page.getByText('已选择：后端开发', {
      exact: true
    }).count(), 0);
  });
  await check('AUTH-UI-10', '会话失效后刷新返回登录', async page => {
    await login(page);
    execFileSync(process.env.SKILLPROOF_QA_PYTHON, ['-B', '-c', "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); cur=c.execute('UPDATE sessions SET expires_at=0 WHERE user_id IN (SELECT id FROM users WHERE email=?)',(sys.argv[2].lower(),)); assert cur.rowcount>0; c.commit(); c.close()", process.env.SKILLPROOF_DB_PATH, a.email]);
    const staleBeforeRefresh = (await page.locator('body').innerText()).includes(`你好，${a.name}`);
    await page.reload();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    return {
      observation: staleBeforeRefresh ? 'Idle page does not proactively detect expiration; refresh detects it.' : ''
    };
  });
  await check('AUTH-UI-11', '岗位请求失败提示与重试', async page => {
    await page.route('**/api/catalog', route => route.abort('failed'));
    await login(page);
    await visible(page, '无法连接服务器，请检查网络后重试');
    await page.unroute('**/api/catalog');
    await page.getByRole('button', {
      name: '重新加载',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    return {
      mode: 'real services with deliberate browser network-failure injection'
    };
  });
  await check('AUTH-UI-12', '初始身份查询失败可重试恢复', async page => {
    await page.route('**/api/auth/me', route => route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: '测试注入：服务暂不可用'
      })
    }));
    await page.goto(origin);
    await visible(page, '测试注入：服务暂不可用');
    await page.unroute('**/api/auth/me');
    await page.getByRole('button', {
      name: '重试',
      exact: true
    }).click();
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    return {
      mode: 'frontend error recovery with explicit 503 injection'
    };
  });
  await check('AUTH-UI-13', '登录提交中禁止重复点击', async page => {
    let requests = 0;
    let release;
    const gate = new Promise(resolve => release = resolve);
    await page.route('**/api/auth/login', async route => {
      requests++;
      await gate;
      await route.continue();
    });
    await page.goto(origin + '/login');
    await page.getByLabel('邮箱', {
      exact: true
    }).fill(a.email);
    await page.getByLabel('密码', {
      exact: true
    }).fill(password);
    await page.getByRole('button', {
      name: '登录',
      exact: true
    }).click();
    const submit = page.locator('button[type=submit]');
    assert.equal(await submit.isDisabled(), true);
    await submit.evaluate(el => {
      el.click();
      el.click();
    });
    release();
    await page.getByRole('heading', {
      name: '选择目标岗位',
      exact: true
    }).waitFor();
    assert.equal(requests, 1);
    return {
      mode: 'real services with controlled request delay'
    };
  });
  await check('AUTH-UI-14', '390px手机登录和岗位页面无横向溢出', async page => {
    await page.goto(origin + '/login');
    await page.getByRole('heading', {
      name: '欢迎回来',
      exact: true
    }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({
      path: root + '/evidence/auth-login-mobile-390.png'
    });
    await login(page);
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const screenshot = root + '/evidence/auth-mobile-390.png';
    await page.screenshot({
      path: screenshot
    });
    return {
      screenshot
    };
  }, {
    viewport: {
      width: 390,
      height: 844
    }
  });
  await check('AUTH-UI-15', '岗位加载中有提示且完成后显示真实岗位', async page => {
    let release;
    const gate = new Promise(resolve => release = resolve);
    let seen;
    const requestSeen = new Promise(resolve => seen = resolve);
    await page.route('**/api/catalog', async route => {
      seen();
      await gate;
      await route.continue();
    });
    try {
      await login(page);
      await requestSeen;
      await visible(page, '正在加载岗位…');
      assert.equal(await page.getByRole('button', {
        name: '选择该岗位',
        exact: true
      }).count(), 0);
    } finally {
      release();
    }
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    return {
      mode: 'real catalog request with controlled browser delay'
    };
  });
  await check('AUTH-UI-16', '空岗位列表有明确提示并可重新加载恢复', async page => {
    await page.route('**/api/catalog', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        roles: [],
        dimensions: []
      })
    }));
    await login(page);
    await visible(page, '暂无岗位数据，请稍后重新加载。');
    assert.equal(await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).count(), 0);
    await page.unroute('**/api/catalog');
    await page.getByRole('button', {
      name: '重新加载',
      exact: true
    }).click();
    await page.getByRole('button', {
      name: '选择该岗位',
      exact: true
    }).waitFor();
    return {
      mode: 'explicit empty-catalog response injection, followed by the real catalog'
    };
  });
  fs.writeFileSync(root + '/results/summary.json', JSON.stringify({
    total: cases.length,
    pass: cases.filter(x => x.status === 'pass').length,
    fail: cases.filter(x => x.status === 'fail').length
  }, null, 2));
  await browser.close();
  if (cases.some(x => x.status === 'fail')) process.exitCode = 1;
  console.log(JSON.stringify({
    summary: {
      total: cases.length,
      pass: cases.filter(x => x.status === 'pass').length,
      fail: cases.filter(x => x.status === 'fail').length
    }
  }));
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
