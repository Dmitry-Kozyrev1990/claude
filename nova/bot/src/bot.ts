import { Bot, Context, InlineKeyboard } from "grammy";
import { AGES, COURSES, GUIDE_URL, RECOMMEND, TEXT } from "./content";
import * as db from "./db";
import type { Age, Course, Env } from "./types";

const HOUR = 3600;
const DAY = 86400;
const H = { parse_mode: "HTML" as const };

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const courseById = (id: string) => COURSES.find((c) => c.id === id);
const isAdmin = (env: Env, id?: number) =>
  !!id && env.ADMIN_IDS.split(",").map((s) => s.trim()).includes(String(id));
const support = (env: Env) => `https://t.me/${env.SUPPORT_USERNAME}`;

/** Купленные курсы с раскрытым пакетом. */
async function owned(env: Env, tgId: number): Promise<string[]> {
  const ids = new Set<string>();
  for (const id of await db.paidCourseIds(env, tgId)) {
    for (const x of courseById(id)?.includes ?? [id]) ids.add(x);
  }
  return [...ids];
}

/** Редактируем сообщение, если можно, иначе шлём новое. */
async function show(ctx: Context, text: string, kb?: InlineKeyboard) {
  try {
    await ctx.editMessageText(text, { ...H, reply_markup: kb });
  } catch {
    await ctx.reply(text, { ...H, reply_markup: kb });
  }
}

// ---------- клавиатуры и тексты ----------

function menu(env: Env, admin = false) {
  const kb = new InlineKeyboard()
    .text("📚 Каталог курсов", "catalog").row()
    .text("🎓 Мои курсы", "my").row()
    .text("❓ Вопросы и ответы", "faq")
    .url("💬 Написать нам", support(env));
  if (admin) kb.row().text("🛠 Админ-панель", "adm");
  return kb;
}

function catalogKb() {
  const kb = new InlineKeyboard();
  COURSES.forEach((c, i) => {
    const step = c.includes ? "⭐" : `${i + 1}.`;
    kb.text(`${step} ${c.title} · ${c.price} ₽`, `course:${c.id}`).row();
  });
  return kb.text("⬅️ В меню", "menu");
}

function courseCard(c: Course) {
  return (
    `<b>${c.title}</b> · ${c.age}\n\n${c.pitch}\n\n` +
    `<b>Формат:</b> ${c.format}\n<b>Понадобится:</b> ${c.needs}\n<b>Итог:</b> ${c.result}\n\n` +
    `<b>Цена:</b> ${c.price} ₽`
  );
}

function outline(c: Course) {
  if (c.includes) {
    return `<b>${c.title}</b>\n\n` + c.includes.map((id, i) => {
      const x = courseById(id)!;
      return `${i + 1}. ${x.title} · ${x.age} · ${x.lessons.length} встреч`;
    }).join("\n");
  }
  return `<b>${c.title}: встречи</b>\n\n` + c.lessons.map((l, i) => `${i + 1}. ${l.title} · ${l.minutes} мин`).join("\n");
}

/** Кнопка «написать для оплаты» открывает личку с готовым текстом про заказ. */
function payKb(env: Env, orderId: number, title: string) {
  const text = encodeURIComponent(`Здравствуйте! Хочу оплатить заказ №${orderId} «${title}»`);
  return new InlineKeyboard()
    .url("💬 Написать для оплаты", `${support(env)}?text=${text}`).row()
    .text("Отменить заказ", `cancel:${orderId}`);
}

function decisionKb(orderId: number) {
  return new InlineKeyboard().text("✅ Подтвердить", `ok:${orderId}`).text("❌ Отклонить", `no:${orderId}`);
}

async function lessonsList(env: Env, tgId: number, c: Course) {
  const done = await db.getDone(env, tgId, c.id);
  const kb = new InlineKeyboard();
  c.lessons.forEach((l, i) => {
    const mark = i < done ? "✅" : i === done ? "▶️" : "🔒";
    kb.text(`${mark} ${i + 1}. ${l.title}`.slice(0, 60), `les:${c.id}:${i}`).row();
  });
  kb.text("⬅️ Мои курсы", "my");
  const text =
    `<b>${c.title}</b>\nПройдено ${Math.min(done, c.lessons.length)} из ${c.lessons.length}.\n\n` +
    (done >= c.lessons.length ? "Курс пройден целиком. Можно вернуться к любой встрече." : "Следующая встреча отмечена ▶️.");
  return { text, kb };
}

