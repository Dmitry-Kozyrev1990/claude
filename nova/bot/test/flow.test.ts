// Сквозной прогон сценариев: локальная D1 (wrangler) + перехват вызовов Telegram API.
import { getPlatformProxy } from "wrangler";
import { readFileSync } from "node:fs";
import { createBot, runJobs } from "../src/bot";
import type { Env } from "../src/types";

const proxy = await getPlatformProxy<{ DB: D1Database }>({ persist: false });
const DB = proxy.env.DB;
for (const stmt of readFileSync("schema.sql", "utf8").split(";").map((s) => s.trim()).filter(Boolean)) {
  await DB.prepare(stmt).run();
}
const env: Env = {
  DB, BOT_TOKEN: "1:x", WEBHOOK_SECRET: "s", ADMIN_IDS: "900", BOT_USERNAME: "nova_bot", SUPPORT_USERNAME: "nova_help",
};

const calls: { method: string; payload: any }[] = [];
let msgId = 1000;
function mkBot() {
  const bot = createBot(env);
  bot.botInfo = { id: 1, is_bot: true, first_name: "Nova", username: "nova_bot" } as any;
  bot.api.config.use(async (_prev, method, payload) => {
    calls.push({ method, payload });
    if (method === "answerCallbackQuery" || method === "editMessageReplyMarkup") return { ok: true, result: true } as any;
    if (method === "editMessageText") return { ok: false, error_code: 400, description: "no edit in test" } as any;
    return { ok: true, result: { message_id: ++msgId, date: 0, chat: { id: (payload as any).chat_id, type: "private" } } } as any;
  });
  return bot;
}
const bot = mkBot();
let upd = 1;
const from = (id: number) => ({ id, is_bot: false, first_name: id === 900 ? "Админ" : "Анна", username: id === 900 ? "admin" : "anna" });
const msg = (id: number, extra: any) => bot.handleUpdate({ update_id: upd++, message: { message_id: upd, date: 0, chat: { id, type: "private" }, from: from(id), ...extra } } as any);
const cb = (id: number, data: string) => bot.handleUpdate({ update_id: upd++, callback_query: { id: String(upd), from: from(id), chat_instance: "c", data, message: { message_id: 1, date: 0, chat: { id, type: "private" }, text: "x" } } } as any);
const sent = () => calls.filter((c) => /^send/.test(c.method) || c.method === "editMessageText");
const last = () => sent().at(-1)!;
const textOf = (c: any) => c.payload.text ?? c.payload.caption ?? "";
const buttons = (c: any) => (c.payload.reply_markup?.inline_keyboard ?? []).flat().map((b: any) => b.callback_data ?? b.url);
let fails = 0;
const check = (name: string, ok: boolean, info?: unknown) => { console.log(`${ok ? "PASS" : "FAIL"} ${name}`); if (!ok) { fails++; console.log("   ", JSON.stringify(info)?.slice(0, 400)); } };

const U = 111, ADMIN = 900, OTHER = 222;

