"""Keep immutable experiment reports and refresh the main document's result table."""
from __future__ import annotations

import json
from pathlib import Path
import re
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DOCUMENT = ROOT.parent / '多盛大厦_G1_Astra_VLA_实验方案与记录.md'
START = '<!-- AUTO_RESULTS_START -->'
END = '<!-- AUTO_RESULTS_END -->'


def record(report: dict) -> Path:
    report = {**report, 'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')}
    run_id = report['run_id']
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', run_id):
        raise ValueError('run_id contains invalid characters')
    folder = ROOT / 'reports'
    folder.mkdir(exist_ok=True)
    path = folder / f'{run_id}.json'
    # A repeated run gets a new ID; earlier failures are never overwritten.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    refresh_document()
    return path


def refresh_document() -> None:
    def cell(value) -> str:
        return str(value).replace('|', ' / ').replace('\n', ' ')

    reports = []
    for path in sorted((ROOT / 'reports').glob('*.json')):
        report = json.loads(path.read_text(encoding='utf-8'))
        reports.append((path, report))
    rows = ['| 记录 | 类别 | 结果 | 实际验证范围 |', '|---|---|---|---|']
    for path, report in reports:
        link = f'g1_astra_vla/reports/{path.name}'
        rows.append('| [' + cell(report['run_id']) + '](' + link + ') | '
                    + cell(report['kind']) + ' | ' + cell(report['status']) + ' | '
                    + cell(report['summary']) + ' |')
    if not reports:
        rows = ['尚无自动追加的本轮生成与任务执行报告。']
    source = DOCUMENT.read_text(encoding='utf-8')
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError('Main document result markers are missing or ambiguous')
    before, rest = source.split(START, 1)
    _, after = rest.split(END, 1)
    DOCUMENT.write_text(before + START + '\n' + '\n'.join(rows) + '\n' + END + after,
                        encoding='utf-8')


if __name__ == '__main__':
    refresh_document()
    print(DOCUMENT)
