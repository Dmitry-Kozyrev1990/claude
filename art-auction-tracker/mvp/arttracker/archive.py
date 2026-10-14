"""Импорт исторических архивов, полученных по лицензии или партнёрскому договору.

    python -m arttracker.collect import-archive archive.csv --mapping config/archive_mapping.example.json

Архив (CSV или XLSX) аукционного дома или владельца базы переводится в формат сырых
лотов конвейера и пишется в data/imported/<источник>.jsonl. Без блока license в файле
сопоставления импорт не выполняется: у каждой записи должно быть известно, на каком
основании она в базе.

Отчёт о качестве показывает, сколько строк принято, какие поля распознаны и какие строки
отклонены и почему — его стоит отправить партнёру вместе с вопросами по архиву.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
IMPORTED = DATA / "imported"
HOUSES_FILE = IMPORTED / "houses.json"

FIELDS = ["sale_id", "sale_title", "sale_date", "lot_number", "artist_raw", "title_raw", "date_raw",
          "medium_raw", "dimensions_raw", "estimate_low", "estimate_high", "estimate_raw", "price",
          "price_raw", "currency", "status", "image_url", "provenance", "literature"]
REQUIRED = ["sale_date", "lot_number", "artist_raw", "title_raw"]
LICENSE_KEYS = ["agreement", "signed_on", "scope", "attribution"]
DEFAULT_STATUS = {
    "продан": "sold", "продано": "sold", "sold": "sold", "да": "sold",
    "не продан": "bought_in", "не продано": "bought_in", "снят с торгов": "withdrawn", "снят": "withdrawn",
    "bought in": "bought_in", "unsold": "bought_in", "passed": "bought_in", "withdrawn": "withdrawn",
}


class ArchiveError(Exception):
    pass


def load_mapping(path: Path) -> dict:
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    lic = m.get("license") or {}
    missing = [k for k in LICENSE_KEYS if not lic.get(k)]
    if missing:
        raise ArchiveError("Импорт без договора не выполняется: в блоке license не заполнены "
                           + ", ".join(missing))
    for key in ("source_id", "house", "columns"):
        if key not in m:
            raise ArchiveError(f"В файле сопоставления нет раздела «{key}»")
    unknown = set(m["columns"]) - set(FIELDS)
    if unknown:
        raise ArchiveError(f"Неизвестные поля в columns: {', '.join(sorted(unknown))}")
    return m


def read_rows(path: Path, mapping: dict) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError as e:
            raise ArchiveError("Для Excel нужен пакет openpyxl: pip install openpyxl "
                               "(или сохраните архив как CSV)") from e
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [{head[i]: ("" if v is None else v) for i, v in enumerate(r)} for r in rows[1:] if any(r)]
    enc = mapping.get("encoding", "utf-8-sig")
    text = path.read_text(encoding=enc)
    delim = mapping.get("delimiter") or csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
    return [r for r in csv.DictReader(text.splitlines(), delimiter=delim) if any((v or "").strip() for v in r.values())]


def parse_date(v, fmt: str | None) -> str | None:
    if isinstance(v, (datetime, date)):
        return (v.date() if isinstance(v, datetime) else v).isoformat()
    v = str(v or "").strip()
    if not v:
        return None
    for f in ([fmt] if fmt else []) + ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y"]:
        try:
            return datetime.strptime(v, f).date().isoformat()
        except ValueError:
            continue
    return None


def _num(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(round(v))
    digits = re.sub(r"[^\d]", "", re.sub(r"[.,]\d{1,2}$", "", str(v).strip()))  # копейки/центы отбрасываем
    return int(digits) if digits else None


def convert(rows: list[dict], m: dict) -> tuple[list[dict], list[dict]]:
    """Строки архива → сырые лоты. Возвращает (принятые, отклонённые с причиной)."""
    cols, house, src = m["columns"], m["house"], m["source_id"]
    status_map = {**DEFAULT_STATUS, **{k.lower(): v for k, v in m.get("status_values", {}).items()}}
    ok, rejected, seen = [], [], set()
    for i, row in enumerate(rows, start=2):  # строка 1 — заголовок
        get = lambda f: row.get(cols[f], "") if f in cols else ""  # noqa: E731
        rec = {f: (str(get(f)).strip() if not isinstance(get(f), (int, float, datetime, date)) else get(f))
               for f in cols}
        sale_date = parse_date(rec.get("sale_date"), m.get("date_format"))
        missing = [f for f in REQUIRED if not (sale_date if f == "sale_date" else rec.get(f))]
        if missing:
            rejected.append({"row": i, "reason": "нет обязательных полей", "detail": ", ".join(missing)})
            continue
        sale_id = rec.get("sale_id") or f"{src}-{sale_date}"
        lot_id = f"{src}:{sale_id}-{rec['lot_number']}"
        if lot_id in seen:
            rejected.append({"row": i, "reason": "дубль лота", "detail": f"лот {rec['lot_number']}, торги {sale_id}"})
            continue
        seen.add(lot_id)
        cur = rec.get("currency") or house["currency"]
        lo, hi = _num(rec.get("estimate_low")), _num(rec.get("estimate_high"))
        est_raw = rec.get("estimate_raw") or (f"{lo} – {hi or lo}" if lo else None)
        price = _num(rec.get("price"))
        price_raw = rec.get("price_raw") or (str(price) if price else None)
        st = status_map.get(str(rec.get("status", "")).strip().lower())
        if not st:
            st = "sold" if price else ("upcoming" if sale_date > date.today().isoformat() else "bought_in")
        ok.append({
            "source": src, "sale_id": sale_id, "sale_title": rec.get("sale_title") or house["name"],
            "sale_date": sale_date, "lot_number": str(rec["lot_number"]), "source_lot_id": lot_id,
            "currency": cur, "image_ref": rec.get("image_url") or f"none:{lot_id}",
            "artist_raw": rec["artist_raw"], "title_raw": rec["title_raw"], "date_raw": rec.get("date_raw") or None,
            "medium_raw": rec.get("medium_raw") or None, "dimensions_raw": rec.get("dimensions_raw") or None,
            "estimate_raw": est_raw, "price_raw": price_raw, "status_raw": st,
            "provenance": rec.get("provenance") or None, "literature": rec.get("literature") or None,
            "license": m["license"]["agreement"],
        })
    return ok, rejected


def quality_report(records: list[dict], rejected: list[dict], total: int) -> dict:
    from .normalize import normalize
    lots = [normalize(r) for r in records]
    fields = {"artist_id": "художник узнан", "medium_class": "техника", "height_cm": "размеры",
              "year_from": "год создания", "est_low": "эстимейт", "hammer_usd": "цена (у проданных)"}
    sold = [l for l in lots if l.status == "sold"]
    cov = {}
    for f, label in fields.items():
        pool = sold if f == "hammer_usd" else lots
        cov[label] = round(sum(getattr(l, f) is not None for l in pool) / len(pool), 3) if pool else 0.0
    unknown = Counter(l.raw["artist_raw"] for l in lots if l.artist_id is None)
    years = Counter(l.year for l in lots)
    return {"rows": total, "accepted": len(records), "rejected": len(rejected),
            "rejected_reasons": Counter(r["reason"] for r in rejected).most_common(),
            "rejected_rows": rejected[:20], "coverage": cov,
            "statuses": Counter(l.status for l in lots).most_common(),
            "years": dict(sorted(years.items())), "new_artists": len(unknown),
            "top_new_artists": unknown.most_common(15)}


def import_archive(path: Path, mapping_path: Path, out_dir: Path = IMPORTED) -> dict:
    m = load_mapping(mapping_path)
    rows = read_rows(path, m)
    records, rejected = convert(rows, m)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{m['source_id']}.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    houses_file = out_dir / "houses.json"
    houses = json.loads(houses_file.read_text(encoding="utf-8")) if houses_file.exists() else {}
    houses[m["source_id"]] = {**m["house"], "license": m["license"]}
    houses_file.write_text(json.dumps(houses, ensure_ascii=False, indent=1), encoding="utf-8")
    from .catalog import register_houses
    register_houses(houses)
    report = quality_report(records, rejected, len(rows))
    (out_dir / f"{m['source_id']}.report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
    return report


def load_imported(directory: Path | None = None) -> list[dict]:
    directory = directory or IMPORTED
    if not directory.exists():
        return []
    out = []
    for p in sorted(directory.glob("*.jsonl")):
        out += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return out
