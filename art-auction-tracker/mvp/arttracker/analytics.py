"""Аналитика: индексы цен, CAGR, ликвидность, смещение к эстимейту, справедливая стоимость."""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta

import numpy as np

from .catalog import HOUSES
from .matching import MatchResult
from .normalize import Lot

YEARS = list(range(2015, 2027))
EN_SOURCES = {"christies", "sothebys", "phillips", "bonhams", "heritage"}


def sold_originals(lots):
    return [l for l in lots if l.status == "sold" and not l.qualifier and l.total_usd]


def hedonic_index(lots: list[Lot], group_of: dict) -> dict:
    """Индекс: регрессия с фиксированными эффектами экземпляра (гибрид гедонистического
    метода и метода повторных продаж).

    log(цена) = эффект года + эффект экземпляра (или варианта) + шум.
    Эффекты лет относительно 2015 года дают индекс (2015 = 100) и 90% интервал.
    """
    rows = [l for l in lots if l.year in YEARS]
    groups = sorted({group_of[l.lot_id] for l in rows})
    years = sorted({l.year for l in rows} - {2015})
    if not rows or len(rows) <= len(groups) + len(years) or 2015 not in {l.year for l in rows}:
        return {}
    gi = {g: i for i, g in enumerate(groups)}
    yi = {y: len(groups) + i for i, y in enumerate(years)}
    X = np.zeros((len(rows), len(groups) + len(years)))
    y = np.zeros(len(rows))
    for r, l in enumerate(rows):
        X[r, gi[group_of[l.lot_id]]] = 1
        if l.year != 2015:
            X[r, yi[l.year]] = 1
        y[r] = math.log(l.total_usd)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(1, len(rows) - X.shape[1])
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.pinv(X.T @ X)
    counts = Counter(l.year for l in rows)
    out = {2015: {"value": 100.0, "lo": 100.0, "hi": 100.0, "n": counts[2015]}}
    for yr in years:
        b = beta[yi[yr]]
        se = math.sqrt(max(cov[yi[yr], yi[yr]], 0))
        out[yr] = {"value": round(100 * math.exp(b), 1), "lo": round(100 * math.exp(b - 1.645 * se), 1),
                   "hi": round(100 * math.exp(b + 1.645 * se), 1), "n": counts[yr]}
    return dict(sorted(out.items()))


def cagr(v0: float, v1: float, years: float) -> float | None:
    if not v0 or not v1 or years <= 0:
        return None
    return (v1 / v0) ** (1 / years) - 1


def index_at(index: dict, year: int) -> float | None:
    if not index:
        return None
    if year in index:
        return index[year]["value"]
    known = sorted(index)
    nearest = min(known, key=lambda y: abs(y - year))
    return index[nearest]["value"]


def estimate_bias(lots: list[Lot]) -> dict:
    """Где цена молотка относительно эстимейта: выше, внутри, ниже, не продан."""
    above = within = below = unsold = 0
    ratios = []
    for l in lots:
        if l.qualifier or not l.est_low:
            continue
        if l.status == "bought_in":
            unsold += 1
            continue
        if l.status != "sold" or not l.hammer_local:
            continue
        mid = (l.est_low + l.est_high) / 2
        ratios.append(l.hammer_local / mid)
        if l.hammer_local > l.est_high:
            above += 1
        elif l.hammer_local < l.est_low:
            below += 1
        else:
            within += 1
    total = above + within + below + unsold
    if not total:
        return {}
    return {"above": round(above / total, 3), "within": round(within / total, 3),
            "below": round(below / total, 3), "unsold": round(unsold / total, 3), "n": total,
            "mean_ratio": round(statistics.mean(ratios), 3) if ratios else None}


def liquidity(lots: list[Lot], today: date) -> dict:
    """Ликвидность: доля проданных, частота появления на торгах, охват домов."""
    since = (today - timedelta(days=3 * 365)).isoformat()
    recent = [l for l in lots if l.sale_date >= since and l.sale_date <= today.isoformat() and not l.qualifier]
    offered = [l for l in recent if l.status in ("sold", "bought_in")]
    sold = [l for l in offered if l.status == "sold"]
    sell_through = len(sold) / len(offered) if offered else 0.0
    per_year = len(offered) / 3
    houses = len({l.source for l in recent})
    score = 100 * (0.5 * sell_through + 0.3 * min(1.0, per_year / 40) + 0.2 * min(1.0, houses / 6))
    return {"sell_through": round(sell_through, 3), "lots_per_year": round(per_year, 1),
            "houses": houses, "score": round(score)}


