import sys, subprocess
sys.path.insert(0, "/home/claude/nova")
from nova_svg import nova

def bot(emotion, pose, w=150):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="20 0 220 210" width="{w}" height="{int(w*210/220)}">{nova(emotion, pose)}</svg>'

RULES = [
    ("Детский режим или аккаунт взрослого",
     "Ребёнок не заводит свой аккаунт в нейросети. Где есть детский режим — включаем его: в Шедевруме детский профиль привязан к аккаунту взрослого и закрыт PIN-кодом, а подписки, друзья и комментарии в нём выключены. В Алисе и GigaChat детских аккаунтов нет: по условиям сервисов ребёнок пользуется ими только под контролем взрослого."),
    ("До 10 лет — только вместе",
     "Младшие школьники пользуются ИИ рядом со взрослым: вы читаете ответ вместе и решаете, что с ним делать. Это не недоверие, а совместная игра."),
    ("Никаких личных данных",
     "В запросах не пишем имя и фамилию, номер школы, адрес, телефон, не загружаем фото и голос — ни свои, ни друзей. Нейросеть не нужно знать, кто вы, чтобы нарисовать дракона."),
    ("ИИ ошибается — проверяем",
     "Нейросеть уверенно выдумывает факты, даты и даже цитаты. Важное сверяем со вторым источником: учебником, энциклопедией, взрослым. Игра «поймай ИИ на ошибке» учит этому лучше лекций."),
    ("Никаких дипфейков реальных людей",
     "Не делаем картинки, видео и голоса с одноклассниками, учителями, родственниками и знаменитостями. Даже в шутку: такая «шутка» может сильно обидеть и быть незаконной."),
    ("ИИ — не друг и не психолог",
     "Чат-бот может звучать тепло, но он не человек и не несёт ответственности за советы. С обидами, страхами и секретами — к людям, которым ребёнок доверяет. Сервисы «ИИ-друзей» и болталки с персонажами детям не подходят."),
    ("Домашка: ИИ объясняет — пишешь ты",
     "Можно попросить объяснить тему, проверить ход решения, придумать похожую задачу для тренировки. Нельзя — получить готовое сочинение или ответ и сдать как своё."),
    ("Раз в неделю — разговор",
     "Родители обычно не видят переписку ребёнка с нейросетью. Поэтому просто спрашивайте: что ты делал с ИИ на этой неделе? Что получилось? Где он ошибся? Без допроса — с интересом."),
]

TOOLS = [
    ("7–10 лет, только с родителем", "Шедеврум в Детском режиме", "картинки, раскраски, голосовой ввод"),
    ("7–14 лет", "Machine Learning for Kids + Scratch", "научить компьютер узнавать картинки или звуки и сделать игру; есть русский язык"),
    ("11–14 лет, правила вместе с родителем", "Алиса AI, GigaChat", "объяснения тем, проверка решений, английский"),
    ("Не рекомендуем детям", "ChatGPT, Gemini, Claude, Character.AI", "официально недоступны в России или оценены экспертами как рискованные для детей; через VPN — тоже нет"),
]

C = dict(v="#7C3AED", vd="#6D28D9", s="#1E1B4B", c="#22D3EE", l="#A3E635", ink="#1E1B4B", muted="#5B5784", paper="#FFFFFF", soft="#F4F1FE")

rules_html = "".join(
    f'<div class="rule"><div class="num">{i}</div><div><h3>{t}</h3><p>{d}</p></div></div>'
    for i, (t, d) in enumerate(RULES, 1))
tools_html = "".join(
    f'<tr><td class="age">{a}</td><td class="tool">{t}</td><td>{u}</td></tr>' for a, t, u in TOOLS)

