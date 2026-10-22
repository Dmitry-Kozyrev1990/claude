CREATE TABLE IF NOT EXISTS users (
  tg_id      INTEGER PRIMARY KEY,
  username   TEXT,
  first_name TEXT,
  age        TEXT,                         -- a7_9 | a10_12 | a13_14 | multi
  source     TEXT,                         -- метка из t.me/<bot>?start=<source>
  created_at INTEGER NOT NULL,
  blocked    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id        INTEGER NOT NULL,
  course_id    TEXT NOT NULL,
  amount       INTEGER NOT NULL,           -- рубли
  status       TEXT NOT NULL DEFAULT 'awaiting', -- awaiting | paid | rejected | canceled
  created_at   INTEGER NOT NULL,
  paid_at      INTEGER,
  decided_by   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(tg_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS progress (
  tg_id     INTEGER NOT NULL,
  course_id TEXT NOT NULL,
  done      INTEGER NOT NULL DEFAULT 0,    -- сколько встреч пройдено
  PRIMARY KEY (tg_id, course_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  tg_id   INTEGER NOT NULL,
  kind    TEXT NOT NULL,                   -- nurture1 | nurture2 | nurture3 | cart
  ref     INTEGER,                         -- order_id для cart
  run_at  INTEGER NOT NULL,
  done    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(done, run_at);