/** Уведомление админам о заказе: после оплаты в личке админ жмёт «Подтвердить». */
async function notifyAdmins(bot: Bot, env: Env, o: db.Order, who: string) {
  const c = courseById(o.course_id);
  const text =
    `🧾 <b>Заказ №${o.id}</b>: «${c?.title ?? o.course_id}», ${o.amount} ₽\n` +
    `От: ${who} (id <code>${o.tg_id}</code>)\n\n` +
    "Покупатель напишет вам в личку. Когда оплата придёт, нажмите «Подтвердить», курс откроется сам.";
  for (const admin of env.ADMIN_IDS.split(",").map((s) => s.trim()).filter(Boolean)) {
    await bot.api
      .sendMessage(admin, text, { ...H, reply_markup: decisionKb(o.id) })
      .catch((e) => console.error("notify admin", admin, e));
  }
}

// ---------- бот ----------

export function createBot(env: Env): Bot {
  const bot = new Bot(env.BOT_TOKEN);

  bot.command("start", async (ctx) => {
    const f = ctx.from!;
    await db.upsertUser(env, f.id, f.username, f.first_name, ctx.match || undefined);
    const kb = new InlineKeyboard();
    AGES.forEach((a, i) => {
      kb.text(a.label, `age:${a.id}`);
      if (i % 2 === 1) kb.row();
    });
    await ctx.reply(TEXT.welcome, { ...H, reply_markup: kb });
  });

  bot.command("menu", (ctx) => ctx.reply("Главное меню:", { reply_markup: menu(env, isAdmin(env, ctx.from?.id)) }));

  bot.callbackQuery(/^age:(\w+)$/, async (ctx) => {
    const age = AGES.find((a) => a.id === ctx.match[1]);
    await ctx.answerCallbackQuery();
    if (!age) return;
    const id = ctx.from.id;
    const prev = await db.getUser(env, id);
    await db.setAge(env, id, age.id);
    if (!prev?.age) {
      // прогрев ставим только при первом выборе возраста
      await db.addJob(env, id, "nurture1", db.now() + DAY);
      await db.addJob(env, id, "nurture2", db.now() + 3 * DAY);
      await db.addJob(env, id, "nurture3", db.now() + 5 * DAY);
    }
    const rec = courseById(RECOMMEND[age.id])!;
    const recTitle = rec.includes ? `пакет «Весь путь»` : rec.title;
    await ctx.reply(TEXT.leadMagnet(recTitle, age.label), {
      ...H,
      reply_markup: new InlineKeyboard()
        .url("Открыть гайд", GUIDE_URL).row()
        .text("Посмотреть курс", `ncourse:${rec.id}`)
        .text("Все курсы", "ncatalog"),
    });
  });

  // --- навигация ---

  bot.callbackQuery("menu", async (ctx) => {
    await ctx.answerCallbackQuery();
    await show(ctx, "Главное меню:", menu(env, isAdmin(env, ctx.from.id)));
  });

  bot.callbackQuery(/^(n?)catalog$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const text = "Курсы от простого к сложному. Любой можно купить отдельно:";
    if (ctx.match[1]) await ctx.reply(text, { reply_markup: catalogKb() });
    else await show(ctx, text, catalogKb());
  });

  bot.callbackQuery("faq", async (ctx) => {
    await ctx.answerCallbackQuery();
    await show(ctx, TEXT.faq, new InlineKeyboard().text("⬅️ В меню", "menu"));
  });

  // n-префикс: кнопка из сообщения прогрева, его не затираем, шлём новое
  bot.callbackQuery(/^(n?)course:([\w-]+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const c = courseById(ctx.match[2]);
    if (!c) return;
    const mine = await owned(env, ctx.from.id);
    const has = c.includes ? c.includes.every((x) => mine.includes(x)) : mine.includes(c.id);
    const kb = new InlineKeyboard();
    if (has) kb.text("🎓 Открыть встречи", c.includes ? "my" : `open:${c.id}`).row();
    else kb.text(`Купить за ${c.price} ₽`, `buy:${c.id}`).row();
    kb.text("Что внутри по встречам", `outline:${c.id}`).row().text("⬅️ К каталогу", "catalog");
    if (ctx.match[1]) await ctx.reply(courseCard(c), { ...H, reply_markup: kb });
    else await show(ctx, courseCard(c), kb);
  });

  bot.callbackQuery(/^outline:([\w-]+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const c = courseById(ctx.match[1]);
    if (c) await show(ctx, outline(c), new InlineKeyboard().text("⬅️ К курсу", `course:${c.id}`));
  });

  // --- покупка через личку ---

  bot.callbackQuery(/^buy:([\w-]+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const c = courseById(ctx.match[1]);
    if (!c) return;
    const id = ctx.from.id;
    let order = await db.openOrder(env, id, c.id);
    if (!order) {
      const orderId = await db.createOrder(env, id, c.id, c.price);
      await db.addJob(env, id, "cart", db.now() + HOUR, orderId);
      order = (await db.getOrder(env, orderId))!;
      await notifyAdmins(bot, env, order, who(await db.getUser(env, id), id));
    }
    await ctx.reply(TEXT.payContact(order.id, c.title, order.amount), {
      ...H,
      reply_markup: payKb(env, order.id, c.title),
    });
  });

  bot.callbackQuery(/^cancel:(\d+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    await db.cancelOrder(env, Number(ctx.match[1]), ctx.from.id);
    await show(ctx, "Заказ отменён. Если передумаете, он в каталоге.", new InlineKeyboard().text("📚 Каталог", "catalog"));
  });

  // --- мои курсы и встречи ---

  bot.callbackQuery("my", async (ctx) => {
    await ctx.answerCallbackQuery();
    const ids = await owned(env, ctx.from.id);
    if (!ids.length) return show(ctx, "Пока нет купленных курсов.", catalogKb());
    const kb = new InlineKeyboard();
    for (const id of ids) {
      const c = courseById(id)!;
      const done = await db.getDone(env, ctx.from.id, id);
      kb.text(`${c.title} · ${Math.min(done, c.lessons.length)}/${c.lessons.length}`, `open:${id}`).row();
    }
    await show(ctx, "Ваши курсы:", kb.text("⬅️ В меню", "menu"));
  });

  bot.callbackQuery(/^open:([\w-]+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const c = courseById(ctx.match[1]);
    if (!c || !(await owned(env, ctx.from.id)).includes(c.id)) return;
    const { text, kb } = await lessonsList(env, ctx.from.id, c);
    await show(ctx, text, kb);
  });

  bot.callbackQuery(/^les:([\w-]+):(\d+)$/, async (ctx) => {
    const c = courseById(ctx.match[1]);
    const i = Number(ctx.match[2]);
    if (!c || !c.lessons[i] || !(await owned(env, ctx.from.id)).includes(c.id)) return ctx.answerCallbackQuery();
    const done = await db.getDone(env, ctx.from.id, c.id);
    if (i > done) return ctx.answerCallbackQuery({ text: "Сначала пройдите предыдущую встречу 🙂", show_alert: true });
    await ctx.answerCallbackQuery();
    const l = c.lessons[i];
    const text = `<b>Встреча ${i + 1} из ${c.lessons.length}</b> · около ${l.minutes} мин\n<b>${l.title}</b>\n\n${l.text}`;
    const kb = new InlineKeyboard();
    if (i >= done) kb.text("✅ Прошли, дальше", `done:${c.id}:${i}`).row();
    else if (c.lessons[i + 1]) kb.text("Следующая встреча ➡️", `les:${c.id}:${i + 1}`).row();
    await show(ctx, text, kb.text("⬅️ Все встречи", `open:${c.id}`));
  });

  bot.callbackQuery(/^done:([\w-]+):(\d+)$/, async (ctx) => {
    const c = courseById(ctx.match[1]);
    const i = Number(ctx.match[2]);
    await ctx.answerCallbackQuery({ text: "Отметил ✅" });
    if (!c || !c.lessons[i] || !(await owned(env, ctx.from.id)).includes(c.id)) return;
    if (i > (await db.getDone(env, ctx.from.id, c.id))) return;
    await db.completeLesson(env, ctx.from.id, c.id, i);
    if (c.lessons[i + 1]) {
      await show(
        ctx,
        `Встреча ${i + 1} пройдена. Следующая открыта, загляните в неё, когда будет 20 свободных минут.`,
        new InlineKeyboard().text("Открыть следующую ➡️", `les:${c.id}:${i + 1}`).row().text("⬅️ Все встречи", `open:${c.id}`),
      );
      return;
    }
    const next = COURSES[COURSES.indexOf(c) + 1];
    const kb = new InlineKeyboard();
    if (next && !next.includes && !(await owned(env, ctx.from.id)).includes(next.id)) kb.text(`Следующая ступень: ${next.title}`, `course:${next.id}`).row();
    await show(ctx, `🎉 Курс «${c.title}» пройден целиком! Поздравьте ребёнка от меня.`, kb.text("🎓 Мои курсы", "my"));
  });

  // --- админ-панель ---

  const adminKb = async () => {
    const s = await db.stats(env);
    return new InlineKeyboard()
      .text(`⏳ Ждут оплаты (${s.awaiting})`, "adm:queue").row()
      .text("📊 Статистика", "adm:stats").text("🧾 Последние заказы", "adm:recent");
  };
  const ADMIN_HELP =
    "🛠 <b>Админ-панель</b>\n\nВыдать курс вручную: <code>/grant id курс</code>\nКурсы: " +
    COURSES.map((c) => `<code>${c.id}</code>`).join(", ");

  bot.command(["admin", "stats"], async (ctx) => {
    if (!isAdmin(env, ctx.from?.id)) return;
    await ctx.reply(ADMIN_HELP, { ...H, reply_markup: await adminKb() });
  });

  bot.callbackQuery("adm", async (ctx) => {
    await ctx.answerCallbackQuery();
    if (isAdmin(env, ctx.from.id)) await show(ctx, ADMIN_HELP, await adminKb());
  });

  bot.callbackQuery("adm:stats", async (ctx) => {
    await ctx.answerCallbackQuery();
    if (!isAdmin(env, ctx.from.id)) return;
    const s = await db.stats(env);
    const ageLabel = (id: string) => AGES.find((a) => a.id === id)?.label ?? id;
    const conv = s.users ? ((s.buyers / s.users) * 100).toFixed(1) : "0";
    await show(
      ctx,
      `📊 <b>Статистика</b>\n\nПользователей: ${s.users} (за сутки +${s.newUsers})\n` +
        `Оплат: ${s.paid} на ${s.revenue} ₽\nПокупателей: ${s.buyers} (${conv}% от всех)\nЖдут оплаты: ${s.awaiting}\n\n` +
        `<b>Возраст детей</b>\n${s.ages.map((a) => `${ageLabel(a.age)}: ${a.n}`).join("\n")}\n\n` +
        `<b>Источники</b>\n${s.sources.map((x) => `${esc(x.source)}: ${x.n}`).join("\n")}`,
      new InlineKeyboard().text("⬅️ Админ-панель", "adm"),
    );
  });

  bot.callbackQuery("adm:recent", async (ctx) => {
    await ctx.answerCallbackQuery();
    if (!isAdmin(env, ctx.from.id)) return;
    const STATUS: Record<string, string> = { awaiting: "⏳ ждёт оплаты", paid: "✅ оплачен", rejected: "❌ отклонён", canceled: "отменён" };
    const rows = await db.recentOrders(env);
    await show(
      ctx,
      "🧾 <b>Последние заказы</b>\n\n" +
        (rows.map((o) => `№${o.id} · ${courseById(o.course_id)?.title ?? o.course_id} · ${o.amount} ₽ · ${STATUS[o.status]} · id <code>${o.tg_id}</code>`).join("\n") || "Заказов пока нет."),
      new InlineKeyboard().text("⬅️ Админ-панель", "adm"),
    );
  });

  bot.callbackQuery("adm:queue", async (ctx) => {
    await ctx.answerCallbackQuery();
    if (!isAdmin(env, ctx.from.id)) return;
    const q = await db.awaitingQueue(env);
    if (!q.length) return ctx.reply("Неоплаченных заказов нет 👌");
    for (const o of q) {
      const u = await db.getUser(env, o.tg_id);
      await notifyAdmins(bot, { ...env, ADMIN_IDS: String(ctx.from.id) }, o, who(u, o.tg_id));
    }
  });

  bot.callbackQuery(/^(ok|no):(\d+)$/, async (ctx) => {
    if (!isAdmin(env, ctx.from.id)) return ctx.answerCallbackQuery();
    const orderId = Number(ctx.match[2]);
    const approve = ctx.match[1] === "ok";
    const changed = await db.decide(env, orderId, approve ? "paid" : "rejected", ctx.from.id);
    const o = await db.getOrder(env, orderId);
    await ctx.answerCallbackQuery({ text: changed ? (approve ? "Подтверждено" : "Отклонено") : "Заказ уже обработан" });
    await ctx.editMessageReplyMarkup({ reply_markup: undefined }).catch(() => {});
    if (!changed || !o) return;
    await ctx.reply(`Заказ №${orderId}: ${approve ? "✅ подтверждён, курс открыт" : "❌ отклонён, покупатель предупреждён"}.`);
    const c = courseById(o.course_id);
    try {
      if (approve) {
        await bot.api.sendMessage(o.tg_id, TEXT.paid(c?.title ?? ""), {
          ...H,
          reply_markup: new InlineKeyboard().text("🎓 Открыть курс", c?.includes ? "my" : `open:${o.course_id}`),
        });
      } else {
        await bot.api.sendMessage(o.tg_id, TEXT.rejected(orderId), {
          reply_markup: new InlineKeyboard().url("💬 Написать нам", support(env)),
        });
      }
    } catch (e) {
      console.error("notify buyer", e);
    }
  });

  bot.command("grant", async (ctx) => {
    if (!isAdmin(env, ctx.from?.id)) return;
    const [idStr, courseId] = (ctx.match ?? "").trim().split(/\s+/);
    const c = courseById(courseId ?? "");
    const tgId = Number(idStr);
    if (!tgId || !c) return ctx.reply("Формат: /grant 123456789 hello");
    if (!(await db.getUser(env, tgId))) return ctx.reply("Такого пользователя нет в боте: пусть сначала нажмёт /start.");
    await db.grant(env, tgId, c.id, ctx.from!.id);
    await ctx.reply(`Готово: «${c.title}» выдан пользователю ${tgId}.`);
    await bot.api
      .sendMessage(tgId, TEXT.paid(c.title), {
        ...H,
        reply_markup: new InlineKeyboard().text("🎓 Открыть курс", c.includes ? "my" : `open:${c.id}`),
      })
      .catch((e) => console.error("grant notify", e));
  });

  bot.on("message", (ctx) => ctx.reply("Нажмите /menu, чтобы открыть меню."));

  return bot;
}

