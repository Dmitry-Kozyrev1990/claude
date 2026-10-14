"""Движок уведомлений: предстоящие лоты против избранного и коллекции пользователя."""
from __future__ import annotations

import math
from datetime import date

from .catalog import HOUSES
from .matching import cosine

SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€"}
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]


def money(x: float, cur: str = "USD") -> str:
    return f"{SYMBOL[cur]}{int(round(x)):,}".replace(",", " ")


def ru_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def state_label(s: str | None) -> str:
    if not s:
        return ""
    if s.isalpha() and set(s) <= set("IVX"):
        return f"состояние {s}"
    return {"1st edition": "1-е издание", "4th edition": "4-е издание", "Vollard edition": "издание Воллара",
            "signed": "подписной тираж", "unsigned": "неподписной тираж"}.get(s, s)


def centroid(vectors):
    c = [sum(xs) / len(vectors) for xs in zip(*vectors)]
    n = math.sqrt(sum(x * x for x in c))
    return [x / n for x in c]


def lot_signal(lot, valuation) -> dict | None:
    """Сравнение эстимейта (с премией) со справедливой стоимостью по аналогам."""
    if not valuation or not lot.est_high_usd:
        return None
    prem = 1 + HOUSES[lot.source]["premium"]
    est_mid_total = (lot.est_low_usd + lot.est_high_usd) / 2 * prem
    gap = valuation["p50"] / est_mid_total - 1
    if gap > 0.15:
        kind = "below_market"
    elif gap < -0.15:
        kind = "above_market"
    else:
        kind = "in_line"
    return {"kind": kind, "gap": round(gap, 3)}


def reason_for(artist, variant, sim, own_variant, own_artist, watch_artists, watch_works):
    """Почему лот попадает в ленту пользователя (та же логика повторена в веб-интерфейсе)."""
    if variant == own_variant or (artist == own_artist and sim > 0.6):
        return "similar"
    if variant in watch_works:
        return "work"
    if artist in watch_artists:
        return "artist"
    return None


def build_alerts(upcoming, variants, valuations, match, emb, lots_by_variant):
    """Пример пользователя: коллекция из одной работы и избранное, которое
    пересекается с ближайшими торгами. Всё помечено в интерфейсе как пример."""
    up_variants = sorted({match.variant_of[l.lot_id] for l in upcoming if not l.qualifier},
                         key=lambda v: -(valuations.get(v) or {}).get("n", 0))
    if not up_variants:
        return {"collection": [], "watchlist": [], "notifications": []}
    own_variant = up_variants[0]
    own = variants[own_variant]
    own_vec = centroid([emb[l.image_ref] for l in lots_by_variant[own_variant]])
    collection = [{"variant": own_variant, "label": "пример",
                   "note": f"лист 37/{own['edition']}" if own.get("edition") else "оттиск из частного собрания"}]

    artists_up = {}
    for l in upcoming:
        if l.artist_id != own["artist"] and not l.qualifier:
            artists_up[l.artist_id] = artists_up.get(l.artist_id, 0) + 1
    watch_artists = [a for a, _ in sorted(artists_up.items(), key=lambda kv: -kv[1])[:2]]
    watch_works = [v for v in up_variants[1:] if variants[v]["artist"] not in watch_artists
                   and variants[v]["artist"] != own["artist"]][:1]
    watchlist = ([{"type": "artist", "id": a} for a in watch_artists]
                 + [{"type": "work", "id": v} for v in watch_works])

    notes = []
    for l in sorted(upcoming, key=lambda l: l.sale_date):
        if l.qualifier:
            continue
        vid = match.variant_of[l.lot_id]
        sim = cosine(emb[l.image_ref], own_vec)
        v = variants[vid]
        val = valuations.get(vid)
        h = HOUSES[l.source]
        est = (f"{money(l.est_low, l.currency)}–{money(l.est_high, l.currency)}" if l.est_low != l.est_high
               else money(l.est_low, l.currency))
        state_txt = f", {state_label(v.get('variant'))}" if v.get("variant") else ""
        notes.append({
            "lot": l.lot_id, "variant": vid, "artist": l.artist_id, "date": l.sale_date,
            "similarity": round(sim, 3),
            "body": f"{v['title']}{state_txt}. {h['name']}, {h['city']}, {ru_date(l.sale_date)}, "
                    f"лот {l.lot_number}. Эстимейт {est}.",
            "fair": (f"Справедливая стоимость по {val['n']} аналогам: {money(val['p10'])}–{money(val['p90'])}, "
                     f"медиана {money(val['p50'])} с премией." if val else "Аналогов пока мало для оценки."),
            "signal": lot_signal(l, val),
            "reason": reason_for(l.artist_id, vid, sim, own_variant, own["artist"], watch_artists, watch_works),
        })
    return {"collection": collection, "watchlist": watchlist, "notifications": notes}
