// YarsiMart User Dashboard — Belanja Live Shopee
// Tugas utama:
// - Profile pojok kanan atas (display_name, username, role, logout)
// - Search → POST /api/search (tercatat ke analitik admin)
// - Klik produk = view → POST /api/action (action='view')
// - Add to cart → POST /api/action (action='cart') + simpan di session
// - Buy → konfirmasi modal → POST /api/action (action='buy')
// - Trending & Bestseller real-time dari Shopee
const fmtRp = (n) => "Rp " + Math.round(n).toLocaleString("id-ID");
const fmtN = (n) => Math.round(n).toLocaleString("id-ID");

// ──────────────────────────────────────────────
// Clock
function updateClock() {
  const n = new Date(),
    D = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"],
    M = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"];
  const ld = document.getElementById("live-date");
  const lt = document.getElementById("live-time");
  if (ld) ld.textContent = D[n.getDay()] + ", " + n.getDate() + " " + M[n.getMonth()] + " " + n.getFullYear();
  if (lt) lt.textContent = n.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
setInterval(updateClock, 1000);
updateClock();

// ──────────────────────────────────────────────
// API helpers
async function apiPost(url, data) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
  return r.json();
}
async function apiGet(url) {
  const r = await fetch(url);
  return r.json();
}

// ──────────────────────────────────────────────
// Toast
let toastTimer = null;
function toast(msg, kind = "") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = "toast show " + kind;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2200);
}

// ──────────────────────────────────────────────
// Nav
function showPage(name, btn) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById("page-" + name).classList.add("active");
  if (btn) {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  }
  if (name === "products") renderAllProducts();
}

function scrollToSection(id) {
  closeProfileMenu();
  showPage("home", document.querySelectorAll("nav button")[0]);
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 50);
}

// ──────────────────────────────────────────────
// Profile dropdown
let CURRENT_USER = null;
function toggleProfileMenu(e) {
  if (e) e.stopPropagation();
  document.getElementById("profile-menu").classList.toggle("open");
}
function closeProfileMenu() {
  const m = document.getElementById("profile-menu");
  if (m) m.classList.remove("open");
}
document.addEventListener("click", (e) => {
  const w = document.getElementById("profile-wrap");
  if (w && !w.contains(e.target)) closeProfileMenu();
});

async function loadProfile() {
  try {
    const r = await apiGet("/api/me");
    if (!r.authenticated) {
      window.location.href = "/login";
      return;
    }
    CURRENT_USER = r.user;
    const initials = (r.user.display_name || r.user.username || "U").trim()[0].toUpperCase();
    document.getElementById("profile-avatar").textContent = initials;
    document.getElementById("profile-name").textContent = r.user.display_name || r.user.username;
    document.getElementById("profile-role").textContent = (r.user.role || "user").toUpperCase();
    document.getElementById("pm-display").textContent = r.user.display_name || r.user.username;
    document.getElementById("pm-username").textContent = "@" + r.user.username;
  } catch (e) {
    console.error("loadProfile error:", e);
  }
}

async function doLogout() {
  try {
    const r = await apiPost("/api/logout", {});
    window.location.href = r.redirect || "/login";
  } catch (e) {
    window.location.href = "/login";
  }
}

// ──────────────────────────────────────────────
// Search
function showSuggestions() {
  const q = document.getElementById("search-input").value.trim().toLowerCase();
  const box = document.getElementById("search-suggestions");
  if (q.length < 2) {
    box.classList.remove("show");
    return;
  }
  const matches = [];
  for (const [pid, p] of Object.entries(PRODUCTS)) {
    if (
      p.n.toLowerCase().includes(q) ||
      p.c.toLowerCase().includes(q) ||
      p.s.toLowerCase().includes(q)
    )
      matches.push({ pid, p });
    if (matches.length >= 8) break;
  }
  if (!matches.length) {
    box.classList.remove("show");
    return;
  }
  box.innerHTML = matches
    .map(
      ({ pid, p }) =>
        `<div class="sug-item" onclick="document.getElementById('search-input').value='${p.n.replace(/'/g, "\\'")}';performSearch()">
          <div class="sug-icon">${ICONS[p.c] || "🛍️"}</div>
          <div class="sug-info">
            <div class="sug-name">${p.n}</div>
            <div class="sug-meta">${p.c} · ${p.s} · ${fmtRp(p.pr)}</div>
          </div>
        </div>`
    )
    .join("");
  box.classList.add("show");
}