def repeat_sales(lots: list[Lot], match: MatchResult) -> list[dict]:
    """Пары последовательных продаж одного экземпляра и их годовая доходность."""
    by_obj = defaultdict(list)
    for l in sold_originals(lots):
        by_obj[match.object_of[l.lot_id]].append(l)
    pairs = []
    for oid, ls in by_obj.items():
        ls.sort(key=lambda l: l.sale_date)
        for a, b in zip(ls, ls[1:]):
            yrs = (date.fromisoformat(b.sale_date) - date.fromisoformat(a.sale_date)).days / 365.25
            if yrs < 0.5:
                continue
            pairs.append({"object": oid, "artist": a.artist_id, "from": a.lot_id, "to": b.lot_id,
                          "years": round(yrs, 1), "p0": a.total_usd, "p1": b.total_usd,
                          "cagr": round(cagr(a.total_usd, b.total_usd, yrs), 4)})
    return pairs


def variant_catalog(lots: list[Lot], match: MatchResult) -> dict:
    """Карточки вариантов работ: название, состояние, размеры, все встреченные написания."""
    by_var = defaultdict(list)
    by_work = defaultdict(list)
    for l in lots:
        if not l.qualifier:
            by_var[match.variant_of[l.lot_id]].append(l)
            by_work[match.work_of[l.lot_id]].append(l)
    # Название — самое частое англоязычное написание на уровне работы, чтобы у вариантов оно совпадало.
    work_title = {}
    for wid, ls in by_work.items():
        en = Counter(l.title for l in ls if l.source in EN_SOURCES)
        work_title[wid] = (en or Counter(l.title for l in ls)).most_common(1)[0][0]
    out = {}
    for vid, ls in by_var.items():
        all_titles = Counter(l.title for l in ls)
        title = work_title[match.work_of[ls[0].lot_id]]
        refs = Counter(l.catalogue_ref for l in ls if l.catalogue_ref)
        key = vid.split("|")[1]
        sizes = [(l.height_cm, l.width_cm) for l in ls if l.height_cm]
        years = Counter((l.year_from, l.year_to) for l in ls if l.year_from)
        y = years.most_common(1)[0][0] if years else (None, None)
        objects = {match.object_of[l.lot_id] for l in ls}
        out[vid] = {
            "id": vid, "work": match.work_of[ls[0].lot_id], "artist": ls[0].artist_id, "title": title,
            "variant": {"ed": None}.get(key, key), "ref": refs.most_common(1)[0][0] if refs else None,
            "medium": ls[0].medium_class,
            "size": [round(statistics.median(s[0] for s in sizes), 1), round(statistics.median(s[1] for s in sizes), 1)] if sizes else None,
            "year": f"{y[0]}" if y[0] == y[1] else f"{y[0]}–{y[1]}",
            "edition": max((l.edition_size for l in ls if l.edition_size), default=None),
            "titles_seen": [t for t, _ in all_titles.most_common()],
            "lots": len(ls), "objects": len(objects),
        }
    return out


def valuation(variant_lots: list[Lot], artist_index: dict, today_year: int) -> dict:
    """Справедливая стоимость по аналогам, приведённым к текущему уровню рынка."""
    comps = []
    now = index_at(artist_index, today_year)
    for l in variant_lots:
        if l.status != "sold" or l.qualifier or not l.total_usd:
            continue
        then = index_at(artist_index, l.year)
        adj = l.total_usd * (now / then) if now and then else l.total_usd
        comps.append({"lot": l.lot_id, "date": l.sale_date, "price": l.total_usd, "adjusted": round(adj)})
    if not comps:
        return {}
    comps.sort(key=lambda c: c["date"], reverse=True)
    vals = sorted(c["adjusted"] for c in comps)
    if len(vals) >= 4:
        q = np.percentile(vals, [10, 50, 90])
        p10, p50, p90 = (int(round(x, -2)) for x in q)
    else:
        p50 = int(round(statistics.median(vals), -2))
        p10, p90 = int(round(p50 * 0.75, -2)), int(round(p50 * 1.3, -2))
    return {"p10": p10, "p50": p50, "p90": p90, "n": len(comps), "comps": [c["lot"] for c in comps[:12]]}
