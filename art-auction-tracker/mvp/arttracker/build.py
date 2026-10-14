"""Полный прогон конвейера: сырые лоты → нормализация → сопоставление → аналитика → дашборд.

Запуск:  python -m arttracker.build          (сгенерирует демо-данные, если их нет)
Результат: data/data.json и web/index.html (самодостаточная страница с данными внутри).
"""
from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from . import generate
from .alerts import build_alerts, lot_signal
from .analytics import (YEARS, cagr, estimate_bias, hedonic_index, index_at, liquidity, repeat_sales,
                        sold_originals, valuation, variant_catalog)
from .catalog import ARTISTS, HOUSES, MARKETS, SEGMENTS, fx
from .matching import match, pairwise_quality
from .normalize import normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"
TODAY = generate.TODAY


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_reference(variants: dict) -> dict:
    """Справочники из открытых источников: Wikidata, музейные карточки, курсы ECB."""
    from .catalog import REFERENCE_DIR
    from .matching import title_similarity
    out = {"artists": {}, "museum": {}, "fx_source": None, "counts": {}}
    path = REFERENCE_DIR / "artists.json"
    if path.exists():
        for r in json.loads(path.read_text(encoding="utf-8")):
            if r.get("artist_id"):
                out["artists"][r["artist_id"]] = {k: r[k] for k in ("wikidata_id", "ulan_id", "birth_year", "death_year")} | {
                    "names": sorted({r["name"], *r.get("labels", {}).values(), *r.get("aliases", [])[:12]})}
        out["counts"]["artists"] = len(out["artists"])
    path = REFERENCE_DIR / "reference_works.json"
    if path.exists():
        refs = json.loads(path.read_text(encoding="utf-8"))
        out["counts"]["museum_cards"] = len(refs)
        for vid, v in variants.items():
            work_titles = [v["title"], *v["titles_seen"]]
            matches = []
            for r in refs:
                if r["artist_id"] != v["artist"]:
                    continue
                sim = max(title_similarity(t, r["title"]) for t in work_titles)
                if sim < 0.6:
                    continue
                size_ok = None
                if v.get("size") and r.get("height_cm") and r.get("width_cm"):
                    a, b = sorted(v["size"]), sorted([r["height_cm"], r["width_cm"]])
                    size_ok = all(abs(x - y) / max(x, y) <= 0.05 for x, y in zip(a, b))
                matches.append({"source": r["source"], "title": r["title"], "date": r["date_display"],
                                "size": [r["height_cm"], r["width_cm"]] if r.get("height_cm") else None,
                                "size_ok": size_ok, "url": r["url"], "public_domain": r.get("public_domain")})
            if matches:
                matches.sort(key=lambda m: (m["size_ok"] is not True, m["source"]))
                out["museum"][vid] = matches[:6]
        out["counts"]["works_with_museum"] = len({VARIANT_WORK(v) for v in out["museum"]})
    path = REFERENCE_DIR / "fx.json"
    if path.exists():
        fx = json.loads(path.read_text(encoding="utf-8"))
        out["fx_source"] = {"name": "ECB", "days": len(fx["daily"]["EUR"]), "last": max(fx["daily"]["EUR"])}
    return out


def VARIANT_WORK(vid: str) -> str:
    return vid.split("|")[0]


def true_index(aid: str) -> dict:
    """Заложенный в генератор уровень цен — только для проверки метода на демо-данных."""
    from .generate_ru import RU_WORKS, ru_index
    f = ru_index if aid in RU_WORKS else generate.artist_index
    return {y: round(100 * f(aid, y + 0.5) / f(aid, 2015.5), 1) for y in YEARS}


def register_unknown_artists(lots):
    """Реальные архивы содержат тысячи художников, которых нет в справочнике: добавляем их
    по нормализованному имени, рынок — по региону дома."""
    from .normalize import tokens
    for l in lots:
        if l.artist_id or l.qualifier:
            continue
        name = re.sub(r"\(.*?\)|\d{4}\s*[–-]\s*\d{4}", "", l.raw["artist_raw"]).strip(" .,")
        aid = "a-" + "-".join(tokens(name))[:60]
        if aid not in ARTISTS:
            ARTISTS[aid] = {"name": name, "name_ru": name, "aliases": [], "life": "", "nationality": "",
                            "segment": "Прочие", "market": "ru" if HOUSES[l.source].get("region") == "ru" else "intl"}
        l.artist_id = aid


