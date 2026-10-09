import { Bot, InlineKeyboard } from "grammy";
import { COURSES, SEGMENTS, TEXT } from "./content";
import {
  addJob, attachPayment, createOrder, dueJobs, finishJob, getOrder, getUser, markBlocked, markCanceled,
  markPaid, now, paidCourseIds, setUserField, stats, upsertUser,
} from "./db";
import type { Course, Env, Segment } from "./types";
import { createPayment, getPayment, rub } from "./yookassa";

const HOUR = 3600;
const DAY = 86400;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const courseById = (id: string) => COURSES.find((c) => c.id === id);

function menu(env: Env) {
  return new InlineKeyboard()
    .text("📚 Каталог курсов", "catalog").row()
    .text("🎓 Мои курсы", "my").row()
    .text("❓ Вопросы и ответы", "faq")
    .url("💬 Написать нам", `https://t.me/${env.SUPPORT_USERNAME}`);
}

function catalogKb(segment: string | null) {
  const kb = new InlineKeyboard();
  const list = COURSES.filter((c) => !segment || c.segments.includes(segment as Segment));
  for (const c of list.length ? list : COURSES) kb.text(`${c.title} — ${c.price} ₽`, `course:${c.id}`).row();
  return kb.text("⬅️ В меню", "menu");
}

function courseCard(c: Course) {
  return (
    `*${c.title}*\n\n${c.pitch}\n\n*Программа:*\n` +
    c.program.map((p) => `• ${p}`).join("\n") +
    `\n\n*Цена:* ${c.price} ₽`
  );
}

/** Выдача доступа: одноразовая ссылка в закрытый чат или запасная ссылка. */
export async function deliverAccess(bot: Bot, tgId: number, c: Course) {
  let link = c.accessUrl;
  if (c.accessChatId) {
    const inv = await bot.api.createChatInviteLink(c.accessChatId, { member_limit: 1, name: `u${tgId}` });
    link = inv.invite_link;
  }
  await bot.api.sendMessage(
    tgId,
    `✅ Оплата получена. Добро пожаловать на «${c.title}»!\n\nВаш доступ: ${link ?? "скоро пришлём"}`,
  );
}

async function startPayment(bot: Bot, env: Env, tgId: number, courseId: string, method: "any" | "sbp") {
  const c = courseById(courseId);
  const user = await getUser(env, tgId);
  if (!c || !user?.email) return;
  const amount = c.price * 100;
  const orderId = await createOrder(env, tgId, c.id, amount);
  const pay = await createPayment(env, { orderId, amountKop: amount, title: c.title, email: user.email, method });
  await attachPayment(env, orderId, pay.id);
  await addJob(env, tgId, "cart", now() + HOUR, orderId);
  const url = pay.confirmation?.confirmation_url;
  await bot.api.sendMessage(
    tgId,
    `Заказ №${orderId}: «${c.title}», ${rub(amount)} ₽\n\n${TEXT.consent}`,
    { reply_markup: new InlineKeyboard().url("💳 Оплатить", url ?? "https://t.me/" + env.BOT_USERNAME) },
  );
}

