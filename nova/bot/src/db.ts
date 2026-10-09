import type { Env } from "./types";

export const now = () => Math.floor(Date.now() / 1000);

export interface User {
  tg_id: number;
  username: string | null;
  segment: string | null;
  source: string | null;
  email: string | null;
  state: string | null;
  blocked: number;
}

export interface Order {
  id: number;
  tg_id: number;
  course_id: string;
  amount: number;
  status: string;
  yk_payment_id: string | null;
}

export async function upsertUser(env: Env, tgId: number, username: string | undefined, source?: string) {
  await env.DB.prepare(
    `INSERT INTO users (tg_id, username, source, created_at) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(tg_id) DO UPDATE SET username = ?2, blocked = 0`,
  )
    .bind(tgId, username ?? null, source ?? null, now())
    .run();
}

export const getUser = (env: Env, tgId: number) =>
  env.DB.prepare("SELECT * FROM users WHERE tg_id = ?1").bind(tgId).first<User>();

export const setUserField = (env: Env, tgId: number, field: "segment" | "email" | "state", value: string | null) =>
  env.DB.prepare(`UPDATE users SET ${field} = ?1 WHERE tg_id = ?2`).bind(value, tgId).run();

export async function createOrder(env: Env, tgId: number, courseId: string, amountKop: number) {
  const r = await env.DB.prepare(
    "INSERT INTO orders (tg_id, course_id, amount, created_at) VALUES (?1, ?2, ?3, ?4)",
  )
    .bind(tgId, courseId, amountKop, now())
    .run();
  return r.meta.last_row_id as number;
}

export const getOrder = (env: Env, id: number) =>
  env.DB.prepare("SELECT * FROM orders WHERE id = ?1").bind(id).first<Order>();

export const attachPayment = (env: Env, orderId: number, paymentId: string) =>
  env.DB.prepare("UPDATE orders SET yk_payment_id = ?1 WHERE id = ?2").bind(paymentId, orderId).run();

/** true только для первого перехода pending → paid (защита от повторных вебхуков). */
export async function markPaid(env: Env, orderId: number): Promise<boolean> {
  const r = await env.DB.prepare(
    "UPDATE orders SET status = 'paid', paid_at = ?1 WHERE id = ?2 AND status != 'paid'",
  )
    .bind(now(), orderId)
    .run();
  return (r.meta.changes ?? 0) > 0;
}

export const markCanceled = (env: Env, orderId: number) =>
  env.DB.prepare("UPDATE orders SET status = 'canceled' WHERE id = ?1 AND status = 'pending'").bind(orderId).run();

export async function paidCourseIds(env: Env, tgId: number): Promise<string[]> {
  const r = await env.DB.prepare("SELECT DISTINCT course_id FROM orders WHERE tg_id = ?1 AND status = 'paid'")
    .bind(tgId)
    .all<{ course_id: string }>();
  return r.results.map((x) => x.course_id);
}

export const addJob = (env: Env, tgId: number, kind: string, runAt: number, ref?: number) =>
  env.DB.prepare("INSERT INTO jobs (tg_id, kind, ref, run_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(tgId, kind, ref ?? null, runAt)
    .run();

export async function dueJobs(env: Env) {
  const r = await env.DB.prepare(
    "SELECT id, tg_id, kind, ref FROM jobs WHERE done = 0 AND run_at <= ?1 ORDER BY run_at LIMIT 50",
  )
    .bind(now())
    .all<{ id: number; tg_id: number; kind: string; ref: number | null }>();
  return r.results;
}

export const finishJob = (env: Env, id: number) =>
  env.DB.prepare("UPDATE jobs SET done = 1 WHERE id = ?1").bind(id).run();

export const markBlocked = (env: Env, tgId: number) =>
  env.DB.prepare("UPDATE users SET blocked = 1 WHERE tg_id = ?1").bind(tgId).run();

export async function stats(env: Env) {
  const [u, p, s] = await Promise.all([
    env.DB.prepare("SELECT COUNT(*) AS n FROM users").first<{ n: number }>(),
    env.DB.prepare("SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS s FROM orders WHERE status='paid'").first<{
      n: number;
      s: number;
    }>(),
    env.DB.prepare("SELECT COALESCE(segment,'—') AS seg, COUNT(*) AS n FROM users GROUP BY seg").all<{
      seg: string;
      n: number;
    }>(),
  ]);
  return { users: u?.n ?? 0, paid: p?.n ?? 0, revenueKop: p?.s ?? 0, segments: s.results };
}
