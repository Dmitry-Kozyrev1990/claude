# Публикация постов Новы из облачной песочницы Composio.
# Запуск (в COMPOSIO_REMOTE_WORKBENCH):
#   import requests; exec(requests.get(RAW + 'publish.py').text)
#   start_install()            -> фоново ставит Chromium
#   install_ready()            -> True, когда готово
#   await render_day(DAY)      -> рисует карточки дня (шрифты Google Fonts)
#   wait_until_msk('19:30')    -> ждёт ≤170 c за вызов, возвращает остаток секунд
#   publish_day(DAY, fill=None, test=False)
import json, os, time, subprocess, datetime, requests

RAW = 'https://raw.githubusercontent.com/Dmitry-Kozyrev1990/claude/main/nova/'
D = '/tmp/nova/'
os.makedirs(D, exist_ok=True)
S = requests.get(RAW + 'content/schedule.json', timeout=30).json()
T = requests.get(RAW + 'content/texts.json', timeout=30).json()
CARDS = None
LOG = globals().get('LOG', {})
MSK = datetime.timezone(datetime.timedelta(hours=3))


def start_install():
    if os.path.exists(D + 'pw_ready'):
        return 'ready'
    subprocess.Popen("bash -c 'pip install -q playwright pillow && python -m playwright install --with-deps chromium "
                     "&& touch /tmp/nova/pw_ready' > /tmp/nova/pw.log 2>&1", shell=True)
    return 'started'


def install_ready():
    return os.path.exists(D + 'pw_ready')


def _day_assets(day):
    names, guide = [], False
    for st in S['days'][day]:
        if st['type'] == 'tg_photo':
            names.append(st['card'])
        elif st['type'] == 'ig_carousel':
            names += st['cards']
        elif st['type'] == 'tg_doc':
            guide = True
    return names, guide


async def render_day(day):
    global CARDS
    from playwright.async_api import async_playwright
    from PIL import Image
    if CARDS is None:
        CARDS = requests.get(RAW + 'content/cards.json', timeout=60).json()
    names, guide = _day_assets(day)
    fonts = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for n in names:
            w, h, html = CARDS[n]
            pg = await b.new_page(viewport={'width': w, 'height': h})
            await pg.set_content(html, wait_until='networkidle')
            await pg.evaluate('document.fonts.ready')
            fonts[n] = await pg.evaluate("[...document.fonts].filter(f=>f.status=='loaded').length")
            await pg.screenshot(path=D + n + '.png', clip={'x': 0, 'y': 0, 'width': w, 'height': h})
            await pg.close()
            if n.startswith('ig_'):
                Image.open(D + n + '.png').convert('RGB').save(D + n + '.jpg', quality=95, subsampling=0)
        if guide:
            pg = await b.new_page()
            await pg.set_content(requests.get(RAW + 'content/guide.html', timeout=30).text, wait_until='networkidle')
            await pg.evaluate('document.fonts.ready')
            await pg.pdf(path=D + 'guide.pdf', format='A4', print_background=True,
                         margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
            fonts['guide'] = 'pdf'
        await b.close()
    bad = [n for n, f in fonts.items() if isinstance(f, int) and f < 2]
    return {'rendered': len(fonts), 'fonts_missing': bad}


def wait_until_msk(hhmm):
    h, m = map(int, hhmm.split(':'))
    now = datetime.datetime.now(MSK)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    left = (target - now).total_seconds()
    if left > 0:
        time.sleep(min(left, 170))
    return max(0, int((target - datetime.datetime.now(MSK)).total_seconds()))


def _url(path):
    r, e = upload_local_file(path)
    if e:
        raise RuntimeError(e)
    return requests.get(r['s3_url'], allow_redirects=True, stream=True).url, r['s3key']


def _run(slug, args, acc):
    r, e = run_composio_tool(slug, args, account=acc)
    if e or (isinstance(r, dict) and r.get('error')):
        raise RuntimeError(f'{slug}: {e or r.get("error")}')
    return r


def _text(st, fill):
    t = T[st['text']]
    if st.get('fill'):
        t = t.replace('{' + st['fill'] + '}', fill or '')
    return t


def publish_day(day, fill=None, test=False):
    """test=True: Telegram -> канал черновиков, Instagram -> только контейнер без публикации."""
    chat = S['drafts'] if test else S['channel']
    tga, iga, igid = S['tg_account'], S['ig_account'], S['ig_user_id']
    out = []
    for st in S['days'][day]:
        k = ('test_' if test else '') + st['key']
        if k in LOG:
            out.append(f'{k}: уже опубликовано')
            continue
        try:
            if st['type'] == 'tg_photo':
                u, _ = _url(D + st['card'] + '.png')
                r = _run('TELEGRAM_SEND_PHOTO', {'chat_id': chat, 'photo': u, 'caption': _text(st, fill), 'parse_mode': 'HTML'}, tga)
                res = r['data']['result']['message_id']
            elif st['type'] == 'tg_doc':
                prev = LOG.get(('test_' if test else '') + st.get('wait_after', ''), {})
                if isinstance(prev, dict) and prev.get('ts'):
                    left = prev['ts'] + st.get('delay', 0) - time.time()
                    if left > 0:
                        time.sleep(min(left, 90))
                u, _ = _url(D + 'guide.pdf')
                r = _run('TELEGRAM_SEND_DOCUMENT', {'chat_id': chat, 'document': u, 'caption': _text(st, fill), 'parse_mode': 'HTML'}, tga)
                res = r['data']['result']['message_id']
            elif st['type'] == 'tg_poll':
                time.sleep(1.2)
                q, opts = S['polls'][st['poll']]
                r = _run('TELEGRAM_SEND_POLL', {'chat_id': chat, 'question': q, 'options': opts, 'is_anonymous': True}, tga)
                res = {'mid': r['data']['result']['message_id'], 'poll_id': r['data']['result']['poll']['id']}
            elif st['type'] == 'ig_carousel':
                keys = [_url(D + n + '.jpg')[1] for n in st['cards']]
                c = _run('INSTAGRAM_CREATE_CAROUSEL_CONTAINER', {'ig_user_id': igid, 'caption': _text(st, fill),
                         'child_image_files': [{'name': f'nova_{i + 1}.jpg', 'mimetype': 'image/jpeg', 's3key': key} for i, key in enumerate(keys)]}, iga)
                cid = c['data']['id']
                if test:
                    res = f'container {cid} (не опубликован)'
                else:
                    p = _run('INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH', {'ig_user_id': igid, 'creation_id': cid, 'max_wait_seconds': 120}, iga)
                    res = p['data'].get('id', str(p['data'])[:80])
            LOG[k] = {'res': res, 'ts': time.time()}
            out.append(f'{k}: OK {res}')
        except Exception as ex:
            out.append(f'{k}: FAIL {str(ex)[:300]}')
    try:
        _run('TELEGRAM_SEND_MESSAGE', {'chat_id': S['drafts'], 'text': ('🧪 ТЕСТ ' if test else '📮 ') + f'Нова, {day}:\n' + '\n'.join(out)}, tga)
    except Exception:
        pass
    return out
