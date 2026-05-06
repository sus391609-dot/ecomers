"""
YarsiMart — Shopee Fashion Analytics + Search Engine
Flask Backend with SQLite Database + Gemini AI Chatbot
5000 Produk (50 Kategori x 100 Toko) + Prediksi Real-Time
"""
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from functools import wraps
import sqlite3, os, re, math, json, hashlib, secrets
from datetime import datetime, date
import urllib.request
import urllib.error

from shopee_realtime import (
    shopee_trending_pids,
    shopee_bestseller_pids,
    daily_estimated_sales,
)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get("YARSIMART_SECRET", "yarsimart-dev-secret-change-me")
DB_PATH = os.path.join(os.path.dirname(__file__), 'yarsimart.db')


# ══════════════════════════════════════════════
# AUTHENTICATION
# ══════════════════════════════════════════════
def hash_pw(password: str) -> str:
    return hashlib.sha256(("yarsimart::" + password).encode("utf-8")).hexdigest()


# Default seed accounts (auto-created saat init_db)
SEED_ACCOUNTS = [
    {"username": "admin", "password": "admin123", "role": "admin", "display_name": "Admin YarsiMart"},
    {"username": "user",  "password": "user123",  "role": "user",  "display_name": "Pengguna Demo"},
]


def login_required(role=None):
    """Decorator: pastikan user sudah login.
    role='admin' → hanya admin boleh; role='user' → user atau admin (admin bisa lihat juga)."""
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            uid = session.get("user_id")
            urole = session.get("role")
            if not uid:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "unauthenticated", "message": "Silakan login dulu"}), 401
                return redirect(url_for("login_page"))
            if role == "admin" and urole != "admin":
                if request.path.startswith("/api/"):
                    return jsonify({"error": "forbidden", "message": "Akses admin diperlukan"}), 403
                return redirect(url_for("user_dashboard"))
            return fn(*args, **kwargs)
        return wrapped
    return deco


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return {
        "id": uid,
        "username": session.get("username"),
        "role": session.get("role"),
        "display_name": session.get("display_name") or session.get("username"),
    }


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
            month_views INTEGER DEFAULT 0,
            last_month_key TEXT,
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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            display_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cart_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            user_id INTEGER,
            username TEXT,
            qty INTEGER DEFAULT 1,
            action TEXT DEFAULT 'add',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_cart_log_pid ON cart_log(product_id);
        CREATE INDEX IF NOT EXISTS idx_cart_log_created ON cart_log(created_at);
    """)
    # Migrasi: pastikan kolom month_views & last_month_key ada walau DB lama
    cols = {row[1] for row in conn.execute("PRAGMA table_info(product_tokens)").fetchall()}
    if "month_views" not in cols:
        conn.execute("ALTER TABLE product_tokens ADD COLUMN month_views INTEGER DEFAULT 0")
    if "last_month_key" not in cols:
        conn.execute("ALTER TABLE product_tokens ADD COLUMN last_month_key TEXT")
    for pid in PRODUCTS:
        conn.execute(
            "INSERT OR IGNORE INTO product_tokens (product_id, tokens, search_count, views, cart_adds, sales) VALUES (?, 0, 0, 0, 0, 0)",
            (pid,)
        )
    # Seed default accounts
    for acc in SEED_ACCOUNTS:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
            (acc["username"], hash_pw(acc["password"]), acc["role"], acc["display_name"]),
        )
    conn.commit()
    conn.close()

# ══════════════════════════════════════════════
# SEARCH LOGIC
# ══════════════════════════════════════════════
def match_products(query, limit=None):
    """Cari produk; default kembalikan SEMUA yang cocok (mis. semua hijab).
    Set `limit` jika perlu membatasi (mis. dari chatbot summary)."""
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
    if limit is not None:
        return results[:limit]
    return results

# ══════════════════════════════════════════════
# PREDICTION ENGINE (Real-Time)
# ══════════════════════════════════════════════
def _month_key():
    return date.today().strftime("%Y-%m")


def _get_month_views(pid, conn=None):
    """Ambil month_views untuk produk; reset jika bulan sudah ganti."""
    own_conn = False
    if conn is None:
        conn = get_db()
        own_conn = True
    cur = conn.execute(
        "SELECT month_views, last_month_key, tokens FROM product_tokens WHERE product_id=?",
        (pid,),
    ).fetchone()
    mk = _month_key()
    mv = 0
    if cur:
        if cur["last_month_key"] != mk:
            # Reset counter saat bulan ganti
            conn.execute(
                "UPDATE product_tokens SET month_views=0, last_month_key=? WHERE product_id=?",
                (mk, pid),
            )
            conn.commit()
            mv = 0
        else:
            mv = cur["month_views"] or 0
    if own_conn:
        conn.close()
    return mv


def _bump_month_views(pid, delta=1, conn=None):
    """Tambah month_views (+ reset bila bulan baru). Gunakan saat user search/click/cart."""
    own_conn = False
    if conn is None:
        conn = get_db()
        own_conn = True
    mk = _month_key()
    conn.execute(
        """
        UPDATE product_tokens
        SET month_views = CASE WHEN last_month_key = ? THEN month_views + ? ELSE ? END,
            last_month_key = ?
        WHERE product_id=?
        """,
        (mk, delta, delta, mk, pid),
    )
    if own_conn:
        conn.commit()
        conn.close()


def predict_product(pid, month_views_override=None):
    """
    Prediksi penjualan bulan ini berdasarkan data bulan lalu.
    Rumus: predicted_sales = last_month_sales * (current_month_views / last_month_views)
    Note: current_month_views = baseline_cmv + month_views_dari_aktivitas_user.
    """
    p = PRODUCTS.get(pid)
    if not p:
        return None

    lmv = p.get("last_month_views", 1)
    lms = p.get("last_month_sales", 0)
    lmr = p.get("last_month_revenue", 0)
    cmv_base = p.get("current_month_views", 0)

    if lmv <= 0:
        lmv = 1

    # Tambahkan aktivitas user pada bulan ini (klik, search match, cart) ke views.
    if month_views_override is None:
        try:
            month_views_user = _get_month_views(pid)
        except Exception:
            month_views_user = 0
    else:
        month_views_user = month_views_override
    cmv = cmv_base + month_views_user

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
        "current_month_views_base": cmv_base,
        "current_month_views_user": month_views_user,
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
    # Data keranjang gabungan (Shopee fiktif + real-time user)
    cart_base = _shopee_baseline_cart_count(pid)
    cart_rate_shopee = _shopee_baseline_cart_rate(pid)
    cart_total = cart_base + cart_adds
    p_meta = PRODUCTS.get(pid, {}) or {}
    views_combined = (p_meta.get("last_month_views", 0) or 0) + views
    cart_rate_combined = round(cart_total / max(1, views_combined) * 100, 2)
    return {
        "tokens": tokens, "views": views, "cart_adds": cart_adds, "sales": sales,
        "ctr": round(ctr, 2), "atc_rate": round(atc_rate, 2), "sales_rate": round(sales_rate, 2),
        "label_prediksi": label_prediksi,
        "pred_daily": max(1, round(boosted_monthly / 30)),
        "pred_weekly": max(1, round(boosted_monthly / 4)),
        "pred_monthly": boosted_monthly,
        "est_revenue": boosted_monthly * PRODUCTS.get(pid, {}).get("price", 0),
        "search_boost": round(search_boost, 2),
        # — Cart analytics (Shopee fiktif + real-time tambahan dari user)
        "cart_base_shopee": cart_base,
        "cart_user": cart_adds,
        "cart_total": cart_total,
        "cart_rate_shopee": cart_rate_shopee,
        "cart_rate_combined": cart_rate_combined,
    }

# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════
@app.route('/')
def root():
    """Root: redirect ke dashboard sesuai role; jika belum login → /login."""
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.route('/login')
def login_page():
    """Halaman login (akses tanpa auth)."""
    user = current_user()
    if user:
        # Sudah login → langsung redirect
        return redirect(url_for("admin_dashboard") if user["role"] == "admin" else url_for("user_dashboard"))
    return render_template('login.html')


@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    """Dashboard admin (analitik + prediksi AI + keranjang)."""
    return render_template('index.html', current_user=current_user())


@app.route('/user')
@login_required(role='user')
def user_dashboard():
    """Dashboard user (search, popular, bestseller, cart, buy)."""
    return render_template('user.html', current_user=current_user())


@app.route('/api/me')
def api_me():
    user = current_user()
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user})


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    role_pref = (data.get('role') or '').strip().lower()  # opsional: 'admin' / 'user'
    if not username or not password:
        return jsonify({"error": "Username & password wajib diisi"}), 400
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, role, display_name FROM users WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    if not row or row["password_hash"] != hash_pw(password):
        return jsonify({"error": "Username atau password salah"}), 401
    if role_pref and row["role"] != role_pref:
        # Salah pilih role di form (misal user coba login lewat tombol admin)
        return jsonify({
            "error": f"Akun ini bukan {role_pref}. Silakan pilih login {row['role']}.",
        }), 403
    session.clear()
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["role"] = row["role"]
    session["display_name"] = row["display_name"] or row["username"]
    return jsonify({
        "ok": True,
        "user": {"id": row["id"], "username": row["username"], "role": row["role"],
                 "display_name": row["display_name"] or row["username"]},
        "redirect": url_for("admin_dashboard") if row["role"] == "admin" else url_for("user_dashboard"),
    })


@app.route('/api/register', methods=['POST'])
def api_register():
    """Registrasi user biasa (role='user'). Admin tidak bisa dibuat dari sini."""
    data = request.json or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    display_name = (data.get('display_name') or username).strip()
    if not username or not password:
        return jsonify({"error": "Username & password wajib diisi"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password minimal 4 karakter"}), 400
    if not re.match(r'^[a-z0-9_.\-]{3,32}$', username):
        return jsonify({"error": "Username 3-32 karakter, huruf kecil/angka/_-."}), 400
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, 'user', ?)",
            (username, hash_pw(password), display_name),
        )
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username sudah dipakai, coba yang lain"}), 409
    conn.close()
    session.clear()
    session["user_id"] = new_id
    session["username"] = username
    session["role"] = "user"
    session["display_name"] = display_name
    return jsonify({
        "ok": True,
        "user": {"id": new_id, "username": username, "role": "user", "display_name": display_name},
        "redirect": url_for("user_dashboard"),
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("login_page")})

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
    mk = _month_key()
    for pid in matched_pids:
        conn.execute("""
            INSERT INTO product_tokens (product_id, tokens, search_count, last_searched, month_views, last_month_key)
            VALUES (?, 1, 1, ?, 1, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                tokens = tokens + 1,
                search_count = search_count + 1,
                last_searched = ?,
                month_views = CASE WHEN last_month_key = ? THEN COALESCE(month_views,0) + 1 ELSE 1 END,
                last_month_key = ?
        """, (pid, now, mk, now, mk, mk))
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
    """Top trending real-time dari Shopee (di-filter ke katalog kita).
    Rotasi harian: list ini berganti tiap hari mengikuti pola Shopee + aktivitas user.
    """
    top_n = int(request.args.get('limit', 50))
    conn = get_db()
    rows = conn.execute("SELECT product_id, tokens, views, last_searched FROM product_tokens").fetchall()
    total_tokens = sum((r["tokens"] or 0) for r in rows)
    token_map = {r["product_id"]: ((r["tokens"] or 0), (r["views"] or 0)) for r in rows}
    last_searched_map = {r["product_id"]: r["last_searched"] for r in rows}
    conn.close()

    use_live = request.args.get('use_live', '1') != '0'
    scored = shopee_trending_pids(
        PRODUCTS, token_map, total_tokens,
        top_n=top_n, use_shopee_live=use_live,
    )

    trending = []
    for pid, score, meta in scored:
        p = PRODUCTS.get(pid, {})
        trending.append({
            "pid": pid,
            "name": p.get("name", ""),
            "cat": p.get("cat", ""),
            "store": p.get("store", ""),
            "price": p.get("price", 0),
            "sp_qty": p.get("sp_qty", 0),
            "sp_rev": p.get("sp_rev", 0),
            "tokens": meta["tokens"],
            "search_count": meta["tokens"],
            "last_searched": last_searched_map.get(pid),
            "trend_score": round(score, 2),
            "shopee_rotation": meta["rotation"],
            "shopee_live_boost": meta["shopee_live_boost"],
        })
    return jsonify({
        "trending": trending,
        "day": date.today().isoformat(),
        "source": "shopee_realtime",
        "count": len(trending),
    })

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
    qty = max(1, int(data.get('qty') or 1))
    if not pid or action not in ['view', 'cart', 'buy']:
        return jsonify({"error": "Invalid action"}), 400
    user = current_user() or {}
    uid = user.get("id")
    uname = user.get("username")
    conn = get_db()
    mk = _month_key()
    if action == 'view':
        conn.execute(
            """UPDATE product_tokens SET
                views = views + 1,
                month_views = CASE WHEN last_month_key = ? THEN COALESCE(month_views,0) + 1 ELSE 1 END,
                last_month_key = ?
               WHERE product_id=?""",
            (mk, mk, pid),
        )
    elif action == 'cart':
        # Cart juga dianggap sinyal kuat → month_views +2
        conn.execute(
            """UPDATE product_tokens SET
                cart_adds = cart_adds + ?,
                month_views = CASE WHEN last_month_key = ? THEN COALESCE(month_views,0) + 2 ELSE 2 END,
                last_month_key = ?
               WHERE product_id=?""",
            (qty, mk, mk, pid),
        )
        conn.execute(
            "INSERT INTO cart_log (product_id, user_id, username, qty, action) VALUES (?, ?, ?, ?, 'add')",
            (pid, uid, uname, qty),
        )
    elif action == 'buy':
        conn.execute(
            """UPDATE product_tokens SET
                sales = sales + ?,
                month_views = CASE WHEN last_month_key = ? THEN COALESCE(month_views,0) + 3 ELSE 3 END,
                last_month_key = ?
               WHERE product_id=?""",
            (qty, mk, mk, pid),
        )
        conn.execute(
            "INSERT INTO cart_log (product_id, user_id, username, qty, action) VALUES (?, ?, ?, ?, 'buy')",
            (pid, uid, uname, qty),
        )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"{action} recorded", "qty": qty})

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
    """Produk terlaris real-time dari Shopee — daftar ini juga rotasi harian.
    Prediksi keranjang (cart-adds-rate → "Potensi Tinggi") TETAP DIPERTAHANKAN
    sebagai akselerator estimasi penjualan, sesuai permintaan.
    """
    top_n = int(request.args.get('limit', 10))
    conn = get_db()
    rows = conn.execute("SELECT product_id, tokens, views FROM product_tokens").fetchall()
    total_tokens = sum((r["tokens"] or 0) for r in rows)
    token_map = {r["product_id"]: ((r["tokens"] or 0), (r["views"] or 0)) for r in rows}
    conn.close()

    use_live = request.args.get('use_live', '1') != '0'
    scored = shopee_bestseller_pids(
        PRODUCTS, token_map, total_tokens,
        top_n=top_n, use_shopee_live=use_live,
    )

    bestsellers = []
    for pid, score, meta in scored:
        p = PRODUCTS.get(pid, {})
        pred = predict_from_search(pid, total_tokens)
        daily_est = daily_estimated_sales(p, meta)
        bestsellers.append({
            "pid": pid,
            "name": p.get("name", ""),
            "cat": p.get("cat", ""),
            "store": p.get("store", ""),
            "price": p.get("price", 0),
            "sp_qty": p.get("sp_qty", 0),
            "shopee_daily_est": daily_est,
            "shopee_score": round(score, 2),
            "shopee_rotation": meta["rotation"],
            **pred,
        })
    return jsonify({
        "bestsellers": bestsellers,
        "day": date.today().isoformat(),
        "source": "shopee_realtime",
        "count": len(bestsellers),
    })

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
        DELETE FROM cart_log;
    """)
    conn.commit()
    conn.close()
    return jsonify({"message": "Database reset!"})


