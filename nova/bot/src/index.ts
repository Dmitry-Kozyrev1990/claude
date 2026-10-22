import { webhookCallback } from "grammy";
import { createBot, runJobs } from "./bot";
import type { Env } from "./types";

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    // Telegram → /tg/<WEBHOOK_SECRET>
    if (req.method === "POST" && url.pathname === `/tg/${env.WEBHOOK_SECRET}`) {
      return webhookCallback(createBot(env), "cloudflare-mod")(req);
    }
    return new Response("Nova bot", { status: 200 });
  },

  async scheduled(_ev: ScheduledController, env: Env, ctx: ExecutionContext) {
    const bot = createBot(env);
    await bot.init();
    ctx.waitUntil(runJobs(bot, env));
  },
};
