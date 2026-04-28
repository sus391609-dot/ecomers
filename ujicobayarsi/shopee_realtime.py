"""
shopee_realtime.py — Modul integrasi data real-time Shopee untuk YarsiMart

Fungsi utama:
  - shopee_trending_pids(products, top_n=50, day=None)
      Mengembalikan list (pid, score, meta) Top N produk trending HARI INI.
      Hanya produk yang ada di katalog `products` yang dimasukkan.
  - shopee_bestseller_pids(products, top_n=50, day=None)
      Mengembalikan list (pid, score, meta) Top N produk terlaris HARI INI
      (berdasarkan estimasi penjualan harian Shopee).
  - try_fetch_shopee_keyword(keyword, limit=20)
      Best-effort fetch ke endpoint search publik Shopee. Akan mengembalikan
      list dict (name, sold, price, rating) jika sukses, atau [] jika gagal
      (anti-bot, network error, dll). Dipakai untuk *menyiram* score produk
      katalog kita dengan angka real Shopee bila tersedia.

Strategi data:
  Shopee tidak menyediakan API publik resmi yang bebas anti-bot, jadi modul
  ini menggunakan dua sumber:
    1) DATA BASELINE dari katalog kita (`sp_qty`, `sp_rev`, `last_month_*`)
       yang berasal dari snapshot scrape Shopee.
    2) DAILY ROTATION yang ditentukan oleh hash SHA256(tanggal+pid).
       Ini meniru perilaku algoritma trending Shopee yang berubah tiap hari.
    3) USER ACTIVITY BOOST dari token pencarian + views di SQLite.
    4) (Opsional) hasil real-time dari endpoint search publik Shopee bila
       berhasil di-fetch — dipakai sebagai pengali tambahan.

Hasil score = baseline_pop * daily_rotation * (1 + user_boost) * (1 + shopee_live_boost)

Karena `daily_rotation` di-seed dengan tanggal hari ini, daftar trending
akan otomatis berganti setiap hari tanpa perlu cron eksternal.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.request
import urllib.error
from datetime import date
from typing import Dict, List, Optional, Tuple


CACHE_DIR = os.path.join(os.path.dirname(__file__), ".shopee_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


# ──────────────────────────────────────────────
# DAILY ROTATION (deterministic per-day shuffle)
# ──────────────────────────────────────────────
def _daily_factor(pid: str, day: str, salt: str = "") -> float:
    """Faktor 0.5 - 1.5 berdasarkan hash(tanggal + pid + salt). Stabil per hari."""
    h = hashlib.sha256(f"{day}:{salt}:{pid}".encode("utf-8")).hexdigest()
    n = int(h[:12], 16) / float(0xFFFFFFFFFFFF)  # 0..1
    return 0.5 + n  # 0.5 .. 1.5


def _today() -> str:
    return date.today().isoformat()


# ──────────────────────────────────────────────
# OPTIONAL: Real Shopee public-search fetch
# ──────────────────────────────────────────────
SHOPEE_SEARCH_URL = (
    "https://shopee.co.id/api/v4/search/search_items"
    "?by=sales&keyword={keyword}&limit={limit}&newest=0&order=desc&page_type=search&version=2"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://shopee.co.id/",
    "X-Requested-With": "XMLHttpRequest",
}


def try_fetch_shopee_keyword(keyword: str, limit: int = 20, timeout: int = 5) -> List[Dict]:
    """Best-effort: fetch top items dari Shopee untuk kata kunci tertentu.
    Mengembalikan [] kalau gagal apa pun penyebabnya (anti-bot, jaringan, dll).
    Hasil di-cache per (keyword, hari) supaya tidak hammering Shopee.
    """
    safe_kw = keyword.lower().strip().replace(" ", "_")
    cache_path = os.path.join(CACHE_DIR, f"kw_{safe_kw}_{_today()}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    url = SHOPEE_SEARCH_URL.format(
        keyword=urllib.request.quote(keyword), limit=limit
    )
    req = urllib.request.Request(url, headers=_HEADERS)
    items: List[Dict] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        for it in (data.get("items") or [])[:limit]:
            ib = it.get("item_basic") or {}
            items.append({
                "name": ib.get("name", ""),
                "sold": ib.get("historical_sold", 0) or ib.get("sold", 0) or 0,
                "price": (ib.get("price", 0) or 0) // 100000,  # Shopee = price * 100k
                "rating": (ib.get("item_rating") or {}).get("rating_star", 0) or 0,
                "shop": ib.get("shop_location", ""),
            })
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError, TimeoutError):
        items = []

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(items, f)
    except Exception:
        pass
    return items


def _shopee_live_boost_map(products: Dict[str, Dict], day: str) -> Dict[str, float]:
    """Untuk tiap kategori unik, coba fetch ke Shopee. Hitung rasio popularitas
    item terhadap rata-rata kategori → boost faktor (0.0 - 1.5) per pid."""
    cache_path = os.path.join(CACHE_DIR, f"live_boost_{day}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    cats = sorted({p["cat"] for p in products.values()})
    boost: Dict[str, float] = {}
    for cat in cats:
        items = try_fetch_shopee_keyword(cat, limit=20)
        if not items:
            continue
        total_sold = sum(it.get("sold", 0) for it in items) or 1
        # Map ke produk kita di kategori ini berdasarkan name-substring match
        cat_pids = [pid for pid, p in products.items() if p["cat"] == cat]
        for pid in cat_pids:
            pname = products[pid]["name"].lower()
            best_match_sold = 0
            for it in items:
                iname = (it.get("name") or "").lower()
                if not iname:
                    continue
                # Token overlap heuristic
                shared = sum(1 for w in pname.split() if len(w) > 2 and w in iname)
                if shared >= 1 and it.get("sold", 0) > best_match_sold:
                    best_match_sold = it["sold"]
            if best_match_sold > 0:
                boost[pid] = min(1.5, math.log1p(best_match_sold) / math.log1p(total_sold))

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(boost, f)
    except Exception:
        pass
    return boost


# ──────────────────────────────────────────────
# CORE SCORING
# ──────────────────────────────────────────────
def _baseline_popularity(p: Dict) -> float:
    """Skor baseline Shopee: gabungan log(qty) dan log(rev) + rating."""
    qty = p.get("sp_qty", 0)
    rev = p.get("sp_rev", 0)
    rt = p.get("rating", 4.5)
    return math.log1p(qty) * 60 + math.log1p(rev) * 8 + rt * 5


def _baseline_sales_rate(p: Dict) -> float:
    """Estimasi penjualan per hari berdasarkan revenue & harga Shopee."""
    qty = p.get("sp_qty", 0)
    # Shopee `sp_qty` = total terjual sepanjang umur produk di Shopee.
    # Kita anggap window ~ 365 hari. Sales rate = qty / 365.
    return qty / 365.0


def _user_boost(tokens: int, views: int, total_tokens: int) -> float:
    """Boost dari aktivitas user. Token dan view masing-masing dianggap sebagai
    sinyal trending. Dinormalisasi terhadap total token DB."""
    if total_tokens <= 0:
        return views * 0.05
    share = tokens / total_tokens
    return share * 5.0 + views * 0.05


def _score_products(
    products: Dict[str, Dict],
    token_map: Dict[str, Tuple[int, int]],
    total_tokens: int,
    *,
    salt: str,
    weight_baseline: float = 1.0,
    weight_sales: float = 0.0,
    day: Optional[str] = None,
    use_shopee_live: bool = True,
) -> List[Tuple[str, float, Dict]]:
    """Hitung score per produk; salt menentukan rotasi (trending vs bestseller)."""
    day = day or _today()
    live_boost = _shopee_live_boost_map(products, day) if use_shopee_live else {}

    scored: List[Tuple[str, float, Dict]] = []
    for pid, p in products.items():
        base_pop = _baseline_popularity(p)
        base_sales = _baseline_sales_rate(p)
        rotation = _daily_factor(pid, day, salt=salt)
        tokens, views = token_map.get(pid, (0, 0))
        u_boost = _user_boost(tokens, views, total_tokens)
        live_b = live_boost.get(pid, 0.0)

        score = (
            (weight_baseline * base_pop + weight_sales * base_sales)
            * rotation
            * (1.0 + u_boost)
            * (1.0 + live_b)
        )

        scored.append((pid, score, {
            "base_pop": round(base_pop, 2),
            "base_sales_per_day": round(base_sales, 2),
            "rotation": round(rotation, 3),
            "user_boost": round(u_boost, 3),
            "shopee_live_boost": round(live_b, 3),
            "tokens": tokens,
            "views": views,
        }))
    scored.sort(key=lambda x: -x[1])
    return scored


def shopee_trending_pids(
    products: Dict[str, Dict],
    token_map: Dict[str, Tuple[int, int]],
    total_tokens: int,
    top_n: int = 50,
    day: Optional[str] = None,
    use_shopee_live: bool = True,
) -> List[Tuple[str, float, Dict]]:
    """Top N produk *trending* HARI INI dari katalog kita.
    Bobot lebih ke popularitas + rotasi harian + aktivitas user."""
    return _score_products(
        products, token_map, total_tokens,
        salt="trending",
        weight_baseline=1.0, weight_sales=0.0,
        day=day, use_shopee_live=use_shopee_live,
    )[:top_n]


def shopee_bestseller_pids(
    products: Dict[str, Dict],
    token_map: Dict[str, Tuple[int, int]],
    total_tokens: int,
    top_n: int = 50,
    day: Optional[str] = None,
    use_shopee_live: bool = True,
) -> List[Tuple[str, float, Dict]]:
    """Top N produk *terlaris* HARI INI. Bobot lebih ke sales rate Shopee."""
    return _score_products(
        products, token_map, total_tokens,
        salt="bestseller",
        weight_baseline=0.4, weight_sales=12.0,
        day=day, use_shopee_live=use_shopee_live,
    )[:top_n]


def daily_estimated_sales(p: Dict, meta: Dict) -> int:
    """Estimasi unit terjual hari ini = sales_rate * rotasi * (1 + boost user)."""
    base = _baseline_sales_rate(p)
    est = base * meta.get("rotation", 1.0) * (1.0 + meta.get("user_boost", 0.0))
    return max(1, int(round(est)))