def run(source: str = "demo") -> dict:
    """source="demo" — синтетические данные с эталоном; "imported" — архивы партнёров."""
    t0 = time.time()
    if source == "imported":
        from .archive import IMPORTED, load_imported
        raw = load_imported()
        if not raw:
            raise SystemExit("Нет импортированных архивов: python -m arttracker.collect import-archive …")
        emb_path = IMPORTED / "image_embeddings.json"
        emb = json.loads(emb_path.read_text()) if emb_path.exists() else {}
    else:
        if not (DATA / "raw_lots.jsonl").exists():
            generate.generate(DATA)
        raw = load_jsonl(DATA / "raw_lots.jsonl")
        emb = json.loads((DATA / "image_embeddings.json").read_text())

    # 1. Нормализация
    lots = [normalize(r) for r in raw]
    if source == "imported":
        register_unknown_artists(lots)
    by_id = {l.lot_id: l for l in lots}
    coverage_fields = {"artist_id": "Художник", "medium_class": "Техника", "height_cm": "Размеры",
                       "year_from": "Год создания", "est_low": "Эстимейт", "catalogue_ref": "Номер в каталоге",
                       "state": "Состояние / издание", "edition_number": "Номер в тираже"}
    coverage = {label: round(sum(getattr(l, f) is not None for l in lots) / len(lots), 3)
                for f, label in coverage_fields.items()}

    # 2. Сопоставление
    m = match(lots, emb)

    # 3. Аналитика
    past = [l for l in lots if l.status != "upcoming"]
    sold = sold_originals(past)
    artists_out = {}
    indices = {}
    by_artist_lots = {}
    for l in past:
        by_artist_lots.setdefault(l.artist_id, []).append(l)
    for aid, a in list(ARTISTS.items()):
        a_lots = by_artist_lots.get(aid, [])
        if not a_lots:
            continue
        a_sold = [l for l in sold if l.artist_id == aid]
        idx = hedonic_index(a_sold, m.object_of)
        indices[aid] = idx
        pairs = [p for p in repeat_sales(a_lots, m)]
        last12 = [l for l in a_sold if l.sale_date >= date(TODAY.year - 1, TODAY.month, TODAY.day).isoformat()]
        artists_out[aid] = {
            "id": aid, "name": a["name"], "name_ru": a["name_ru"], "life": a["life"],
            "nationality": a["nationality"], "segment": a["segment"],
            "index": idx,
            "market": a["market"],
            "true_index": true_index(aid) if source == "demo" else None,
            "cagr_all": round(cagr(idx[2015]["value"], idx[max(idx)]["value"], max(idx) - 2015), 4) if idx else None,
            "cagr_3y": round(cagr(index_at(idx, 2023), index_at(idx, 2026), 3), 4) if idx else None,
            "liquidity": liquidity(a_lots, TODAY),
            "bias": estimate_bias(a_lots),
            "turnover_12m": sum(l.total_usd for l in last12),
            "turnover_total": sum(l.total_usd for l in a_sold),
            "lots_total": len([l for l in a_lots if not l.qualifier]),
            "repeat": {"n": len(pairs), "median_cagr": round(statistics.median(p["cagr"] for p in pairs), 4) if pairs else None},
        }

    # Рынок в целом, по рынкам и по сегментам: та же регрессия на всех лотах.
    market = {"all": hedonic_index(sold, m.object_of)}
    for mk in MARKETS:
        market[mk] = hedonic_index([l for l in sold if ARTISTS[l.artist_id]["market"] == mk], m.object_of)

    # Где продаётся русское искусство: оборот в России и за рубежом по годам.
    ru_geo = {}
    for l in sold:
        if ARTISTS[l.artist_id]["market"] != "ru":
            continue
        g = ru_geo.setdefault(l.year, {"ru": 0, "abroad": 0, "lots_ru": 0, "lots_abroad": 0})
        where = "ru" if HOUSES[l.source]["region"] == "ru" else "abroad"
        g[where] += l.total_usd
        g["lots_" + where] += 1
    for seg in sorted({a["segment"] for a in ARTISTS.values()}):
        seg_lots = [l for l in sold if ARTISTS[l.artist_id]["segment"] == seg]
        market[seg] = hedonic_index(seg_lots, m.object_of)

    variants = variant_catalog(lots, m)
    lots_by_variant = defaultdict(list)
    for l in lots:
        if not l.qualifier:
            lots_by_variant[m.variant_of[l.lot_id]].append(l)
    valuations = {}
    for vid, v in variants.items():
        valuations[vid] = valuation([l for l in lots_by_variant[vid] if l.status != "upcoming"],
                                    indices.get(v["artist"], {}), TODAY.year)
        v["valuation"] = valuations[vid]
        v_sold = sorted([l for l in lots_by_variant[vid] if l.status == "sold"], key=lambda l: l.sale_date)
        v["last_sale"] = v_sold[-1].lot_id if v_sold else None
    for aid in artists_out:
        artists_out[aid]["variants"] = sorted(
            [vid for vid, v in variants.items() if v["artist"] == aid],
            key=lambda vid: -variants[vid]["lots"])

    # 4. Предстоящие торги и уведомления
    upcoming = [l for l in lots if l.status == "upcoming"]
    alerts = build_alerts(upcoming, variants, valuations, m, emb, lots_by_variant)
    from .portfolio import build_portfolio
    portfolio = build_portfolio(variants, lots_by_variant, artists_out, upcoming, m, TODAY)
    upcoming_out = []
    for l in sorted(upcoming, key=lambda l: l.sale_date):
        vid = m.variant_of[l.lot_id]
        upcoming_out.append({"lot": l.lot_id, "signal": lot_signal(l, valuations.get(vid))})

    # 5. Оценка качества сопоставления по эталону (есть только у синтетических данных)
    quality = None
    if source == "demo":
        truth = {t["source_lot_id"]: t for t in load_jsonl(DATA / "truth.jsonl")}
        quality = {lvl: pairwise_quality(getattr(m, f"{lvl}_of"), {k: v[f"{lvl}_id"] for k, v in truth.items()})
                   for lvl in ("work", "variant", "object")}

    review = []
    for s in sorted(m.review_queue, key=lambda s: -s.prob)[:8]:
        review.append({"level": s.level, "prob": round(s.prob, 3), "features": s.features, "a": s.a, "b": s.b})

    n = len(lots)
    # 6. Открытые справочники (если собраны: python -m arttracker.collect …)
    reference = load_reference(variants)

    lots_out = []
    for l in lots:
        r = l.raw
        lots_out.append({
            "id": l.lot_id, "a": l.artist_id, "v": m.variant_of[l.lot_id], "o": m.object_of[l.lot_id],
            "d": l.sale_date, "h": l.source, "n": l.lot_number, "s": l.status, "q": l.qualifier,
            "ar": r["artist_raw"], "t": r["title_raw"], "m": r.get("medium_raw"), "dim": r.get("dimensions_raw"),
            "er": r.get("estimate_raw"), "pr": r.get("price_raw"), "cur": l.currency,
            "el": l.est_low, "eh": l.est_high, "elu": l.est_low_usd, "ehu": l.est_high_usd,
            "hu": l.hammer_usd, "tu": l.total_usd, "st": l.state, "ed": l.edition_number,
            "ref": l.catalogue_ref, "hc": l.height_cm, "wc": l.width_cm,
            "inf": l.lot_id in m.variant_inferred,
        })

    objects = Counter(m.object_of[l.lot_id] for l in sold)
    data = {
        "meta": {
            "today": TODAY.isoformat(), "built_seconds": round(time.time() - t0, 1),
            "synthetic": source == "demo",
            "licenses": sorted({r["license"] for r in raw if r.get("license")}),
            "markets": MARKETS, "segments": SEGMENTS,
            "rub_per_usd": round(1 / fx("RUB", TODAY.year), 2),
            "by_market": {mk: {"lots": sum(1 for l in lots if ARTISTS.get(l.artist_id, {}).get("market") == mk),
                               "sold": sum(1 for l in sold if ARTISTS[l.artist_id]["market"] == mk),
                               "turnover": sum(l.total_usd for l in sold if ARTISTS[l.artist_id]["market"] == mk),
                               "artists": sum(1 for a in ARTISTS.values() if a["market"] == mk)}
                          for mk in MARKETS},
            "counts": {
                "raw": len(raw), "sources": len({h["name"] for h in HOUSES.values()}), "artists": len(ARTISTS),
                "sold": len(sold), "bought_in": sum(l.status == "bought_in" for l in past),
                "upcoming": len(upcoming), "after": sum(1 for l in lots if l.qualifier),
                "works": len({w for w in m.work_of.values() if not w.startswith("x:")}),
                "variants": len(variants),
                "objects": len({o for o in m.object_of.values() if not o.startswith("x:")}),
                "objects_resold": sum(1 for c in objects.values() if c >= 2),
                "turnover": sum(l.total_usd for l in sold),
            },
        },
        "houses": HOUSES,
        "reference": reference,
        "artists": artists_out,
        "market": market,
        "ru_geo": dict(sorted(ru_geo.items())),
        "variants": variants,
        "lots": lots_out,
        "repeat_pairs": repeat_sales(past, m),
        "upcoming": upcoming_out,
        "alerts": alerts,
        "portfolio": portfolio,
        "pipeline": {
            "coverage": coverage, "blocks": m.blocks, "pairs_compared": m.pairs_compared,
            "pairs_naive": n * (n - 1) // 2, "review_queue": len(m.review_queue), "review": review,
            "quality": quality, "variant_inferred": len(m.variant_inferred),
        },
    }
    return data


def write(data: dict, out: str = "index.html"):
    DATA.mkdir(exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (DATA / "data.json").write_text(payload, encoding="utf-8")
    template = (WEB / "template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", payload.replace("</", "<\\/"))
    (WEB / out).write_text(html, encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="arttracker.build")
    ap.add_argument("--source", choices=["demo", "imported"], default="demo")
    args = ap.parse_args()
    d = run(args.source)
    out = "index.html" if args.source == "demo" else "real.html"
    write(d, out)
    c = d["meta"]["counts"]
    q = d["pipeline"]["quality"]
    print(f"лотов: {c['raw']}, продано: {c['sold']}, работ: {c['works']}, вариантов: {c['variants']}, "
          f"экземпляров: {c['objects']} (перепродавались: {c['objects_resold']})")
    if q:
        print("качество сопоставления (F1): " + ", ".join(f"{k} {v['f1']:.3f}" for k, v in q.items()))
    print(f"уведомлений для примера пользователя: {sum(1 for n in d['alerts']['notifications'] if n['reason'])}, в очереди проверки: {d['pipeline']['review_queue']}")
    print(f"готово за {d['meta']['built_seconds']} с → web/{out}")
