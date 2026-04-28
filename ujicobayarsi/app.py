"""
YarsiMart — Shopee Fashion Analytics + Search Engine
Flask Backend with SQLite Database + Gemini AI Chatbot
"""
from flask import Flask, jsonify, request, render_template
import sqlite3, os, re, math, json
from datetime import datetime
import urllib.request
import urllib.error

app = Flask(__name__, static_folder='static', template_folder='templates')
DB_PATH = os.path.join(os.path.dirname(__file__), 'yarsimart.db')

# ══════════════════════════════════════════════
# GEMINI AI CONFIG
# ══════════════════════════════════════════════
GEMINI_API_KEY = "AIzaSyDJcwPYspL9-VEXvR-myXV9k3o5kHD6XLE"

# Hanya 3 flash model — sesuai yang tersedia di akun ini
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-flash-latest",
]

def get_gemini_url(model):
    # Gunakan query param key= (paling kompatibel)
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

def get_gemini_headers():
    # Tambahkan kedua metode auth: header + query param (lebih andal)
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

def local_fallback_reply(user_message, products, stats):
    """Jawaban lokal berbasis data toko jika Gemini tidak tersedia"""
    q = user_message.lower()
    fmt_rp = lambda n: f"Rp {int(n):,}".replace(",", ".")

    # Produk terlaris by revenue
    if any(w in q for w in ["terlaris", "bestseller", "best seller", "laku"]):
        top3 = sorted(products.values(), key=lambda p: p["sp_rev"], reverse=True)[:3]
        result = "🏆 **Top 3 Produk Terlaris (Revenue Shopee):**\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(top3):
            result += f"{medals[i]} {p['name']} — {fmt_rp(p['sp_rev'])}\n"
        return result

    # Produk termahal
    if any(w in q for w in ["mahal", "harga tinggi", "premium", "termahal"]):
        top3 = sorted(products.values(), key=lambda p: p["price"], reverse=True)[:3]
        result = "💎 **Top 3 Produk Termahal:**\n"
        for i, p in enumerate(top3):
            result += f"• {p['name']} — {fmt_rp(p['price'])}\n"
        return result

    # Produk termurah
    if any(w in q for w in ["murah", "terjangkau", "hemat", "termurah"]):
        top3 = sorted(products.values(), key=lambda p: p["price"])[:3]
        result = "💚 **Top 3 Produk Termurah:**\n"
        for i, p in enumerate(top3):
            result += f"• {p['name']} — {fmt_rp(p['price'])}\n"
        return result

    # Pendapatan / revenue total
    if any(w in q for w in ["pendapatan", "revenue", "omzet", "total"]):
        # Ambil total sales dari DB (jika ada di stats)
        db_sales = stats.get("total_db_sales", 0)
        static_qty = sum(p["sp_qty"] for p in products.values())
        static_rev = sum(p["sp_rev"] for p in products.values())
        
        return (
            f"💰 **Pendapatan YarsiMart:**\n"
            f"• Total Terjual (Shopee): **{static_qty:,} pcs**\n"
            f"• Total Terjual (Real-time DB): **{db_sales:,} pcs**\n"
            f"• Total Revenue (Shopee): **{fmt_rp(static_rev)}**\n"
            f"• Total Pencarian: **{stats.get('total_searches', 0)}**\n"
            f"• Total Token: **{stats.get('total_tokens', 0)}**\n\n"
            f"_Data real-time terus bertambah seiring aktivitas pencarian & checkout._"
        )

    # Trending / populer
    if any(w in q for w in ["trending", "populer", "popular", "dicari", "token"]):
        return (
            f"🔥 **Data Trending YarsiMart:**\n"
            f"• Total Pencarian DB: {stats.get('total_searches', 0)}\n"
            f"• Total Token Produk: {stats.get('total_tokens', 0)}\n"
            f"• Kata Kunci Unik: {stats.get('unique_keywords', 0)}\n"
            f"Lihat tab **🔥 Trending** di dashboard untuk detail lengkap!"
        )

    # Cari nama produk spesifik
    for p in products.values():
        words = p["name"].lower().split()
        if any(w in q for w in words if len(w) > 3):
            return (
                f"🛍️ **{p['name']}**\n"
                f"• Kategori: {p['cat']}\n"
                f"• Harga: **{fmt_rp(p['price'])}**\n"
                f"• Terjual di Shopee: {p['sp_qty']:,} pcs\n"
                f"• Revenue: {fmt_rp(p['sp_rev'])}"
            )

    # Prediksi (Harian, Mingguan, Bulanan)
    if any(w in q for w in ["prediksi", "ramalan", "forecast", "perkiraan", "proyeksi"]):
        # Cari produk yang cocok dengan query
        matched_results = match_products(q)
        if matched_results:
            p = matched_results[0] # Ambil yang paling relevan
            pid = p["pid"]
            total_tokens = stats.get("total_tokens", 0)
            pred = predict_from_search(pid, total_tokens)
            live = stats.get("live_data", {}).get(pid, {})
            
            return (
                f"<div style='border-left:4px solid #ee4d2d;padding-left:10px;margin:5px 0'>"
                f"<b>🔮 Prediksi Penjualan: {p['name']}</b><br>"
                f"• Harian: <b>{pred['pred_daily']} unit</b><br>"
                f"• Mingguan: <b>{pred['pred_weekly']} unit</b><br>"
                f"• Bulanan: <b>{pred['pred_monthly']} unit</b><br>"
                f"• Est. Revenue: <b>{fmt_rp(pred['est_revenue'])}</b><br>"
                f"• Status: <span style='color:#ee4d2d;font-weight:bold'>{pred['label_prediksi']}</span><br><br>"
                f"<small><i>Berdasarkan {live.get('tokens', 0)} pencarian & {live.get('sales', 0)} checkout di database.</i></small>"
                f"</div>"
            )
        else:
            return "Saya bisa memprediksi penjualan produk. Coba tanyakan: 'Prediksi mingguan hijab' atau 'Gimana ramalan kemeja batik?'"

    # Jawaban default
    return (
        "Halo! 👋 Saya YarsiBot. Saya bisa membantu tentang:\n"
        "• 🔮 **Prediksi Penjualan** (Harian/Mingguan/Bulanan)\n"
        "• 🏆 Produk terlaris / termahal / termurah\n"
        "• 💰 Pendapatan & revenue Shopee\n"
        "• 🔥 Data trending & pencarian\n"
        "• 🛍️ Info produk spesifik\n\n"
        "_💡 Tip: Ketik 'Prediksi hijab' atau 'Produk terlaris'!_"
    )

