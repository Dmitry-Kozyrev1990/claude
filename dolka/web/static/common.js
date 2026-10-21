// Общие помощники для кабинета организатора и страницы участника.
const D = {
  async api(method, url, body, headers = {}) {
    const opts = { method, headers: { "X-Requested-With": "dolka", ...headers }, credentials: "same-origin" };
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
  store: {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* приватный режим */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* приватный режим */ } },
  },
};
