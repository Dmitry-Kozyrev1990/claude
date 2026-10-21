// Общие помощники для кабинета организатора и страницы участника — в браузере и в мини-приложении Telegram.
const TG = window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData ? window.Telegram.WebApp : null;
let mainButtonHandler = null;
let backButtonHandler = null;

const D = {
  tg: TG,          // объект Telegram.WebApp, если страница открыта как мини-приложение
  session: null,   // сессия организатора в Telegram (вместо cookie)
  async api(method, url, body, headers = {}) {
    const base = { "X-Requested-With": "dolka" };
    if (D.session) base.Authorization = "Bearer " + D.session;
    if (TG) base["X-Tg-Init-Data"] = TG.initData;
    const opts = { method, headers: { ...base, ...headers }, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch (e) { /* пустой ответ */ }
    if (!res.ok) {
      const err = new Error((data && data.detail && (typeof data.detail === "string" ? data.detail : "Проверьте поля формы.")) || "Ошибка сервера");
      err.status = res.status;
      throw err;
    }
    return data;
  },
  esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  },
  rub(kop) {
    const neg = kop < 0; kop = Math.abs(kop);
    const r = Math.floor(kop / 100), k = kop % 100;
    return (neg ? "−" : "") + r.toLocaleString("ru-RU") + (k ? "," + String(k).padStart(2, "0") : "") + " ₽";
  },
  // '1,5' → 1500 (тысячные доли), чтобы шаги и коробки считались без ошибок дробей
  milli(v) {
    const n = Number(String(v ?? "").replace(",", ".").replace(/\s/g, ""));
    return Number.isFinite(n) ? Math.round(n * 1000) : NaN;
  },
  fmtMilli(m) { return String(Math.round(m) / 1000).replace(".", ","); },
  lineKop(priceKop, milli) { return Math.floor((priceKop * milli + 500) / 1000); },
  feeKop(goods, pct) { return Math.round(goods * pct / 100); },
  date(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  },
  toast(msg) {
    const t = document.createElement("div");
    t.className = "toast"; t.textContent = msg; document.body.appendChild(t);
    setTimeout(() => t.remove(), 2600);
  },
  async copy(text) {
    try { await navigator.clipboard.writeText(text); D.toast("Скопировано"); }
    catch (e) { window.prompt("Скопируйте:", text); }
  },
  async confirm(msg) {
    if (TG && TG.showConfirm) return new Promise(resolve => TG.showConfirm(msg, ok => resolve(!!ok)));
    return window.confirm(msg);
  },
  haptic(kind) {
    try { if (TG && TG.HapticFeedback) TG.HapticFeedback.notificationOccurred(kind); } catch (e) { /* старый клиент */ }
  },
  // Отправить ссылку в чат: в Telegram — штатный выбор чата, в браузере — системное «Поделиться» или копирование.
  share(url, text) {
    if (TG) { TG.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text || "")}`); return; }
    if (navigator.share) { navigator.share({ url, text }).catch(() => {}); return; }
    D.copy((text ? text + "\n" : "") + url);
  },
  // Скачать CSV: сервер выдаёт одноразовую подписанную ссылку, она работает и без cookie (в Telegram).
  async download(linkUrl) {
    const res = await D.api("POST", linkUrl);
    if (TG && TG.isVersionAtLeast && TG.isVersionAtLeast("8.0") && TG.downloadFile) TG.downloadFile({ url: res.url, file_name: res.file_name });
    else if (TG) TG.openLink(res.url);
    else location.href = res.url;
  },
  mainButton(text, fn) {
    if (!TG) return;
    if (mainButtonHandler) TG.MainButton.offClick(mainButtonHandler);
    mainButtonHandler = null;
    if (!text) { TG.MainButton.hide(); return; }
    mainButtonHandler = fn;
    TG.MainButton.setText(text);
    TG.MainButton.onClick(fn);
    TG.MainButton.show();
  },
  backButton(fn) {
    if (!TG) return;
    if (backButtonHandler) TG.BackButton.offClick(backButtonHandler);
    backButtonHandler = fn || null;
    if (!fn) { TG.BackButton.hide(); return; }
    TG.BackButton.onClick(fn);
    TG.BackButton.show();
  },
  // Цвета Telegram поверх наших токенов, чтобы мини-приложение выглядело родным в любой теме.
  applyTgTheme() {
    if (!TG) return;
    const tp = TG.themeParams || {};
    const r = document.documentElement;
    r.dataset.theme = TG.colorScheme === "dark" ? "dark" : "light";
    const map = { "--bg": tp.secondary_bg_color || tp.bg_color, "--card": tp.section_bg_color || tp.bg_color,
      "--ink": tp.text_color, "--muted": tp.hint_color, "--accent": tp.button_color,
      "--accent-ink": tp.button_text_color, "--bad": tp.destructive_text_color };
    Object.entries(map).forEach(([k, v]) => { if (v) r.style.setProperty(k, v); });
    r.style.setProperty("--line", "color-mix(in srgb, var(--muted) 28%, transparent)");
    r.style.setProperty("--accent-soft", "color-mix(in srgb, var(--accent) 14%, transparent)");
    try { TG.setHeaderColor("secondary_bg_color"); } catch (e) { /* старый клиент */ }
    try { if (map["--bg"]) TG.setBackgroundColor(map["--bg"]); } catch (e) { /* старый клиент */ }
  },
  tgUserName() {
    const u = TG && TG.initDataUnsafe && TG.initDataUnsafe.user;
    if (!u) return "";
    const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
    return u.username ? (name ? `${name} (@${u.username})` : "@" + u.username) : name;
  },
  store: {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* приватный режим */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* приватный режим */ } },
  },
};