# ══════════════════════════════════════════════
# PRODUCT CATALOG (Shopee Only)
# ══════════════════════════════════════════════
PRODUCTS = {
    "P001": {"name":"Kemeja Batik Premium Pria","cat":"Kemeja","price":179173,"sp_qty":474,"sp_rev":87784774},
    "P002": {"name":"Kaos Polos Cotton Combed 30s","cat":"Kaos","price":72094,"sp_qty":849,"sp_rev":63591940},
    "P003": {"name":"Celana Chino Slim Fit Pria","cat":"Celana","price":221530,"sp_qty":380,"sp_rev":79957252},
    "P004": {"name":"Dress Casual Wanita Korea","cat":"Dress","price":146037,"sp_qty":366,"sp_rev":56847305},
    "P005": {"name":"Jaket Bomber Oversize Pria","cat":"Jaket","price":307395,"sp_qty":66,"sp_rev":21111474},
    "P006": {"name":"Hijab Segi Empat Voal Premium","cat":"Hijab","price":65049,"sp_qty":1178,"sp_rev":76632143},
    "P007": {"name":"Rok Midi Floral Wanita","cat":"Rok","price":132728,"sp_qty":167,"sp_rev":21754879},
    "P008": {"name":"Kemeja Flanel Kotak Pria","cat":"Kemeja","price":145912,"sp_qty":518,"sp_rev":75102131},
    "P009": {"name":"Legging Premium Anti Tembus","cat":"Celana","price":88682,"sp_qty":727,"sp_rev":61669701},
    "P010": {"name":"Sweater Rajut Oversize Kekinian","cat":"Sweater","price":181527,"sp_qty":128,"sp_rev":25148662},
    "P011": {"name":"Baju Koko Pria Modern Elzatta","cat":"Koko","price":161310,"sp_qty":673,"sp_rev":111394816},
    "P012": {"name":"Celana Jogger Sport Unisex","cat":"Celana","price":109453,"sp_qty":466,"sp_rev":53551443},
    "P013": {"name":"Blouse Chiffon Kerja Wanita","cat":"Blouse","price":113158,"sp_qty":409,"sp_rev":48779501},
    "P014": {"name":"Kaos Graphic Streetwear Viral","cat":"Kaos","price":89636,"sp_qty":420,"sp_rev":39863237},
    "P015": {"name":"Gamis Syari Rabbani Terbaru","cat":"Gamis","price":286824,"sp_qty":483,"sp_rev":132720951},
    "P016": {"name":"Hoodie Oversize Polos Unisex","cat":"Hoodie","price":180628,"sp_qty":539,"sp_rev":94278378},
    "P017": {"name":"Jeans Wide Leg Wanita Tren","cat":"Celana","price":226089,"sp_qty":303,"sp_rev":69750849},
    "P018": {"name":"Mukena Cantik Motif Bunga","cat":"Mukena","price":146056,"sp_qty":600,"sp_rev":87023230},
    "P019": {"name":"Jaket Denim Pria Vintage","cat":"Jaket","price":299432,"sp_qty":105,"sp_rev":29890164},
    "P020": {"name":"Crop Top Wanita Knit Trendy","cat":"Atasan","price":89964,"sp_qty":512,"sp_rev":45465950},
    "P021": {"name":"Kemeja Oxford Putih Pria","cat":"Kemeja","price":149095,"sp_qty":495,"sp_rev":77021300},
    "P022": {"name":"Celana Kulot Linen Wanita","cat":"Celana","price":131019,"sp_qty":442,"sp_rev":59744367},
    "P023": {"name":"Cardigan Rajut Panjang Wanita","cat":"Outer","price":174666,"sp_qty":191,"sp_rev":35512194},
    "P024": {"name":"Bra Sport High Impact Wanita","cat":"Pakaian Dalam","price":72669,"sp_qty":776,"sp_rev":58379615},
    "P025": {"name":"Batik Couple Kondangan Premium","cat":"Batik","price":343639,"sp_qty":370,"sp_rev":129516047},
}

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
    try:
        conn.execute("ALTER TABLE product_tokens ADD COLUMN views INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE product_tokens ADD COLUMN cart_adds INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE product_tokens ADD COLUMN sales INTEGER DEFAULT 0")
    except:
        pass
    for pid in PRODUCTS:
        conn.execute(
            "INSERT OR IGNORE INTO product_tokens (product_id, tokens, search_count) VALUES (?, 0, 0)",
            (pid,)
        )
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
# SEARCH LOGIC
# ══════════════════════════════════════════════
def match_products(query):
    """Find products matching query by name or category"""
    q = query.lower().strip()
    if not q:
        return []
    results = []
    for pid, p in PRODUCTS.items():
        name_lower = p["name"].lower()
        cat_lower = p["cat"].lower()
        score = 0
        if q in name_lower:
            score = 100
        elif q in cat_lower:
            score = 80
        else:
            words = q.split()
            matched = sum(1 for w in words if w in name_lower or w in cat_lower)
            if matched > 0:
                score = int(60 * matched / len(words))
        if score > 0:
            results.append({"pid": pid, "score": score, **p})
    results.sort(key=lambda x: -x["score"])
    return results

