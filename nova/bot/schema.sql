CREATE TABLE IF NOT EXISTS users (
  tg_id      INTEGER PRIMARY KEY,
  username   TEXT,
  segment    TEXT,
  source     TEXT,
  email      TEXT,
  state      TEXT,
  created_at INTEGER NOT NULL,
  blocked    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id         INTEGER NOT NULL,
  course_id     TEXT NOT NULL,
  amount        INTEGER NOT NULL,          -- в копейках
  status        TEXT NOT NULL DEFAULT 'pending', -- pending | paid | canceled
  yk_payment_id TEXT UNIQUE,
  created_at    INTEGER NOT NULL,
  paid_at       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(tg_id);

CREATE TABLE IF NOT EXISTS jobs (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id   INTEGER NOT NULL,
  kind    TEXT NOT NULL,                   -- nurture1 | nurture2 | cart
  ref     INTEGER,                         -- order_id для cart
  run_at  INTEGER NOT NULL,
  done    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(done, run_at);