# ══════════════════════════════════════════════
# CART ANALYTICS (admin) — Real-time + fallback fiktif Shopee
# ══════════════════════════════════════════════
def _shopee_baseline_cart_rate(pid: str) -> float:
    """Rate keranjang fiktif (deterministik) berbasis hash pid + popularitas Shopee.
    Dipakai sebagai baseline kalau Shopee live tidak bisa di-fetch.
    Range realistis: 1.5% - 12% dari views.
    """
    p = PRODUCTS.get(pid, {})
    h = hashlib.sha256(f"cart:{pid}".encode("utf-8")).hexdigest()
    n = int(h[:8], 16) / float(0xFFFFFFFF)  # 0..1
    # Produk dengan rating tinggi & terjual banyak → cart-rate lebih tinggi
    rating = p.get("rating", 4.5)
    qty = p.get("sp_qty", 0)
    qty_factor = min(1.0, math.log1p(qty) / math.log(1 + 20000))  # 0..1
    base = 1.5 + n * 6.0          # 1.5..7.5
    bonus = qty_factor * 3.0 + (rating - 4.0) * 1.5
    rate = base + max(0, bonus)
    return round(min(12.0, max(0.5, rate)), 2)


def _shopee_baseline_cart_count(pid: str) -> int:
    """Jumlah keranjang fiktif untuk produk: berdasarkan sp_qty dan rate."""
    p = PRODUCTS.get(pid, {})
    qty = p.get("sp_qty", 0)
    rate = _shopee_baseline_cart_rate(pid) / 100.0
    # Asumsi: tiap qty terjual datang dari ~ N keranjang; konversi cart→buy ~25%.
    base = int(qty * (rate * 4))  # cart_count ~ qty * cart_to_buy_ratio
    return max(0, base)