def predict_from_search(pid, total_tokens):
    """Predict sales based on search frequency, CTR, and conversions"""
    conn = get_db()
    row = conn.execute("SELECT tokens, views, cart_adds, sales FROM product_tokens WHERE product_id=?", (pid,)).fetchone()
    conn.close()

    tokens    = row["tokens"]    if row else 0
    views     = row["views"]     if row else 0
    cart_adds = row["cart_adds"] if row else 0
    sales     = row["sales"]     if row else 0

    ctr       = (views     / tokens * 100) if tokens > 0 else 0
    atc_rate  = (cart_adds / tokens * 100) if tokens > 0 else 0
    sales_rate= (sales     / tokens * 100) if tokens > 0 else 0

    label_prediksi = 'Normal'
    if atc_rate > 2.0 and sales_rate < 1.0:
        label_prediksi = 'Potensi Tinggi'

    p = PRODUCTS.get(pid, {})
    base_monthly = p.get("sp_qty", 0) / 13

    search_boost = 1.0
    if total_tokens > 0 and tokens > 0:
        share = tokens / total_tokens
        search_boost = 1.0 + (share * 5)
        if ctr > 5.0:      search_boost += 0.5
        if atc_rate > 2.0: search_boost += 1.0

    pred_daily   = max(1, round(base_monthly / 30 * search_boost))
    pred_weekly  = max(1, round(base_monthly / 4  * search_boost))
    pred_monthly = max(1, round(base_monthly       * search_boost))
    est_revenue  = pred_monthly * p.get("price", 0)

    return {
        "tokens": tokens, "views": views, "cart_adds": cart_adds, "sales": sales,
        "ctr": round(ctr, 2), "atc_rate": round(atc_rate, 2), "sales_rate": round(sales_rate, 2),
        "label_prediksi": label_prediksi,
        "pred_daily": pred_daily, "pred_weekly": pred_weekly, "pred_monthly": pred_monthly,
        "est_revenue": est_revenue, "search_boost": round(search_boost, 2),
    }

# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search products + record to database + update tokens"""
    data  = request.json or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"error": "Query kosong"}), 400

    results      = match_products(query)
    matched_pids = [r["pid"] for r in results]

    conn = get_db()
    now  = datetime.now().isoformat()

    cur = conn.execute(
        "INSERT INTO searches (query, result_count, created_at) VALUES (?, ?, ?)",
        (query, len(results), now)
    )
    search_id = cur.lastrowid

    for pid in matched_pids:
        conn.execute("""
            INSERT INTO product_tokens (product_id, tokens, search_count, last_searched)
            VALUES (?, 1, 1, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                tokens = tokens + 1,
                search_count = search_count + 1,
                last_searched = ?
        """, (pid, now, now))
        conn.execute(
            "INSERT INTO search_product_log (search_id, product_id, created_at) VALUES (?, ?, ?)",
            (search_id, pid, now)
        )

    words = re.findall(r'[a-zA-Z\u00C0-\u024F]+', query.lower())
    for word in words:
        if len(word) > 1:
            conn.execute("""
                INSERT INTO keyword_counts (keyword, count, last_searched)
                VALUES (?, 1, ?)
                ON CONFLICT(keyword) DO UPDATE SET
                    count = count + 1,
                    last_searched = ?
            """, (word, now, now))

    conn.commit()
    conn.close()

    result_data = [
        {
            "pid": r["pid"], "name": r["name"], "cat": r["cat"],
            "price": r["price"], "sp_qty": r["sp_qty"], "sp_rev": r["sp_rev"], "score": r["score"],
        }
        for r in results
    ]

    return jsonify({
        "query": query,
        "count": len(results),
        "results": result_data,
        "search_id": search_id,
        "message": f"✅ Pencarian '{query}' tercatat ke database. {len(matched_pids)} produk mendapat token.",
    })

@app.route('/api/trending')
def api_trending():
    """Get top 25 trending products by token count"""
    conn = get_db()
    rows = conn.execute(
        "SELECT product_id, tokens, search_count, last_searched FROM product_tokens ORDER BY tokens DESC LIMIT 25"
    ).fetchall()
    conn.close()

    trending = []
    for r in rows:
        pid = r["product_id"]
        p   = PRODUCTS.get(pid, {})
        trending.append({
            "pid": pid, "name": p.get("name",""), "cat": p.get("cat",""),
            "price": p.get("price",0), "sp_qty": p.get("sp_qty",0), "sp_rev": p.get("sp_rev",0),
            "tokens": r["tokens"], "search_count": r["search_count"], "last_searched": r["last_searched"],
        })
    return jsonify({"trending": trending})

