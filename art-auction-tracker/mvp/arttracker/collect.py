"""Сбор данных из открытых источников.

    python -m arttracker.collect status                 # реестр источников и их статус
    python -m arttracker.collect artists                # справочник художников из Wikidata
    python -m arttracker.collect works                  # эталонные карточки работ (AIC и The Met)
    python -m arttracker.collect fx                     # курсы валют ECB
    python -m arttracker.collect discover               # поиск аукционных домов, музеев и коллекций в Wikidata
    python -m arttracker.collect lots URL_FILE          # лоты со страниц одобренных аукционных сайтов

Результаты пишутся в data/reference/ и data/collected_lots.jsonl. Конвейер
(build.py) подхватывает справочники автоматически, если файлы есть.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from .catalog import ARTISTS
from .sources import registry
from .sources.adapters import fetch_artists, fetch_fx, parse_lot_page, search_artic, search_met
from .sources.base import PoliteClient, SourceNotAllowed
from .sources.discovery import CATEGORIES, discover

DATA = Path(__file__).resolve().parent.parent / "data"
REF = DATA / "reference"

# Что искать в музейных коллекциях: по одной строке на работу из каталога демо.
WORK_QUERIES = [
    "Rembrandt Three Crosses", "Rembrandt Hundred Guilder Print", "Rembrandt Self-Portrait Leaning on a Stone Sill",
    "Rembrandt The Shell", "Dürer Melencolia", "Dürer Knight, Death and the Devil", "Dürer Saint Jerome in his Study",
    "Dürer Adam and Eve", "Goya sleep of reason", "Goya Disparate de miedo", "Picasso Minotauromachy",
    "Picasso Frugal Repast", "Matisse Jazz Icarus", "Warhol Marilyn", "Warhol Campbell's Soup", "Lichtenstein Sweet Dreams Baby",
]


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {path.relative_to(DATA.parent)}")


CATEGORY_RU = {"auction_house": "Аукционные дома", "art_museum": "Художественные музеи",
               "bank_collection": "Коллекции банков", "private_collection": "Частные коллекции"}


def cmd_status(_):
    rows = list(registry.REGISTRY.values()) + registry.approved_auction_sources()
    for p in rows:
        mark = {"approved": "✓", "pending_review": "…", "blocked": "✗"}[p.status]
        print(f"{mark} {p.id:<16} {p.kind:<10} {p.status:<15} {p.license}")
        if p.note:
            print(f"  {p.note}")
    cands = registry.discovered_candidates()
    if cands:
        counts = Counter(c["category"] for c in cands)
        print("\nНайдено через Wikidata (ждут проверки): " + ", ".join(
            f"{CATEGORY_RU.get(k, k).lower()} — {v}" for k, v in counts.items()))
    else:
        print("\nКандидаты из Wikidata ещё не собраны: python -m arttracker.collect discover")


def cmd_discover(args):
    cands = discover(PoliteClient(registry.get("wikidata")), args.category or None, max_pages=args.max_pages)
    path = registry.CANDIDATES
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    counts = Counter(c["category"] for c in cands)
    with_site = Counter(c["category"] for c in cands if c["website"])
    for cat in CATEGORIES:
        print(f"{CATEGORY_RU[cat]:<26} {counts[cat]:>6}, с сайтом: {with_site[cat]}")
    print(f"→ {path.relative_to(DATA.parent)} (все в статусе «ждёт проверки условий»)")


def cmd_artists(_):
    client = PoliteClient(registry.get("wikidata"))
    names = [a["name"] for a in ARTISTS.values()] + [al for a in ARTISTS.values() for al in a["aliases"][:1]]
    recs = fetch_artists(client, sorted(set(names)))
    out = []
    for r in recs:
        aid = next((k for k, a in ARTISTS.items() if r.name in [a["name"], *a["aliases"]]), None)
        out.append({"artist_id": aid, **r.__dict__})
    save(REF / "artists.json", out)
    print(f"художников: {len(out)}, сопоставлено с каталогом: {sum(1 for o in out if o['artist_id'])}")


def cmd_works(args):
    out = []
    for name, search in (("artic", search_artic), ("met", search_met)):
        try:
            client = PoliteClient(registry.get(name))
        except SourceNotAllowed as e:
            print(e, file=sys.stderr)
            continue
        for q in WORK_QUERIES[: args.limit_queries]:
            out += [w.to_dict() for w in search(client, q, limit=args.per_query)]
    save(REF / "reference_works.json", out)
    print(f"эталонных карточек: {len(out)}, с изображением: {sum(1 for w in out if w['image_url'])}")


def cmd_fx(_):
    fx = fetch_fx(PoliteClient(registry.get("ecb")))
    save(REF / "fx.json", fx)
    print("среднегодовые курсы к доллару: " + ", ".join(
        f"{c} {min(v)}–{max(v)}" for c, v in fx["annual"].items()))


def cmd_lots(args):
    approved = {d: p for p in registry.approved_auction_sources() for d in p.domains}
    urls = [u.strip() for u in Path(args.url_file).read_text().splitlines() if u.strip()]
    clients, out, skipped = {}, [], 0
    for url in urls:
        host = urlparse(url).hostname or ""
        policy = next((p for d, p in approved.items() if host == d or host.endswith("." + d)), None)
        if not policy:
            print(f"пропуск (домен не одобрен): {url}", file=sys.stderr)
            skipped += 1
            continue
        client = clients.setdefault(policy.id, PoliteClient(policy))
        try:
            resp = client.get(url)
        except SourceNotAllowed as e:
            print(f"пропуск: {e}", file=sys.stderr)
            skipped += 1
            continue
        lot = parse_lot_page(resp.text(), url, policy.id) if resp.status == 200 else None
        if lot:
            out.append(lot)
    path = DATA / "collected_lots.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        for lot in out:
            f.write(json.dumps(lot, ensure_ascii=False) + "\n")
    print(f"лотов: {len(out)}, пропущено: {skipped} → {path.relative_to(DATA.parent)}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="arttracker.collect")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("artists").set_defaults(fn=cmd_artists)
    w = sub.add_parser("works")
    w.add_argument("--per-query", type=int, default=5)
    w.add_argument("--limit-queries", type=int, default=len(WORK_QUERIES))
    w.set_defaults(fn=cmd_works)
    sub.add_parser("fx").set_defaults(fn=cmd_fx)
    d = sub.add_parser("discover")
    d.add_argument("--category", action="append", choices=list(CATEGORIES))
    d.add_argument("--max-pages", type=int, default=20)
    d.set_defaults(fn=cmd_discover)
    lots = sub.add_parser("lots")
    lots.add_argument("url_file")
    lots.set_defaults(fn=cmd_lots)
    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except SourceNotAllowed as e:
        sys.exit(f"Источник недоступен: {e}")
    except OSError as e:
        sys.exit(f"Сеть недоступна: {e}. Проверьте, что домен разрешён в настройках окружения.")


if __name__ == "__main__":
    main()