@app.route('/api/cart_stats')
def api_cart_stats():
    """Statistik keranjang real-time (untuk halaman admin "Keranjang").

    Kombinasi:
      - Baseline fiktif Shopee per produk (deterministik).
      - Real-time tambahan dari user lokal (cart_log + product_tokens.cart_adds).
      - Persentase add-to-cart Shopee real-time (live boost) bila tersedia.

    Setiap kali user lokal menambah ke keranjang → angka ini bertambah.
    """
    top_n = int(request.args.get('limit', 20))
    conn = get_db()
    rows = conn.execute(
        "SELECT product_id, cart_adds, views, sales FROM product_tokens"
    ).fetchall()
    total_cart_user = sum((r["cart_adds"] or 0) for r in rows)
    total_views_user = sum((r["views"] or 0) for r in rows)
    total_sales_user = sum((r["sales"] or 0) for r in rows)
    cart_map = {r["product_id"]: (r["cart_adds"] or 0, r["views"] or 0, r["sales"] or 0) for r in rows}
    recent_count_24h = conn.execute(
        "SELECT COUNT(*) as c FROM cart_log WHERE action='add' AND datetime(created_at) >= datetime('now', '-1 day')"
    ).fetchone()["c"]
    recent_count_1h = conn.execute(
        "SELECT COUNT(*) as c FROM cart_log WHERE action='add' AND datetime(created_at) >= datetime('now', '-1 hour')"
    ).fetchone()["c"]
    # Per-product details
    items = []
    total_cart_combined = 0
    total_views_combined = 0
    for pid, p in PRODUCTS.items():
        cart_user, views_user, sales_user = cart_map.get(pid, (0, 0, 0))
        cart_base = _shopee_baseline_cart_count(pid)
        cart_total = cart_base + cart_user
        # Views ~ pakai last_month_views shopee + views user
        views_base = p.get("last_month_views", 0)
        views_total = views_base + views_user
        cart_rate = round(cart_total / max(1, views_total) * 100, 2)
        items.append({
            "pid": pid,
            "name": p.get("name", ""),
            "cat": p.get("cat", ""),
            "store": p.get("store", ""),
            "price": p.get("price", 0),
            "cart_user": cart_user,
            "cart_base": cart_base,
            "cart_total": cart_total,
            "views_total": views_total,
            "cart_rate": cart_rate,
            "sales_user": sales_user,
            "rating": p.get("rating", 4.5),
        })
        total_cart_combined += cart_total
        total_views_combined += views_total
    items.sort(key=lambda x: -x["cart_total"])
    overall_cart_rate = round(total_cart_combined / max(1, total_views_combined) * 100, 2)
    # Shopee category cart-rate fiktif (deterministik per kategori per hari)
    cat_rates = {}
    for cat in {p["cat"] for p in PRODUCTS.values()}:
        h = hashlib.sha256(f"cart_cat:{cat}:{date.today().isoformat()}".encode()).hexdigest()
        n = int(h[:8], 16) / float(0xFFFFFFFF)
        cat_rates[cat] = round(2.5 + n * 6.5, 2)  # 2.5%..9%
    conn.close()
    return jsonify({
        "overall": {
            "total_cart_combined": total_cart_combined,
            "total_views_combined": total_views_combined,
            "overall_cart_rate": overall_cart_rate,
            "total_cart_user": total_cart_user,
            "total_views_user": total_views_user,
            "total_sales_user": total_sales_user,
            "recent_24h": recent_count_24h,
            "recent_1h": recent_count_1h,
            "shopee_avg_cart_rate": round(sum(cat_rates.values()) / max(1, len(cat_rates)), 2),
        },
        "category_cart_rate": [
            {"cat": c, "shopee_cart_rate_pct": r}
            for c, r in sorted(cat_rates.items(), key=lambda x: -x[1])
        ],
        "top_products": items[:top_n],
        "day": date.today().isoformat(),
        "source": "shopee_realtime+local",
    })


