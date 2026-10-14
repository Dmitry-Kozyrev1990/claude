-- Схема PostgreSQL для продуктовой версии (MVP пока хранит данные в JSON).
-- Требует расширений: CREATE EXTENSION pg_trgm; CREATE EXTENSION vector;

-- ---------- справочники ----------
CREATE TABLE sources (
    id           text PRIMARY KEY,               -- wikidata, artic, christies …
    name         text NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('reference', 'fx', 'auction')),
    status       text NOT NULL CHECK (status IN ('approved', 'pending_review', 'blocked')),
    license      text,
    terms_url    text,
    reviewed_on  date,
    review_note  text
);

CREATE TABLE artists (
    id            bigserial PRIMARY KEY,
    canonical     text NOT NULL,
    name_ru       text,
    birth_year    int,
    death_year    int,
    nationality   text,
    segment       text
);
CREATE TABLE artist_names (                       -- все написания: языки, «Фамилия, Имя», псевдонимы
    artist_id  bigint REFERENCES artists ON DELETE CASCADE,
    name       text NOT NULL,
    normalized text NOT NULL,
    lang       text,
    source_id  text REFERENCES sources,
    PRIMARY KEY (artist_id, normalized)
);
CREATE INDEX artist_names_trgm ON artist_names USING gin (normalized gin_trgm_ops);
CREATE TABLE artist_external_ids (
    artist_id bigint REFERENCES artists ON DELETE CASCADE,
    scheme    text NOT NULL,                      -- wikidata, ulan
    value     text NOT NULL,
    PRIMARY KEY (scheme, value)
);

CREATE TABLE auction_houses (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    city        text,
    country     text,
    currency    text,
    premium_rule jsonb                            -- шкала премии покупателя по периодам
);

CREATE TABLE fx_rates (
    currency text,
    day      date,
    usd_per_unit numeric(12, 6) NOT NULL,
    source_id text REFERENCES sources,
    PRIMARY KEY (currency, day)
);

-- ---------- сырые данные ----------
CREATE TABLE raw_documents (                      -- каждый ответ источника хранится как есть
    id          bigserial PRIMARY KEY,
    source_id   text REFERENCES sources,
    url         text NOT NULL,
    fetched_at  timestamptz NOT NULL,
    http_status int,
    storage_key text NOT NULL                     -- путь в S3/MinIO
);

-- ---------- торги и лоты ----------
CREATE TABLE sales (
    id          text PRIMARY KEY,
    house_id    text REFERENCES auction_houses,
    title       text,
    city        text,
    starts_at   date,
    ends_at     date,
    status      text CHECK (status IN ('upcoming', 'live', 'closed'))
);

CREATE TABLE works (                              -- произведение (композиция)
    id          bigserial PRIMARY KEY,
    artist_id   bigint REFERENCES artists,
    title       text NOT NULL,
    year_from   int,
    year_to     int,
    medium_class text,
    catalogue_ref text,                           -- B.78, F&S II.31 …
    is_multiple boolean
);
CREATE TABLE variants (                           -- состояние доски, издание, подписной тираж
    id        bigserial PRIMARY KEY,
    work_id   bigint REFERENCES works ON DELETE CASCADE,
    code      text,
    edition_size int
);
CREATE TABLE objects (                            -- физический экземпляр
    id        bigserial PRIMARY KEY,
    variant_id bigint REFERENCES variants ON DELETE CASCADE,
    impression_number int
);

CREATE TABLE lots (
    id              text PRIMARY KEY,             -- id лота у источника
    source_id       text REFERENCES sources,
    sale_id         text REFERENCES sales,
    lot_number      text,
    raw_document_id bigint REFERENCES raw_documents,
    artist_id       bigint REFERENCES artists,
    attribution     text,                          -- NULL | after | attributed | circle | school
    title_raw       text,
    title           text,
    year_from       int,
    year_to         int,
    medium_raw      text,
    medium_class    text,
    height_cm       numeric(7, 1),
    width_cm        numeric(7, 1),
    size_class      text GENERATED ALWAYS AS (
        CASE WHEN greatest(height_cm, width_cm) < 40 THEN 'S'
             WHEN greatest(height_cm, width_cm) <= 100 THEN 'M'
             WHEN height_cm IS NOT NULL THEN 'L' END) STORED,
    state           text,
    signed          boolean,
    edition_number  int,
    edition_size    int,
    catalogue_ref   text,
    currency        text,
    est_low         numeric(14, 2),
    est_high        numeric(14, 2),
    hammer          numeric(14, 2),
    premium_price   numeric(14, 2),
    hammer_usd      numeric(14, 2),
    premium_usd     numeric(14, 2),
    status          text CHECK (status IN ('upcoming', 'sold', 'bought_in', 'withdrawn', 'unknown')),
    provenance      text,
    literature      text,
    url             text
);
CREATE INDEX lots_artist_date ON lots (artist_id, status);
CREATE INDEX lots_filters ON lots (medium_class, size_class, currency);

