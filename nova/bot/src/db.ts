import type { Env } from "./types";

export const now = () => Math.floor(Date.now() / 1000);

export interface User {
  tg_id: number;
  username: string | null;
  first_name: string | null;
  age: string | null;
  source: string | null;
  blocked: number;
}

export interface Order {
  id: number;
  tg_id: number;
  course_id: string;
  amount: number;
  status: "awaiting" | "paid" | "rejected" | "canceled";
  created_at: number;
}

const one = <T>(env: Env, sql: string, ...args: unknown[]) => env.DB.prepare(sql).bind(...args).first<T>();
const run = (env: Env, sql: string, ...args: unknown[]) => env.DB.prepare(sql).bind(...args).run();
const all = async <T>(env: Env, sql: string, ...args: unknown[]) =>
  (await env.DB.prepare(sql).bind(...args).all<T>()).results;

// --- пользователи ---

export const upsertUser = (env: Env, id: number, username?: string, firstName?: string, source?: string) =>
  run(
    env,
    `INSERT INTO users (tg_id, username, first_name, source, created_at) VALUES (?1, ?2, ?3, ?4, ?5)
     ON CONFLICT(tg_id) DO UPDATE SET username = ?2, first_name = ?3, blocked = 0`,
    id, username ?? null, firstName ?? null, source ?? null, now(),
  );

export const getUser = (env: Env, id: number) => one<User>(env, "SELECT * FROM users WHERE tg_id = ?1", id);

export const setAge = (env: Env, id: number, age: string) => run(env, "UPDATE users SET age = ?1 WHERE tg_id = ?2", age, id);

export const markBlocked = (env: Env, id: number) => run(env, "UPDATE users SET blocked = 1 WHERE tg_id = ?1", id);

// --- заказы ---

export async function createOrder(env: Env, tgId: number, courseId: string, amount: number) {
  const r = await run(
    env,
    "INSERT INTO orders (tg_id, course_id, amount, created_at) VALUES (?1, ?2, ?3, ?4)",
    tgId, courseId, amount, now(),
  );
  return r.meta.last_row_id as number;
}

export const getOrder = (env: Env, id: number) => one<Order>(env, "SELECT * FROM orders WHERE id = ?1", id);

/** Открытый (неоплаченный) заказ пользователя на этот курс — чтобы не плодить дубли. */
export const openOrder = (env: Env, tgId: number, courseId: string) =>
  one<Order>(
    env,
    "SELECT * FROM orders WHERE tg_id = ?1 AND course_id = ?2 AND status = 'awaiting' ORDER BY id DESC LIMIT 1",
    tgId, courseId,
  );

/** Решение админа. true только для первого решения: двойное нажатие ничего не ломает. */
export async function decide(env: Env, orderId: number, status: "paid" | "rejected", adminId: number) {
  const r = await run(
    env,
    `UPDATE orders SET status = ?1, decided_by = ?2, paid_at = CASE WHEN ?1 = 'paid' THEN ?3 ELSE NULL END
     WHERE id = ?4 AND status = 'awaiting'`,
    status, adminId, now(), orderId,
  );
  return (r.meta.changes ?? 0) > 0;
}

export const cancelOrder = (env: Env, orderId: number, tgId: number) =>
  run(env, "UPDATE orders SET status = 'canceled' WHERE id = ?1 AND tg_id = ?2 AND status = 'awaiting'", orderId, tgId);

/** Заказы, которые ждут оплаты: по ним админ подтверждает или отклоняет. */
export const awaitingQueue = (env: Env) =>
  all<Order>(env, "SELECT * FROM orders WHERE status = 'awaiting' ORDER BY id LIMIT 20");

export const recentOrders = (env: Env) => all<Order>(env, "SELECT * FROM orders ORDER BY id DESC LIMIT 10");

export async function paidCourseIds(env: Env, tgId: number): Promise<string[]> {
  const r = await all<{ course_id: string }>(
    env, "SELECT DISTINCT course_id FROM orders WHERE tg_id = ?1 AND status = 'paid'", tgId,
  );
  return r.map((x) => x.course_id);
}

/** Ручная выдача доступа админом (подарок, оплата наличными и т. п.) */
export const grant = (env: Env, tgId: number, courseId: string, adminId: number) =>
  run(
    env,
    "INSERT INTO orders (tg_id, course_id, amount, status, created_at, paid_at, decided_by) VALUES (?1, ?2, 0, 'paid', ?3, ?3, ?4)",
    tgId, courseId, now(), adminId,
  );

// --- прогресс по встречам ---

export async function getDone(env: Env, tgId: number, courseId: string) {
  const r = await one<{ done: number }>(env, "SELECT done FROM progress WHERE tg_id = ?1 AND course_id = ?2", tgId, courseId);
  return r?.done ?? 0;
}

/** Отметить встречу n (с нуля) пройденной. Прогресс только растёт. */
export const completeLesson = (env: Env, tgId: number, courseId: string, n: number) =>
  run(
    env,
    `INSERT INTO progress (tg_id, course_id, done) VALUES (?1, ?2, ?3)
     ON CONFLICT(tg_id, course_id) DO UPDATE SET done = MAX(done, ?3)`,
    tgId, courseId, n + 1,
  );

// --- фоновые задачи ---

export const addJob = (env: Env, tgId: number, kind: string, runAt: number, ref?: number) =>
  run(env, "INSERT INTO jobs (tg_id, kind, ref, run_at) VALUES (?1, ?2, ?3, ?4)", tgId, kind, ref ?? null, runAt);

export const dueJobs = (env: Env) =>
  all<{ id: number; tg_id: number; kind: string; ref: number | null }>(
    env, "SELECT id, tg_id, kind, ref FROM jobs WHERE done = 0 AND run_at <= ?1 ORDER BY run_at LIMIT 50", now(),
  );

export const finishJob = (env: Env, id: number) => run(env, "UPDATE jobs SET done = 1 WHERE id = ?1", id);

// --- статистика ---

export async function stats(env: Env) {
  const dayAgo = now() - 86400;
  const [users, newUsers, paid, awaiting, ages, sources] = await Promise.all([
    one<{ n: number }>(env, "SELECT COUNT(*) AS n FROM users"),
    one<{ n: number }>(env, "SELECT COUNT(*) AS n FROM users WHERE created_at >= ?1", dayAgo),
    one<{ n: number; s: number; buyers: number }>(
      env, "SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS s, COUNT(DISTINCT tg_id) AS buyers FROM orders WHERE status = 'paid' AND amount > 0",
    ),
    one<{ n: number }>(env, "SELECT COUNT(*) AS n FROM orders WHERE status = 'awaiting'"),
    all<{ age: string; n: number }>(env, "SELECT COALESCE(age,'—') AS age, COUNT(*) AS n FROM users GROUP BY age"),
    all<{ source: string; n: number }>(
      env, "SELECT COALESCE(source,'—') AS source, COUNT(*) AS n FROM users GROUP BY source ORDER BY n DESC LIMIT 5",
    ),
  ]);
  return {
    users: users?.n ?? 0,
    newUsers: newUsers?.n ?? 0,
    paid: paid?.n ?? 0,
    revenue: paid?.s ?? 0,
    buyers: paid?.buyers ?? 0,
    awaiting: awaiting?.n ?? 0,
    ages,
    sources,
  };
}
