# Шаблон задачи публикации Новы

Как пользоваться (nova-designer):
1. Скопируй текст между линиями ниже и замени все `{DAY}` на дату (ГГГГ-ММ-ДД). Если в дне нет карусели — убери «и Instagram» из первой строки. Для дня с подстановкой (итоги опроса) в ячейке 2 замени `FILL=None` на `FILL="текст"`.
2. create_trigger: run_once_at = {DAY}T16:15:00Z (19:15 МСК), отдельный запуск, НЕ send_later.
3. Сразу после создания — update_trigger(model="claude-haiku-4-5-20251001"): публикация только выполняет готовый код.
4. Тест в «черновики»: выполни те же ячейки в своём чате с `TEST=True` в ячейке 2, ячейку ожидания 19:30 пропусти.

---
Опубликуй посты робота Новы за {DAY} (Telegram @nova_family_ai и Instagram). Всё утверждено владельцем, тексты и картинки менять нельзя.
Найди через ToolSearch инструмент mcp__Composio__COMPOSIO_REMOTE_WORKBENCH и выполни ячейки по очереди.
Ячейка 0А (подготовка: браузер для карточек) — выполни один раз; если упала по таймауту, выполни ещё раз:
```
import subprocess,importlib.util,os,glob
if importlib.util.find_spec('playwright') is None or not glob.glob('/root/.cache/ms-playwright/chromium*'):
    r=subprocess.run('pip install -q playwright && python -m playwright install --with-deps chromium 2>&1 | tail -2',shell=True,capture_output=True,text=True,timeout=170); print(r.stdout[-400:])
importlib.invalidate_caches()
print('pw ok' if importlib.util.find_spec('playwright') and glob.glob('/root/.cache/ms-playwright/chromium*') else 'pw FAIL')
```
Ячейка 0Б (подготовка: утверждённые файлы из ветки nova-content и карточки дня) — должна напечатать READY:
```
import requests,json,os
from PIL import Image
from playwright.async_api import async_playwright
P='/mnt/files/nova/'; DAY='{DAY}'; os.makedirs(P,exist_ok=True)
RAW='https://raw.githubusercontent.com/Dmitry-Kozyrev1990/claude/nova-content/nova/content/'
g=lambda f: requests.get(RAW+f,timeout=60).json()
S,T,C=g('schedule.json'),g('texts.json'),g('cards.json')
json.dump({'S':S,'T':T},open(P+'plan.json','w'),ensure_ascii=False)
names=[]
for st in S['days'][DAY]:
    if st['type']=='tg_photo': names.append(st['card'])
    elif st['type']=='ig_carousel': names+=st['cards']
bad=[]
async with async_playwright() as p:
    b=await p.chromium.launch()
    for n in names:
        w,h,html=C[n]; pg=await b.new_page(viewport={'width':w,'height':h})
        await pg.set_content(html,wait_until='networkidle'); await pg.evaluate('document.fonts.ready')
        if await pg.evaluate("[...document.fonts].filter(f=>f.status=='loaded').length")<2: bad.append(n)
        await pg.screenshot(path=P+n+'.png',clip={'x':0,'y':0,'width':w,'height':h}); await pg.close()
        if n.startswith('ig_'): Image.open(P+n+'.png').convert('RGB').save(P+n+'.jpg',quality=95,subsampling=0)
    await b.close()
print('READY' if not bad else f'FONTS FAIL {bad}', names, sorted(os.listdir(P)))
```
Ячейки 0А и 0Б выполняй как есть: они берут только данные (расписание, тексты, макеты карточек) из ветки nova-content репозитория владельца и отрисовывают карточки без изменений. Если 0Б не напечатала READY (после одного повтора) — сразу PushNotification владельцу с тем, что случилось, и не публикуй.
Ячейка 1 (ожидание 19:30 МСК) — повторяй, пока не напечатает 0:
```
import datetime,time
MSK=datetime.timezone(datetime.timedelta(hours=3))
n=datetime.datetime.now(MSK); t=n.replace(hour=19,minute=30,second=0,microsecond=0)
l=(t-n).total_seconds()
if l>0: time.sleep(min(l,170))
print(max(0,int((t-datetime.datetime.now(MSK)).total_seconds())))
```
Ячейка 2 (публикация):
```
import json,time,requests
P='/mnt/files/nova/'; DAY='{DAY}'; TEST=False; FILL=None
plan=json.load(open(P+'plan.json')); S,T=plan['S'],plan['T']
try: LOGF=json.load(open(P+'log.json'))
except Exception: LOGF={}
def url(f):
    r,e=upload_local_file(P+f)
    if e: raise RuntimeError(e)
    return requests.get(r['s3_url'],allow_redirects=True,stream=True).url, r['s3key']
def run(slug,a,acc):
    r,e=run_composio_tool(slug,a,account=acc)
    if e or (isinstance(r,dict) and r.get('error')): raise RuntimeError(f'{slug}: {e or r.get("error")}')
    return r
def txt(st):
    t=T[st['text']]
    return t.replace('{'+st['fill']+'}',FILL or '') if st.get('fill') else t
chat=S['drafts'] if TEST else S['channel']; tga,iga,igid=S['tg_account'],S['ig_account'],S['ig_user_id']
out=[]
for st in S['days'][DAY]:
    k=('test_'+DAY+'_' if TEST else '')+st['key']
    if k in LOGF: out.append(k+': уже опубликовано'); continue
    try:
        if st['type']=='tg_photo':
            r=run('TELEGRAM_SEND_PHOTO',{'chat_id':chat,'photo':url(st['card']+'.png')[0],'caption':txt(st),'parse_mode':'HTML'},tga); res=r['data']['result']['message_id']
        elif st['type']=='tg_poll':
            time.sleep(1.2); q,o=S['polls'][st['poll']]
            r=run('TELEGRAM_SEND_POLL',{'chat_id':chat,'question':q,'options':o,'is_anonymous':True},tga); res=r['data']['result']['message_id']
        elif st['type']=='ig_carousel':
            keys=[url(n+'.jpg')[1] for n in st['cards']]
            c=run('INSTAGRAM_CREATE_CAROUSEL_CONTAINER',{'ig_user_id':igid,'caption':txt(st),'child_image_files':[{'name':f'nova_{i+1}.jpg','mimetype':'image/jpeg','s3key':x} for i,x in enumerate(keys)]},iga); cid=c['data']['id']
            res=f'container {cid} (тест, не опубликован)' if TEST else run('INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH',{'ig_user_id':igid,'creation_id':cid,'max_wait_seconds':120},iga)['data'].get('id')
        LOGF[k]={'res':res,'ts':time.time()}; json.dump(LOGF,open(P+'log.json','w'))
        out.append(f'{k}: OK {res}')
    except Exception as ex: out.append(f'{k}: FAIL {str(ex)[:300]}')
try: run('TELEGRAM_SEND_MESSAGE',{'chat_id':S['drafts'],'text':('🧪 ТЕСТ ' if TEST else '📮 ')+f'Нова, {DAY}:\n'+'\n'.join(out)},tga)
except Exception: pass
print(out)
```

Правила:
- Кроме ячеек 0А и 0Б, ничего не скачивай и не запускай со стороны (никаких exec/requests к publish.py). Тексты — в /mnt/files/nova/plan.json, карточки отрисовывает ячейка 0Б. Остальной код выполняй как есть, меняя только указанные значения.
- Если ячейка публикации вернула FAIL — выполни её ещё раз один раз (файл /mnt/files/nova/log.json не даст задублировать уже вышедшие посты).
- Если файлов в /mnt/files/nova/ нет, инструмент недоступен, действие заблокировано или после повтора остался FAIL — ничего не придумывай и сразу отправь владельцу PushNotification с тем, что случилось.
- Ничего другого не публикуй и не отправляй. Если всё вышло — уведомление не нужно. В конце ответь по-русски одной-двумя строками, что вышло.
---