html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nunito:wght@800;900&family=Golos+Text:wght@400;500;600;700&display=swap"><style>
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: 'Golos Text', 'DejaVu Sans', sans-serif; color:{C['ink']}; background:{C['paper']}; }}
.page {{ width:210mm; height:296mm; padding:16mm 16mm 12mm; position:relative; page-break-after:always; overflow:hidden; }}
.page:last-child {{ page-break-after:auto; }}
.hero {{ background:{C['s']}; color:white; border-radius:18px; padding:18px 22px; display:flex; align-items:center; }}
.hero .txt {{ flex:1; padding-left:14px; }}
.kicker {{ color:{C['l']}; font-size:11pt; font-weight:600; letter-spacing:.04em; text-transform:uppercase; }}
h1 {{ font-family:'Nunito',sans-serif; font-size:27pt; letter-spacing:-.01em; line-height:1.1; margin:6px 0 8px; font-weight:800; }}
.lead {{ font-size:11pt; line-height:1.45; color:#D9D6F7; margin:0; }}
.rules {{ margin-top:10px; }}
.rule {{ display:flex; padding:6px 0; border-bottom:1px solid #E6E2FA; }}
.rule:last-child {{ border-bottom:none; }}
.num {{ font-family:'Nunito',sans-serif; box-shadow:0 3px 0 #4C1D95; width:30px; height:30px; min-width:30px; border-radius:50%; background:{C['v']}; color:white; font-weight:800; font-size:13pt; text-align:center; line-height:30px; margin-right:14px; }}
.rule h3 {{ font-family:'Nunito',sans-serif; font-weight:900; margin:2px 0 3px; font-size:13pt; }}
.rule p {{ margin:0; font-size:10pt; line-height:1.45; color:#3A3666; }}
h2 {{ font-family:'Nunito',sans-serif; font-size:19pt; margin:4px 0 10px; font-weight:800; }}
table {{ width:100%; border-collapse:collapse; font-size:10pt; }}
th {{ text-align:left; background:{C['soft']}; color:{C['vd']}; padding:8px 10px; font-size:9.5pt; text-transform:uppercase; letter-spacing:.03em; }}
td {{ padding:9px 10px; border-bottom:1px solid #E6E2FA; vertical-align:top; line-height:1.4; }}
td.age {{ font-weight:600; width:30%; }} td.tool {{ font-weight:700; width:28%; }}
tr.no td {{ color:#8A1C1C; }}
.box {{ background:{C['soft']}; border-left:5px solid {C['l']}; border-radius:10px; padding:12px 16px; margin-top:16px; }}
.box h3 {{ font-family:'Nunito',sans-serif; font-weight:900; margin:0 0 6px; font-size:13pt; }}
.box ol {{ margin:0; padding-left:20px; font-size:10.5pt; line-height:1.55; }}
.box ul {{ margin:0; padding-left:18px; font-size:10.5pt; line-height:1.55; }}
.foot {{ position:absolute; left:16mm; right:16mm; bottom:10mm; font-size:8.5pt; color:{C['muted']}; line-height:1.4; border-top:1px solid #E6E2FA; padding-top:6px; }}
.brand {{ font-weight:700; color:{C['v']}; }}
.side {{ display:flex; align-items:center; margin-top:16px; }}
.side .t {{ flex:1; padding-left:12px; font-size:11pt; line-height:1.45; }}
</style></head><body>
<div class="page">
  <div class="hero">{bot('joy','wave',120)}<div class="txt">
    <div class="kicker">Гайд Новы · для родителей детей 7–14 лет</div>
    <h1>Безопасный ИИ дома: 8&nbsp;правил</h1>
    <p class="lead">Нейросетями уже пользуется большинство школьников 11–14 лет. Вот короткие правила, с которыми ИИ становится полезной игрой, а не тревогой.</p>
  </div></div>
  <div class="rules">{rules_html}</div>
  <div class="foot"><span class="brand">Робот Нова · t.me/nova_family_ai</span> — Нова проверяет нейросети для вашей семьи. Нова — персонаж, созданный с помощью ИИ. Это памятка, а не официальная методика: российских официальных рекомендаций для родителей по детскому ИИ пока нет.</div>
</div>
<div class="page">
  <h2>Что можно и чего нельзя: по возрасту</h2>
  <table><tr><th>Возраст</th><th>Сервис</th><th>Для чего</th></tr>{tools_html}</table>
  <div class="box"><h3>3 вопроса для разговора на этой неделе</h3><ul>
    <li>Что самое интересное ты сделал с нейросетью?</li>
    <li>Был случай, когда ИИ ответил неправильно или странно?</li>
    <li>Что бы ты хотел попробовать сделать с ИИ вместе со мной?</li>
  </ul></div>
  <div class="box proj"><h3>Проект на 10 минут: своя раскраска</h3><ol>
    <li>Взрослый открывает Шедеврум и включает Детский режим.</li>
    <li>Ребёнок придумывает героя и место: «ёжик-космонавт на Луне».</li>
    <li>Пишем запрос: <i>«контурный рисунок для раскраски, ёжик-космонавт на Луне, толстые чёрные линии, белый фон, без цвета»</i>.</li>
    <li>Выбираем лучший вариант, сохраняем и печатаем. Раскрашиваем вместе.</li>
    <li>Бонус: спросите, что ИИ нарисовал «не так», — это первый шаг к критическому мышлению.</li>
  </ol></div>
  <div class="side">{bot('think','point',110)}<div class="t"><b>Условия сервисов меняются примерно раз в квартал.</b> Поэтому у каждого обзора Новы есть дата проверки. Этот гайд проверен <b>4 октября 2026 года</b>. Новые проверки и совместные проекты на 10 минут — в Telegram-канале <b>t.me/nova_family_ai</b>.</div></div>
  <div class="foot">Источники: условия сервисов «Алиса AI» (Яндекс, ред. от 10.09.2026), GigaChat для несовершеннолетних (Сбер), справка Шедеврума о Детском режиме; Machine Learning for Kids; оценки безопасности ИИ-сервисов Common Sense Media (2025). <span class="brand">Робот Нова</span> не связан с перечисленными сервисами и не получает от них оплату.</div>
</div>
</body></html>"""

open("/home/claude/nova/guide/guide.html", "w", encoding="utf-8").write(html)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome") if False else p.chromium.launch()
    pg=b.new_page(); pg.goto("file:///home/claude/nova/guide/guide.html"); pg.wait_for_timeout(300)
    pg.pdf(path="/home/claude/nova/guide/Безопасный ИИ дома — гайд Новы.pdf", format="A4", print_background=True, margin=dict(top="0",bottom="0",left="0",right="0"))
    b.close()
print("ok")