CREATE TABLE lot_images (
    lot_id     text REFERENCES lots ON DELETE CASCADE,
    url        text,
    storage_key text,
    phash      bit(64),
    embedding  vector(768),                       -- CLIP / DINOv2
    PRIMARY KEY (lot_id, url)
);

CREATE TABLE lot_links (                          -- результат сопоставления
    lot_id     text PRIMARY KEY REFERENCES lots ON DELETE CASCADE,
    object_id  bigint REFERENCES objects,
    confidence real,
    method     text,                              -- rules | model | expert
    reviewed_by text,
    reviewed_at timestamptz
);

CREATE TABLE reference_works (                    -- музейные карточки (AIC, The Met)
    source_id  text REFERENCES sources,
    source_key text,
    work_id    bigint REFERENCES works,
    title      text,
    artist     text,
    medium     text,
    height_cm  numeric(7, 1),
    width_cm   numeric(7, 1),
    image_url  text,
    embedding  vector(768),
    PRIMARY KEY (source_id, source_key)
);

-- ---------- пользователи ----------
CREATE TABLE users (id bigserial PRIMARY KEY, email text UNIQUE, telegram_chat_id text, plan text);
CREATE TABLE watchlist_items (
    user_id bigint REFERENCES users ON DELETE CASCADE,
    kind    text CHECK (kind IN ('artist', 'work', 'search')),
    ref     text NOT NULL,                        -- id художника, варианта или JSON сохранённого поиска
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (user_id, kind, ref)
);
CREATE TABLE collection_items (
    id        bigserial PRIMARY KEY,
    user_id   bigint REFERENCES users ON DELETE CASCADE,
    variant_id bigint REFERENCES variants,
    note      text,
    embedding vector(768)                         -- фото работы пользователя
);
CREATE TABLE notifications (
    id      bigserial PRIMARY KEY,
    user_id bigint REFERENCES users ON DELETE CASCADE,
    lot_id  text REFERENCES lots,
    reason  text,                                 -- similar | work | artist | result
    sent_at timestamptz,
    channel text,
    UNIQUE (user_id, lot_id, reason)              -- одно уведомление на лот и причину
);

-- ---------- витрины (пересчёт ночью) ----------
CREATE MATERIALIZED VIEW mv_artist_yearly AS
SELECT artist_id, extract(year FROM s.ends_at)::int AS year,
       count(*) FILTER (WHERE l.status IN ('sold', 'bought_in')) AS offered,
       count(*) FILTER (WHERE l.status = 'sold') AS sold,
       sum(premium_usd) FILTER (WHERE l.status = 'sold') AS turnover_usd,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY premium_usd) FILTER (WHERE l.status = 'sold') AS median_usd
FROM lots l JOIN sales s ON s.id = l.sale_id
WHERE l.attribution IS NULL
GROUP BY 1, 2;

CREATE MATERIALIZED VIEW mv_artist_breakdown AS
SELECT artist_id, medium_class, size_class, h.country,
       CASE WHEN premium_usd < 10000 THEN '<10k' WHEN premium_usd < 100000 THEN '10k–100k'
            WHEN premium_usd < 1000000 THEN '100k–1m' ELSE '>1m' END AS price_band,
       count(*) AS lots, sum(premium_usd) AS turnover_usd
FROM lots l JOIN sales s ON s.id = l.sale_id JOIN auction_houses h ON h.id = s.house_id
WHERE l.status = 'sold' AND l.attribution IS NULL
GROUP BY 1, 2, 3, 4, 5;

-- Индекс цен, оценки и рейтинги считает Python (arttracker/analytics.py)
-- и пишет в таблицы mv_artist_index, valuations, mv_artist_ranking, mv_top_lots.
