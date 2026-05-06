---
name: testing-yarsimart
description: End-to-end test the YarsiMart analytics app (Flask + SQLite). Use when verifying admin dashboard, user dashboard, prediction formula, cart log, or login UI changes.
---

# Testing YarsiMart

YarsiMart is a Flask app under `ujicobayarsi/` with two roles: **admin** (analytics dashboard) and **user** (shop dashboard). Aksi user (search/view/cart/buy) langsung tercatat ke admin analytics via tabel `cart_log` + `product_tokens`.

## Quickstart

```bash
cd ujicobayarsi
rm -f yarsimart.db   # optional: reset state for clean test
python3 app.py       # starts on http://127.0.0.1:5000
```

Server logs are in stdout. Reload happens on `app.py` save (debug=True).

## Seeded accounts

| Username | Password | Role |
|----------|----------|------|
| `admin`  | `admin123` | admin |
| `user`   | `user123`  | user  |

Access `/` → redirects ke `/login`. Admin → `/admin`, user → `/user`.

## Running admin + user simultaneously

Session cookie is shared across normal Chrome tabs, jadi membuka tab kedua TIDAK akan login sebagai user kedua. Pakai **Chrome Incognito** (`Ctrl+Shift+N`) untuk sesi user paralel di samping admin di window utama. Atau pakai dua browser berbeda. Logout via profile dropdown di pojok kanan atas → "Keluar".

Alternative untuk smoke test cepat: gunakan `requests` di shell dengan dua `Session()` objects — backend pakai cookie session standar Flask.

## Key product constants for assertions

Produk-produk di-seed deterministik dari `_seed_products()` di `app.py`. Contoh produk uji yang dipakai berkali-kali:

| ID    | Nama | lmv | lms | ratio (`lmv//lms`) | cart weight | buy weight |
|-------|------|-----|-----|--------------------|-------------|------------|
| P0010 | Jersey Premium Hijab — Shopee Fashion Mall | 33892 | 754 | 44 | 22 | 44 |

Untuk mengkonfirmasi nilai aktual produk lain, jalankan:
```python
python3 -c "import sqlite3, json; r=sqlite3.connect('yarsimart.db').execute(\"SELECT id, name, last_month_views, last_month_sales FROM products WHERE id='P0010'\").fetchone(); print(r)"
```
Atau lihat `_seed_products()` langsung — angkanya deterministik dari `random.Random(seed)`.

## Prediction formula & token weighting

Halaman admin **Prediksi AI** menampilkan blok `🧮 Rumus Prediksi LIVE` dengan empat baris:
1. Rasio Bulan Kemarin: `views_lalu / beli_lalu = N`
2. Bobot Token: `view = +1 · cart = +N/2 · buy = +N`
3. Views Bulan Ini = `baseline + aktivitas user`
4. Prediksi Beli: `beli_lalu × (views_skrg / views_lalu)`

Di bawahnya 4-card row: KLIK USER, CART USER, BELI USER, Σ TOKEN USER.
Auto-refresh 5 detik via `startPredictionAutoRefresh()` di `static/js/app.js`.

Backend logic: `_views_per_sale_ratio()`, `_cart_token_weight()`, `_buy_token_weight()` di `app.py`. Di-apply di `/api/action`.

## Catatan UI testing penting

- **User dashboard auto-fires view events** untuk setiap kartu produk yang di-render (20 kartu trending + 20 bestsellers = ~40 view events per page load). Jadi `KLIK USER` tidak hanya bertambah saat user manual klik — termasuk saat scroll/render. Kalau test mengandalkan KLIK USER count exact, throttling-nya belum ada, jadi pengaruh 20-40 dari render perlu di-anticipate.
- **Cart Shopee baseline (e.g. 2.055)** tidak akan ikut bertambah saat user lokal cart 1 item — itu deterministik per hari dari `_get_cart_stats()`. Hanya `Cart User (Live)` dan `Total Cart` yang ikut naik.
- **Logout endpoint `/api/logout` adalah POST**, jadi jangan navigate ke URL ini langsung (akan 405). Pakai profile dropdown → tombol "Keluar".
- **3D login effects** memakai CSS keyframes + JS mousemove. Untuk verifikasi visual, cukup screenshot — orbs, grid floor, dan glass card terlihat statis. Mouse-tilt parallax butuh hover untuk terlihat efeknya.

## Login page selectors

- `#tab-user` / `#tab-admin` — toggle role tabs
- `#user-username`, `#user-password`, `#user-login-btn` — form login pengguna
- `#admin-username`, `#admin-password`, `#admin-login-btn` — form login admin
- Indicator slider di `#tab-indicator` translateX-nya ditentukan oleh JS

## Selector untuk admin Prediksi AI

- `#predProduct` — dropdown 5000 produk (group by kategori)
- `#formula-pred-block` — blok rumus prediksi (di-inject by `injectFormulaIntoPrediction()`)
- Per-card breakdown: data-attributes `data-tok-clicks`, `data-tok-carts`, `data-tok-buys`, `data-tok-total`

## Selector untuk admin Keranjang tab

- Tab nav `[data-section='keranjang']` → section `#section-keranjang`
- Activity feed table `#cart-recent-table` auto-refresh 10 detik
- KPI cards: `#cart-kpi-total`, `#cart-kpi-rate`, `#cart-kpi-shopee`, `#cart-kpi-live`

## Devin Secrets Needed

Tidak ada. App standalone, tidak butuh env vars eksternal.

## Common gotchas

- Kalau `python3 app.py` exit dengan error "port in use", kill: `lsof -ti:5000 | xargs -r kill -9`.
- DB `yarsimart.db` disimpan persistent. Untuk testing yang butuh state bersih, hapus dulu.
- Pre-commit hooks belum dikonfigurasi. Lint dengan `python3 -m py_compile ujicobayarsi/app.py`.
- Tidak ada CI di repo (per Mei 2026).
