"""posts.md -> texts_week.json {ключ: текст}; печатает длины подписей Telegram (видимые символы)."""
import re, json, html, sys
src = open('/home/claude/claude/nova/weeks/2026-10-12_31/posts.md', encoding='utf-8').read()
secs = re.split(r'\n### ', src)[1:]
T = {}; meta = []
for s in secs:
    m = re.match(r'(\d\d)\.10\.2026', s)
    if not m: continue
    d = m.group(1) + '10'
    tgm = re.search(r'\*\*Telegram\*\*\s*```html\n(.*?)\n```', s, re.S)
    igm = re.search(r'\*\*Instagram — подпись\*\*\s*```text\n(.*?)\n```', s, re.S)
    if tgm: T['T' + d] = tgm.group(1).strip()
    if igm: T['IG' + d] = igm.group(1).strip()
    meta.append((d, bool(tgm), bool(igm), s.split('\n')[0][:70]))
json.dump(T, open('/home/claude/work/texts_week.json', 'w'), ensure_ascii=False, indent=1)
for k, v in T.items():
    vis = html.unescape(re.sub(r'<[^>]+>', '', v))
    ph = sorted(set(re.findall(r'\{[^}]+\}', v)))
    lim = 1024 if k.startswith('T') else 2200
    print(f"{k:7s} {len(vis):5d}/{lim} {'!!' if len(vis)>lim else ''} {' '.join(ph)}")
