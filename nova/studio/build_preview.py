import sys
sys.path.insert(0, "/home/claude/nova")
from nova_svg import nova

def bot(emotion, pose, cls=""):
    return (f'<svg class="bot {cls}" xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" aria-hidden="true">'
            f'{nova(emotion, pose)}</svg>')

def spark(x, y, s, color):
    # four-point sparkle, positioned in % of card
    return (f'<svg class="spark" style="left:{x}%;top:{y}%;width:{s}cqw;height:{s}cqw" viewBox="0 0 24 24" aria-hidden="true">'
            f'<path d="M12 0 C13 8 16 11 24 12 C16 13 13 16 12 24 C11 16 8 13 0 12 C8 11 11 8 12 0Z" fill="{color}"/></svg>')

def clouds(color):
    circles = "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in
                      [(0,60,34),(48,52,30),(96,64,36),(150,50,32),(200,62,38),(256,54,30),(306,66,36),(360,52,34),(400,62,30)])
    return (f'<svg class="clouds" viewBox="0 0 400 90" preserveAspectRatio="none" aria-hidden="true">'
            f'<g fill="{color}">{circles}<rect x="0" y="62" width="400" height="40"/></g></svg>')

# ---------- cards ----------
TG1 = f'''
<div class="card wide" style="--bg:#1E1B4B;--plate:#7C3AED;--plate-edge:#4C1D95;--plate-ink:#FFFFFF">
  <div class="blob" style="right:2%;top:6%;width:44cqw;height:44cqw;background:#2B2670"></div>
  {spark(56,14,3.2,"#A3E635")}{spark(90,58,2.2,"#22D3EE")}{spark(60,70,1.8,"#A3E635")}
  <div class="txt" style="left:6cqw;top:9cqw;width:50cqw">
    <div class="kick" style="color:#A3E635">робот нова</div>
    <div class="h" style="font-size:9.4cqw;color:#fff">привет, я&nbsp;нова</div>
    <div class="plate" style="font-size:2.7cqw">проверяю нейросети для вашей семьи</div>
  </div>
  {bot("joy","wave","tilt-l")}
  {clouds("#2B2670")}
</div>'''.replace('class="bot tilt-l"', 'class="bot tilt-l" style="right:5cqw;bottom:4cqw;width:38cqw"')

TG2 = f'''
<div class="card wide" style="--bg:#1E1B4B;--plate:#22D3EE;--plate-edge:#0E7490;--plate-ink:#1E1B4B">
  {spark(64,16,2.6,"#FB923C")}{spark(92,12,1.8,"#22D3EE")}
  <div class="txt" style="left:6cqw;top:8cqw;width:60cqw">
    <div class="kick" style="color:#FB923C">что дети спрашивают у ии</div>
    <div class="h num" style="font-size:17cqw;color:#FB923C">1 из 4</div>
    <div class="plate" style="font-size:2.8cqw">детей советуются с ИИ о личном</div>
    <div class="sub" style="font-size:2.3cqw;color:#C9C4F5">а знает об этом 1 из 12 родителей</div>
  </div>
  {bot("surprise","stand","p2")}
  <div class="src">«Ведомости», сентябрь 2026</div>
  {clouds("#2B2670")}
</div>'''.replace('class="bot p2"', 'class="bot" style="right:6cqw;bottom:5cqw;width:27cqw"')

def ig(bg, kick, kick_c, head, head_c, head_size, plate, plate_bg, plate_edge, plate_ink, emotion, pose, botstyle, extra="", cloud=None, src=""):
    cl = clouds(cloud) if cloud else ""
    s = f'<div class="src" style="color:{head_c};opacity:.75">{src}</div>' if src else ""
    return f'''
<div class="card tall" style="--bg:{bg};--plate:{plate_bg};--plate-edge:{plate_edge};--plate-ink:{plate_ink}">
  {extra}
  <div class="txt" style="left:8cqw;top:9cqw;width:84cqw">
    <div class="kick" style="color:{kick_c}">{kick}</div>
    <div class="h" style="font-size:{head_size}cqw;color:{head_c}">{head}</div>
    <div class="plate" style="font-size:4.3cqw">{plate}</div>
  </div>
  <svg class="bot" style="{botstyle}" xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" aria-hidden="true">{nova(emotion, pose)}</svg>
  {s}{cl}
</div>'''

