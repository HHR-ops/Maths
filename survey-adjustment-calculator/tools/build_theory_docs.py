"""Generate the offline companion from the same content used by React."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
doc = json.loads((ROOT/'frontend/src/knowledge.json').read_text(encoding='utf-8'))
articles = {a['id']: a for a in doc['articles']}
sources = {s['id']: s for s in doc['sources']}
lines = ['# 测量平差理论与知识', '',
         '本手册与程序内六章十三篇知识内容来自同一份数据。正文、公式、算例和自测可离线阅读；外部参考链接需联网。交互例题在程序左侧“理论与知识”中使用。', '',
         '公式按 v = 平差值 − 观测值；本手册为自行编写的学习材料与算例，参考资料用于进一步阅读。', '',
         '## 符号速查', '', '| 符号 | 含义 |', '| --- | --- |']
for symbol, description in doc['symbols']: lines.append(f'| {symbol} | {description} |')
for i, c in enumerate(doc['chapters'], 1):
    lines.extend(['', f'## {i}. {c["title"]}', '', c['subtitle'], ''])
    for key in c['articles']:
        a = articles[key]
        lines.extend([f'### {a["title"]}', '', a['summary'], ''])
        for s in a['sections']:
            lines.extend([f'#### {s["title"]}', ''])
            for p in s.get('paragraphs', []): lines.extend([p, ''])
            for formula in s.get('formulas', []): lines.extend(['$$', formula, '$$', ''])
            if 'table' in s:
                table = s['table']
                lines.extend(['| '+' | '.join(table['headers'])+' |', '| '+' | '.join(['---']*len(table['headers']))+' |'])
                lines.extend('| '+' | '.join(row)+' |' for row in table['rows'])
                lines.append('')
            if 'example' in s: lines.extend(['**算例：'+s['example']['title']+'**', '', s['example']['text'], ''])
            if 'callout' in s: lines.extend(['> '+s['callout'], ''])
        q = a['quiz']
        lines.extend(['**理解自测：** '+q['question'], ''])
        lines.extend(f'{j+1}. {o}' for j, o in enumerate(q['options']))
        lines.extend(['', '**答案：** '+str(q['answer']+1)+'。'+q['explanation'], '', '**参考资料：** '+ '；'.join(f'[{sources[k]["title"]}]({sources[k]["url"]})' for k in a['sources']), ''])
(ROOT/'docs/THEORY.md').write_text('\n'.join(lines).rstrip()+'\n', encoding='utf-8')
print('Generated docs/THEORY.md from knowledge.json.')
