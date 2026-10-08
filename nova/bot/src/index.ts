import { webhookCallback } from "grammy";
import { createBot, handleYooKassa, runJobs } from "./bot";
import type { Env } from "./types";

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    const bot = createBot(env);

    // Telegram → /tg/<WEBHOOK_SECRET>
    if (req.method === "POST" && url.pathname === `/tg/${env.WEBHOOK_SECRET}`) {
      return webhookCallback(bot, "cloudflare-mod")(req);
    }

    // ЮKassa → /yookassa/<WEBHOOK_SECRET>
    if (req.method === "POST" && url.pathname === `/yookassa/${env.WEBHOOK_SECRET}`) {
      const event = await req.json().catch(() => null);
      await bot.init();
      // 200 нужно вернуть быстро, иначе ЮKassa начнёт ретраи
      ctx.waitUntil(handleYooKassa(bot, env, event).catch((e) => console.error("yookassa", e)));
      return new Response("ok");
    }

    return new Response("Nova bot", { status: 200 });
  },

  async scheduled(_ev: ScheduledController, env: Env, ctx: ExecutionContext) {
    const bot = createBot(env);
    await bot.init();
    ctx.waitUntil(runJobs(bot, env));
  },
};