await msg(U, { text: "/start post_12", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
check("приветствие с кнопками возраста", textOf(last()).includes("Сколько лет ребёнку") && buttons(last()).includes("age:a10_12"), last());

await cb(U, "age:a10_12");
check("подарок + совет «Как машина учится» для 10–12", textOf(last()).includes("«Как машина учится»") && buttons(last()).includes("ncourse:learn"), last());
const jobs = await DB.prepare("SELECT kind FROM jobs WHERE tg_id=?").bind(U).all();
check("поставлено 3 сообщения прогрева", jobs.results.length === 3, jobs.results);
await cb(U, "age:a7_9");
const jobs2 = await DB.prepare("SELECT COUNT(*) n FROM jobs WHERE tg_id=?").bind(U).first<{ n: number }>();
check("повторный выбор возраста не дублирует прогрев", jobs2?.n === 3, jobs2);

await cb(U, "ncourse:learn");
check("карточка курса с кнопкой покупки", textOf(last()).includes("790 ₽") && buttons(last()).includes("buy:learn"), last());

const b1 = calls.length;
await cb(U, "buy:learn");
const toUser = calls.slice(b1).find((c) => c.payload.chat_id === U && c.method === "sendMessage");
const payUrl = buttons(toUser).find((b: string) => b?.startsWith("https://t.me/nova_help")) ?? "";
check("покупателю: заказ, сумма и кнопка «Написать для оплаты»", textOf(toUser).includes("№1") && textOf(toUser).includes("790") && !!payUrl, toUser);
check("в кнопке готовый текст с номером заказа", decodeURIComponent(payUrl).includes("заказ №1 «Как машина учится»"), payUrl);
const toAdmin = calls.slice(b1).find((c) => c.payload.chat_id === "900");
check("админу пришёл заказ с кнопками и ссылкой на покупателя", buttons(toAdmin).includes("ok:1") && textOf(toAdmin).includes('tg://user?id=111'), toAdmin);
const b1b = calls.length;
await cb(U, "buy:learn");
const orders = await DB.prepare("SELECT COUNT(*) n FROM orders").first<{ n: number }>();
check("повторное «Купить» не создаёт второй заказ и не дёргает админа", orders?.n === 1 && !calls.slice(b1b).some((c) => c.payload.chat_id === "900"), orders);

await cb(U, "open:learn");
check("до оплаты встречи закрыты", !textOf(last()).includes("Пройдено"), last());

await cb(U, "ok:1");
const o1 = await DB.prepare("SELECT status FROM orders WHERE id=1").first<{ status: string }>();
check("не-админ не может подтвердить оплату", o1?.status === "awaiting", o1);

const b2 = calls.length;
await cb(ADMIN, "ok:1");
const o2 = await DB.prepare("SELECT status, decided_by FROM orders WHERE id=1").first<any>();
check("админ подтвердил → заказ оплачен", o2?.status === "paid" && o2?.decided_by === ADMIN, o2);
check("покупатель получил «оплата подтверждена» с кнопкой курса", calls.slice(b2).some((c) => c.payload.chat_id === U && c.payload.text?.includes("Оплата подтверждена") && buttons(c).includes("open:learn")), calls.slice(b2));
const b3 = calls.length;
await cb(ADMIN, "ok:1");
check("повторное подтверждение ничего не шлёт покупателю", !calls.slice(b3).some((c) => c.payload.chat_id === U), calls.slice(b3));

await cb(U, "open:learn");
check("список встреч: 0 из 5, первая ▶️, вторая 🔒", textOf(last()).includes("Пройдено 0 из 5"), last());
const b4 = calls.length;
await cb(U, "les:learn:2");
check("закрытая встреча не открывается", calls.slice(b4).some((c) => c.method === "answerCallbackQuery" && c.payload.show_alert), calls.slice(b4));
await cb(U, "les:learn:0");
check("первая встреча открывается", textOf(last()).includes("Встреча 1 из 5") && buttons(last()).includes("done:learn:0"), last());
await cb(U, "done:learn:3");
check("нельзя отметить встречу через голову", (await DB.prepare("SELECT done FROM progress WHERE tg_id=?").bind(U).first<any>()) == null);
for (let i = 0; i < 5; i++) await cb(U, `done:learn:${i}`);
const prog = await DB.prepare("SELECT done FROM progress WHERE tg_id=? AND course_id='learn'").bind(U).first<any>();
check("пройдены все 5 встреч", prog?.done === 5, prog);
check("поздравление и следующая ступень", textOf(last()).includes("пройден целиком") && buttons(last()).includes("course:safe"), last());

await cb(OTHER, "les:learn:0");
check("чужой пользователь не видит встречи купленного курса", !textOf(last()).includes("Встреча 1 из 5") || last().payload.chat_id !== OTHER, last());

// отклонение и отмена
await msg(OTHER, { text: "/start", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
await cb(OTHER, "buy:hello");
await cb(ADMIN, "no:2");
check("отклонение: покупатель предупреждён", calls.some((c) => c.payload.chat_id === OTHER && c.payload.text?.includes("закрыт без оплаты")));
await cb(OTHER, "buy:safe");
await cb(OTHER, "cancel:3");
const b7 = calls.length;
await cb(ADMIN, "ok:3");
const o3 = await DB.prepare("SELECT status FROM orders WHERE id=3").first<any>();
check("отменённый покупателем заказ нельзя подтвердить", o3?.status === "canceled" && !calls.slice(b7).some((c) => c.payload.chat_id === OTHER), o3);

// пакет и ручная выдача
await msg(ADMIN, { text: "/grant 222 all", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
await cb(OTHER, "my");
check("пакет открывает все 5 курсов", buttons(last()).filter((b: string) => b.startsWith("open:")).length === 5, last());

// админ-панель
await msg(ADMIN, { text: "/admin", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
check("админ-панель открывается админу", textOf(last()).includes("Админ-панель") && buttons(last()).includes("adm:queue"), last());
const b5 = calls.length;
await msg(U, { text: "/admin", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
check("обычному пользователю админ-панель не отвечает", !calls.slice(b5).some((c) => textOf(c).includes("Админ-панель")));
await cb(ADMIN, "adm:stats");
check("статистика считает выручку", textOf(last()).includes("Оплат: 1 на 790 ₽"), textOf(last()));

// крон: напоминание о брошенном заказе и прогрев
await msg(333, { text: "/start", entities: [{ type: "bot_command", offset: 0, length: 6 }] });
await cb(333, "age:a13_14");
await cb(333, "buy:safe");
await DB.prepare("UPDATE jobs SET run_at = 0").run();
const b6 = calls.length;
await runJobs(bot, env);
const cronMsgs = calls.slice(b6).filter((c) => c.payload.chat_id === 333).map((c) => c.payload.text.slice(0, 40));
check("крон: напоминание о заказе + 3 сообщения прогрева для нового", cronMsgs.length === 4, cronMsgs);
check("крон: купившему прогрев не шлём", !calls.slice(b6).some((c) => c.payload.chat_id === U), calls.slice(b6).filter((c) => c.payload.chat_id === U));

// тексты встреч: влезают в сообщение Telegram и не ломают HTML-разметку
const { COURSES } = await import("../src/content");
for (const c of COURSES) for (const [i, l] of c.lessons.entries()) {
  const header = `Встреча ${i + 1} из ${c.lessons.length} · около ${l.minutes} мин\n${l.title}\n\n`;
  const plain = (header + l.text).replace(/<[^>]+>/g, "");
  const tags = [...l.text.matchAll(/<\/?([a-z]+)[^>]*>/g)].map((m) => m[1]);
  const bad = tags.filter((t) => !["b", "i", "a", "code"].includes(t));
  const open = (t: string) => (l.text.match(new RegExp(`<${t}[ >]`, "g")) ?? []).length;
  const close = (t: string) => (l.text.match(new RegExp(`</${t}>`, "g")) ?? []).length;
  const balanced = ["b", "i", "a", "code"].every((t) => open(t) === close(t));
  if (plain.length > 4096 || bad.length || !balanced) check(`встреча ${c.id}#${i + 1}: длина ${plain.length}, теги ок`, false, { bad, balanced });
}
check("все тексты встреч ≤ 4096 знаков и с корректной разметкой", true);

await proxy.dispose();
console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
process.exit(fails ? 1 : 0);
