"""Сопоставление (entity resolution): какие лоты — одна работа и один физический экземпляр.

Уровни: работа → вариант (состояние доски, издание, подписной/неподписной тираж)
→ экземпляр (конкретный оттиск). Конвейер:
1. блокировка по художнику и классу техники;
2. признаки пары: номер в каталоге, название, размеры, сходство изображений, год;
3. оценка вероятности совпадения (логистическая функция с заданными весами —
   в продукте веса обучаются на размеченных парах);
4. объединение в кластеры с ограничением «два лота одних торгов — разные объекты»;
5. пары в серой зоне уходят в очередь ручной проверки.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from .normalize import UNIQUE_MEDIA, Lot, tokens

WORK_THRESHOLD = 0.85
REVIEW_LOW = 0.5
OBJECT_IMAGE_THRESHOLD = 0.975
STOPWORDS = {"the", "a", "of", "from", "and", "la", "le", "les", "de", "der", "die", "das",
             "aus", "one", "plate", "in", "his", "on"}


def cosine(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def title_similarity(a: str, b: str) -> float:
    """Максимум из сходства по словам, вхождения одного названия в другое
    («The Three Crosses» внутри полного названия) и символьных триграмм."""
    ta = {t for t in tokens(a) if t not in STOPWORDS}
    tb = {t for t in tokens(b) if t not in STOPWORDS}
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    overlap = 0.85 * len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0

    def grams(s):
        s = " ".join(tokens(s))
        return {s[i:i + 3] for i in range(max(0, len(s) - 2))}
    ga, gb = grams(a), grams(b)
    dice = 2 * len(ga & gb) / (len(ga) + len(gb)) if ga and gb else 0.0
    return max(jac, overlap, dice)


def size_difference(a: Lot, b: Lot) -> float | None:
    """Относительная разница размеров с учётом возможной перестановки сторон."""
    if None in (a.height_cm, a.width_cm, b.height_cm, b.width_cm):
        return None

    def rel(x, y):
        return abs(x - y) / max(x, y)
    straight = max(rel(a.height_cm, b.height_cm), rel(a.width_cm, b.width_cm))
    rotated = max(rel(a.height_cm, b.width_cm), rel(a.width_cm, b.height_cm))
    return min(straight, rotated)


@dataclass
class PairScore:
    a: str
    b: str
    prob: float
    features: dict
    level: str = "work"


def pair_features(a: Lot, b: Lot, emb: dict) -> dict:
    ref = 0
    if a.catalogue_ref and b.catalogue_ref:
        ref = 1 if a.catalogue_ref == b.catalogue_ref else -1
    year = 0.0
    if a.year_from and b.year_from:
        year = min(abs(a.year_from - b.year_from), abs((a.year_to or a.year_from) - (b.year_to or b.year_from)))
    return {
        "ref": ref,
        "title": round(title_similarity(a.title, b.title), 3),
        "size": None if (d := size_difference(a, b)) is None else round(d, 4),
        "image": round(cosine(emb[a.image_ref], emb[b.image_ref]), 4)
        if a.image_ref in emb and b.image_ref in emb else None,
        "year": year,
    }


def work_probability(f: dict, unique: bool = False) -> float:
    if unique:
        # Уникальные картины: названия типовые («Морской пейзаж»), разные картины часто
        # называются одинаково, а одна картина в Москве и Лондоне — по-разному.
        # Решают изображение и размер; название и год лишь добавляют уверенности.
        if f["image"] is None:
            z = -3.0 + 3.0 * f["title"] + 3.0 * (f["ref"] == 1)  # без фото: название + точный размер
        else:
            z = 60.0 * (f["image"] - 0.95) + 1.5 * f["title"]
        z += (0.0 if f["size"] is None else 2.0 * (f["size"] <= 0.01) - 80.0 * max(0.0, f["size"] - 0.02))
        z -= 1.5 * min(f["year"], 3)
        return 1 / (1 + math.exp(-z))
    z = (-4.0
         + 3.0 * (f["ref"] == 1) - 5.0 * (f["ref"] == -1)
         + 2.5 * f["title"]
         + 12.0 * ((0.3 if f["image"] is None else f["image"]) - 0.3)
         + (0.0 if f["size"] is None else 1.5 * (f["size"] <= 0.01) - 60.0 * max(0.0, f["size"] - 0.04))
         - 0.8 * min(f["year"], 5))
    return 1 / (1 + math.exp(-z))


class UnionFind:
    def __init__(self, items, sale_of):
        self.parent = {i: i for i in items}
        self.sales = {i: {sale_of[i]} for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b, allow_same_sale=False) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        if not allow_same_sale and self.sales[ra] & self.sales[rb]:
            return False
        self.parent[rb] = ra
        self.sales[ra] |= self.sales.pop(rb)
        return True

    def groups(self):
        g = defaultdict(list)
        for x in self.parent:
            g[self.find(x)].append(x)
        return list(g.values())


@dataclass
class MatchResult:
    work_of: dict = field(default_factory=dict)      # lot_id → work cluster id
    variant_of: dict = field(default_factory=dict)   # lot_id → variant cluster id
    object_of: dict = field(default_factory=dict)    # lot_id → object cluster id
    variant_inferred: set = field(default_factory=set)  # лоты, чей вариант определён по изображению
    review_queue: list = field(default_factory=list)
    pairs_compared: int = 0
    blocks: int = 0


def match(lots: list[Lot], emb: dict) -> MatchResult:
    res = MatchResult()
    by_id = {l.lot_id: l for l in lots}
    blocks = defaultdict(list)
    for l in lots:
        if l.qualifier:  # «After …», «Circle of …» — отдельные объекты, не оригиналы
            res.work_of[l.lot_id] = res.variant_of[l.lot_id] = res.object_of[l.lot_id] = f"x:{l.lot_id}"
            continue
        blocks[(l.artist_id, l.medium_class)].append(l)
    res.blocks = len(blocks)

    # --- уровень работы
    for (artist, medium), group in blocks.items():
        uf = UnionFind([l.lot_id for l in group], {l.lot_id: l.sale_id for l in group})
        scored = []
        for a, b in combinations(group, 2):
            res.pairs_compared += 1
            f = pair_features(a, b, emb)
            p = work_probability(f, unique=medium in UNIQUE_MEDIA)
            if f["image"] is None and medium not in UNIQUE_MEDIA:
                p = min(p, 0.8)  # без изображения тиражную работу не объединяем автоматически
            if p >= REVIEW_LOW:
                scored.append(PairScore(a.lot_id, b.lot_id, p, f))
        for s in sorted(scored, key=lambda s: -s.prob):
            if s.prob >= WORK_THRESHOLD:
                uf.union(s.a, s.b, allow_same_sale=True)  # одна работа может быть дважды в одних торгах
        best = {}
        for s in scored:
            ca, cb = uf.find(s.a), uf.find(s.b)
            if s.prob < WORK_THRESHOLD and ca != cb:
                key = tuple(sorted((ca, cb)))
                if key not in best or s.prob > best[key].prob:
                    best[key] = s
        res.review_queue.extend(best.values())
        for g in uf.groups():
            wid = f"w:{artist}:{min(g)}"
            for lid in g:
                res.work_of[lid] = wid

    # --- уровень варианта
    works = defaultdict(list)
    for lid, wid in res.work_of.items():
        if not wid.startswith("x:"):
            works[wid].append(by_id[lid])
    for wid, group in works.items():
        keys = {l.variant_key for l in group} - {"ed"}
        centroids = {}
        for k in keys:
            vecs = [emb[l.image_ref] for l in group if l.variant_key == k and l.image_ref in emb]
            if not vecs:
                continue
            c = [sum(xs) / len(vecs) for xs in zip(*vecs)]
            n = math.sqrt(sum(x * x for x in c))
            centroids[k] = [x / n for x in c]
        for l in group:
            k = l.variant_key
            if k == "ed" and centroids and not l.edition_number and l.image_ref in emb:
                # Вариант не указан в описании: берём ближайший по изображению.
                k = max(centroids, key=lambda c: cosine(emb[l.image_ref], centroids[c]))
                res.variant_inferred.add(l.lot_id)
            res.variant_of[l.lot_id] = f"{wid}|{k}"

    # --- уровень экземпляра
    variants = defaultdict(list)
    for lid, vid in res.variant_of.items():
        if not vid.startswith("x:"):
            variants[vid].append(by_id[lid])
    for vid, group in variants.items():
        if group[0].medium_class in UNIQUE_MEDIA:  # уникальная работа: вариант и экземпляр совпадают
            for l in group:
                res.object_of[l.lot_id] = f"{vid}|o:{min(x.lot_id for x in group)}"
            continue
        uf = UnionFind([l.lot_id for l in group], {l.lot_id: l.sale_id for l in group})
        numbered = [l for l in group if l.edition_number]
        by_number = defaultdict(list)
        for l in numbered:
            by_number[l.edition_number].append(l)
        for same in by_number.values():
            for other in same[1:]:
                uf.union(same[0].lot_id, other.lot_id)
        loose = [l for l in group if not l.edition_number]
        pairs, doubtful = [], []
        for a, b in combinations(loose, 2):
            if a.image_ref not in emb or b.image_ref not in emb:
                continue  # без изображений оттиски одной доски не различить
            c = cosine(emb[a.image_ref], emb[b.image_ref])
            d = size_difference(a, b)
            if d is not None and d > 0.008:
                continue
            if c >= OBJECT_IMAGE_THRESHOLD and d is not None:
                pairs.append((c, a.lot_id, b.lot_id))
            elif c >= 0.95:  # похоже, но фото плохое или размеров нет — решает эксперт
                doubtful.append((c, a, b))
        for c, a, b in sorted(pairs, reverse=True):
            uf.union(a, b)
        best = {}
        for c, a, b in sorted(doubtful, reverse=True, key=lambda t: t[0]):
            ca, cb = uf.find(a.lot_id), uf.find(b.lot_id)
            key = tuple(sorted((ca, cb)))
            if ca != cb and a.sale_id != b.sale_id and key not in best:
                prob = round(0.4 + (c - 0.95) / 0.05 * 0.5, 3)
                best[key] = PairScore(a.lot_id, b.lot_id, prob, pair_features(a, b, emb), "object")
        res.review_queue.extend(best.values())
        for g in uf.groups():
            oid = f"{vid}|o:{min(g)}"
            for lid in g:
                res.object_of[lid] = oid
    return res


def pairwise_quality(pred: dict, truth: dict) -> dict:
    """Точность и полнота по парам лотов относительно эталонной разметки."""
    def pairs(assign):
        g = defaultdict(list)
        for k, v in assign.items():
            g[v].append(k)
        return {tuple(sorted(p)) for members in g.values() for p in combinations(members, 2)}
    keys = set(pred) & set(truth)
    p = pairs({k: pred[k] for k in keys})
    t = pairs({k: truth[k] for k in keys})
    tp = len(p & t)
    precision = tp / len(p) if p else 1.0
    recall = tp / len(t) if t else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "pairs_true": len(t), "pairs_pred": len(p)}
