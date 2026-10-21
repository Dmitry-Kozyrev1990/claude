// Кабинет организатора: закупки, позиции и коробки, участники, оплаты, факт по весу, раздача, тексты для чата.
(function () {
  const root = document.getElementById("root");
  let ME = null;            // /api/me
  let P = null;             // открытая закупка (owner_view)
  let filter = "all";       // фильтр участников
  let editItem = null;      // id позиции в форме правки
  let error = "";

  const go = h => { location.hash = h; };
  const route = () => location.hash.replace(/^#/, "").split("/");
  const shareUrl = p => `${location.origin}/z/${p.slug}`;
  const pct = v => String(v).replace(".", ",");

  async function start() {
    try { ME = await D.api("GET", "/api/me"); } catch (e) { root.innerHTML = `<div class="err">${D.esc(e.message)}</div>`; return; }
    window.addEventListener("hashchange", show);
    show();
  }

  async function show() {
    error = "";
    if (!ME.me) return renderAuth(route()[0] === "login" ? "login" : "register");
    const [view, id, tab] = route();
    try {
      if (view === "p" && id) { P = await D.api("GET", `/api/purchases/${id}`); return renderPurchase(tab || "items"); }
      if (view === "new") return renderPurchaseForm(null);
      if (view === "plan") return renderPlan();
      return renderList(await D.api("GET", "/api/purchases"));
    } catch (e) {
      if (e.status === 401) { ME.me = null; return renderAuth("login"); }
      root.innerHTML = top() + `<div class="err">${D.esc(e.message)}</div><a href="#">К списку закупок</a>`;
    }
  }

  function top() {
    const badge = ME.plan === "pro" ? `<span class="badge">${ME.trial ? "Пробный «Про»" : "Про"}</span>` : `<span class="badge grey">Бесплатный</span>`;
    return `<div class="top"><a class="logo" href="#"><img src="/static/icon.svg" alt="">Долька</a>
      <div class="row"><a href="#plan">${badge}</a><button class="ghost sm" id="logout">Выйти</button></div></div>`;
  }

  function bindTop() {
    const b = document.getElementById("logout");
    if (b) b.onclick = async () => { await D.api("POST", "/api/logout"); ME = await D.api("GET", "/api/me"); go(""); show(); };
  }

  function planNote() {
    if (ME.plan === "pro" && ME.trial) return `<div class="note">Пробный период «Про» до ${D.date(ME.sub_ends)}. Дальше — 500 ₽ в месяц или бесплатный тариф с ограничениями. <a href="#plan">Тарифы</a></div>`;
    if (ME.plan === "free") return `<div class="note">Бесплатный тариф: ${ME.limits.active_purchases} незакрытая закупка, до ${ME.limits.orders_per_purchase} участников. <a href="#plan">Подключить «Про» за 500 ₽/мес</a></div>`;
    return "";
  }

  // ---------- вход ----------
  function renderAuth(mode) {
    const reg = mode === "register";
    root.innerHTML = `<div class="top"><a class="logo" href="/"><img src="/static/icon.svg" alt="">Долька</a></div>
      <div class="card" style="max-width:420px;margin:24px auto">
        <h1>${reg ? "Регистрация организатора" : "Вход"}</h1>
        ${reg ? `<p class="muted">14 дней «Про» бесплатно, без карты.</p>` : ""}
        <div class="err hidden" id="err"></div>
        <form id="f">
          ${reg ? `<label>Как к вам обращаться<input name="name" maxlength="80" autocomplete="name"></label>` : ""}
          <label>Почта<input name="email" type="email" required autocomplete="email"></label>
          <label>Пароль${reg ? " (от 8 символов)" : ""}<input name="password" type="password" required minlength="${reg ? 8 : 1}" autocomplete="${reg ? "new-password" : "current-password"}"></label>
          <button class="primary" style="width:100%">${reg ? "Создать аккаунт" : "Войти"}</button>
        </form>
        <p class="small" style="margin-top:12px">${reg ? `Уже есть аккаунт? <a href="#login">Войти</a>` : `Нет аккаунта? <a href="#register">Зарегистрироваться</a>`}</p>
      </div>`;
    document.getElementById("f").onsubmit = async ev => {
      ev.preventDefault();
      const f = ev.target;
      try {
        ME = await D.api("POST", reg ? "/api/register" : "/api/login",
          { email: f.email.value, password: f.password.value, name: f.name ? f.name.value : "" });
        go(""); show();
      } catch (e) {
        const el = document.getElementById("err"); el.textContent = e.message; el.classList.remove("hidden");
      }
    };
  }

  // ---------- список ----------
  function renderList(list) {
    const cards = list.map(p => `<a class="card" href="#p/${p.id}" style="display:block;text-decoration:none;color:inherit">
        <div class="row between"><b>${D.esc(p.title)}</b><span class="badge ${p.status === "closed" ? "grey" : p.status === "open" ? "" : "warn"}">${D.esc(p.status_name)}</span></div>
        <div class="small muted">${p.supplier ? D.esc(p.supplier) + " · " : ""}участников: ${p.participants}${p.deadline ? " · стоп " + D.date(p.deadline) : ""}</div>
      </a>`).join("");
    root.innerHTML = top() + planNote() + `
      <div class="row between" style="margin-bottom:12px"><h1 style="margin:0">Мои закупки</h1>
        <a class="btn primary" href="#new">+ Новая закупка</a></div>
      ${cards || `<div class="card"><h2>Первая закупка</h2>
        <p>Создайте закупку, добавьте позиции поставщика и отправьте ссылку в чат. Участники заказывают сами — без регистрации, а вы видите сводку, коробки, долги и список раздачи.</p>
        <a class="btn primary" href="#new">Создать закупку</a></div>`}`;
    bindTop();
  }

  // ---------- форма закупки ----------
  function purchaseFields(p) {
    p = p || { title: "", supplier: "", description: "", deadline: "", min_total_kop: 0, fee_pct: 10, pickup: "", pay_info: "" };
    return `
      <label>Название<input name="title" required maxlength="120" value="${D.esc(p.title)}" placeholder="Например: Крупы и масло, октябрь"></label>
      <div class="grid2">
        <label>Поставщик<input name="supplier" maxlength="200" value="${D.esc(p.supplier)}" placeholder="База, сайт или фермер"></label>
        <label>Стоп заказов (мск)<input name="deadline" type="datetime-local" value="${D.esc(p.deadline || "")}"></label>
        <label>Минимальный заказ у поставщика, ₽<input name="min_total" inputmode="decimal" value="${p.min_total_kop ? p.min_total_kop / 100 : ""}" placeholder="0"></label>
        <label>Оргсбор, %<input name="fee_pct" inputmode="decimal" value="${pct(p.fee_pct)}"></label>
      </div>
      <label>Описание для участников<textarea name="description" maxlength="4000" placeholder="Условия, сроки поставки, что важно знать">${D.esc(p.description)}</textarea></label>
      <label>Как оплатить<textarea name="pay_info" maxlength="1000" placeholder="Перевод по СБП на +7…, банк, получатель. Деньги идут вам напрямую.">${D.esc(p.pay_info)}</textarea></label>
      <label>Где и когда раздача<textarea name="pickup" maxlength="1000" placeholder="Адрес, подъезд, время">${D.esc(p.pickup)}</textarea></label>`;
  }

  function formData(f) {
    return { title: f.title.value, supplier: f.supplier.value, deadline: f.deadline.value, min_total: f.min_total.value || 0,
      fee_pct: (f.fee_pct.value || "0").replace(",", "."), description: f.description.value,
      pay_info: f.pay_info.value, pickup: f.pickup.value };
  }

  function renderPurchaseForm() {
    root.innerHTML = top() + `<a href="#">← Закупки</a><h1 style="margin-top:12px">Новая закупка</h1>
      <div class="err hidden" id="err"></div>
      <form class="card" id="f">${purchaseFields(null)}<button class="primary">Создать и добавить позиции</button></form>`;
    bindTop();
    document.getElementById("f").onsubmit = async ev => {
      ev.preventDefault();
      try {
        const p = await D.api("POST", "/api/purchases", formData(ev.target));
        go(`p/${p.id}/items`);
      } catch (e) { const el = document.getElementById("err"); el.textContent = e.message; el.classList.remove("hidden"); }
    };
  }

  // ---------- закупка ----------
  async function act(fn) {
    try { const res = await fn(); if (res && res.items) P = res; else if (res && res.purchase) P = res.purchase; error = ""; }
    catch (e) { error = e.message; }
    renderPurchase(route()[2] || "items");
  }

  function renderPurchase(tab) {
    const s = P.summary;
    const minLine = P.min_total_kop
      ? `<div class="small" style="margin-top:8px">Минимальный заказ: ${D.rub(s.supplier_kop)} из ${D.rub(P.min_total_kop)} ${s.min_reached ? "✓" : ""}</div>
         <div class="bar ${s.min_reached ? "" : "warn"}" style="margin-top:4px"><i style="width:${Math.min(100, Math.round(s.supplier_kop / P.min_total_kop * 100))}%"></i></div>` : "";
    const statusOpts = Object.entries(ME.statuses).map(([k, v]) => `<option value="${k}" ${k === P.status ? "selected" : ""}>${v}</option>`).join("");
    const tabs = [["items", "Позиции"], ["orders", `Участники · ${s.participants}`], ["chat", "Тексты для чата"], ["settings", "Настройки"]]
      .map(([k, v]) => `<button data-tab="${k}" class="${k === tab ? "on" : ""}">${v}</button>`).join("");
    let body = "";
    if (tab === "orders") body = ordersTab();
    else if (tab === "chat") body = chatTab();
    else if (tab === "settings") body = settingsTab();
    else body = itemsTab();
    root.innerHTML = top() + `<a href="#">← Закупки</a>
      <div class="card" style="margin-top:12px">
        <div class="row between"><h1 style="margin:0">${D.esc(P.title)}</h1>
          <select id="status" style="width:auto">${statusOpts}</select></div>
        <div class="small muted" style="margin-top:4px">${P.supplier ? D.esc(P.supplier) + " · " : ""}${P.deadline ? "стоп " + D.date(P.deadline) : "без даты стопа"}${P.status === "open" && !P.accepting ? " · стоп прошёл, участники уже не могут менять заказы" : ""}</div>
        <div class="row" style="margin-top:12px"><input readonly value="${D.esc(shareUrl(P))}" style="flex:1;min-width:0"><button id="copyShare">Копировать ссылку</button></div>
        ${minLine}
      </div>
      <div class="stats" style="margin-bottom:12px">
        <div class="card"><div class="small muted">У поставщика</div><div class="stat">${D.rub(s.supplier_kop)}</div></div>
        <div class="card"><div class="small muted">Оргсбор</div><div class="stat">${D.rub(s.fee_kop)}</div></div>
        <div class="card"><div class="small muted">Оплачено</div><div class="stat">${D.rub(s.paid_kop)}</div><div class="small muted">из ${D.rub(s.total_kop)}</div></div>
        <div class="card"><div class="small muted">Долги</div><div class="stat">${D.rub(s.debt_kop)}</div><div class="small muted">${s.unpaid} чел. · выдано ${s.picked_up}/${s.participants}</div></div>
      </div>
      ${error ? `<div class="err">${D.esc(error)}</div>` : ""}
      <div class="tabs">${tabs}</div>
      ${body}`;
    bindTop();
    root.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => go(`p/${P.id}/${b.dataset.tab}`));
    document.getElementById("copyShare").onclick = () => D.copy(shareUrl(P));
    document.getElementById("status").onchange = ev => act(() => D.api("PUT", `/api/purchases/${P.id}`, { status: ev.target.value }));
    bindTab(tab);
  }

  // ---------- позиции ----------
  function itemsTab() {
    const rows = P.items.map(i => {
      const pack = i.pack ? (i.missing ? `<span class="badge warn">не хватает ${i.missing} ${D.esc(i.unit)}</span>
          <button class="sm" data-trim="${i.id}" title="Снять остаток с последних заказов">Обрезать до коробок</button>`
        : i.total_milli ? `<span class="badge">коробок: ${i.packs}</span>` : "") : "";
      return `<div class="item">
        <div class="row between"><div class="grow"><b>${D.esc(i.name)}</b>
          <div class="small muted">${D.rub(i.price_kop)} за ${D.esc(i.unit)} · шаг ${i.step}${i.pack ? ` · коробка ${i.pack}` : ""}</div></div>
          <div style="text-align:right"><b>${i.total} ${D.esc(i.unit)}</b><div class="small muted">${D.rub(i.sum_kop)}</div></div></div>
        <div class="row" style="margin-top:6px">${pack}
          <button class="sm ghost" data-edit="${i.id}">Изменить</button><button class="sm ghost danger" data-del="${i.id}">Удалить</button></div>
      </div>`;
    }).join("");
    const e = editItem ? P.items.find(i => i.id === editItem) : null;
    const units = ME.units.map(u => `<option ${e && e.unit === u ? "selected" : ""}>${u}</option>`).join("");
    return `<div class="card"><div class="row between"><h2 style="margin:0">Позиции</h2>
        ${P.items.length ? `<a class="btn sm" href="/api/purchases/${P.id}/export/supplier.csv">Заказ поставщику (CSV)</a>` : ""}</div>
        <div class="list">${rows || `<p class="muted" style="margin-top:8px">Добавьте позиции из прайса поставщика.</p>`}</div></div>
      <form class="card" id="itemForm">
        <h3>${e ? "Изменить позицию" : "Добавить позицию"}</h3>
        <label>Название<input name="name" required maxlength="200" value="${D.esc(e ? e.name : "")}" placeholder="Гречка ядрица"></label>
        <div class="grid2">
          <label>Единица<select name="unit">${units}</select></label>
          <label>Цена за единицу, ₽<input name="price" required inputmode="decimal" value="${e ? e.price_kop / 100 : ""}"></label>
          <label>Шаг заказа (например 1 или 0,5)<input name="step" inputmode="decimal" value="${e ? e.step : "1"}"></label>
          <label>Коробка (ряд) — сколько единиц, 0 если нет<input name="pack" inputmode="decimal" value="${e ? e.pack || "0" : "0"}"></label>
        </div>
        <div class="row"><button class="primary">${e ? "Сохранить" : "Добавить"}</button>${e ? `<button type="button" id="cancelItem">Отмена</button>` : ""}</div>
      </form>`;
  }

  function bindItems() {
    root.querySelectorAll("[data-trim]").forEach(b => b.onclick = async () => {
      if (!confirm("Снять остаток до целой коробки с самых поздних заказов?")) return;
      try {
        const res = await D.api("POST", `/api/items/${b.dataset.trim}/trim`);
        P = res.purchase;
        D.toast(res.removed.length ? "Обрезано: " + res.removed.map(r => `${r.name} −${r.removed}`).join(", ") : "Нечего обрезать");
      } catch (e) { error = e.message; }
      renderPurchase("items");
    });
    root.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => { editItem = +b.dataset.edit; renderPurchase("items"); document.getElementById("itemForm").scrollIntoView(); });
    root.querySelectorAll("[data-del]").forEach(b => b.onclick = () => {
      const i = P.items.find(x => x.id === +b.dataset.del);
      if (!confirm(`Удалить «${i.name}»?${i.total_milli ? " Позиция пропадёт из заказов участников." : ""}`)) return;
      act(() => D.api("DELETE", `/api/items/${i.id}`));
    });
    const c = document.getElementById("cancelItem");
    if (c) c.onclick = () => { editItem = null; renderPurchase("items"); };
    document.getElementById("itemForm").onsubmit = ev => {
      ev.preventDefault();
      const f = ev.target;
      const body = { name: f.name.value, unit: f.unit.value, price: f.price.value.replace(",", "."),
        step: f.step.value.replace(",", "."), pack: (f.pack.value || "0").replace(",", ".") };
      const id = editItem;
      editItem = null;
      act(() => id ? D.api("PUT", `/api/items/${id}`, body) : D.api("POST", `/api/purchases/${P.id}/items`, body));
    };
  }

  // ---------- участники ----------
  function ordersTab() {
    const items = Object.fromEntries(P.items.map(i => [i.id, i]));
    const f = { all: () => true, unpaid: o => o.balance_kop > 0, says: o => o.says_paid && o.balance_kop > 0, notpicked: o => !o.picked_up };
    const counts = Object.fromEntries(Object.entries(f).map(([k, fn]) => [k, P.orders.filter(fn).length]));
    const chips = [["all", "Все"], ["unpaid", "Не оплатили"], ["says", "Сообщили об оплате"], ["notpicked", "Не выдано"]]
      .map(([k, v]) => `<button data-filter="${k}" class="${filter === k ? "on" : ""}">${v} · ${counts[k]}</button>`).join("");
    const cards = P.orders.filter(f[filter]).map(o => {
      const lines = o.lines.map(l => {
        const i = items[l.item_id];
        return `<tr><td>${D.esc(i.name)}</td><td class="num">${l.qty} ${D.esc(i.unit)}</td>
          <td class="num"><input class="line-fact" data-fact="${o.id}:${l.item_id}" value="${D.esc(l.fact)}" placeholder="факт" inputmode="decimal" aria-label="Факт, ${D.esc(i.unit)}"></td>
          <td class="num">${D.rub(l.sum_kop)}</td></tr>`;
      }).join("");
      const pay = o.balance_kop <= 0 ? (o.balance_kop < 0 ? `<span class="badge warn">переплата ${D.rub(-o.balance_kop)}</span>` : `<span class="badge">оплачено</span>`)
        : o.says_paid ? `<span class="badge warn">говорит, что оплатил(а)</span>` : `<span class="badge bad">долг ${D.rub(o.balance_kop)}</span>`;
      return `<div class="card">
        <div class="row between"><div><b>${D.esc(o.name)}</b>${o.phone ? ` · <a href="tel:${D.esc(o.phone)}">${D.esc(o.phone)}</a>` : ""}</div>${pay}</div>
        ${o.comment ? `<div class="small muted">«${D.esc(o.comment)}»</div>` : ""}
        <div class="scroll"><table style="margin-top:8px"><tr><th>Позиция</th><th class="num">Заказ</th><th class="num">Факт</th><th class="num">Сумма</th></tr>${lines}
          <tr><td colspan="3">Итого${o.fee_kop ? ` (оргсбор ${D.rub(o.fee_kop)})` : ""}</td><td class="num"><b>${D.rub(o.total_kop)}</b></td></tr></table></div>
        <div class="row" style="margin-top:8px">
          <label style="margin:0;flex:1;min-width:140px">Оплачено, ₽<input data-paid="${o.id}" inputmode="decimal" value="${o.paid_kop ? o.paid_kop / 100 : ""}" placeholder="0"></label>
          <button class="sm" data-fullpay="${o.id}">= ${D.rub(o.total_kop)}</button>
          <label class="row" style="margin:0;color:var(--ink)"><input type="checkbox" data-picked="${o.id}" ${o.picked_up ? "checked" : ""} style="width:auto"> выдано</label>
          <button class="sm ghost danger" data-delorder="${o.id}">Удалить</button>
        </div></div>`;
    }).join("");
    return `<div class="row between" style="margin-bottom:8px"><div class="tabs" style="margin:0;padding:0">${chips}</div>
        ${P.orders.length ? `<a class="btn sm" href="/api/purchases/${P.id}/export/orders.csv">Лист раздачи (CSV)</a>` : ""}</div>
      ${P.orders.length ? `<p class="small muted">«Факт» — сколько реально приехало по весу; сумма участника пересчитается автоматически.</p>` : ""}
      ${cards || `<div class="card muted">${P.orders.length ? "Нет участников в этом фильтре." : "Пока никто не заказал. Отправьте ссылку в чат — вкладка «Тексты для чата»."}</div>`}`;
  }

  function bindOrders() {
    root.querySelectorAll("[data-filter]").forEach(b => b.onclick = () => { filter = b.dataset.filter; renderPurchase("orders"); });
    root.querySelectorAll("[data-fact]").forEach(inp => inp.onchange = () => {
      const [oid, iid] = inp.dataset.fact.split(":");
      act(() => D.api("PUT", `/api/orders/${oid}`, { facts: { [iid]: inp.value.replace(",", ".") } }));
    });
    root.querySelectorAll("[data-paid]").forEach(inp => inp.onchange = () =>
      act(() => D.api("PUT", `/api/orders/${inp.dataset.paid}`, { paid: (inp.value || "0").replace(",", ".") })));
    root.querySelectorAll("[data-fullpay]").forEach(b => b.onclick = () => {
      const o = P.orders.find(x => x.id === +b.dataset.fullpay);
      act(() => D.api("PUT", `/api/orders/${o.id}`, { paid: o.total_kop / 100 }));
    });
    root.querySelectorAll("[data-picked]").forEach(cb => cb.onchange = () =>
      act(() => D.api("PUT", `/api/orders/${cb.dataset.picked}`, { picked_up: cb.checked })));
    root.querySelectorAll("[data-delorder]").forEach(b => b.onclick = () => {
      const o = P.orders.find(x => x.id === +b.dataset.delorder);
      if (confirm(`Удалить заказ участника ${o.name}?`)) act(() => D.api("DELETE", `/api/orders/${o.id}`));
    });
  }

  // ---------- тексты для чата ----------
  function chatTexts() {
    const url = shareUrl(P);
    const list = P.items.map(i => `• ${i.name} — ${D.rub(i.price_kop)}/${i.unit}${i.pack ? ` (коробка ${i.pack})` : ""}`).join("\n");
    const head = [`🛒 Совместная закупка: ${P.title}`];
    if (P.supplier) head.push(`Поставщик: ${P.supplier}`);
    if (P.deadline) head.push(`Стоп заказов: ${D.date(P.deadline)}`);
    head.push(P.fee_pct ? `Оргсбор: ${pct(P.fee_pct)}%` : "Без оргсбора");
    const announce = [...head, "", list, "", `Заказать (без регистрации): ${url}`].join("\n");
    const debtors = P.orders.filter(o => o.balance_kop > 0);
    const remind = debtors.length ? [`💳 Напоминаю об оплате закупки «${P.title}»:`,
      ...debtors.map(o => `— ${o.name}: ${D.rub(o.balance_kop)}${o.says_paid ? " (отметили оплату — проверяю)" : ""}`),
      "", ...(P.pay_info ? [`Как оплатить: ${P.pay_info}`] : []), "Сумму и состав заказа видно по вашей личной ссылке."].join("\n") : "";
    const open = P.items.filter(i => i.missing);
    const packs = open.length ? [`📦 Добираем коробки в закупке «${P.title}»:`,
      ...open.map(i => `— ${i.name}: не хватает ${i.missing} ${i.unit}`), "", `Добавить в заказ: ${url}`,
      "Если коробка не соберётся, остаток снимем с последних заказов."].join("\n") : "";
    const arrived = [`✅ Закупка «${P.title}» приехала!`, P.pickup ? `Раздача: ${P.pickup}` : "",
      "Суммы пересчитаны по факту веса — проверьте свой заказ по личной ссылке.",
      P.pay_info ? `Доплата: ${P.pay_info}` : ""].filter(Boolean).join("\n");
    return [["Объявление о сборе", announce], ["Добор коробок", packs], ["Напоминание должникам", remind], ["Приехало, раздача", arrived]];
  }

  function chatTab() {
    return chatTexts().map(([t, txt], n) => `<div class="card"><h3>${t}</h3>
      ${txt ? `<pre class="chat">${D.esc(txt)}</pre><button data-copytext="${n}">Копировать</button>`
        : `<p class="muted small">${n === 1 ? "Все коробки собраны." : "Должников нет."}</p>`}</div>`).join("");
  }

  function bindChat() {
    const texts = chatTexts();
    root.querySelectorAll("[data-copytext]").forEach(b => b.onclick = () => D.copy(texts[+b.dataset.copytext][1]));
  }

  // ---------- настройки ----------
  function settingsTab() {
    return `<form class="card" id="settings">${purchaseFields(P)}<button class="primary">Сохранить</button></form>
      <div class="card"><h3>Повторить закупку</h3><p class="small muted">Новая закупка с теми же поставщиком, позициями и условиями — без заказов.</p>
        <button id="copyP">Создать копию</button></div>
      <div class="card"><h3>Удалить закупку</h3><p class="small muted">Удалятся все заказы участников. Отменить нельзя.</p>
        <button class="danger" id="delP">Удалить</button></div>`;
  }

  function bindSettings() {
    document.getElementById("settings").onsubmit = ev => {
      ev.preventDefault();
      act(() => D.api("PUT", `/api/purchases/${P.id}`, formData(ev.target))).then(() => { if (!error) D.toast("Сохранено"); });
    };
    document.getElementById("copyP").onclick = async () => {
      try { const p = await D.api("POST", `/api/purchases/${P.id}/copy`); go(`p/${p.id}/settings`); D.toast("Копия создана — поправьте стоп и цены"); }
      catch (e) { error = e.message; renderPurchase("settings"); }
    };
    document.getElementById("delP").onclick = async () => {
      if (!confirm(`Удалить «${P.title}» вместе со всеми заказами?`)) return;
      await D.api("DELETE", `/api/purchases/${P.id}`); go("");
    };
  }

  function bindTab(tab) {
    ({ items: bindItems, orders: bindOrders, chat: bindChat, settings: bindSettings }[tab] || bindItems)();
  }

  // ---------- тариф ----------
  function renderPlan() {
    const pro = ME.plans.pro;
    const until = ME.sub_ends ? `<p>${ME.trial ? "Пробный период" : "Подписка"} действует до <b>${D.date(ME.sub_ends)}</b>.</p>` : "";
    root.innerHTML = top() + `<a href="#">← Закупки</a><h1 style="margin-top:12px">Тариф</h1>
      <div class="err hidden" id="err"></div>
      <div class="card"><h2>Бесплатный</h2><p>1 незакрытая закупка, до 15 участников в ней. Все функции.</p></div>
      <div class="card"><h2>Про</h2><p>Без ограничений по закупкам и участникам.</p>${until}
        <div class="row">${pro.durations.map(d => `<button class="${d.id === "1m" ? "primary" : ""}" data-buy="${d.id}">${d.label} — ${D.rub(d.price_rub * 100)}</button>`).join("")}</div>
        ${ME.payments === "demo" ? `<p class="small muted" style="margin-top:8px">Тестовый режим: подписка включится без списания денег.</p>` : ""}
      </div>`;
    bindTop();
    root.querySelectorAll("[data-buy]").forEach(b => b.onclick = async () => {
      try {
        const res = await D.api("POST", "/api/checkout", { plan: "pro", duration: b.dataset.buy });
        if (res.status === "redirect") { location.href = res.url; return; }
        ME = await D.api("GET", "/api/me"); D.toast("Тариф «Про» подключён"); renderPlan();
      } catch (e) { const el = document.getElementById("err"); el.textContent = e.message; el.classList.remove("hidden"); }
    });
  }

  start();
})();