@app.route('/api/keywords')
def api_keywords():
    """Get top searched keywords"""
    conn = get_db()
    rows = conn.execute(
        "SELECT keyword, count, last_searched FROM keyword_counts ORDER BY count DESC LIMIT 15"
    ).fetchall()
    conn.close()
    return jsonify({"keywords": [{"keyword": r["keyword"], "count": r["count"], "last": r["last_searched"]} for r in rows]})

@app.route('/api/action', methods=['POST'])
def api_action():
    data   = request.json or {}
    pid    = data.get('pid')
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
    """Get overall search statistics"""
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
        "recent_searches": [{"query": r["query"], "time": r["created_at"]} for r in recent],
    })

@app.route('/api/bestsellers')
def api_bestsellers():
    """Get bestseller predictions based on search data"""
    conn = get_db()
    total_tokens = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
    rows = conn.execute(
        "SELECT product_id, tokens FROM product_tokens WHERE tokens > 0 ORDER BY tokens DESC LIMIT 10"
    ).fetchall()
    conn.close()

    bestsellers = []
    for r in rows:
        pid  = r["product_id"]
        pred = predict_from_search(pid, total_tokens)
        p    = PRODUCTS.get(pid, {})
        bestsellers.append({
            "pid": pid, "name": p.get("name",""), "cat": p.get("cat",""),
            "price": p.get("price",0), "sp_qty": p.get("sp_qty",0), **pred,
        })
    return jsonify({"bestsellers": bestsellers})

