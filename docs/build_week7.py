"""Rebuild week7 evidence tables and charts from the saved GitHub snapshot."""
from pathlib import Path
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import csv
import json
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo('Asia/Shanghai')
SNAPSHOT = json.loads((ROOT / 'github-snapshot.json').read_text(encoding='utf-8'))
ISSUES = {x['number']: x for x in SNAPSHOT['issues'] if 'pull_request' not in x}
PRS = {x['number']: x for x in SNAPSHOT['pulls']}
LATEST = json.loads((ROOT / 'week7-latest-status.json').read_text(encoding='utf-8'))
CURRENT_ISSUES = ISSUES | {x['number']: x for x in LATEST['issues']}
CHECKED = datetime.strptime(LATEST['checkedAt'], '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=ZoneInfo('UTC')).astimezone(TZ)
BASE = {1, *range(3, 15)}
PR_ISSUE = {2: 1, 18: 14, 19: 7, 20: 3, 21: 14, 22: 5, 23: 11,
            24: 14, 25: 10, 26: 4, 27: 9, 28: 8, 29: 12, 30: 6,
            31: 12, 32: 1, 34: 33, 35: 14, 36: 14, 37: 33, 38: 12}
parse = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))


def remaining(day, scope, submitted=False):
    boundary = datetime.combine(day + timedelta(days=1), time(), TZ)
    covered = {PR_ISSUE[n] for n, p in PRS.items()
               if n in PR_ISSUE and parse(p['created_at']) < boundary}
    return sorted(n for n in scope if n not in covered) if submitted else sorted(
        n for n in scope if not ISSUES[n]['closed_at'] or parse(ISSUES[n]['closed_at']) >= boundary)


def link(n, kind='issues', label=None):
    kind = 'pull' if kind == 'pulls' else kind
    return f'[{label or "#" + str(n)}](https://github.com/SkillProof-Team/SkillProof/{kind}/{n})'


def replace_table(document, name, table):
    start = f'<!-- GENERATED_{name}_TABLE -->'
    end = f'<!-- END_{name}_TABLE -->'
    block = start + '\n\n' + table.rstrip() + '\n\n' + end
    if end in document:
        return re.sub(re.escape(start) + r'.*?' + re.escape(end), lambda _: block, document, flags=re.S)
    return document.replace(start, block)