IG = [
  ig("#7C3AED","робот нова","#A3E635","ваш ребёнок уже пользуется&nbsp;ИИ","#FFFFFF",11.5,
     "кто объяснил ему правила?","#A3E635","#4D7C0F","#1E1B4B","joy","wave",
     "right:9cqw;bottom:5cqw;width:42cqw;transform:rotate(-6deg)",
     '<div class="blob" style="right:2cqw;bottom:-4cqw;width:58cqw;height:58cqw;background:#1E1B4B"></div>'+spark(12,62,4,"#A3E635")+spark(22,74,2.4,"#22D3EE"), cloud="#6D28D9"),
  ig("#1E1B4B","цифра дня","#22D3EE","62%","#22D3EE",26,
     "школьников 8–15 лет пользуются нейросетями","#7C3AED","#4C1D95","#FFFFFF","think","point",
     "right:6cqw;bottom:7cqw;width:38cqw", spark(78,18,3,"#A3E635"), cloud="#2B2670", src="Анкетолог, 2025"),
  ig("#FB923C","а родители?","#1E1B4B","8 из 100","#1E1B4B",18,
     "знают, что ребёнок советуется с&nbsp;ИИ о&nbsp;личном","#1E1B4B","#0B0A24","#FFFFFF","sad","stand",
     "right:7cqw;bottom:7cqw;width:40cqw", spark(80,16,3,"#FFFFFF"), src="«Ведомости», 2026"),
  ig("#A3E635","что делаю я","#1E1B4B","проверено","#1E1B4B",13.5,
     "возраст, настройки и дата проверки","#1E1B4B","#0B0A24","#FFFFFF","proud","cheer",
     "right:8cqw;bottom:8cqw;width:52cqw", spark(14,70,3.6,"#7C3AED")+spark(26,82,2.2,"#1E1B4B")),
  ig("#1E1B4B","начните с гайда","#A3E635","8 правил","#A3E635",16,
     "безопасного ИИ дома. Бесплатно в Telegram","#7C3AED","#4C1D95","#FFFFFF","wink","wave",
     "right:6cqw;bottom:9cqw;width:52cqw",
     spark(16,66,3.4,"#22D3EE")+'<div class="tag">ссылка в профиле ↑</div>', cloud="#2B2670"),
]

def tz(palette, comp, type_, prompt):
    sw = "".join(f'<li><span class="sw" style="background:{h}"></span><span><b>{n}</b><code>{h}</code></span></li>' for n, h in palette)
    return f'''<details class="tz"><summary>ТЗ на визуал</summary>
<div class="tz-body">
  <div><h4>Палитра</h4><ul class="pal">{sw}</ul></div>
  <div><h4>Композиция</h4><p>{comp}</p></div>
  <div><h4>Типографика и приёмы</h4><p>{type_}</p></div>
  <div class="full"><h4>Промпт для фона (Midjourney / DALL-E 3)</h4><pre>{prompt}</pre></div>
</div></details>'''

def hooks(chosen, alts):
    a = "".join(f"<li><span class='hk-t'>{t}</span>{x}</li>" for t, x in alts)
    return f'''<div class="hooks"><div class="hk-chosen"><span class="hk-t">выбран · {chosen[0]}</span>{chosen[1]}</div>
<ul class="hk-alt">{a}</ul></div>'''

P1 = """<b>Робот будет учить вас обращаться с роботами.</b> Звучит подозрительно, понимаю.

Я Нова. Моя работа: проверять нейросети раньше, чем до них доберётся ваш ребёнок. Большинство школьников постарше уже пробовали ИИ. Правила им объясняют редко.

Что здесь будет:
- <b>Проверено Новой.</b> Сервисы, которые работают в России без VPN: с какого возраста, что включить, когда я их проверял.
- <b>Сделали с Новой.</b> Проекты на 10 минут, которые вы делаете вместе с ребёнком.
- <b>Домашка без списывания.</b> ИИ объясняет, пишет ребёнок.
- <b>Как устроен ИИ.</b> Простыми словами, чтобы вы могли пересказать за ужином.

Начнём с подарка: ниже гайд «Безопасный ИИ дома: 8 правил». Две страницы, как раз на чашку чая ☕

Я персонаж, созданный с помощью ИИ. Каждый пост перед публикацией читает живой человек.

<b>А ваш ребёнок уже пробовал нейросети? Напишите в комментариях, какие.</b>"""

