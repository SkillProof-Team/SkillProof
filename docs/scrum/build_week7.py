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

    font_manager.fontManager.addfont('C:/Windows/Fonts/msyh.ttc')
    plt.rcParams['font.family'] = font_manager.FontProperties(fname='C:/Windows/Fonts/msyh.ttc').get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['svg.fonttype'] = 'path'
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    for filename, field, adjusted, title in [
        ('week7-burndown', 'fixed_without_pr', 'adjusted_without_pr', '按首次提交PR统计'),
        ('week7-closed-burndown', 'fixed_open', 'adjusted_open', '按Issue关闭统计')]:
        fig, ax = plt.subplots(figsize=(12.5, 5.8), dpi=160)
        ax.axvspan(7.5, 14.4, color='#eef5fb', zorder=0)
        ax.plot(range(15), [13] + [r[field] for r in rows], color='#2166ac', marker='o', lw=2.4, label='原13项固定基线')
        ax.plot(range(15), [13] + [r[adjusted] for r in rows], color='#d97706', marker='s', ms=4, lw=1.8, ls='--', label='调整后P0范围（新增#33、移出#13）')
        ax.plot(range(15), [13 * (1 - i / 14) for i in range(15)], color='#8a94a3', ls=':', label='原13项理想线')
        # Keep the requested completion scenario separate from dated GitHub facts.
        end_fixed, end_adjusted = (2, 2) if field == 'fixed_open' else (1, 0)
        snapshot_fixed, snapshot_adjusted = (4, 4) if field == 'fixed_open' else (1, 0)
        ax.plot([14, 15], [rows[-1][field], snapshot_fixed], color='#2166ac', marker='o', lw=2)
        ax.plot([14, 15], [rows[-1][adjusted], snapshot_adjusted], color='#d97706', marker='s', ls='--')
        ax.plot([15, 16], [snapshot_fixed, end_fixed], color='#2166ac', marker='D', ls=':', lw=2, label='提交后口径：#10、#14按完成计入')
        ax.plot([15, 16], [snapshot_adjusted, end_adjusted], color='#d97706', marker='D', ls=':')
        ax.axvline(13, color='#7c3aed', lw=1, ls=':')
        ax.text(12.85, 10.7, '11/7会议', ha='right', color='#6d28d9', fontsize=10)
        ax.set(title='SkillProof两周冲刺燃尽图｜' + title, ylabel='剩余任务数（个）', xlabel='北京时间；提交后为预期完成口径', ylim=(-0.5, 15), xlim=(-0.25, 16.4))
        ax.set_xticks(range(17), ['基线'] + [(date(2026,10,26)+timedelta(days=i)).strftime('%m/%d') for i in range(14)] + ['11/09快照', '本次提交后'], rotation=35)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis='y', alpha=.18)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='upper right', fontsize=9)
        ax.text(.01, -.26, '11/6新增#33；11/8 #13移出P0。末点将PR #25对应#10与T12 #14计为完成，不回填历史关单日期。', transform=ax.transAxes, fontsize=9, color='#475569')
        fig.tight_layout(rect=(0, .05, 1, 1))
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
    submission += '| 11月9日快照 | 已有PR提交情况 | 1 | 0 |\n| 本次提交后（组长指定口径） | #10、#14按完成；首次提交PR统计不变 | 1 | 0 |\n'
    closed += '| 11月9日20:27快照 | #7、#11已关闭 | 4 | 4 |\n| 本次提交后（组长指定口径） | PR #25对应#10、T12 #14按完成计入 | 2 | 2 |\n'
    with (ROOT / 'completion-scenario.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['point', 'fixed_open', 'adjusted_open', 'fixed_without_pr', 'adjusted_without_pr', 'counted_complete'])
        writer.writerow(['2026-11-09 20:27 snapshot', 4, 4, 1, 0, ''])
        writer.writerow(['after this submission (requested scenario)', 2, 2, 1, 0, '10;14'])

    commits = {x['sha']:x for x in SNAPSHOT['commits']}
    evidence = json.loads((ROOT / 'github-evidence.json').read_text(encoding='utf-8'))
    extra = json.loads((ROOT / 'github-evidence-extra.json').read_text(encoding='utf-8'))
    for x in evidence['pr25commits'] + extra['pr38commits']:
        commits[x['sha']] = x
    entries = [
        ('付熙瑜','7907e7c','真实会话报告查询、评分契约与测试',9,27),
        ('付熙瑜','da9860f','审核并合并统一工程检查（合并者贡献）',33,34),
        ('付熙瑜','17e7d50','审核并合并测评生命周期（合并者贡献）',8,28),
        ('李宛霖','fa257b7','修复注册页刷新跳转',7,19),
        ('李宛霖','e86e0e8','修复组合重音姓名校验',7,19),
        ('李宛霖','eb05cab','整合答题流程',10,25),
        ('李宛霖','a00ba96','同步main并接入真实结果页',10,25),
        ('常嶅阳','1951993','对齐真实报告契约',11,23),
        ('常嶅阳','98b4adf','记录真实报告流程验证',11,23),
        ('常嶅阳','e52e8e3','修复非法URL、旧报告与精度边界',11,23),
        ('冯皙丹','1a7fdb4','认证与岗位查询接口',6,30),
        ('冯皙丹','8516c23','不可见姓名和UTF-8读取修复',6,30),
        ('冯皙丹','f7df6d4','同步main并保留测试依赖锁定',6,30),
        ('王斯语','be167be','同步main并完成测评后端联调',8,28),
        ('王斯语','9095c72','同步已确认18题抽题规则',8,28),
        ('王绥源','d2f5edd','接入前后端CI检查',33,34),
        ('王绥源','242ce55','增加PR必测登记检查',33,37),
        ('王绥源','5906f5f','补充保存提交与评分验收',12,38),
    ]
    table = '| 成员 | 日期（北京） | Commit | 签入内容 | 对应Issue | PR / 最新状态 |\n| --- | --- | --- | --- | --- | --- |\n'
    for person, prefix, description, issue, pr in entries:
        matches = [sha for sha in commits if sha.startswith(prefix)]
        assert len(matches) == 1, prefix
        sha = matches[0]
        stamp = parse(commits[sha]['commit']['author']['date']).astimezone(TZ)
        state = '已合并' if PRS[pr]['merged_at'] else 'Draft，未合并' if PRS[pr]['draft'] else 'Open，未合并'
        table += f'| {person} | {stamp.month}/{stamp.day}' + ('（会后最新）' if stamp.day == 9 else '') + f' | [{prefix}](https://github.com/SkillProof-Team/SkillProof/commit/{sha}) | {description} | {link(issue)} | {link(pr,"pulls")}；{state} |\n'
    doc = ROOT / 'week7.md'
    content = doc.read_text(encoding='utf-8')
    for key, value in [('COMMIT',table),('SUBMISSION',submission),('CLOSED',closed)]:
        content = replace_table(content, key, value)
    doc.write_text(content, encoding='utf-8')
    print('PASS: 14 daily records, both scope series, 18 verified commit rows; charts and blog rebuilt.')


if __name__ == '__main__':
    main()