def main():
    rows = []
    for i in range(14):
        day = date(2026, 10, 26) + timedelta(days=i)
        scope = set(BASE)
        if day >= date(2026, 11, 6):
            scope.add(33)
        if day >= date(2026, 11, 8):
            scope.remove(13)
        fixed = remaining(day, BASE)
        adjusted = remaining(day, scope)
        without = remaining(day, BASE, True)
        adjusted_without = remaining(day, scope, True)
        rows.append(dict(date=str(day), fixed_open=len(fixed), adjusted_open=len(adjusted),
                         fixed_without_pr=len(without), adjusted_without_pr=len(adjusted_without),
                         fixed_open_issues=';'.join(map(str, fixed)),
                         adjusted_open_issues=';'.join(map(str, adjusted)),
                         scope_total=len(scope)))
    assert [x['fixed_open'] for x in rows[:7]] == [12, 12, 12, 12, 12, 11, 9]
    assert [x['fixed_open'] for x in rows[7:]] == [9, 9, 9, 9, 9, 9, 6]
    assert [x['adjusted_open'] for x in rows[7:]] == [9, 9, 9, 9, 10, 10, 6]
    assert [x['adjusted_without_pr'] for x in rows[7:]] == [1, 1, 1, 1, 2, 1, 0]
    with (ROOT / 'burndown-data.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    current_scope = (BASE | {33}) - {13}
    fixed_now = sorted(n for n in BASE if CURRENT_ISSUES[n]['state'] == 'open')
    adjusted_now = sorted(n for n in current_scope if CURRENT_ISSUES[n]['state'] == 'open')
    fixed_after = sorted(set(fixed_now) - {14})
    adjusted_after = sorted(set(adjusted_now) - {14})
    assert fixed_now == [12, 13, 14] and adjusted_now == [12, 14]
    assert fixed_after == [12, 13] and adjusted_after == [12]

    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams['font.family'] = font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc').get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['svg.fonttype'] = 'path'
    assets = ROOT / 'scrum' / 'assets'
    assets.mkdir(exist_ok=True)
    for filename, field, adjusted, title in [
        ('week7-burndown', 'fixed_without_pr', 'adjusted_without_pr', '按首次提交PR统计'),
        ('week7-closed-burndown', 'fixed_open', 'adjusted_open', '按Issue关闭统计')]:
        fig, ax = plt.subplots(figsize=(12.5, 5.8), dpi=160)
        end_fixed, end_adjusted = (len(fixed_after), len(adjusted_after)) if field == 'fixed_open' else (1, 0)
        dates = [date(2026, 10, 26) + timedelta(days=i) for i in range(15)]
        ax.plot(range(15), [r[field] for r in rows] + [end_fixed], color='#2166ac', marker='o', lw=2.4, label='原13项基线')
        ax.plot(range(15), [r[adjusted] for r in rows] + [end_adjusted], color='#d97706', marker='s', ms=4, lw=1.8, ls='--', label='调整后P0范围')
        ax.plot(range(15), [13 * (1 - i / 13) for i in range(14)] + [0], color='#8a94a3', ls=':', label='理想线')
        ax.set(title='SkillProof燃尽图｜' + title, ylabel='剩余任务数（个）', xlabel='日期', ylim=(-0.5, 14), xlim=(-0.25, 14.25))
        ax.set_xticks(range(15), [day.strftime('%m/%d') for day in dates], rotation=35)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis='y', alpha=.18)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='upper right', fontsize=10)
        fig.tight_layout()
        for ext in ['png', 'svg']:
            fig.savefig(assets / f'{filename}.{ext}', facecolor='white')
            if ext == 'svg':
                svg = assets / f'{filename}.{ext}'
                svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
        plt.close(fig)

    submission = '| 日期 | 当日首次提交 / 范围变化 | 原13项剩余未提交PR | 调整后P0剩余未提交PR |\n| --- | --- | ---: | ---: |\n'
    closed = '| 日期 | 当日关单 / 范围变化 | 原13项剩余未关闭 | 调整后P0剩余未关闭 |\n| --- | --- | ---: | ---: |\n'
    for r in rows[6:]:
        d = date.fromisoformat(r['date'])
        submission_note = {1:'第一周末基线', 2:link(6)+'首次由'+link(30,'pulls','PR #30')+'覆盖', 6:'新增P0 '+link(33)+'，尚无关联PR', 7:link(33)+'首次由'+link(34,'pulls','PR #34')+'覆盖', 8:link(13)+'改为P2，移出调整范围'}.get(d.day, '无')
        closed_note = '第一周末基线' if d == date(2026,11,1) else '；'.join(link(n)+'关闭' for n in sorted(BASE) if ISSUES[n]['closed_at'] and parse(ISSUES[n]['closed_at']).astimezone(TZ).date() == d) or '无'
        if d == date(2026,11,6):
            closed_note = '新增P0 '+link(33)+'，未关闭'
        if d == date(2026,11,8):
            closed_note += '；'+link(13)+'移出P0，仍Open'
        submission += f'| {d.month}月{d.day}日 | {submission_note} | {r["fixed_without_pr"]} | {r["adjusted_without_pr"]} |\n'
        closed += f'| {d.month}月{d.day}日 | {closed_note} | {r["fixed_open"]} | {r["adjusted_open"]} |\n'
    submission += '| 11月9日 | 已有PR提交情况 | 1 | 0 |\n'
    closed += f'| 11月9日 | #7、#10、#11、#33已关闭；按约定计入T12 #14完成 | {len(fixed_after)} | {len(adjusted_after)} |\n'
    with (ROOT / 'completion-scenario.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['point', 'fixed_open', 'adjusted_open', 'fixed_without_pr', 'adjusted_without_pr', 'counted_complete'])
        writer.writerow([f'{CHECKED:%Y-%m-%d %H:%M} verified status', len(fixed_now), len(adjusted_now), 1, 0, '10;33'])
        writer.writerow(['after this submission (requested scenario)', len(fixed_after), len(adjusted_after), 1, 0, '10;14;33'])

    doc = ROOT / 'scrum' / 'week7.md'
    content = doc.read_text(encoding='utf-8')
    for heading, image, table in [
        ('### 1.按首次提交PR统计', '![两周燃尽图：剩余未提交PR任务数]', submission),
        ('### 2.按Issue关闭统计', '![两周燃尽图：剩余未关闭任务数]', closed),
    ]:
        begin = content.index(heading) + len(heading)
        end = content.index(image, begin)
        content = content[:begin] + '\n\n' + table.rstrip() + '\n\n' + content[end:]
    doc.write_text(content, encoding='utf-8')
    print('PASS: history preserved; latest P0 count 2; after T12 completion count 1; tables and charts rebuilt.')


if __name__ == '__main__':
    main()