P1b = """📎 <b>Гайд «Безопасный ИИ дома: 8 правил»</b>

Внутри правила для всей семьи, сервисы по возрасту, 3 вопроса для разговора с ребёнком и проект на 10 минут. Проверено 4 октября 2026.

Сохраните и перешлите в родительский чат класса. Там он пригодится больше, чем в «Избранном»."""

P2 = """<b>Каждый четвёртый ребёнок советуется с чат-ботом о личном. Знает об этом примерно каждый двенадцатый родитель.</b>

Это данные опроса, о котором в сентябре писали «Ведомости»: так делают 24% детей, а в курсе 8% родителей.

Чат-бот ответит вежливо и уверенно. Только он не знает вашего ребёнка, не отвечает за свой совет и ошибается чаще, чем кажется.

Что можно сделать без запретов и паники:
- Спросите спокойно: «Ты спрашивал у нейросети что-нибудь про себя или друзей?»
- За «да» не ругайте. Лучше узнайте, что ИИ посоветовал.
- Разберите совет вместе: что сказал бы человек, который тебя знает?
- Договоритесь: обиды, страхи и секреты обсуждаем с людьми, а ИИ оставляем для учёбы и проектов.

Я робот, и даже я советую с обидами идти к маме или папе 🤖

<b>А вы знаете, о чём ваш ребёнок спрашивает ИИ?</b> Ответьте в опросе ниже, он анонимный. Итоги покажу в воскресенье."""

IGCAP = """Ваш ребёнок уже пользуется ИИ. Кто объяснил ему правила?

Я Нова, робот, который проверяет нейросети для семей с детьми 7–14 лет. Рассказываю, какие сервисы работают в России, с какого возраста и что сделать с ребёнком за 10 минут.

Заберите бесплатный гайд «Безопасный ИИ дома: 8 правил». Ссылка на Telegram в профиле 👆

Я персонаж, созданный с помощью ИИ.

#нейросетидлядетей #ииидети #родителям #цифроваягигиена #школьники"""

def tg_post(card, text, meta, doc=None):
    body = f'<div class="tg-media">{card}</div>' if card else ""
    if doc:
        body = f'<div class="tg-doc"><span class="doc-ic" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 2h8l5 5v15H6z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M14 2v5h5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></span><span><b>{doc}</b><small>PDF · 2 страницы · 265 КБ</small></span></div>'
    return f'''<div class="tg"><div class="tg-head"><span class="ava">{bot("joy","stand")}</span><span><b>Робот Нова</b><small>{meta}</small></span></div>
{body}<div class="tg-text">{text}</div></div>'''

POLL = '''<div class="tg poll"><div class="poll-q"><b>Ваш ребёнок пользуется нейросетями?</b><small>Анонимный опрос</small></div>
<ul>''' + "".join(f"<li><span class='rd'></span>{o}</li>" for o in ["Да, регулярно","Иногда","Пробовал пару раз","Нет","Не знаю"]) + "</ul></div>"

T_TYPE = "Заголовок <b>Nunito Black</b>, строчными, межстрочный 0,95, трекинг −2%. Пояснение <b>Golos Text Medium</b> на объёмной плашке (тень снизу 0,9&nbsp;% ширины, тон темнее плашки) — так делают «кнопки» в референсе. Капс-надпись сверху: трекинг +8%. Выключка влево."