@app.route('/api/cart_recent')
def api_cart_recent():
    """Daftar keranjang terbaru (real, dari user). Dipakai admin untuk lihat
    aktivitas keranjang pengguna terkini."""
    limit = int(request.args.get('limit', 30))
    conn = get_db()
    rows = conn.execute(
        """SELECT id, product_id, user_id, username, qty, action, created_at
           FROM cart_log WHERE action='add'
           ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        p = PRODUCTS.get(r["product_id"], {})
        out.append({
            "id": r["id"],
            "pid": r["product_id"],
            "name": p.get("name", "(produk tidak ditemukan)"),
            "cat": p.get("cat", ""),
            "store": p.get("store", ""),
            "price": p.get("price", 0),
            "qty": r["qty"],
            "username": r["username"] or "(tamu)",
            "user_id": r["user_id"],
            "created_at": r["created_at"],
            "action": r["action"],
        })
    return jsonify({"recent": out, "count": len(out)})

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
    """Chatbot endpoint. Tidak pernah membalas error 5xx ke user \u2014
    setiap error apa pun di-handle dengan fallback data cadangan lokal."""
    try:
        return _api_chat_impl()
    except Exception as e:
        # Last-resort safety net: pastikan user selalu dapat respons.
        try:
            data = request.get_json(silent=True) or {}
            msg = data.get('message', '')
        except Exception:
            msg = ''
        try:
            stats_local = {"total_searches": 0, "total_tokens": 0, "total_db_sales": 0, "unique_keywords": 0}
            fb = local_fallback_reply(msg or 'bantu saya', stats_local)
        except Exception:
            fb = "Hai! Saya YarsiBot. Coba ketik 'produk terlaris' atau 'prediksi hijab'."
        fb_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", fb)
        fb_html += (
            f"\n\n<i style='font-size:0.72rem;color:#94a3b8'>"
            f"\u26a0\ufe0f Layanan AI sedang gangguan, mode cadangan dipakai. ({type(e).__name__})"
            f"</i>"
        )
        return jsonify({"reply": fb_html, "status": "local", "error_detail": str(e)})


def _api_chat_impl():
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
                # Tidak ada candidates → jangan langsung error, fallback lokal supaya user dapat jawaban.
                last_error = f"Model {model}: tidak ada candidates dari Gemini"
                continue
            return jsonify({"reply": reply, "status": "ok", "model": model})
        except urllib.error.HTTPError as e:
            # Apa pun status (403, 429, 500, dll) → lanjut ke model berikutnya / fallback lokal.
            try:
                err_body = e.read().decode('utf-8', errors='ignore')[:200]
            except Exception:
                err_body = ""
            last_error = f"Model {model}: HTTP {e.code} {err_body}"
            continue
        except Exception as e:
            last_error = f"Model {model}: {str(e)}"
            continue

    # Semua model gagal → jawab dengan data cadangan lokal (TIDAK PERNAH error ke user)
    stats_local = {
        "total_searches": total_searches,
        "total_tokens": total_tokens,
        "total_db_sales": total_sales,
        "unique_keywords": unique_kw,
    }
    try:
        fallback = local_fallback_reply(user_message, stats_local)
    except Exception as e:
        fallback = (
            "Saat ini layanan AI sedang gangguan, namun toko tetap berjalan normal. "
            f"Silakan coba kata kunci lain. (debug: {e})"
        )
    # Render markdown bold & cantumkan info mode
    fallback_formatted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", fallback)
    fallback_formatted += (
        f"\n\n<i style='font-size:0.72rem;color:#94a3b8'>"
        f"ℹ️ Mode data cadangan aktif — Gemini AI tidak tersedia ({last_error})"
        f"</i>"
    )
    return jsonify({"reply": fallback_formatted, "status": "local", "error_detail": last_error})

# Inisialisasi DB di module load supaya user seed (admin/user) selalu tersedia
# di setiap import — termasuk dijalankan oleh WSGI atau test runner.
try:
    init_db()
except Exception as _e:
    print(f"[YarsiMart] init_db error (akan dicoba ulang saat first request): {_e}")


if __name__ == '__main__':
    print(f"[YarsiMart] {TOTAL_PRODUCTS} Produk | 50 Kategori | 100 Toko — http://127.0.0.1:5000")
    print("[YarsiMart] Login default: admin/admin123 (admin) · user/user123 (user)")
    app.run(debug=True, port=5000, host='0.0.0.0')
