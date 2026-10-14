"""Сбор данных из открытых источников.

    python -m arttracker.collect status                 # реестр источников и их статус
    python -m arttracker.collect artists                # справочник художников из Wikidata
    python -m arttracker.collect works                  # эталонные карточки работ (AIC и The Met)
    python -m arttracker.collect fx                     # курсы валют ECB
    python -m arttracker.collect fx-cbr                 # курс рубля Банка России
    python -m arttracker.collect import-archive F --mapping M   # архив партнёра по договору
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
from .normalize import parse_artist
from .sources import registry
from .sources.adapters import fetch_artists, fetch_fx, parse_lot_page, search_artic, search_met
from .sources.base import PoliteClient, SourceNotAllowed
from .sources.discovery import CATEGORIES, discover

DATA = Path(__file__).resolve().parent.parent / "data"
REF = DATA / "reference"

# Что искать в музейных коллекциях: по одной строке на работу из каталога демо.
WORK_QUERIES = [
    ("rembrandt", "Rembrandt Three Crosses"), ("rembrandt", "Rembrandt Hundred Guilder Print"),
    ("rembrandt", "Rembrandt self-portrait leaning stone sill"), ("rembrandt", "Rembrandt shell conus"),
    ("durer", "Dürer Melencolia"), ("durer", "Dürer Knight Death Devil"), ("durer", "Dürer Saint Jerome study"),
    ("durer", "Dürer Adam and Eve"), ("goya", "Goya sleep of reason monsters"), ("goya", "Goya Disparate miedo"),
    ("picasso", "Picasso Minotauromachy"), ("picasso", "Picasso Frugal Repast"), ("matisse", "Matisse Jazz Icarus"),
    ("warhol", "Warhol Marilyn"), ("warhol", "Warhol Campbell's Soup"), ("lichtenstein", "Lichtenstein Sweet Dreams Baby"),
]


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {path.relative_to(DATA.parent)}")


CATEGORY_RU = {"auction_house": "Аукционные дома", "ru_auction_house": "Аукционные дома России", "art_museum": "Художественные музеи",
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
    names = [n for a in ARTISTS.values() for n in [a["name"], *a["aliases"]] if " " in n or n == a["name"]]
    recs = fetch_artists(client, sorted(set(names)))
    if not recs:
        sys.exit("Wikidata не вернул ни одной записи; справочник не изменён.")
    out = []
    for r in recs:
        aid = next((k for k, a in ARTISTS.items() if r.name in [a["name"], *a["aliases"]]), None)
        out.append({"artist_id": aid, **r.__dict__})
    save(REF / "artists.json", out)
    print(f"художников: {len(out)}, сопоставлено с каталогом: {sum(1 for o in out if o['artist_id'])}")


def cmd_works(args):
    out, rejected = [], 0
    for name, search in (("artic", search_artic), ("met", search_met)):
        try:
            client = PoliteClient(registry.get(name))
        except SourceNotAllowed as e:
            print(e, file=sys.stderr)
            continue
        for artist_id, q in WORK_QUERIES[: args.limit_queries]:
            for w in search(client, q, limit=args.per_query):
                # Поиск музеев полнотекстовый: оставляем только работы нужного художника.
                if w.artist and parse_artist(w.artist)[0] == artist_id:
                    out.append({"artist_id": artist_id, "query": q, **w.to_dict()})
                else:
                    rejected += 1
    seen, unique = set(), []
    for w in out:
        if (w["source"], w["source_id"]) not in seen:
            seen.add((w["source"], w["source_id"]))
            unique.append(w)
    if not unique:
        sys.exit("Музеи не вернули ни одной подходящей карточки; справочник не изменён.")
    save(REF / "reference_works.json", unique)
    by_src = Counter(w["source"] for w in unique)
    print(f"эталонных карточек: {len(unique)} ({', '.join(f'{k}: {v}' for k, v in by_src.items())}), "
          f"с изображением: {sum(1 for w in unique if w['image_url'])}; отсеяно чужих авторов: {rejected}")


def cmd_fx(_):
    fx = fetch_fx(PoliteClient(registry.get("ecb")))
    save(REF / "fx.json", fx)
    days = len(fx["daily"]["EUR"])
    print(f"дней с курсами: {days}; среднегодовые курсы к доллару: " + "; ".join(
        f"{c} {min(v.values()):.3f}–{max(v.values()):.3f}" for c, v in fx["annual"].items()))


def cmd_fx_cbr(_):
    from .sources.adapters import fetch_rub
    fx = fetch_rub(PoliteClient(registry.get("cbr")))
    save(REF / "fx_cbr.json", fx)
    a = fx["annual"]["RUB"]
    print(f"дней с курсом: {len(fx['daily_rub_per_usd'])}; среднегодовой курс, руб. за $: "
          + ", ".join(f"{y}: {1 / v:.1f}" for y, v in a.items()))


def cmd_import_archive(args):
    from .archive import ArchiveError, import_archive
    try:
        rep = import_archive(Path(args.file), Path(args.mapping))
    except ArchiveError as e:
        sys.exit(f"Импорт остановлен: {e}")
    print(f"строк: {rep['rows']}, принято: {rep['accepted']}, отклонено: {rep['rejected']}")
    for reason, n in rep["rejected_reasons"]:
        print(f"  отклонено «{reason}»: {n}")
    print("распознано: " + ", ".join(f"{k} {round(v * 100)}%" for k, v in rep["coverage"].items()))
    print(f"годы: {', '.join(f'{y}: {n}' for y, n in rep['years'].items())}")
    if rep["new_artists"]:
        print(f"художников нет в справочнике: {rep['new_artists']} (будут добавлены при сборке), например: "
              + "; ".join(n for n, _ in rep["top_new_artists"][:5]))
    print("отчёт: data/imported/*.report.json; сборка на импортированных данных: "
          "python -m arttracker.build --source imported")


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
    w.add_argument("--per-query", type=int, default=10)
    w.add_argument("--limit-queries", type=int, default=len(WORK_QUERIES))
    w.set_defaults(fn=cmd_works)
    sub.add_parser("fx").set_defaults(fn=cmd_fx)
    d = sub.add_parser("discover")
    d.add_argument("--category", action="append", choices=list(CATEGORIES))
    d.add_argument("--max-pages", type=int, default=20)
    d.set_defaults(fn=cmd_discover)
    sub.add_parser("fx-cbr").set_defaults(fn=cmd_fx_cbr)
    ia = sub.add_parser("import-archive")
    ia.add_argument("file")
    ia.add_argument("--mapping", required=True)
    ia.set_defaults(fn=cmd_import_archive)
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