html = f'''<title>Посты Новы: предпросмотр</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Golos+Text:wght@400;500;600&display=swap">
<style>
/* Layout: одна колонка ленты; на широком экране пост слева, ТЗ и хуки справа. Карточки — фиксированный брендовый цвет в любой теме */
:root{{
  --page:#F3F1FA; --surface:#FFFFFF; --ink:#1B1838; --muted:#5E5A7D; --line:#E2DEF2; --accent:#6D28D9;
  --tg-bubble:#FFFFFF; --tg-bg:#DCE6EE;
  --display:"Nunito","Golos Text",system-ui,sans-serif; --body:"Golos Text",system-ui,-apple-system,"Segoe UI",sans-serif;
}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--page:#121024;--surface:#1C1934;--ink:#ECE9FA;--muted:#A6A1C7;--line:#2E2A50;--accent:#B9A3FF;--tg-bubble:#1F2A36;--tg-bg:#0E1621;color-scheme:dark}}}}
:root[data-theme="dark"]{{--page:#121024;--surface:#1C1934;--ink:#ECE9FA;--muted:#A6A1C7;--line:#2E2A50;--accent:#B9A3FF;--tg-bubble:#1F2A36;--tg-bg:#0E1621;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{background:var(--page);color:var(--ink);font-family:var(--body);font-size:15px;line-height:1.5}}
.wrap{{max-width:1120px;margin:0 auto;padding-inline:20px;padding-block:28px 56px;display:grid;gap:40px}}
header h1{{font-family:var(--display);font-weight:900;font-size:clamp(28px,4.6vw,44px);line-height:1;margin:0 0 10px;text-wrap:balance}}
header p{{margin:0;color:var(--muted);max-width:66ch}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}}
.chip{{font-size:12.5px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);color:var(--muted);background:var(--surface)}}
section{{display:grid;gap:16px}}
.sec-h{{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;border-bottom:1px solid var(--line);padding-bottom:8px}}
.sec-h h2{{font-family:var(--display);font-weight:900;font-size:24px;margin:0}}
.sec-h span{{color:var(--muted);font-size:13.5px}}
.row{{display:grid;grid-template-columns:minmax(0,440px) minmax(0,1fr);gap:24px;align-items:start}}
@media (max-width:860px){{.row{{grid-template-columns:minmax(0,1fr)}}}}
.side{{display:grid;gap:14px;min-width:0}}
/* telegram mock */
.feed{{background:var(--tg-bg);border-radius:18px;padding:14px;display:grid;gap:10px}}
.tg{{background:var(--tg-bubble);border-radius:14px;overflow:hidden;box-shadow:0 1px 2px rgb(0 0 0/.12)}}
.tg-head{{display:flex;gap:10px;align-items:center;padding:10px 12px 8px}}
.tg-head small,.poll-q small,.tg-doc small{{display:block;color:var(--muted);font-size:12px}}
.ava{{width:34px;height:34px;border-radius:50%;background:#1E1B4B;display:grid;place-items:center;overflow:hidden;flex:none}}
.ava .bot{{position:static;width:30px;transform:none}}
.tg-media{{padding:0}}
.tg-text{{padding:10px 14px 14px;white-space:pre-line;font-size:14.5px;line-height:1.45}}
.tg-doc{{display:flex;gap:12px;align-items:center;padding:4px 14px 2px}}
.doc-ic{{width:42px;height:42px;border-radius:50%;background:#7C3AED;color:#fff;display:grid;place-items:center;flex:none}}
.doc-ic svg{{width:22px;height:22px}}
.poll{{padding:12px 14px}}
.poll ul{{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:8px}}
.poll li{{display:flex;gap:10px;align-items:center;font-size:14.5px}}
.rd{{width:18px;height:18px;border-radius:50%;border:2px solid var(--muted);flex:none}}
/* cards */
.card{{container-type:inline-size;position:relative;overflow:hidden;background:var(--bg);width:100%;font-family:var(--display)}}
.card.wide{{aspect-ratio:16/9}}
.card.tall{{aspect-ratio:4/5;border-radius:6px}}
.card .txt{{position:absolute;display:flex;flex-direction:column;align-items:flex-start;gap:2.4cqw;z-index:2}}
.card .kick{{font-family:var(--body);font-weight:600;text-transform:uppercase;letter-spacing:.08em;font-size:2.2cqw}}
.card.tall .kick{{font-size:3.4cqw}}
.card.tall .plate{{max-width:72cqw}}
.card .h{{font-weight:900;line-height:.95;letter-spacing:-.02em;text-wrap:balance}}
.card .num{{letter-spacing:-.04em}}
.card .plate{{font-family:var(--body);font-weight:500;line-height:1.25;background:var(--plate);color:var(--plate-ink);padding:1.1em 1.3em;border-radius:.9em;box-shadow:0 .9cqw 0 var(--plate-edge);max-width:100%;margin-top:1cqw}}
.card .sub{{font-family:var(--body);font-weight:500}}
.card .bot{{position:absolute;z-index:1}}
.card .tilt-l{{transform:rotate(-6deg)}}
.card .blob{{position:absolute;border-radius:50%}}
.card .spark{{position:absolute;z-index:1}}
.card .clouds{{position:absolute;left:0;right:0;bottom:-1px;width:100%;height:9cqw;z-index:0}}
.card .src{{position:absolute;left:6cqw;bottom:3cqw;font-family:var(--body);font-size:1.7cqw;color:#A9A4D6;z-index:2}}
.card.tall .src{{left:8cqw;bottom:4cqw;font-size:2.8cqw}}
.card .tag{{position:absolute;left:8cqw;bottom:7cqw;font-family:var(--body);font-weight:600;font-size:3.6cqw;color:#A3E635;z-index:2}}
/* carousel */
.ig{{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:14px;display:grid;gap:12px;min-width:0}}
.slides{{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(220px,300px);gap:12px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x mandatory}}
.slides figure{{margin:0;scroll-snap-align:start;display:grid;gap:6px}}
.slides figcaption{{font-size:12px;color:var(--muted)}}
.cap{{white-space:pre-line;font-size:14.5px;border-top:1px solid var(--line);padding-top:10px}}
/* hooks and tz */
.hooks{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px;display:grid;gap:10px}}
.hk-t{{display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--accent);font-weight:600;margin-bottom:2px}}
.hk-chosen{{font-weight:600}}
.hk-alt{{list-style:none;margin:0;padding:10px 0 0;border-top:1px solid var(--line);display:grid;gap:8px;color:var(--muted);font-size:14px}}
.hk-alt .hk-t{{color:var(--muted)}}
.tz{{background:var(--surface);border:1px solid var(--line);border-radius:14px}}
.tz summary{{cursor:pointer;padding:12px 14px;font-weight:600}}
.tz summary:focus-visible{{outline:2px solid var(--accent);outline-offset:2px;border-radius:14px}}
.tz-body{{padding:0 14px 14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.tz-body .full{{grid-column:1/-1}}
.tz h4{{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}}
.tz p{{margin:0;font-size:14px}}
.pal{{list-style:none;margin:0;padding:0;display:grid;gap:6px}}
.pal li{{display:flex;gap:10px;align-items:center;font-size:13.5px}}
.pal b{{font-weight:500;margin-right:6px}}
.sw{{width:26px;height:26px;border-radius:7px;border:1px solid var(--line);flex:none}}
code,pre{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}
pre{{margin:0;white-space:pre-wrap;background:var(--page);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.note{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;color:var(--muted);font-size:14px}}
.note b{{color:var(--ink)}}
</style>

<div class="wrap">
<header>
  <h1>Посты Новы на 5–6 октября</h1>
  <p>Пробная версия по правилам nova-copywriter и ui-ux-pro-max, визуальный референс — веб-страницы Duolingo: плоские сочные заливки, крупный округлый заголовок строчными, объёмные плашки-«кнопки», персонаж крупно, облака и искры. В канал ничего не отправлено.</p>
  <div class="chips"><span class="chip">Nunito Black + Golos Text</span><span class="chip">текст на обложке ≤ 20%</span><span class="chip">1 главная цифра + 5–7 слов</span><span class="chip">эмодзи ≤ 2 на пост</span></div>
</header>

<section>
  <div class="sec-h"><h2>Пост 1 · знакомство</h2><span>Telegram · пн 5 октября, 19:30 · закрепить</span></div>
  <div class="row">
    <div class="feed">{tg_post(TG1, P1, "пн 19:30")}</div>
    <div class="side">
      {hooks(("разрыв шаблона","Робот будет учить вас обращаться с роботами. Звучит подозрительно, понимаю."),
             [("боль в лоб","Ваш ребёнок спрашивает у нейросети то, что не спрашивает у вас. И вы об этом, скорее всего, не знаете."),
              ("недосказанность","Меня собрали для одной работы: проверять нейросети раньше, чем до них доберётся ваш ребёнок.")])}
      {tz([("Доминирующий","#1E1B4B"),("Вторичный","#7C3AED"),("Акцент","#A3E635")],
          "Знакомство. Текст слева на 55% ширины: капс-надпись, заголовок, плашка. Нова справа крупно, наклон −6°, машет. Мягкий круг за персонажем, две искры, облака по нижнему краю.",
          T_TYPE,
          "flat vector edtech illustration background, deep indigo night sky #1E1B4B, one large soft circle in #2B2670 on the right, small four-point sparkles in lime #A3E635 and cyan #22D3EE, chunky rounded cloud shapes along the bottom edge in #2B2670, playful friendly mood, clean geometric shapes, generous empty space on the left half for a headline, no text --ar 16:9 --style raw")}
    </div>
  </div>
</section>

<section>
  <div class="sec-h"><h2>Пост 1b · гайд</h2><span>Telegram · пн 5 октября, 19:31 · сразу после знакомства</span></div>
  <div class="row">
    <div class="feed">{tg_post(None, P1b, "пн 19:31", doc="Безопасный ИИ дома — гайд Новы.pdf")}</div>
    <div class="side"><div class="note"><b>Хук здесь не нужен:</b> это вложение к посту-знакомству. Файл будет называться по-человечески, а не набором букв. Сам гайд переверстаю в новых шрифтах после вашего одобрения стиля.</div></div>
  </div>
</section>

<section>
  <div class="sec-h"><h2>Карусель · знакомство</h2><span>Instagram · пн 5 октября, 19:30 · 5 слайдов 1080×1350</span></div>
  <div class="row">
    <div class="ig">
      <div class="slides">{"".join(f'<figure>{c}<figcaption>Слайд {i}/5</figcaption></figure>' for i, c in enumerate(IG, 1))}</div>
      <div class="cap">{IGCAP}</div>
    </div>
    <div class="side">
      {hooks(("боль в лоб","Ваш ребёнок уже пользуется ИИ. Кто объяснил ему правила?"),
             [("разрыв шаблона","Робот, который проверяет роботов"),("недосказанность","8 правил ИИ, которые стоит знать до 14 лет")])}
      {tz([("Доминирующий","#1E1B4B"),("Вторичный","#7C3AED"),("Акцент","#A3E635 / #FB923C")],
          "Каждый слайд — своя сплошная заливка: фиолетовый, индиго, оранжевый, лайм, индиго. Слева сверху одна главная цифра или слово, под ним плашка с пояснением. Нова в правом нижнем углу с разной эмоцией. Источник цифры мелко внизу слева.",
          T_TYPE + " Цифры набраны с трекингом −4%, чтобы держались единым блоком.",
          "flat vector background for an Instagram carousel, solid vivid violet #7C3AED field, chunky rounded cloud band along the bottom in #6D28D9, a few four-point sparkles in lime #A3E635 and cyan #22D3EE, friendly edtech style, crisp geometric shapes, large empty area in the upper two thirds for a headline, no text --ar 4:5 --style raw")}
    </div>
  </div>
</section>

<section>
  <div class="sec-h"><h2>Пост 2 · «1 из 4»</h2><span>Telegram · вт 6 октября, 19:30 · пост + опрос</span></div>
  <div class="row">
    <div class="feed">{tg_post(TG2, P2, "вт 19:30")}{POLL}</div>
    <div class="side">
      {hooks(("разрыв шаблона","Каждый четвёртый ребёнок советуется с чат-ботом о личном. Знает об этом примерно каждый двенадцатый родитель."),
             [("боль в лоб","Ребёнок поссорился с другом и пошёл за советом к нейросети. Вы узнаете об этом последним."),
              ("недосказанность","Есть вопрос, который дети задают ИИ втрое чаще, чем думают родители. И он не про домашку.")])}
      {tz([("Доминирующий","#1E1B4B"),("Вторичный","#22D3EE"),("Акцент","#FB923C")],
          "Тревожная тема, поэтому тёплый оранжевый акцент. Главная цифра «1 из 4» слева сверху на 60% ширины, под ней циановая плашка, ниже мелкая вторая цифра. Нова справа с удивлённым лицом. Источник мелко внизу.",
          T_TYPE,
          "flat vector background, deep indigo #1E1B4B, soft abstract chat bubble shapes in #2B2670 drifting on the right side, two small four-point sparkles in warm orange #FB923C and cyan #22D3EE, rounded cloud band along the bottom, calm but slightly alert mood, modern edtech web illustration, large empty area on the left for a big number, no text --ar 16:9 --style raw")}
    </div>
  </div>
</section>

<div class="note"><b>Чтобы работал вопрос «напишите в комментариях»,</b> к каналу нужно привязать группу обсуждений: «Управление каналом» → «Обсуждение» → создать группу. Без неё комментарии в Telegram не открываются.</div>
</div>
'''
open("/home/claude/nova/preview/nova-posts-preview.html", "w", encoding="utf-8").write(html)
print(len(html))