export function createBot(env: Env): Bot {
  const bot = new Bot(env.BOT_TOKEN);

  bot.command("start", async (ctx) => {
    const from = ctx.from!;
    await upsertUser(env, from.id, from.username, ctx.match || undefined);
    const kb = new InlineKeyboard();
    for (const s of SEGMENTS) kb.text(s.label, `seg:${s.id}`).row();
    await ctx.reply(TEXT.welcome, { reply_markup: kb });
  });

  bot.command("menu", (ctx) => ctx.reply("Главное меню:", { reply_markup: menu(env) }));

  bot.command("stats", async (ctx) => {
    if (String(ctx.from?.id) !== env.ADMIN_ID) return;
    const s = await stats(env);
    await ctx.reply(
      `Пользователей: ${s.users}\nОплат: ${s.paid}\nВыручка: ${rub(s.revenueKop)} ₽\n\n` +
        s.segments.map((x) => `${x.seg}: ${x.n}`).join("\n"),
    );
  });

  bot.callbackQuery(/^seg:(\w+)$/, async (ctx) => {
    const seg = ctx.match[1];
    const id = ctx.from.id;
    const prev = await getUser(env, id);
    await setUserField(env, id, "segment", seg);
    // прогрев ставим только при первом выборе сегмента, чтобы не дублировать
    if (!prev?.segment) {
      await addJob(env, id, "nurture1", now() + DAY);
      await addJob(env, id, "nurture2", now() + 3 * DAY);
    }
    await ctx.answerCallbackQuery();
    await ctx.reply(TEXT.leadMagnet);
    await ctx.reply("Что дальше?", { reply_markup: menu(env) });
  });

  bot.callbackQuery("menu", async (ctx) => {
    await ctx.answerCallbackQuery();
    await ctx.editMessageText("Главное меню:", { reply_markup: menu(env) });
  });

  bot.callbackQuery("catalog", async (ctx) => {
    const u = await getUser(env, ctx.from.id);
    await ctx.answerCallbackQuery();
    await ctx.editMessageText("Выберите курс:", { reply_markup: catalogKb(u?.segment ?? null) });
  });

  bot.callbackQuery("faq", async (ctx) => {
    await ctx.answerCallbackQuery();
    await ctx.editMessageText(TEXT.faq, { reply_markup: new InlineKeyboard().text("⬅️ В меню", "menu") });
  });

  bot.callbackQuery(/^course:([\w-]+)$/, async (ctx) => {
    const c = courseById(ctx.match[1]);
    await ctx.answerCallbackQuery();
    if (!c) return;
    await ctx.editMessageText(courseCard(c), {
      parse_mode: "Markdown",
      reply_markup: new InlineKeyboard().text("Купить", `buy:${c.id}`).row().text("⬅️ К каталогу", "catalog"),
    });
  });

  bot.callbackQuery(/^buy:([\w-]+)$/, async (ctx) => {
    const courseId = ctx.match[1];
    const u = await getUser(env, ctx.from.id);
    await ctx.answerCallbackQuery();
    if (!courseById(courseId)) return;
    if (!u?.email) {
      await setUserField(env, ctx.from.id, "state", `email:${courseId}`);
      await ctx.reply("Укажите email: на него придёт чек об оплате.");
      return;
    }
    await ctx.reply("Выберите способ оплаты:", {
      reply_markup: new InlineKeyboard()
        .text("💳 Картой", `pay:${courseId}:any`).row()
        .text("⚡ СБП", `pay:${courseId}:sbp`),
    });
  });

  bot.callbackQuery(/^pay:([\w-]+):(any|sbp)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    try {
      await startPayment(bot, env, ctx.from.id, ctx.match[1], ctx.match[2] as "any" | "sbp");
    } catch (e) {
      console.error(e);
      await ctx.reply("Не получилось создать платёж. Попробуйте ещё раз или напишите нам.");
    }
  });

  bot.callbackQuery("my", async (ctx) => {
    await ctx.answerCallbackQuery();
    const ids = await paidCourseIds(env, ctx.from.id);
    if (!ids.length) {
      await ctx.reply("Пока нет купленных курсов.", { reply_markup: catalogKb(null) });
      return;
    }
    const kb = new InlineKeyboard();
    for (const id of ids) {
      const c = courseById(id);
      if (c) kb.text(`Доступ: ${c.title}`, `access:${c.id}`).row();
    }
    await ctx.reply("Ваши курсы:", { reply_markup: kb });
  });

  bot.callbackQuery(/^access:([\w-]+)$/, async (ctx) => {
    await ctx.answerCallbackQuery();
    const c = courseById(ctx.match[1]);
    const owned = await paidCourseIds(env, ctx.from.id);
    if (c && owned.includes(c.id)) await deliverAccess(bot, ctx.from.id, c);
  });

  // Ввод email (единственный текст, который мы ждём)
  bot.on("message:text", async (ctx) => {
    const u = await getUser(env, ctx.from.id);
    const m = u?.state?.match(/^email:([\w-]+)$/);
    if (!m) return ctx.reply("Нажмите /menu, чтобы открыть меню.");
    const email = ctx.message.text.trim();
    if (!EMAIL_RE.test(email)) return ctx.reply("Похоже, в адресе ошибка. Введите email ещё раз.");
    await setUserField(env, ctx.from.id, "email", email);
    await setUserField(env, ctx.from.id, "state", null);
    await ctx.reply("Выберите способ оплаты:", {
      reply_markup: new InlineKeyboard()
        .text("💳 Картой", `pay:${m[1]}:any`).row()
        .text("⚡ СБП", `pay:${m[1]}:sbp`),
    });
  });

  return bot;
}

/** Обработка вебхука ЮKassa: доверяем только статусу, полученному из API. */
export async function handleYooKassa(bot: Bot, env: Env, event: any) {
  const paymentId: string | undefined = event?.object?.id;
  if (!paymentId) return;
  const pay = await getPayment(env, paymentId);
  const orderId = Number(pay.metadata?.order_id);
  const order = orderId ? await getOrder(env, orderId) : null;
  if (!order || order.yk_payment_id !== pay.id) return;

  if (pay.status === "succeeded") {
    if (pay.amount.value !== rub(order.amount)) return; // сумма не совпала — не выдаём
    if (!(await markPaid(env, order.id))) return; // уже обработано
    const c = courseById(order.course_id);
    if (c) await deliverAccess(bot, order.tg_id, c);
  } else if (pay.status === "canceled") {
    await markCanceled(env, order.id);
  }
}

/** Крон: прогрев и напоминания о неоплаченных заказах. */
export async function runJobs(bot: Bot, env: Env) {
  for (const j of await dueJobs(env)) {
    try {
      const user = await getUser(env, j.tg_id);
      if (!user || user.blocked) {
        await finishJob(env, j.id);
        continue;
      }
      if (j.kind === "cart" && j.ref) {
        const order = await getOrder(env, j.ref);
        if (order?.status === "pending") {
          const c = courseById(order.course_id);
          if (c) {
            await bot.api.sendMessage(j.tg_id, TEXT.cart(c.title), {
              reply_markup: new InlineKeyboard().text("Вернуться к курсу", `course:${c.id}`),
            });
          }
        }
      } else if (j.kind === "nurture1" || j.kind === "nurture2") {
        const bought = await paidCourseIds(env, j.tg_id);
        if (!bought.length) {
          await bot.api.sendMessage(j.tg_id, j.kind === "nurture1" ? TEXT.nurture1 : TEXT.nurture2, {
            reply_markup: new InlineKeyboard().text("📚 Каталог курсов", "catalog"),
          });
        }
      }
      await finishJob(env, j.id);
    } catch (e: any) {
      if (e?.error_code === 403) await markBlocked(env, j.tg_id); // пользователь заблокировал бота
      else console.error("job failed", j.id, e);
      await finishJob(env, j.id);
    }
  }
}
