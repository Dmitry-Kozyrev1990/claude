// Страница закупки для участника: без регистрации. В браузере заказ привязан к личной ссылке (токену),
// в мини-приложении Telegram — к аккаунту участника (сервер проверяет initData), кнопка «Оформить» — штатная.
window.DolkaJoin = { start(slugArg) { join(slugArg); } };

function join(slug) {
  const key = "dolka:" + slug;
  const params = new URLSearchParams(location.search);
  if (!D.tg && params.get("t")) {
    D.store.set(key, params.get("t"));
    history.replaceState(null, "", location.pathname);
  }
  let token = D.tg ? null : D.store.get(key);
  let P = null;          // данные закупки
  let qty = {};          // item_id → тысячные доли
  let editing = false;   // участник меняет уже оформленный заказ
  let error = "";
  const root = document.getElementById("root");
  const bar = document.getElementById("bar") || document.createElement("div");

  const hdr = () => (token ? { "X-Order-Token": token } : {});
  const myLink = () => `${location.origin}/z/${slug}?t=${encodeURIComponent(token)}`;

  async function load() {
    try {
      P = await D.api("GET", `/api/z/${slug}`, undefined, hdr());
    } catch (e) {
      root.innerHTML = `<div class="err">${e.status === 404 ? "Закупка не найдена. Проверьте ссылку." : D.esc(e.message)}</div>`;
      return;
    }
    if (token && !P.my_order) { token = null; D.store.del(key); }
    qty = {};
    if (P.my_order) P.my_order.lines.forEach(l => { qty[l.item_id] = D.milli(l.qty); });
    document.title = P.title + " — Долька";
    render();
  }

  function totals() {
    let goods = 0;
    P.items.forEach(i => { goods += D.lineKop(i.price_kop, qty[i.id] || 0); });
    const fee = D.feeKop(goods, P.fee_pct);
    return { goods, fee, total: goods + fee };
  }

  function packInfo(i) {
    if (!i.pack) return "";
    const pack = D.milli(i.pack), total = i.total_milli;
    const rest = total % pack;
    const pct = pack ? Math.round((rest || (total ? pack : 0)) / pack * 100) : 0;
    const text = !total ? `Коробка ${i.pack} ${i.unit} — пока никто не заказал`
      : rest ? `Набрано ${D.fmtMilli(rest)} из ${i.pack} ${i.unit} — не хватает ${i.missing} ${i.unit}`
      : `Коробок собрано: ${i.packs}`;
    return `<div class="small ${rest ? "" : "muted"}" style="margin-top:6px">${text}</div>
      <div class="bar ${rest ? "warn" : ""}" style="margin-top:4px"><i style="width:${pct}%"></i></div>`;
  }

  function itemRow(i, canEdit) {
    const q = qty[i.id] || 0;
    const control = canEdit
      ? `<div class="qty">
           <button type="button" data-dec="${i.id}" aria-label="Меньше">−</button>
           <input inputmode="decimal" data-qty="${i.id}" value="${q ? D.fmtMilli(q) : ""}" placeholder="0" aria-label="Количество, ${D.esc(i.unit)}">
           <button type="button" data-inc="${i.id}" aria-label="Больше">+</button>
         </div>`
      : (q ? `<b>${D.fmtMilli(q)} ${D.esc(i.unit)}</b>` : "");
    return `<div class="item">
      <div class="row between nowrap">
        <div class="grow">
          <div><b>${D.esc(i.name)}</b></div>
          <div class="small muted">${D.rub(i.price_kop)} за ${D.esc(i.unit)}${i.step !== "1" ? ` · шаг ${i.step} ${D.esc(i.unit)}` : ""}</div>
        </div>
        ${control}
      </div>
      ${packInfo(i)}
    </div>`;
  }

  function render() {
    const canEdit = P.accepting && (!P.my_order || editing);
    const mine = P.my_order;
    const min = P.min_total_kop;
    const minPct = min ? Math.min(100, Math.round(P.progress_kop / min * 100)) : 100;
    let html = `
      <div class="top"><a class="logo" href="/"><img src="/static/icon.svg" alt="">Долька</a>
        <span class="badge ${P.status === "open" ? "" : "grey"}">${D.esc(P.status_name)}</span></div>
      <h1>${D.esc(P.title)}</h1>
      ${P.supplier ? `<p class="muted">Поставщик: ${D.esc(P.supplier)}</p>` : ""}
      ${P.deadline ? `<p>Стоп заказов: <b>${D.date(P.deadline)}</b> (мск)</p>` : ""}
      ${P.description ? `<div class="card" style="white-space:pre-wrap">${D.esc(P.description)}</div>` : ""}
      ${min ? `<div class="card"><div class="row between small"><span>Минимальный заказ у поставщика</span>
          <b>${D.rub(P.progress_kop)} из ${D.rub(min)}</b></div>
          <div class="bar ${P.min_reached ? "" : "warn"}" style="margin-top:6px"><i style="width:${minPct}%"></i></div>
          <div class="small muted" style="margin-top:6px">Участников: ${P.participants}</div></div>` : ""}
      ${error ? `<div class="err">${D.esc(error)}</div>` : ""}`;

    if (mine && !editing) html += myOrderCard(mine);
    if (!P.accepting && !mine) html += `<div class="note">Сбор заказов закрыт.</div>`;

    html += `<div class="card"><h2>${canEdit ? "Выберите товары" : "Позиции"}</h2>
      <div class="list">${P.items.map(i => itemRow(i, canEdit)).join("") || `<p class="muted">Организатор ещё не добавил позиции.</p>`}</div></div>`;

    if (canEdit && P.items.length) {
      const name = mine ? mine.name : (D.store.get("dolka:name") || D.tgUserName());
      const phone = mine ? mine.phone : (D.store.get("dolka:phone") || "");
      html += `<form class="card" id="form">
        <h2>Ваши данные</h2>
        <div class="grid2">
          <label>Имя или ник, как в чате<input name="name" required maxlength="80" value="${D.esc(name)}" autocomplete="name"></label>
          <label>Телефон (для связи и раздачи)<input name="phone" maxlength="30" value="${D.esc(phone)}" inputmode="tel" autocomplete="tel"></label>
        </div>
        <label>Комментарий организатору<input name="comment" maxlength="500" value="${D.esc(mine ? mine.comment : "")}"></label>
        <div id="sum" class="small muted"></div>
        <div class="row" style="margin-top:8px">
          <button class="primary${D.tg ? " hidden" : ""}" type="submit">${mine ? "Сохранить изменения" : "Оформить заказ"}</button>
          ${mine ? `<button type="button" id="cancelEdit">Не менять</button>` : ""}
        </div>
      </form>`;
    }
    if (P.pickup) html += `<div class="card"><h3>Где и когда забрать</h3><div style="white-space:pre-wrap">${D.esc(P.pickup)}</div></div>`;
    html += `<div class="row" style="margin-bottom:12px"><button id="shareJoin">Позвать соседей</button>
      ${D.tg ? `<button class="ghost" id="becomeOrg">Собрать свою закупку</button>` : ""}</div>`;
    html += `<p class="small muted">Деньги переводятся организатору напрямую. Сервис «Долька» помогает вести учёт и не принимает платежи участников.</p>`;
    root.innerHTML = html;
    bind(canEdit);
    updateSum(canEdit);
  }

  function myOrderCard(o) {
    const names = Object.fromEntries(P.items.map(i => [i.id, i]));
    const lines = o.lines.map(l => {
      const i = names[l.item_id] || { name: "?", unit: "" };
      return `<tr><td>${D.esc(i.name)}</td><td class="num">${l.fact ? `<s class="muted">${l.qty}</s> ${l.fact}` : l.qty} ${D.esc(i.unit)}</td><td class="num">${D.rub(l.sum_kop)}</td></tr>`;
    }).join("");
    const balance = o.balance_kop;
    const payState = balance <= 0 ? `<span class="badge">Оплачено</span>`
      : o.says_paid ? `<span class="badge warn">Ждёт проверки организатором</span>`
      : `<span class="badge bad">К оплате ${D.rub(balance)}</span>`;
    return `<div class="card">
      <div class="row between"><h2 style="margin:0">Ваш заказ</h2>${payState}</div>
      <div class="scroll"><table style="margin-top:8px">${lines}
        <tr><td>Товары</td><td></td><td class="num">${D.rub(o.goods_kop)}</td></tr>
        ${o.fee_kop ? `<tr><td>Оргсбор ${String(P.fee_pct).replace(".", ",")}%</td><td></td><td class="num">${D.rub(o.fee_kop)}</td></tr>` : ""}
        <tr><td><b>Итого</b></td><td></td><td class="num"><b>${D.rub(o.total_kop)}</b></td></tr>
        ${o.paid_kop ? `<tr><td>Оплачено</td><td></td><td class="num">${D.rub(o.paid_kop)}</td></tr>` : ""}
        ${balance < 0 ? `<tr><td>Переплата, вернёт организатор</td><td></td><td class="num">${D.rub(-balance)}</td></tr>` : ""}
      </table></div>
      ${o.lines.some(l => l.fact) ? `<p class="small muted">Сумма пересчитана по факту веса.</p>` : ""}
      ${balance > 0 && P.pay_info ? `<div class="ok" style="margin-top:12px;white-space:pre-wrap"><b>Как оплатить:</b>\n${D.esc(P.pay_info)}</div>` : ""}
      ${o.picked_up ? `<p><span class="badge">Заказ выдан</span></p>` : ""}
      <div class="row" style="margin-top:8px">
        ${balance > 0 && !o.says_paid ? `<button class="primary" id="paid">Я оплатил(а)</button>` : ""}
        ${balance > 0 && o.says_paid ? `<button id="unpaid">Ещё не оплатил(а)</button>` : ""}
        ${P.accepting ? `<button id="edit">Изменить заказ</button><button class="danger ghost" id="cancel">Отменить</button>` : ""}
      </div>
      ${D.tg ? `<div class="small muted" style="margin-top:12px">Заказ привязан к вашему Telegram: откройте закупку по той же ссылке с любого устройства. Бот пришлёт, когда сбор закроется и когда всё приедет.</div>`
        : `<div class="small muted" style="margin-top:12px">Ваша личная ссылка на заказ — сохраните её, чтобы открыть заказ с другого устройства:</div>
      <div class="row" style="margin-top:4px"><input readonly value="${D.esc(myLink())}" class="grow" style="flex:1"><button id="copyLink">Копировать</button></div>`}
    </div>`;
  }

  function step(id) { const i = P.items.find(x => x.id === id); return D.milli(i.step); }

  function bind(canEdit) {
    root.querySelectorAll("[data-inc]").forEach(b => b.onclick = () => change(+b.dataset.inc, 1));
    root.querySelectorAll("[data-dec]").forEach(b => b.onclick = () => change(+b.dataset.dec, -1));
    root.querySelectorAll("[data-qty]").forEach(inp => inp.oninput = () => {
      const v = D.milli(inp.value);
      qty[+inp.dataset.qty] = Number.isFinite(v) && v > 0 ? v : 0;
      updateSum(canEdit);
    });
    const form = document.getElementById("form");
    if (form) form.onsubmit = submit;
    const on = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
    on("edit", () => { editing = true; error = ""; render(); });
    on("cancelEdit", () => { editing = false; error = ""; load(); });
    on("copyLink", () => D.copy(myLink()));
    on("paid", () => setPaid(true));
    on("shareJoin", () => D.share(P.tg_link || location.href, `🛒 Совместная закупка: ${P.title}`));
    on("becomeOrg", () => { D.mainButton(null); location.hash = ""; window.DolkaApp.start(); });
    on("unpaid", () => setPaid(false));
    on("cancel", async () => {
      if (!await D.confirm("Отменить заказ целиком?")) return;
      try { await D.api("DELETE", `/api/z/${slug}/order`, undefined, hdr()); }
      catch (e) { D.toast(e.message); return; }
      D.store.del(key); token = null; editing = false; load();
    });
  }

  function change(id, dir) {
    const s = step(id);
    qty[id] = Math.max(0, (qty[id] || 0) + dir * s);
    const inp = root.querySelector(`[data-qty="${id}"]`);
    if (inp) inp.value = qty[id] ? D.fmtMilli(qty[id]) : "";
    updateSum(true);
  }

  function updateSum(canEdit) {
    const t = canEdit ? totals() : null;
    if (D.tg) {
      // В Telegram вместо своей нижней панели — главная кнопка клиента
      D.mainButton(t && t.goods ? `${P.my_order ? "Сохранить" : "Оформить"} · ${D.rub(t.total)}` : null, () => {
        const f = document.getElementById("form");
        if (f) f.requestSubmit();
      });
    }
    if (!canEdit || D.tg) {
      bar.classList.add("hidden");
      const sum = document.getElementById("sum");
      if (sum && t) sum.textContent = t.goods ? `Товары ${D.rub(t.goods)}${t.fee ? ` + оргсбор ${D.rub(t.fee)}` : ""} = ${D.rub(t.total)}` : "";
      return;
    }
    const sum = document.getElementById("sum");
    if (sum) sum.textContent = t.goods ? `Товары ${D.rub(t.goods)}${t.fee ? ` + оргсбор ${D.rub(t.fee)}` : ""} = ${D.rub(t.total)}` : "";
    bar.classList.toggle("hidden", !t.goods);
    document.getElementById("barTotal").textContent = D.rub(t.total);
    document.getElementById("barNote").textContent = t.fee ? `с оргсбором ${String(P.fee_pct).replace(".", ",")}%` : "итого";
    document.getElementById("barBtn").onclick = () => {
      const f = document.getElementById("form");
      if (f) f.scrollIntoView({ behavior: "smooth" });
    };
  }

  async function submit(ev) {
    ev.preventDefault();
    const f = ev.target;
    const bad = P.items.find(i => (qty[i.id] || 0) % step(i.id));
    if (bad) { error = `«${bad.name}»: количество кратно ${bad.step} ${bad.unit}.`; render(); return; }
    const lines = {};
    Object.entries(qty).forEach(([id, m]) => { if (m > 0) lines[id] = D.fmtMilli(m).replace(",", "."); });
    const body = { name: f.name.value, phone: f.phone.value, comment: f.comment.value, lines };
    f.querySelector("button[type=submit]").disabled = true;
    try {
      const res = await D.api("POST", `/api/z/${slug}/order`, body, hdr());
      if (!D.tg) { token = res.token; D.store.set(key, token); }
      D.haptic("success");
      // Боту нужно разрешение писать участнику, иначе уведомления о стопе и раздаче не дойдут
      const u = D.tg && D.tg.initDataUnsafe.user;
      if (u && !u.allows_write_to_pm && D.tg.requestWriteAccess) { try { D.tg.requestWriteAccess(); } catch (e) { /* старый клиент */ } }
      D.store.set("dolka:name", body.name); D.store.set("dolka:phone", body.phone);
      editing = false; error = "";
      D.toast("Заказ сохранён");
      await load();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      D.haptic("error");
      error = e.message; render();
    }
  }

  async function setPaid(v) {
    try { P = await D.api("POST", `/api/z/${slug}/paid`, { paid: v }, hdr()); }
    catch (e) { D.toast(e.message); return; }
    D.toast(v ? "Организатор увидит отметку об оплате" : "Отметка снята");
    render();
  }

  load();
}

if (!window.DOLKA_TG) join(location.pathname.split("/").filter(Boolean).pop());