/** Имя покупателя ссылкой на его профиль: из уведомления можно сразу написать ему. */
function who(u: db.User | null, tgId: number) {
  const name = `<a href="tg://user?id=${tgId}">${esc(u?.first_name ?? "покупатель")}</a>`;
  return u?.username ? `${name} (@${esc(u.username)})` : name;
}

// ---------- крон: прогрев и напоминания ----------

export async function runJobs(bot: Bot, env: Env) {
  for (const j of await db.dueJobs(env)) {
    try {
      const user = await db.getUser(env, j.tg_id);
      if (!user || user.blocked) {
        await db.finishJob(env, j.id);
        continue;
      }
      if (j.kind === "cart" && j.ref) {
        const o = await db.getOrder(env, j.ref);
        const c = o && courseById(o.course_id);
        if (o?.status === "awaiting" && c) {
          await bot.api.sendMessage(j.tg_id, TEXT.cart(c.title), { ...H, reply_markup: payKb(env, o.id, c.title) });
        }
      } else if (j.kind.startsWith("nurture") && !(await db.paidCourseIds(env, j.tg_id)).length) {
        const rec = courseById(RECOMMEND[(user.age as Age) ?? "a7_9"] ?? "hello")!;
        const nurture: Record<string, [string, InlineKeyboard]> = {
          nurture1: [
            TEXT.nurture1(rec.includes ? "пакета «Весь путь»" : rec.title),
            new InlineKeyboard().text("Посмотреть курс", `ncourse:${rec.id}`).text("Все курсы", "ncatalog"),
          ],
          nurture2: [TEXT.nurture2, new InlineKeyboard().text("Посмотреть курс", "ncourse:safe").text("Все курсы", "ncatalog")],
          nurture3: [TEXT.nurture3, new InlineKeyboard().text("Курс про учёбу", "ncourse:study").text("Пакет «Весь путь»", "ncourse:all")],
        };
        const n = nurture[j.kind];
        if (n) await bot.api.sendMessage(j.tg_id, n[0], { ...H, reply_markup: n[1] });
      }
      await db.finishJob(env, j.id);
    } catch (e: any) {
      if (e?.error_code === 403) await db.markBlocked(env, j.tg_id); // пользователь заблокировал бота
      else console.error("job failed", j.id, e);
      await db.finishJob(env, j.id);
    }
  }
}
