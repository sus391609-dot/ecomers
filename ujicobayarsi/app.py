"""
YarsiMart — Shopee Fashion Analytics + Search Engine
Flask Backend with SQLite Database + Gemini AI Chatbot
5000 Produk (50 Kategori x 100 Toko) + Prediksi Real-Time
"""
from flask import Flask, jsonify, request, render_template
import sqlite3, os, re, math, json
from datetime import datetime
import urllib.request
import urllib.error

app = Flask(__name__, static_folder='static', template_folder='templates')
DB_PATH = os.path.join(os.path.dirname(__file__), 'yarsimart.db')

GEMINI_API_KEY = "AIzaSyDJcwPYspL9-VEXvR-myXV9k3o5kHD6XLE"
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]

def get_gemini_url(model):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

def get_gemini_headers():
    return {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}

# ══════════════════════════════════════════════
# PRODUCT CATALOG — 5000 Produk (loaded from generated data)
# ══════════════════════════════════════════════
import importlib.util, sys
_data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'products_data.py')
if os.path.exists(_data_path):
    _spec = importlib.util.spec_from_file_location("products_data", _data_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    PRODUCTS = _mod.PRODUCTS
else:
    PRODUCTS = {}

TOTAL_PRODUCTS = len(PRODUCTS)

# ══════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS product_tokens (
            product_id TEXT PRIMARY KEY,
            tokens INTEGER DEFAULT 0,
            search_count INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            cart_adds INTEGER DEFAULT 0,
            sales INTEGER DEFAULT 0,
            last_searched DATETIME
        );
        CREATE TABLE IF NOT EXISTS keyword_counts (
            keyword TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0,
            last_searched DATETIME
        );
        CREATE TABLE IF NOT EXISTS search_product_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER,
            product_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (search_id) REFERENCES searches(id)
        );
    """)
    for pid in PRODUCTS:
        conn.execute(
            "INSERT OR IGNORE INTO product_tokens (product_id, tokens, search_count, views, cart_adds, sales) VALUES (?, 0, 0, 0, 0, 0)",
            (pid,)
        )
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
# SEARCH LOGIC
# ══════════════════════════════════════════════
def match_products(query, limit=50):
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for pid, p in PRODUCTS.items():
        name_lower = p["name"].lower()
        cat_lower = p["cat"].lower()
        store_lower = p["store"].lower()
        score = 0
        if q in name_lower:
            score = 100
        elif q in cat_lower:
            score = 80
        elif q in store_lower:
            score = 70
        else:
            words = q.split()
            matched = sum(1 for w in words if w in name_lower or w in cat_lower or w in store_lower)
            if matched > 0:
                score = int(60 * matched / len(words))
        if score > 0:
            results.append({"pid": pid, "score": score, **p})
    results.sort(key=lambda x: -x["score"])
    return results[:limit]

# ══════════════════════════════════════════════
# PREDICTION ENGINE (Real-Time)
# ══════════════════════════════════════════════
def predict_product(pid):
    """
    Prediksi penjualan bulan ini berdasarkan data bulan lalu.
    Rumus: predicted_sales = last_month_sales * (current_month_views / last_month_views)
    """
    p = PRODUCTS.get(pid)
    if not p:
        return None

    lmv = p.get("last_month_views", 1)
    lms = p.get("last_month_sales", 0)
    lmr = p.get("last_month_revenue", 0)
    cmv = p.get("current_month_views", 0)

    if lmv <= 0:
        lmv = 1

    conversion_rate = lms / lmv
    growth_rate = cmv / lmv if lmv > 0 else 1.0
    growth_pct = round((growth_rate - 1) * 100, 1)

    predicted_sales = max(0, round(lms * growth_rate))
    predicted_revenue = predicted_sales * p["price"]

    predicted_daily = max(0, round(predicted_sales / 30))
    predicted_weekly = max(0, round(predicted_sales / 4))

    if growth_pct > 50:
        trend_label = "Sangat Meningkat"
        trend_color = "#16a34a"
    elif growth_pct > 10:
        trend_label = "Meningkat"
        trend_color = "#22c55e"
    elif growth_pct > -10:
        trend_label = "Stabil"
        trend_color = "#eab308"
    elif growth_pct > -30:
        trend_label = "Menurun"
        trend_color = "#f97316"
    else:
        trend_label = "Sangat Menurun"
        trend_color = "#dc2626"

    return {
        "pid": pid,
        "name": p["name"],
        "cat": p["cat"],
        "store": p["store"],
        "price": p["price"],
        "last_month_views": lmv,
        "last_month_sales": lms,
        "last_month_revenue": lmr,
        "current_month_views": cmv,
        "conversion_rate": round(conversion_rate * 100, 2),
        "growth_rate": round(growth_rate, 2),
        "growth_pct": growth_pct,
        "predicted_sales": predicted_sales,
        "predicted_daily": predicted_daily,
        "predicted_weekly": predicted_weekly,
        "predicted_revenue": predicted_revenue,
        "trend_label": trend_label,
        "trend_color": trend_color,
        "sp_qty": p["sp_qty"],
        "sp_rev": p["sp_rev"],
        "rating": p.get("rating", 4.5),
    }

def predict_from_search(pid, total_tokens):
    """Enhanced prediction combining static data + search token boost"""
    conn = get_db()
    row = conn.execute("SELECT tokens, views, cart_adds, sales FROM product_tokens WHERE product_id=?", (pid,)).fetchone()
    conn.close()
    tokens    = row["tokens"]    if row else 0
    views     = row["views"]     if row else 0
    cart_adds = row["cart_adds"] if row else 0
    sales     = row["sales"]     if row else 0
    ctr       = (views / tokens * 100) if tokens > 0 else 0
    atc_rate  = (cart_adds / tokens * 100) if tokens > 0 else 0
    sales_rate= (sales / tokens * 100) if tokens > 0 else 0
    label_prediksi = 'Normal'
    if atc_rate > 2.0 and sales_rate < 1.0:
        label_prediksi = 'Potensi Tinggi'
    base = predict_product(pid) or {}
    pred_monthly = base.get("predicted_sales", 0)
    search_boost = 1.0
    if total_tokens > 0 and tokens > 0:
        share = tokens / total_tokens
        search_boost = 1.0 + (share * 5)
        if ctr > 5.0:      search_boost += 0.5
        if atc_rate > 2.0: search_boost += 1.0
    boosted_monthly = max(1, round(pred_monthly * search_boost)) if pred_monthly > 0 else max(1, round(base.get("last_month_sales", 1) * search_boost))
    return {
        "tokens": tokens, "views": views, "cart_adds": cart_adds, "sales": sales,
        "ctr": round(ctr, 2), "atc_rate": round(atc_rate, 2), "sales_rate": round(sales_rate, 2),
        "label_prediksi": label_prediksi,
        "pred_daily": max(1, round(boosted_monthly / 30)),
        "pred_weekly": max(1, round(boosted_monthly / 4)),
        "pred_monthly": boosted_monthly,
        "est_revenue": boosted_monthly * PRODUCTS.get(pid, {}).get("price", 0),
        "search_boost": round(search_boost, 2),
    }

# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    data  = request.json or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"error": "Query kosong"}), 400
    results = match_products(query)
    matched_pids = [r["pid"] for r in results]
    conn = get_db()
    now  = datetime.now().isoformat()
    cur = conn.execute("INSERT INTO searches (query, result_count, created_at) VALUES (?, ?, ?)", (query, len(results), now))
    search_id = cur.lastrowid
    for pid in matched_pids:
        conn.execute("""
            INSERT INTO product_tokens (product_id, tokens, search_count, last_searched)
            VALUES (?, 1, 1, ?)
            ON CONFLICT(product_id) DO UPDATE SET tokens = tokens + 1, search_count = search_count + 1, last_searched = ?
        """, (pid, now, now))
        conn.execute("INSERT INTO search_product_log (search_id, product_id, created_at) VALUES (?, ?, ?)", (search_id, pid, now))
    words = re.findall(r'[a-zA-Z\u00C0-\u024F]+', query.lower())
    for word in words:
        if len(word) > 1:
            conn.execute("""
                INSERT INTO keyword_counts (keyword, count, last_searched) VALUES (?, 1, ?)
                ON CONFLICT(keyword) DO UPDATE SET count = count + 1, last_searched = ?
            """, (word, now, now))
    conn.commit()
    conn.close()
    result_data = [
        {"pid": r["pid"], "name": r["name"], "cat": r["cat"], "store": r.get("store",""),
         "price": r["price"], "sp_qty": r["sp_qty"], "sp_rev": r["sp_rev"], "score": r["score"]}
        for r in results
    ]
    return jsonify({"query": query, "count": len(results), "results": result_data,
                     "search_id": search_id,
                     "message": f"Pencarian '{query}' tercatat ke database. {len(matched_pids)} produk mendapat token."})

@app.route('/api/trending')
def api_trending():
    conn = get_db()
    rows = conn.execute("SELECT product_id, tokens, search_count, last_searched FROM product_tokens ORDER BY tokens DESC LIMIT 50").fetchall()
    conn.close()
    trending = []
    for r in rows:
        pid = r["product_id"]
        p = PRODUCTS.get(pid, {})
        trending.append({
            "pid": pid, "name": p.get("name",""), "cat": p.get("cat",""), "store": p.get("store",""),
            "price": p.get("price",0), "sp_qty": p.get("sp_qty",0), "sp_rev": p.get("sp_rev",0),
            "tokens": r["tokens"], "search_count": r["search_count"], "last_searched": r["last_searched"],
        })
    return jsonify({"trending": trending})

@app.route('/api/keywords')
def api_keywords():
    conn = get_db()
    rows = conn.execute("SELECT keyword, count, last_searched FROM keyword_counts ORDER BY count DESC LIMIT 15").fetchall()
    conn.close()
    return jsonify({"keywords": [{"keyword": r["keyword"], "count": r["count"], "last": r["last_searched"]} for r in rows]})

@app.route('/api/action', methods=['POST'])
def api_action():
    data = request.json or {}
    pid = data.get('pid')
    action = data.get('action')
    if not pid or action not in ['view', 'cart', 'buy']:
        return jsonify({"error": "Invalid action"}), 400
    conn = get_db()
    if action == 'view':
        conn.execute("UPDATE product_tokens SET views = views + 1 WHERE product_id=?", (pid,))
    elif action == 'cart':
        conn.execute("UPDATE product_tokens SET cart_adds = cart_adds + 1 WHERE product_id=?", (pid,))
    elif action == 'buy':
        conn.execute("UPDATE product_tokens SET sales = sales + 1 WHERE product_id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"{action} recorded"})

@app.route('/api/stats')
def api_stats():
    conn = get_db()
    total_searches    = conn.execute("SELECT COUNT(*) as c FROM searches").fetchone()["c"]
    total_tokens      = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
    unique_keywords   = conn.execute("SELECT COUNT(*) as c FROM keyword_counts").fetchone()["c"]
    products_searched = conn.execute("SELECT COUNT(*) as c FROM product_tokens WHERE tokens > 0").fetchone()["c"]
    recent = conn.execute("SELECT query, created_at FROM searches ORDER BY id DESC LIMIT 5").fetchall()
    conn.close()
    return jsonify({
        "total_searches": total_searches, "total_tokens": total_tokens,
        "unique_keywords": unique_keywords, "products_searched": products_searched,
        "total_products": TOTAL_PRODUCTS,
        "recent_searches": [{"query": r["query"], "time": r["created_at"]} for r in recent],
    })

@app.route('/api/bestsellers')
def api_bestsellers():
    conn = get_db()
    total_tokens = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
    rows = conn.execute("SELECT product_id, tokens FROM product_tokens WHERE tokens > 0 ORDER BY tokens DESC LIMIT 10").fetchall()
    conn.close()
    bestsellers = []
    for r in rows:
        pid = r["product_id"]
        pred = predict_from_search(pid, total_tokens)
        p = PRODUCTS.get(pid, {})
        bestsellers.append({"pid": pid, "name": p.get("name",""), "cat": p.get("cat",""),
                            "store": p.get("store",""), "price": p.get("price",0), "sp_qty": p.get("sp_qty",0), **pred})
    return jsonify({"bestsellers": bestsellers})

@app.route('/api/predict/<pid>')
def api_predict(pid):
    if pid not in PRODUCTS:
        return jsonify({"error": "Product not found"}), 404
    conn = get_db()
    total_tokens = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
    conn.close()
    pred = predict_from_search(pid, total_tokens)
    base_pred = predict_product(pid) or {}
    p = PRODUCTS[pid]
    return jsonify({
        "pid": pid, "name": p["name"], "cat": p["cat"], "store": p["store"], "price": p["price"],
        **pred, **{k: v for k, v in base_pred.items() if k not in pred},
    })

@app.route('/api/predict_all')
def api_predict_all():
    """Get prediction summary for all categories"""
    cat = request.args.get('cat', '')
    store = request.args.get('store', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))

    filtered = {}
    for pid, p in PRODUCTS.items():
        if cat and p["cat"] != cat:
            continue
        if store and p["store"] != store:
            continue
        filtered[pid] = p

    total = len(filtered)
    pids = list(filtered.keys())
    start = (page - 1) * per_page
    end = start + per_page
    page_pids = pids[start:end]

    results = []
    for pid in page_pids:
        pred = predict_product(pid)
        if pred:
            results.append(pred)

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page),
        "results": results,
    })

@app.route('/api/category_summary')
def api_category_summary():
    """Get aggregated data per category"""
    summary = {}
    for pid, p in PRODUCTS.items():
        cat = p["cat"]
        if cat not in summary:
            summary[cat] = {
                "cat": cat, "store_count": 0, "total_sp_qty": 0, "total_sp_rev": 0,
                "total_lm_views": 0, "total_lm_sales": 0, "total_cmv": 0,
                "total_predicted_sales": 0, "total_predicted_rev": 0,
                "avg_price": 0, "_prices": [],
            }
        s = summary[cat]
        s["store_count"] += 1
        s["total_sp_qty"] += p["sp_qty"]
        s["total_sp_rev"] += p["sp_rev"]
        s["total_lm_views"] += p["last_month_views"]
        s["total_lm_sales"] += p["last_month_sales"]
        s["total_cmv"] += p["current_month_views"]
        s["_prices"].append(p["price"])
        pred = predict_product(pid)
        if pred:
            s["total_predicted_sales"] += pred["predicted_sales"]
            s["total_predicted_rev"] += pred["predicted_revenue"]

    result = []
    for cat, s in summary.items():
        s["avg_price"] = round(sum(s["_prices"]) / len(s["_prices"])) if s["_prices"] else 0
        conv = round(s["total_lm_sales"] / s["total_lm_views"] * 100, 2) if s["total_lm_views"] > 0 else 0
        growth = round((s["total_cmv"] / s["total_lm_views"] - 1) * 100, 1) if s["total_lm_views"] > 0 else 0
        del s["_prices"]
        s["conversion_rate"] = conv
        s["growth_pct"] = growth
        result.append(s)
    result.sort(key=lambda x: x["total_sp_rev"], reverse=True)
    return jsonify({"categories": result})

@app.route('/api/store_summary')
def api_store_summary():
    """Get aggregated data per store"""
    cat_filter = request.args.get('cat', '')
    summary = {}
    for pid, p in PRODUCTS.items():
        if cat_filter and p["cat"] != cat_filter:
            continue
        store = p["store"]
        if store not in summary:
            summary[store] = {
                "store": store, "product_count": 0, "total_sp_qty": 0, "total_sp_rev": 0,
                "total_lm_views": 0, "total_lm_sales": 0, "total_cmv": 0,
                "total_predicted_sales": 0, "categories": set(),
            }
        s = summary[store]
        s["product_count"] += 1
        s["total_sp_qty"] += p["sp_qty"]
        s["total_sp_rev"] += p["sp_rev"]
        s["total_lm_views"] += p["last_month_views"]
        s["total_lm_sales"] += p["last_month_sales"]
        s["total_cmv"] += p["current_month_views"]
        s["categories"].add(p["cat"])
        pred = predict_product(pid)
        if pred:
            s["total_predicted_sales"] += pred["predicted_sales"]

    result = []
    for store, s in summary.items():
        s["categories"] = list(s["categories"])
        s["cat_count"] = len(s["categories"])
        growth = round((s["total_cmv"] / s["total_lm_views"] - 1) * 100, 1) if s["total_lm_views"] > 0 else 0
        s["growth_pct"] = growth
        result.append(s)
    result.sort(key=lambda x: x["total_sp_rev"], reverse=True)
    return jsonify({"stores": result})

@app.route('/api/reset', methods=['POST'])
def api_reset():
    conn = get_db()
    conn.executescript("""
        DELETE FROM searches;
        DELETE FROM search_product_log;
        UPDATE product_tokens SET tokens=0, search_count=0, views=0, cart_adds=0, sales=0, last_searched=NULL;
        DELETE FROM keyword_counts;
    """)
    conn.commit()
    conn.close()
    return jsonify({"message": "Database reset!"})

# ══════════════════════════════════════════════
# GEMINI AI CHATBOT (Enhanced)
# ══════════════════════════════════════════════
def local_fallback_reply(user_message, stats):
    q = user_message.lower()
    fmt_rp = lambda n: f"Rp {int(n):,}".replace(",", ".")

    if any(w in q for w in ["terlaris", "bestseller", "best seller", "laku"]):
        top5 = sorted(PRODUCTS.values(), key=lambda p: p["sp_rev"], reverse=True)[:5]
        result = "**Top 5 Produk Terlaris (Revenue Shopee):**\n"
        for i, p in enumerate(top5):
            result += f"{i+1}. {p['name']} ({p['store']}) — {fmt_rp(p['sp_rev'])}\n"
        return result

    if any(w in q for w in ["mahal", "premium", "termahal"]):
        top5 = sorted(PRODUCTS.values(), key=lambda p: p["price"], reverse=True)[:5]
        result = "**Top 5 Produk Termahal:**\n"
        for i, p in enumerate(top5):
            result += f"{i+1}. {p['name']} ({p['store']}) — {fmt_rp(p['price'])}\n"
        return result

    if any(w in q for w in ["murah", "terjangkau", "hemat", "termurah"]):
        top5 = sorted(PRODUCTS.values(), key=lambda p: p["price"])[:5]
        result = "**Top 5 Produk Termurah:**\n"
        for i, p in enumerate(top5):
            result += f"{i+1}. {p['name']} ({p['store']}) — {fmt_rp(p['price'])}\n"
        return result

    if any(w in q for w in ["pendapatan", "revenue", "omzet", "total"]):
        total_qty = sum(p["sp_qty"] for p in PRODUCTS.values())
        total_rev = sum(p["sp_rev"] for p in PRODUCTS.values())
        total_lms = sum(p["last_month_sales"] for p in PRODUCTS.values())
        return (
            f"**Pendapatan YarsiMart (5000 Produk):**\n"
            f"- Total Terjual Shopee: **{total_qty:,} pcs**\n"
            f"- Total Revenue Shopee: **{fmt_rp(total_rev)}**\n"
            f"- Penjualan Bulan Lalu: **{total_lms:,} pcs**\n"
            f"- Total Pencarian DB: **{stats.get('total_searches', 0)}**\n"
            f"- Total Token: **{stats.get('total_tokens', 0)}**"
        )

    if any(w in q for w in ["trending", "populer", "popular", "dicari"]):
        return (
            f"**Data Trending YarsiMart:**\n"
            f"- Total Pencarian DB: {stats.get('total_searches', 0)}\n"
            f"- Total Token Produk: {stats.get('total_tokens', 0)}\n"
            f"- Total Produk: {TOTAL_PRODUCTS}\n"
            f"- Total Kategori: 50\n"
            f"- Total Toko: 100\n"
            f"Lihat tab **Analitik** untuk detail lengkap!"
        )

    # Prediksi
    if any(w in q for w in ["prediksi", "ramalan", "forecast", "perkiraan", "proyeksi", "bulan ini", "bulan depan"]):
        matched = match_products(q, limit=3)
        if matched:
            lines = []
            for r in matched[:3]:
                pred = predict_product(r["pid"])
                if pred:
                    lines.append(
                        f"**{pred['name']}** ({pred['store']}):\n"
                        f"  Bulan lalu: {pred['last_month_views']:,} views, {pred['last_month_sales']:,} terjual\n"
                        f"  Bulan ini: {pred['current_month_views']:,} views (+{pred['growth_pct']}%)\n"
                        f"  Prediksi terjual: **{pred['predicted_sales']:,} unit** ({pred['trend_label']})\n"
                        f"  Est. Revenue: **{fmt_rp(pred['predicted_revenue'])}**"
                    )
            if lines:
                return "**Prediksi Penjualan:**\n\n" + "\n\n".join(lines)
        return "Saya bisa memprediksi penjualan produk. Coba tanyakan: 'Prediksi hijab' atau 'Prediksi kaos'."

    # Toko specific
    if any(w in q for w in ["toko", "store", "seller", "penjual"]):
        for store_name in ["Aero Street", "Fashion House ID", "Hijab Cantik Store", "Distro Bandung", "Urban Outfit Co"]:
            if store_name.lower() in q:
                store_products = [p for p in PRODUCTS.values() if p["store"] == store_name][:5]
                result = f"**Toko: {store_name}** ({len([p for p in PRODUCTS.values() if p['store'] == store_name])} produk):\n"
                for p in store_products:
                    result += f"- {p['name']} ({p['cat']}) — {fmt_rp(p['price'])}\n"
                return result

    # Kategori specific
    for cat in set(p["cat"] for p in PRODUCTS.values()):
        if cat.lower() in q:
            cat_products = sorted([p for p in PRODUCTS.values() if p["cat"] == cat], key=lambda x: x["sp_rev"], reverse=True)[:5]
            total_cat = len([p for p in PRODUCTS.values() if p["cat"] == cat])
            result = f"**Kategori: {cat}** ({total_cat} produk dari {total_cat} toko):\n"
            for p in cat_products[:5]:
                result += f"- {p['name']} ({p['store']}) — {fmt_rp(p['price'])} | Terjual: {p['sp_qty']:,}\n"
            return result

    # Produk spesifik
    matched = match_products(q, limit=1)
    if matched:
        p = matched[0]
        pred = predict_product(p["pid"])
        if pred:
            return (
                f"**{p['name']}** (Toko: {p.get('store','')})\n"
                f"- Kategori: {p['cat']}\n"
                f"- Harga: **{fmt_rp(p['price'])}**\n"
                f"- Terjual di Shopee: {p['sp_qty']:,} pcs\n"
                f"- Revenue: {fmt_rp(p['sp_rev'])}\n"
                f"- Views bulan lalu: {pred['last_month_views']:,}\n"
                f"- Prediksi bulan ini: **{pred['predicted_sales']:,} unit** ({pred['trend_label']})"
            )

    return (
        "Halo! Saya YarsiBot. Saya bisa membantu tentang:\n"
        "- **Prediksi Penjualan** per produk, toko, atau kategori\n"
        "- **Data pencarian** dan tren penjualan\n"
        "- Produk terlaris / termahal / termurah\n"
        "- Pendapatan & revenue 5000 produk Shopee\n"
        "- Info toko dan kategori\n\n"
        "_Tip: Ketik 'Prediksi hijab' atau 'Produk terlaris'!_"
    )

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data         = request.json or {}
    user_message = data.get('message', '').strip()
    history      = data.get('history', [])
    if not user_message:
        return jsonify({"error": "Pesan kosong"}), 400

    try:
        conn           = get_db()
        total_searches = conn.execute("SELECT COUNT(*) as c FROM searches").fetchone()["c"]
        total_tokens   = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
        total_sales    = conn.execute("SELECT COALESCE(SUM(sales),0) as s FROM product_tokens").fetchone()["s"]
        unique_kw      = conn.execute("SELECT COUNT(*) as c FROM keyword_counts").fetchone()["c"]
        top_kw         = conn.execute("SELECT keyword, count FROM keyword_counts ORDER BY count DESC LIMIT 10").fetchall()
        conn.close()
    except Exception:
        total_searches, total_tokens, total_sales, unique_kw = 0, 0, 0, 0
        top_kw = []

    # Compact product context — top 20 products by revenue
    top_products = sorted(PRODUCTS.items(), key=lambda x: x[1]["sp_rev"], reverse=True)[:20]
    product_lines = []
    for pid, p in top_products:
        pred = predict_product(pid)
        if pred:
            product_lines.append(
                f"{p['name']}|Toko:{p['store']}|Kat:{p['cat']}|Harga:{p['price']}|SP_Qty:{p['sp_qty']}|"
                f"LM_Views:{p['last_month_views']}|LM_Sales:{p['last_month_sales']}|CM_Views:{p['current_month_views']}|"
                f"Pred:{pred['predicted_sales']}|Trend:{pred['trend_label']}"
            )

    # Category summary
    cat_summary = {}
    for p in PRODUCTS.values():
        c = p["cat"]
        if c not in cat_summary:
            cat_summary[c] = {"views": 0, "sales": 0, "rev": 0, "count": 0}
        cat_summary[c]["views"] += p["last_month_views"]
        cat_summary[c]["sales"] += p["last_month_sales"]
        cat_summary[c]["rev"] += p["sp_rev"]
        cat_summary[c]["count"] += 1

    top_cats = sorted(cat_summary.items(), key=lambda x: x[1]["rev"], reverse=True)[:15]
    cat_ctx = "; ".join([f"{c}({d['count']} produk,{d['sales']} terjual)" for c, d in top_cats])

    top_kw_str = ", ".join([f"{r['keyword']}({r['count']})" for r in top_kw[:8]]) or "belum ada"

    system_prompt = (
        "Kamu adalah YarsiBot, pakar analitik YarsiMart dengan 5000 produk (50 kategori x 100 toko Shopee). "
        "WAJIB: Gunakan angka dari DATA REAL-TIME. Jangan mengarang angka. "
        "Prediksi bulan ini dihitung: predicted_sales = last_month_sales * (current_month_views / last_month_views). "
        "Jika views bulan ini naik 100%, prediksi penjualan juga naik 100%. "
        "Format jawaban dengan bold pada angka, gunakan emoji. "
        f"STATISTIK TOKO: total_cari={total_searches}, total_tokens={total_tokens}, total_sales_db={total_sales}, unik_kw={unique_kw}, total_produk={TOTAL_PRODUCTS}. "
        f"KATA KUNCI TERPOPULER: {top_kw_str}. "
        f"TOP KATEGORI: {cat_ctx}. "
        f"TOP PRODUK: {' || '.join(product_lines[:10])}. "
        "Tugasmu: Menampilkan prediksi, pencarian, penjualan per produk/toko/kategori."
    )

    contents = []
    for h in history[-8:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.75, "maxOutputTokens": 800, "topP": 0.9},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
    }).encode('utf-8')

    last_error = "Semua model Gemini tidak tersedia."
    for model in GEMINI_MODELS:
        try:
            req = urllib.request.Request(get_gemini_url(model), data=payload, headers=get_gemini_headers(), method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            candidates = result.get("candidates", [])
            if candidates:
                reply = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                reply = reply or "Maaf, AI tidak menghasilkan respons. Coba lagi."
            else:
                reply = "Maaf, saya tidak bisa menjawab itu. Silakan tanya seputar toko YarsiMart."
            return jsonify({"reply": reply, "status": "ok", "model": model})
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return jsonify({"error": "API key tidak valid (403)", "reply": "Konfigurasi API Gemini bermasalah."}), 502
            last_error = f"Model {model}: HTTP {e.code}"
            continue
        except Exception as e:
            last_error = f"Model {model}: {str(e)}"
            continue

    stats_local = {"total_searches": total_searches, "total_tokens": total_tokens, "total_db_sales": total_sales, "unique_keywords": unique_kw}
    fallback = local_fallback_reply(user_message, stats_local)
    fallback_formatted = (
        fallback.replace("**", "<b>", 1).replace("**", "</b>", 1)
        + f"\n\n<i style='font-size:0.72rem;color:#94a3b8'>Mode lokal aktif — Gemini AI sedang penuh ({last_error})</i>"
    )
    return jsonify({"reply": fallback_formatted, "status": "local"})

if __name__ == '__main__':
    init_db()
    print(f"[YarsiMart] {TOTAL_PRODUCTS} Produk | 50 Kategori | 100 Toko — http://127.0.0.1:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')
