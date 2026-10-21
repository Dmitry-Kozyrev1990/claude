// Точка входа мини-приложения Telegram: по start_param (t.me/<бот>?startapp=<код>) или ?z=<код>
// открываем закупку для участника, иначе — кабинет организатора.
(function () {
  const root = document.getElementById("root");
  if (!D.tg) {
    root.innerHTML = `<div class="card"><h1>Откройте в Telegram</h1>
      <p>Эта страница работает внутри Telegram. В браузере пользуйтесь <a href="/app">веб-версией</a>.</p></div>`;
    return;
  }
  D.tg.ready();
  D.tg.expand();
  D.applyTgTheme();
  D.tg.onEvent("themeChanged", D.applyTgTheme);
  try { if (D.tg.disableVerticalSwipes) D.tg.disableVerticalSwipes(); } catch (e) { /* старый клиент */ }
  const start = (D.tg.initDataUnsafe && D.tg.initDataUnsafe.start_param) || new URLSearchParams(location.search).get("z") || "";
  if (/^[a-z0-9]{4,32}$/.test(start) && !location.hash) window.DolkaJoin.start(start);
  else window.DolkaApp.start();
})();
