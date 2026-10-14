"""Нормализация сырых лотов: из текста разных домов — в единые поля."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

from .catalog import ARTISTS, HOUSES, REFERENCE_DIR, fx

QUALIFIERS = [
    (r"^(after|nach|d'après|d’après)\s+", "after"),
    (r"^(attributed to|zugeschrieben)\s+", "attributed"),
    (r"^(circle of|umkreis von?)\s+", "circle"),
    (r"^(school of|schule des?)\s+", "school"),
]
ORDINALS = {"first": "I", "second": "II", "third": "III", "fourth": "IV", "fifth": "V",
            "sixth": "VI", "seventh": "VII"}


def unaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unaccent(s).lower())


# ---------- художник ----------

def _artist_keys():
    keys = {}
    for aid, a in ARTISTS.items():
        for name in [a["name"], *a["aliases"]]:
            keys[" ".join(tokens(name))] = aid
    # Имена и псевдонимы из Wikidata (python -m arttracker.collect artists), если собраны.
    ref = REFERENCE_DIR / "artists.json"
    if ref.exists():
        for r in json.loads(ref.read_text(encoding="utf-8")):
            if r.get("artist_id"):
                for name in [r["name"], *r.get("labels", {}).values(), *r.get("aliases", [])]:
                    keys.setdefault(" ".join(tokens(name)), r["artist_id"])
    return keys


ARTIST_KEYS = _artist_keys()


def parse_artist(raw: str) -> tuple[str | None, str | None]:
    """Возвращает (artist_id, квалификатор атрибуции)."""
    s = raw.strip()
    qualifier = None
    for pattern, q in QUALIFIERS:
        if re.match(pattern, s, re.I):
            qualifier, s = q, re.sub(pattern, "", s, flags=re.I)
            break
    s = re.sub(r"\(.*?\)", "", s).strip()
    if "," in s:  # «Kusama, Yayoi» → «Yayoi Kusama»
        last, first = [x.strip() for x in s.split(",", 1)]
        s = f"{first} {last}"
    key = " ".join(tokens(s))
    if key in ARTIST_KEYS:
        return ARTIST_KEYS[key], qualifier
    # Нечёткое совпадение по множеству слов.
    toks = set(key.split())
    best, best_score = None, 0.0
    for k, aid in ARTIST_KEYS.items():
        kt = set(k.split())
        score = len(toks & kt) / len(toks | kt)
        if score > best_score:
            best, best_score = aid, score
    return (best if best_score >= 0.5 else None), qualifier


# ---------- даты ----------

def parse_year(text: str | None) -> tuple[int | None, int | None, bool]:
    if not text:
        return None, None, False
    circa = bool(re.search(r"\b(circa|c\.|ca\.|um)\s*\d", text, re.I))
    m = re.search(r"(1[4-9]\d{2}|20\d{2})(?:\s*[-–]\s*(\d{2,4}))?", text)
    if not m:
        return None, None, circa
    y1 = int(m.group(1))
    y2 = y1
    if m.group(2):
        tail = m.group(2)
        y2 = int(str(y1)[: 4 - len(tail)] + tail)
    return y1, y2, circa


# ---------- размеры ----------

NUM = r"\d+(?:[.,]\d+)?"


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _inch(s: str) -> float:
    """«37 5/8», «37-5/8», «36» → дюймы."""
    m = re.match(r"(\d+)(?:[\s-]+(\d+)/(\d+))?$", s.strip())
    if not m:
        return float("nan")
    v = float(m.group(1))
    if m.group(2):
        v += int(m.group(2)) / int(m.group(3))
    return v


def parse_dimensions(raw: str | None) -> tuple[float | None, float | None]:
    """Высота и ширина в сантиметрах. Метрика в строке важнее дюймов."""
    if not raw:
        return None, None
    m = re.search(rf"({NUM})\s*(?:x|×|by|:)\s*({NUM})\s*(mm|cm)", raw, re.I)
    if m:
        k = 0.1 if m.group(3).lower() == "mm" else 1.0
        return round(_num(m.group(1)) * k, 1), round(_num(m.group(2)) * k, 1)
    frac = r"\d+(?:[\s-]+\d+/\d+)?"
    m = re.search(rf"({frac})\s*(?:x|by)\s*({frac})\s*(?:in\b|in\.|inches)", raw, re.I)
    if m:
        return round(_inch(m.group(1)) * 2.54, 1), round(_inch(m.group(2)) * 2.54, 1)
    return None, None


# ---------- деньги ----------

def parse_amounts(raw: str | None) -> list[int]:
    if not raw:
        return []
    found = re.findall(r"\d{1,3}(?:[.,\s]\d{3})+|\d+", raw)
    return [int(re.sub(r"[.,\s]", "", x)) for x in found]


# ---------- описание: техника, состояние, тираж, каталог ----------

MEDIUM_CLASSES = [
    ("screenprint", r"screenprint|silkscreen|serigraph|siebdruck"),
    ("lithograph", r"lithograph"),
    ("stencil", r"pochoir"),
    ("intaglio", r"etching|engraving|drypoint|burin|aquatint|radierung|kupferstich|kaltnadel|aquatinta"),
    ("woodcut", r"woodcut|holzschnitt"),
]

REF_PATTERNS = [
    (r"\bF\.?\s*&\s*S\.?\s*(II\.\d+)", "F&S {}"),
    (r"\bFeldman[- ]Schellmann\s*(II\.\d+)", "F&S {}"),
    (r"\bCorlett\s*((?:[IVX]+\.)?\d+)", "Corlett {}"),
    (r"\bBloch\s*(\d+)", "Bloch {}"),
    (r"\bHarris\s*(\d+)", "Harris {}"),
    (r"\bLittmann\s*p\.\s*([\d-]+)", "Littmann p.{}"),
    (r"\bBartsch\s*(\d+)", "B.{}"),
    (r"\bB\.\s*(\d+)\b", "B.{}"),
]


def parse_medium_class(text: str) -> str | None:
    t = text.lower()
    for cls, pat in MEDIUM_CLASSES:
        if re.search(pat, t):
            return cls
    return None


def parse_ref(text: str) -> str | None:
    for pat, fmt in REF_PATTERNS:
        m = re.search(pat, text)
        if m:
            return fmt.format(m.group(1))
    return None


def parse_state(text: str) -> str | None:
    """Состояние доски или издание: «State IV», «fourth state», «IV. Zustand», «1st edition»."""
    m = re.search(r"\bstate\s+([IVX]+)\b", text, re.I) or re.search(r"\b([IVX]+)\.\s*Zustand", text)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b(first|second|third|fourth|fifth|sixth|seventh)\s+state\b", text, re.I)
    if m:
        return ORDINALS[m.group(1).lower()]
    m = re.search(r"\b(1st|first|1\.)\s*(edition|Ausgabe)", text, re.I)
    if m:
        return "1st edition"
    m = re.search(r"\b(4th|fourth|4\.)\s*(edition|Ausgabe)", text, re.I)
    if m:
        return "4th edition"
    if re.search(r"vollard", text, re.I):
        return "Vollard edition"
    return None


def parse_signed(text: str) -> bool | None:
    if re.search(r"\b(unsigned|unsigniert)\b", text, re.I):
        return False
    if re.search(r"\b(signed|signiert)\b", text, re.I):
        return True
    return None


def parse_edition(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"(?:numbered|nummeriert|Ed\.|Exemplar)\s*(\d+)\s*/\s*(\d+)", text, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def clean_title(raw: str) -> str:
    """Название без года, номера каталога и указания состояния — для сравнения."""
    t = re.sub(r"\((?:F\.\s*&\s*S\.|Corlett|Bloch|B\.)[^)]*\)", "", raw)
    t = re.sub(r",?\s*State\s+[IVX]+\b", "", t, flags=re.I)
    t = re.sub(r"[.,]?\s*(?:circa\s*|c\.\s*|um\s*)?\b(?:1[4-9]|20)\d{2}(?:\s*[-–]\s*\d{2,4})?\.?\s*$", "", t)
    return t.strip(" .,")


# ---------- итоговая запись ----------

@dataclass
class Lot:
    lot_id: str
    source: str
    house: str
    sale_id: str
    sale_date: str
    year: int
    lot_number: str
    artist_id: str | None
    qualifier: str | None
    title: str
    title_raw: str
    year_from: int | None
    year_to: int | None
    circa: bool
    medium_class: str | None
    height_cm: float | None
    width_cm: float | None
    catalogue_ref: str | None
    state: str | None
    signed: bool | None
    edition_number: int | None
    edition_size: int | None
    currency: str
    est_low: int | None
    est_high: int | None
    est_low_usd: float | None
    est_high_usd: float | None
    hammer_local: int | None
    hammer_usd: float | None
    total_usd: float | None
    status: str
    image_ref: str
    raw: dict

    @property
    def variant_key(self) -> str:
        """Признак, который различает варианты внутри одной работы."""
        if self.state:
            return self.state
        if self.signed is False:
            return "unsigned"
        if self.signed and self.edition_size and self.artist_id == "banksy":
            return "signed"
        return "ed"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw")
        return d


def normalize(raw: dict) -> Lot:
    house = HOUSES[raw["source"]]
    artist_id, qualifier = parse_artist(raw["artist_raw"])
    title_raw = raw["title_raw"]
    text = " ".join(x for x in [title_raw, raw.get("medium_raw") or ""] if x)
    y1, y2, circa = parse_year(raw.get("date_raw") or title_raw)
    h, w = parse_dimensions(raw.get("dimensions_raw"))
    ed_no, ed_size = parse_edition(text)
    year = int(raw["sale_date"][:4])
    rate = fx(raw["currency"], year)

    est = parse_amounts(raw.get("estimate_raw"))
    est_low, est_high = (est[0], est[-1]) if est else (None, None)
    price = parse_amounts(raw.get("price_raw"))
    price = price[0] if price else None

    status = raw.get("status_raw") or ("sold" if price else "unknown")
    hammer_local = total_local = None
    if price:
        if house["price_mode"] == "total":
            total_local = price
            hammer_local = round(price / (1 + house["premium"]))
        else:
            hammer_local = price
            total_local = price * (1 + house["premium"])

    return Lot(
        lot_id=raw["source_lot_id"], source=raw["source"], house=house["name"],
        sale_id=raw["sale_id"], sale_date=raw["sale_date"], year=year, lot_number=raw["lot_number"],
        artist_id=artist_id, qualifier=qualifier, title=clean_title(title_raw), title_raw=title_raw,
        year_from=y1, year_to=y2, circa=circa, medium_class=parse_medium_class(text),
        height_cm=h, width_cm=w, catalogue_ref=parse_ref(text), state=parse_state(text),
        signed=parse_signed(text), edition_number=ed_no, edition_size=ed_size,
        currency=raw["currency"], est_low=est_low, est_high=est_high,
        est_low_usd=round(est_low * rate) if est_low else None,
        est_high_usd=round(est_high * rate) if est_high else None,
        hammer_local=hammer_local,
        hammer_usd=round(hammer_local * rate) if hammer_local else None,
        total_usd=round(total_local * rate) if total_local else None,
        status=status, image_ref=raw["image_ref"], raw=raw,
    )
