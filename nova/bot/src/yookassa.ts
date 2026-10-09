import type { Env } from "./types";

const API = "https://api.yookassa.ru/v3";

const auth = (env: Env) => "Basic " + btoa(`${env.YK_SHOP_ID}:${env.YK_SECRET_KEY}`);

export interface YkPayment {
  id: string;
  status: "pending" | "waiting_for_capture" | "succeeded" | "canceled";
  amount: { value: string; currency: string };
  metadata?: { order_id?: string };
  confirmation?: { confirmation_url?: string };
}

export const rub = (kop: number) => (kop / 100).toFixed(2);

export async function createPayment(
  env: Env,
  p: { orderId: number; amountKop: number; title: string; email: string; method: "any" | "sbp" },
): Promise<YkPayment> {
  const body: Record<string, unknown> = {
    amount: { value: rub(p.amountKop), currency: "RUB" },
    capture: true,
    description: `Заказ №${p.orderId}: ${p.title}`.slice(0, 128),
    confirmation: { type: "redirect", return_url: `https://t.me/${env.BOT_USERNAME}` },
    metadata: { order_id: String(p.orderId) },
    receipt: {
      customer: { email: p.email },
      items: [
        {
          description: p.title.slice(0, 128),
          quantity: "1.00",
          amount: { value: rub(p.amountKop), currency: "RUB" },
          vat_code: Number(env.VAT_CODE || "1"),
          payment_mode: "full_payment",
          payment_subject: "service",
        },
      ],
    },
  };
  if (p.method === "sbp") body.payment_method_data = { type: "sbp" };

  const res = await fetch(`${API}/payments`, {
    method: "POST",
    headers: {
      Authorization: auth(env),
      "Content-Type": "application/json",
      // один ключ на заказ+способ: повторное нажатие не создаёт дубль платежа
      "Idempotence-Key": `order-${p.orderId}-${p.method}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`YooKassa create ${res.status}: ${await res.text()}`);
  return res.json<YkPayment>();
}

/** Вебхуки ЮKassa не подписаны, поэтому статус всегда перепроверяем запросом к API. */
export async function getPayment(env: Env, id: string): Promise<YkPayment> {
  const res = await fetch(`${API}/payments/${encodeURIComponent(id)}`, { headers: { Authorization: auth(env) } });
  if (!res.ok) throw new Error(`YooKassa get ${res.status}: ${await res.text()}`);
  return res.json<YkPayment>();
}