@app.route('/api/predict/<pid>')
def api_predict(pid):
    """Get prediction for a single product"""
    if pid not in PRODUCTS:
        return jsonify({"error": "Product not found"}), 404
    conn = get_db()
    total_tokens = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
    conn.close()
    pred = predict_from_search(pid, total_tokens)
    p    = PRODUCTS[pid]
    return jsonify({"pid": pid, "name": p["name"], "cat": p["cat"], "price": p["price"], **pred})

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Reset all search data"""
    conn = get_db()
    conn.executescript("""
        DELETE FROM searches;
        DELETE FROM search_product_log;
        UPDATE product_tokens SET tokens=0, search_count=0, last_searched=NULL;
        DELETE FROM keyword_counts;
    """)
    conn.commit()
    conn.close()
    return jsonify({"message": "Database reset!"})

# ══════════════════════════════════════════════
# GEMINI AI CHATBOT
# ══════════════════════════════════════════════
@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Gemini AI Chatbot — hanya menjawab topik e-commerce YarsiMart"""
    data         = request.json or {}
    user_message = data.get('message', '').strip()
    history      = data.get('history', [])   # [{role, text}, ...]

    if not user_message:
        return jsonify({"error": "Pesan kosong"}), 400

    # ── Ambil data real-time dari SQLite ──
    try:
        conn           = get_db()
        total_searches = conn.execute("SELECT COUNT(*) as c FROM searches").fetchone()["c"]
        total_tokens   = conn.execute("SELECT COALESCE(SUM(tokens),0) as s FROM product_tokens").fetchone()["s"]
        total_sales    = conn.execute("SELECT COALESCE(SUM(sales),0) as s FROM product_tokens").fetchone()["s"]
        unique_kw      = conn.execute("SELECT COUNT(*) as c FROM keyword_counts").fetchone()["c"]
        top_kw         = conn.execute(
            "SELECT keyword, count FROM keyword_counts ORDER BY count DESC LIMIT 10"
        ).fetchall()
        all_db_data    = conn.execute(
            "SELECT product_id, tokens, views, cart_adds, sales FROM product_tokens"
        ).fetchall()
        db_map = {r["product_id"]: dict(r) for r in all_db_data}
        conn.close()
    except Exception:
        total_searches, total_tokens, total_sales, unique_kw = 0, 0, 0, 0
        top_kw, db_map = [], {}

    # ── Ringkasan katalog produk + Prediksi + Sales DB (ringkas) ──
    product_lines = []
    for pid, p in PRODUCTS.items():
        live = db_map.get(pid, {"tokens":0, "views":0, "cart_adds":0, "sales":0})
        pred = predict_from_search(pid, total_tokens)
        product_lines.append(
            f"{p['name']} | Harga:{p['price']} | Shopee:{p['sp_qty']} | DB_Sales:{live['sales']} | "
            f"Tokens:{live['tokens']} | Pred_Mgu:{pred['pred_weekly']} | Status:{pred['label_prediksi']}"
        )

    top_kw_str  = ", ".join([f"{r['keyword']}({r['count']})" for r in top_kw[:8]]) or "belum ada"
    product_ctx = " || ".join(product_lines)
    # Filter top products for summary (max 5)
    top_products = sorted(db_map.values(), key=lambda x: x["tokens"], reverse=True)[:5]
    token_lines = []
    for r in top_products:
        p = PRODUCTS.get(r["product_id"], {})
        if p:
            token_lines.append(
                f"{p['name']}: {r['tokens']} cari, {r['sales']} terjual"
            )
    token_ctx = "; ".join(token_lines) if token_lines else "Belum ada data pencarian."

    # ── System Prompt (Sangat Eksplisit) ──
    system_prompt = (
        "Kamu adalah YarsiBot, pakar analitik YarsiMart. "
        "WAJIB: Gunakan angka dari DATA REAL-TIME di bawah untuk menjawab. Jangan mengarang angka. "
        "Jika ditanya prediksi, sebutkan angka 'Pred_Mgu' atau 'Pred_Bln' yang ada di daftar produk. "
        "Format jawaban dengan bold pada angka agar jelas. Gunakan emoji. "
        f"STATISTIK TOKO: total_cari={total_searches}, total_tokens={total_tokens}, total_sales_db={total_sales}, unik_kw={unique_kw}. "
        f"KATA KUNCI TERPOPULER: {top_kw_str}. "
        f"PRODUK & PREDIKSI (DATA ASLI): {product_ctx}. "
        "Tugasmu: Menampilkan hasil prediksi dan penjualan secara detail jika ditanya."
    )

    # ── Bangun konten percakapan (multi-turn, max 8 pesan terakhir) ──
    contents = []
    for h in history[-8:]:
        role = "user" if h.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": h.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.75,
            "maxOutputTokens": 600,
            "topP": 0.9,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
    }).encode('utf-8')

    # ── Kirim ke Gemini — fallback otomatis ke model berikutnya ──
    last_error = "Semua model Gemini tidak tersedia."
    for model in GEMINI_MODELS:
        try:
            req = urllib.request.Request(
                get_gemini_url(model),
                data=payload,
                headers=get_gemini_headers(),
                method="POST"
            )
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
            code = e.code
            if code == 403:
                # API key tidak valid — hentikan
                return jsonify({
                    "error": "API key tidak valid (403)",
                    "reply": "⚠️ Konfigurasi API Gemini bermasalah."
                }), 502
            # 429 (rate limit), 404 (model tidak tersedia), 400, 5xx → coba berikutnya
            last_error = f"Model {model}: HTTP {code}"
            continue
        except Exception as e:
            last_error = f"Model {model}: {str(e)}"
            continue

    # Semua Gemini model gagal — gunakan fallback lokal
    stats_local = {
        "total_searches": total_searches,
        "total_tokens":   total_tokens,
        "total_db_sales": total_sales,
        "unique_keywords": unique_kw,
        "live_data":      db_map,
    }
    fallback = local_fallback_reply(user_message, PRODUCTS, stats_local)
    fallback_formatted = (
        fallback
        .replace("**", "<b>", 1).replace("**", "</b>", 1)  # first bold pair
        + f"\n\n<i style='font-size:0.72rem;color:#94a3b8'>⚡ Mode lokal aktif — Gemini AI sedang penuh ({last_error})</i>"
    )
    return jsonify({"reply": fallback_formatted, "status": "local"})

# ══════════════════════════════════════════════
if __name__ == '__main__':
    init_db()
    print("[YarsiMart] Shopee Analytics + Gemini AI -- http://127.0.0.1:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')