async function performSearch() {
  const input = document.getElementById("search-input");
  const q = input.value.trim();
  if (!q) return;
  document.getElementById("search-suggestions").classList.remove("show");
  const res = await apiPost("/api/search", { query: q });
  document.getElementById("search-query-display").textContent = q;
  document.getElementById("search-results").style.display = "block";
  document.getElementById("search-result-info").innerHTML = `
    <div class="db-status" style="margin-bottom:1rem">
      <div class="db-indicator">✅ Pencarian "${q}" tercatat ke analitik admin</div>
      <div>Search ID: #${res.search_id || "-"} · ${res.count || 0} produk ditemukan</div>
    </div>`;
  if (res.results && res.results.length) {
    document.getElementById("search-results-grid").innerHTML = res.results
      .slice(0, 60)
      .map((r) => productCard(r.pid))
      .join("");
  } else {
    document.getElementById("search-results-grid").innerHTML =
      '<div class="empty-keywords">Tidak ada produk ditemukan untuk "' + q + '"</div>';
  }
  input.value = "";
  refreshDashboard();
  // Scroll ke hasil pencarian
  document.getElementById("search-results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeSearchResults() {
  document.getElementById("search-results").style.display = "none";
}

// ──────────────────────────────────────────────
// Cards
function productCard(pid) {
  const p = PRODUCTS[pid];
  if (!p) return "";
  return `<div class="product-card">
    <div class="product-img" onclick="viewProduct('${pid}')" style="cursor:pointer">
      ${ICONS[p.c] || "🛍️"}
    </div>
    <div class="product-info">
      <div class="product-name" onclick="viewProduct('${pid}')" style="cursor:pointer">${p.n}</div>
      <div class="product-cat">${p.c} · ${p.s}</div>
      <div class="product-price">${fmtRp(p.pr)}</div>
      <div class="product-sold">Terjual: ${fmtN(p.sp_qty)} · ⭐${p.rt}</div>
      <div class="btn-group">
        <button class="btn-sm btn-cart" onclick="addToCart('${pid}')">🛒 Keranjang</button>
        <button class="btn-sm btn-buy" onclick="openBuyModal('${pid}')">💳 Beli</button>
      </div>
    </div>
  </div>`;
}

// ──────────────────────────────────────────────
// Trending / Bestseller
function renderTrending(trending) {
  const el = document.getElementById("trending-grid");
  const ranks = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"];
  if (!trending || !trending.length) {
    el.innerHTML = '<div class="empty-keywords" style="grid-column:1/-1">Memuat data trending dari Shopee...</div>';
    return;
  }
  el.innerHTML = trending
    .slice(0, 10)
    .map((t, i) => {
      const p = PRODUCTS[t.pid];
      if (!p) return "";
      const liveBadge =
        (t.shopee_live_boost || 0) > 0
          ? '<span style="font-size:.55rem;color:#16a34a;font-weight:700">🔴 LIVE Shopee</span>'
          : "";
      return `<div class="trend-card" onclick="viewProduct('${t.pid}')">
        <div class="trend-rank">${ranks[i] || "#" + (i + 1)}</div>
        <div class="trend-icon">${ICONS[p.c] || "🛍️"}</div>
        <div class="trend-name">${p.n}</div>
        <div class="trend-fire">${fmtRp(p.pr)}</div>
        <div class="trend-tokens">${t.tokens ? "🎯 " + t.tokens + " token" : "📊 Skor " + (t.trend_score || 0)}</div>
        ${liveBadge}
        <div style="font-size:.6rem;color:var(--text3);margin-top:.2rem">${p.s}</div>
        <div class="btn-group" style="margin-top:.45rem;justify-content:center">
          <button class="btn-sm btn-cart" onclick="event.stopPropagation();addToCart('${t.pid}')">🛒</button>
          <button class="btn-sm btn-buy" onclick="event.stopPropagation();openBuyModal('${t.pid}')">💳 Beli</button>
        </div>
      </div>`;
    })
    .join("");
}

function renderBestsellers(bestsellers) {
  const el = document.getElementById("bestseller-grid");
  if (!bestsellers || !bestsellers.length) {
    el.innerHTML = '<div class="empty-keywords">Memuat data terlaris dari Shopee...</div>';
    return;
  }
  el.innerHTML = bestsellers
    .map((b) => {
      const p = PRODUCTS[b.pid];
      if (!p) return "";
      const dailyShopee = b.shopee_daily_est ? `Shopee ~<b>${fmtN(b.shopee_daily_est)}</b>/hari` : "";
      return `<div class="bs-card">
        <div class="bs-icon" onclick="viewProduct('${b.pid}')" style="cursor:pointer">${ICONS[p.c] || "🛍️"}</div>
        <div class="bs-info">
          <div class="bs-name" onclick="viewProduct('${b.pid}')" style="cursor:pointer">${b.name}</div>
          <div class="bs-cat">${b.cat} · ${b.store || p.s} · ${dailyShopee}</div>
          <div class="bs-stats">
            <div class="bs-stat">⭐ <b>${p.rt}</b></div>
            <div class="bs-stat">📦 Terjual <b>${fmtN(p.sp_qty)}</b></div>
            <div class="bs-stat">💰 <b>${fmtRp(p.pr)}</b></div>
          </div>
          <div class="btn-group" style="margin-top:.55rem">
            <button class="btn-sm btn-cart" onclick="addToCart('${b.pid}')">🛒 Keranjang</button>
            <button class="btn-sm btn-buy" onclick="openBuyModal('${b.pid}')">💳 Beli</button>
          </div>
        </div>
      </div>`;
    })
    .join("");
}

// ──────────────────────────────────────────────
// Dashboard refresh (live data)
async function refreshDashboard() {
  try {
    const [stats, trend, best, cartStats] = await Promise.all([
      apiGet("/api/stats"),
      apiGet("/api/trending?limit=20"),
      apiGet("/api/bestsellers?limit=10"),
      apiGet("/api/cart_stats?limit=1"),
    ]);
    document.getElementById("stat-products").textContent = fmtN(stats.total_products || 5000);
    document.getElementById("stat-searches").textContent = fmtN(stats.total_searches || 0);
    renderTrending(trend.trending);
    renderBestsellers(best.bestsellers);
    const tt = document.getElementById("trending-tag");
    if (tt && trend.day) tt.textContent = `🟢 Real-time Shopee · ${trend.day} · ${trend.count || 0} produk`;
    const bt = document.getElementById("bestseller-tag");
    if (bt && best.day) bt.textContent = `🟢 Real-time Shopee · ${best.day}`;
    document.getElementById("strip-day").textContent = trend.day || "—";
    document.getElementById("strip-cart24").textContent = fmtN(cartStats?.overall?.recent_24h || 0);
    document.getElementById("strip-trend").textContent = fmtN(trend.count || 0);
  } catch (e) {
    console.error("refreshDashboard error:", e);
  }
}

// ──────────────────────────────────────────────
// View / Cart / Buy
async function viewProduct(pid) {
  // Catat klik sebagai 'view' ke admin analytics
  try {
    await apiPost("/api/action", { pid, action: "view" });
  } catch (e) {}
  const p = PRODUCTS[pid];
  if (!p) return;
  toast(`Melihat: ${p.n} — ${fmtRp(p.pr)}`);
}

let cart = []; // [{pid, qty, n, pr, s}]
function loadCart() {
  try {
    const raw = localStorage.getItem("yarsimart_cart");
    cart = raw ? JSON.parse(raw) : [];
  } catch (e) {
    cart = [];
  }
}
function persistCart() {
  try {
    localStorage.setItem("yarsimart_cart", JSON.stringify(cart));
  } catch (e) {}
}

function toggleCart() {
  closeProfileMenu();
  document.getElementById("cart-sidebar").classList.toggle("open");
}

async function addToCart(pid) {
  const p = PRODUCTS[pid];
  if (!p) return;
  const item = cart.find((x) => x.pid === pid);
  if (item) item.qty++;
  else cart.push({ pid, qty: 1, n: p.n, pr: p.pr, s: p.s, c: p.c });
  persistCart();
  renderCart();
  // Catat ke admin analytics secara real-time
  try {
    const r = await apiPost("/api/action", { pid, action: "cart", qty: 1 });
    if (r && r.success) toast(`Ditambah ke keranjang: ${p.n}`, "success");
  } catch (e) {
    toast("Gagal sinkron ke server, tapi tersimpan lokal", "error");
  }
}

function removeFromCart(idx) {
  cart.splice(idx, 1);
  persistCart();
  renderCart();
}

function changeQty(idx, delta) {
  if (!cart[idx]) return;
  cart[idx].qty = Math.max(1, cart[idx].qty + delta);
  persistCart();
  renderCart();
}

function renderCart() {
  const el = document.getElementById("cart-items");
  const totalQty = cart.reduce((s, c) => s + c.qty, 0);
  const totalRp = cart.reduce((s, c) => s + c.pr * c.qty, 0);
  document.getElementById("cart-total").textContent = fmtRp(totalRp);
  document.getElementById("stat-cart-mine").textContent = fmtN(totalQty);
  document.getElementById("pm-cart-count").textContent = totalQty;
  const badge = document.getElementById("cart-badge");
  badge.textContent = totalQty;
  badge.style.display = totalQty > 0 ? "block" : "none";
  if (!cart.length) {
    el.innerHTML =
      "<p style='text-align:center;color:#999;margin-top:2rem'>Keranjang kosong.<br/>Tambahkan produk dulu yuk!</p>";
    return;
  }
  el.innerHTML = cart
    .map(
      (c, i) =>
        `<div class="cart-item" style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid #eee;padding:.7rem 0">
          <div style="flex:1;min-width:0;padding-right:.5rem">
            <div style="font-weight:600;font-size:.85rem;margin-bottom:3px">${c.n}</div>
            <div style="font-size:.7rem;color:#888">${c.s}</div>
            <div style="font-size:.78rem;color:#444;margin-top:3px">${fmtRp(c.pr)}</div>
            <div style="display:flex;align-items:center;gap:.35rem;margin-top:.4rem">
              <button onclick="changeQty(${i},-1)" style="border:1px solid #ddd;background:#fff;width:24px;height:24px;border-radius:5px;cursor:pointer">−</button>
              <span style="font-weight:600;min-width:18px;text-align:center">${c.qty}</span>
              <button onclick="changeQty(${i},1)" style="border:1px solid #ddd;background:#fff;width:24px;height:24px;border-radius:5px;cursor:pointer">+</button>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:.4rem">
            <button onclick="removeFromCart(${i})" style="border:none;background:none;color:#dc2626;cursor:pointer;font-size:1.05rem">🗑️</button>
            <button onclick="openBuyModal('${c.pid}', ${c.qty})" class="btn-sm btn-buy" style="padding:.3rem .55rem;font-size:.7rem">Beli</button>
          </div>
        </div>`
    )
    .join("");
}

// ──────────────────────────────────────────────
// Buy modal (single or full cart)
let pendingBuy = null; // {pid, qty} OR {all:true}

function openBuyModal(pid, qty) {
  const p = PRODUCTS[pid];
  if (!p) return;
  qty = qty || 1;
  pendingBuy = { pid, qty };
  document.getElementById("modal-title").textContent = "Konfirmasi Pembelian";
  document.getElementById("modal-text").innerHTML =
    "Klik <b>Ya, Beli Sekarang</b> untuk menyelesaikan pembelian. Aksi ini akan tercatat ke <b>analitik admin</b> sebagai data terjual.";
  document.getElementById("modal-product").innerHTML = `
    <b>${p.n}</b><br />
    <span style="color:#666">${p.c} · ${p.s}</span><br />
    Harga: <b>${fmtRp(p.pr)}</b> × ${qty} = <b>${fmtRp(p.pr * qty)}</b>`;
  document.getElementById("modal-buy").classList.add("open");
}

function openCheckoutAllModal() {
  if (!cart.length) {
    toast("Keranjang kosong.", "error");
    return;
  }
  pendingBuy = { all: true };
  const totalQty = cart.reduce((s, c) => s + c.qty, 0);
  const totalRp = cart.reduce((s, c) => s + c.pr * c.qty, 0);
  document.getElementById("modal-title").textContent = "Beli Semua di Keranjang";
  document.getElementById("modal-text").innerHTML =
    "Klik <b>Ya, Beli Sekarang</b> untuk menyelesaikan pembelian semua item di keranjang. Setiap item akan tercatat ke analitik admin.";
  document.getElementById("modal-product").innerHTML = `
    <b>${cart.length} produk · ${totalQty} item</b><br />
    Total: <b>${fmtRp(totalRp)}</b>`;
  document.getElementById("modal-buy").classList.add("open");
}

function checkoutAll() {
  openCheckoutAllModal();
}

function closeBuyModal() {
  document.getElementById("modal-buy").classList.remove("open");
  pendingBuy = null;
}

async function confirmBuy() {
  if (!pendingBuy) return;
  const btn = document.getElementById("modal-ok-btn");
  btn.disabled = true;
  btn.textContent = "Memproses...";
  try {
    if (pendingBuy.all) {
      // Beli seluruh keranjang
      for (const c of cart) {
        await apiPost("/api/action", { pid: c.pid, action: "buy", qty: c.qty });
      }
      toast(`Pembelian ${cart.length} produk berhasil!`, "success");
      cart = [];
      persistCart();
      renderCart();
      document.getElementById("cart-sidebar").classList.remove("open");
    } else {
      const { pid, qty } = pendingBuy;
      await apiPost("/api/action", { pid, action: "buy", qty });
      const p = PRODUCTS[pid];
      toast(`Pembelian "${p.n}" berhasil!`, "success");
      // Hapus dari cart kalau ada
      const idx = cart.findIndex((x) => x.pid === pid);
      if (idx >= 0) {
        cart.splice(idx, 1);
        persistCart();
        renderCart();
      }
    }
    closeBuyModal();
    refreshDashboard();
  } catch (e) {
    toast("Gagal memproses pembelian.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Ya, Beli Sekarang";
  }
}

// ──────────────────────────────────────────────
// Semua Produk (paginated)
let currentCatFilter = "";
let currentStoreFilter = "";
let currentProductPage = 1;
const productsPerPage = 50;

function renderAllProducts() {
  const sel = document.getElementById("cat-filter");
  if (sel && sel.options.length <= 1) {
    const cats = [...new Set(Object.values(PRODUCTS).map((p) => p.c))].sort();
    cats.forEach((c) => {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = c;
      sel.appendChild(o);
    });
  }
  const selStore = document.getElementById("store-filter");
  if (selStore && selStore.options.length <= 1) {
    const stores = [...new Set(Object.values(PRODUCTS).map((p) => p.s))].sort();
    stores.forEach((s) => {
      const o = document.createElement("option");
      o.value = s;
      o.textContent = s;
      selStore.appendChild(o);
    });
  }
  filterProducts();
}

function filterProducts() {
  currentCatFilter = document.getElementById("cat-filter").value;
  const sf = document.getElementById("store-filter");
  currentStoreFilter = sf ? sf.value : "";
  currentProductPage = 1;
  renderProductPage();
}

function renderProductPage() {
  const filtered = Object.keys(PRODUCTS).filter((pid) => {
    const p = PRODUCTS[pid];
    if (currentCatFilter && p.c !== currentCatFilter) return false;
    if (currentStoreFilter && p.s !== currentStoreFilter) return false;
    return true;
  });
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / productsPerPage));
  const start = (currentProductPage - 1) * productsPerPage;
  const pageItems = filtered.slice(start, start + productsPerPage);
  document.getElementById("all-product-grid").innerHTML = pageItems.map(productCard).join("");
  document.getElementById("product-count-info").textContent =
    `Menampilkan ${total ? start + 1 : 0}-${Math.min(start + productsPerPage, total)} dari ${total} produk`;
  const pagEl = document.getElementById("product-pagination");
  if (pagEl) {
    let h = "";
    if (currentProductPage > 1)
      h += `<button class="btn-sm btn-view" onclick="currentProductPage--;renderProductPage()">◀ Prev</button>`;
    h += `<span style="font-size:.8rem;font-weight:600;padding:0 .5rem">Hal ${currentProductPage}/${totalPages}</span>`;
    if (currentProductPage < totalPages)
      h += `<button class="btn-sm btn-view" onclick="currentProductPage++;renderProductPage()">Next ▶</button>`;
    pagEl.innerHTML = h;
  }
}

// ──────────────────────────────────────────────
// Init
window.addEventListener("load", async () => {
  loadCart();
  renderCart();
  await loadProfile();
  await refreshDashboard();
  setInterval(refreshDashboard, 15000);
});
