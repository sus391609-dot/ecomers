// YarsiMart App v5 — 5000 Produk (50 Kategori x 100 Toko) + Prediksi Real-Time
const fmtRp=n=>"Rp "+Math.round(n).toLocaleString("id-ID");
const fmtN=n=>Math.round(n).toLocaleString("id-ID");

// Clock
function updateClock(){const n=new Date(),D=["Minggu","Senin","Selasa","Rabu","Kamis","Jumat","Sabtu"],M=["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agt","Sep","Okt","Nov","Des"];document.getElementById("live-date").textContent=D[n.getDay()]+", "+n.getDate()+" "+M[n.getMonth()]+" "+n.getFullYear();document.getElementById("live-time").textContent=n.toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit",second:"2-digit"});}
setInterval(updateClock,1000);updateClock();

// Nav
function showPage(name,btn){document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));document.getElementById("page-"+name).classList.add("active");if(btn){document.querySelectorAll("nav button").forEach(b=>b.classList.remove("active"));btn.classList.add("active");}if(name==="analytics")setTimeout(renderAnalytics,100);}

// API
async function apiPost(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});return r.json();}
async function apiGet(url){const r=await fetch(url);return r.json();}

// Search
function showSuggestions(){
  const q=document.getElementById("search-input").value.trim().toLowerCase();
  const box=document.getElementById("search-suggestions");
  if(q.length<2){box.classList.remove("show");return;}
  const matches=[];
  for(const[pid,p]of Object.entries(PRODUCTS)){
    if(p.n.toLowerCase().includes(q)||p.c.toLowerCase().includes(q)||p.s.toLowerCase().includes(q))matches.push({pid,p});
    if(matches.length>=8)break;
  }
  if(!matches.length){box.classList.remove("show");return;}
  box.innerHTML=matches.map(({pid,p})=>`<div class="sug-item" onclick="document.getElementById('search-input').value='${p.n}';performSearch()"><div class="sug-icon">${ICONS[p.c]||"🛍️"}</div><div class="sug-info"><div class="sug-name">${p.n}</div><div class="sug-meta">${p.c} · ${p.s} · ${fmtRp(p.pr)}</div></div></div>`).join("");
  box.classList.add("show");
}

async function performSearch(){
  const input=document.getElementById("search-input");
  const q=input.value.trim();
  if(!q)return;
  document.getElementById("search-suggestions").classList.remove("show");
  const res=await apiPost('/api/search',{query:q});
  document.getElementById("search-query-display").textContent=q;
  document.getElementById("search-results").style.display="block";
  document.getElementById("search-result-info").innerHTML=`<div class="db-status" style="margin-bottom:1rem"><div class="db-indicator">✅ ${res.message}</div><div>Search ID: #${res.search_id} · ${res.count} produk ditemukan</div></div>`;
  if(res.results&&res.results.length){
    document.getElementById("search-results-grid").innerHTML=res.results.map(r=>productCard(r.pid)).join("");
  }else{
    document.getElementById("search-results-grid").innerHTML='<div class="empty-keywords">Tidak ada produk ditemukan untuk "'+q+'"</div>';
  }
  input.value="";
  refreshDashboard();
}

function closeSearchResults(){document.getElementById("search-results").style.display="none";}

// Dashboard Refresh
async function refreshDashboard(){
  try{
    const[stats,kw,trend,best]=await Promise.all([apiGet('/api/stats'),apiGet('/api/keywords'),apiGet('/api/trending?limit=50'),apiGet('/api/bestsellers?limit=10')]);
    document.getElementById("stat-searches").textContent=fmtN(stats.total_searches);
    document.getElementById("stat-tokens").textContent=fmtN(stats.total_tokens);
    document.getElementById("db-msg").textContent=`${stats.total_searches} pencarian · ${stats.total_tokens} token · ${stats.products_searched}/${stats.total_products||5000} produk dicari`;
    renderKeywords(kw.keywords);
    renderTrending(trend.trending);
    renderBestsellers(best.bestsellers);
    renderRecent(stats.recent_searches);
    document.getElementById("kw-count-tag").textContent=`Database: ${stats.unique_keywords} kata kunci`;
    const tt=document.getElementById("trending-tag");
    if(tt&&trend.day) tt.textContent=`🟢 Real-time Shopee · rotasi harian · ${trend.day} · ${trend.count||0} produk`;
    const bt=document.getElementById("bestseller-tag");
    if(bt&&best.day) bt.textContent=`🟢 Real-time Shopee · ${best.day} · Prediksi keranjang aktif`;
  }catch(e){console.error("Dashboard refresh error:",e);}
}

function renderKeywords(keywords){
  const el=document.getElementById("top-keywords");
  if(!keywords||!keywords.length){el.innerHTML='<div class="empty-keywords">🔍 Belum ada pencarian. Cari produk di search bar!</div>';return;}
  el.innerHTML='<div class="keywords-grid">'+keywords.map((k,i)=>`<div class="keyword-chip" onclick="document.getElementById('search-input').value='${k.keyword}';performSearch()"><span class="kw-rank">#${i+1}</span><span class="kw-text">${k.keyword}</span><span class="kw-count">${k.count}</span></div>`).join("")+'</div>';
}

function renderTrending(trending){
  const el=document.getElementById("trending-grid");
  const ranks=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"];
  if(!trending||!trending.length){el.innerHTML='<div class="empty-keywords" style="grid-column:1/-1">Belum ada data trending.</div>';return;}
  // Tampilkan top 10 dari 50 (50 adalah daftar trending hari ini)
  el.innerHTML=trending.slice(0,10).map((t,i)=>{
    const p=PRODUCTS[t.pid];if(!p)return"";
    const liveBadge=(t.shopee_live_boost||0)>0?'<span style="font-size:.55rem;color:#16a34a;font-weight:700">🔴 LIVE Shopee</span>':'';
    const tokInfo=t.tokens?`🎯 ${t.tokens} token`:`📊 Skor ${t.trend_score||0}`;
    return`<div class="trend-card" onclick="openPrediction('${t.pid}')"><div class="trend-rank">${ranks[i]||"#"+(i+1)}</div><div class="trend-icon">${ICONS[p.c]||"🛍️"}</div><div class="trend-name">${p.n}</div><div class="trend-fire">${fmtRp(p.pr)}</div><div class="trend-tokens">${tokInfo}</div>${liveBadge}<div style="font-size:.6rem;color:var(--text3);margin-top:.2rem">${p.s}</div></div>`;
  }).join("");
}

function renderBestsellers(bestsellers){
  const el=document.getElementById("bestseller-grid");
  if(!bestsellers||!bestsellers.length){el.innerHTML='<div class="empty-keywords">Belum ada data terlaris.</div>';return;}
  el.innerHTML=bestsellers.map(b=>{
    const p=PRODUCTS[b.pid];if(!p)return"";
    const cartLabel=(b.label_prediksi&&b.label_prediksi!=="Normal")?`<span style="font-size:.6rem;color:#dc2626;font-weight:700">🛒 ${b.label_prediksi}</span>`:'';
    const dailyShopee=b.shopee_daily_est?`Shopee ~<b>${fmtN(b.shopee_daily_est)}</b>/hari`:'';
    return`<div class="bs-card" onclick="openPrediction('${b.pid}')"><div class="bs-icon">${ICONS[p.c]||"🛍️"}</div><div class="bs-info"><div class="bs-name">${b.name}</div><div class="bs-cat">${b.cat} · ${b.store||p.s} · ${dailyShopee}</div><div class="bs-stats"><div class="bs-stat">📅 <b>${b.pred_daily}</b>/hari</div><div class="bs-stat">📆 <b>${b.pred_weekly}</b>/minggu</div><div class="bs-stat">🗓️ <b>${b.pred_monthly}</b>/bulan</div></div>${cartLabel}</div><div class="bs-pred"><div class="bs-pred-val">${fmtRp(b.est_revenue)}</div><div class="bs-pred-lbl">Est. Revenue/bln</div></div></div>`;
  }).join("");
}

function renderRecent(recent){
  const el=document.getElementById("recent-searches");
  if(!recent||!recent.length){el.innerHTML='<div class="empty-keywords">Belum ada riwayat pencarian.</div>';return;}
  el.innerHTML='<div class="keywords-grid">'+recent.map(r=>`<div class="keyword-chip"><span class="kw-text">🕐 "${r.query}"</span><span style="font-size:.6rem;color:var(--text3)">${new Date(r.time).toLocaleTimeString("id-ID")}</span></div>`).join("")+'</div>';
}

async function resetDB(){
  if(!confirm("Reset semua data pencarian?"))return;
  await apiPost('/api/reset',{});
  refreshDashboard();
  document.getElementById("db-msg").textContent="Database direset!";
}

// KPI
function renderKPI(){
  document.getElementById("kpi-grid").innerHTML=`
    <div class="kpi-card"><div class="kpi-label">🟠 Unit Shopee</div><div class="kpi-val" style="color:var(--primary)">${fmtN(TOTALS.qty)}</div><div class="kpi-badge up">Data 5000 Produk</div></div>
    <div class="kpi-card"><div class="kpi-label">💰 Pendapatan Shopee</div><div class="kpi-val" style="font-size:1rem">${fmtRp(TOTALS.rev)}</div><div class="kpi-badge up">50 Kategori</div></div>
    <div class="kpi-card"><div class="kpi-label">📦 Produk Terdaftar</div><div class="kpi-val">${fmtN(TOTALS.products)}</div><div class="kpi-badge up">${TOTALS.categories} Kategori · ${TOTALS.stores} Toko</div></div>
    <div class="kpi-card"><div class="kpi-label">🗄️ Database Engine</div><div class="kpi-val" style="font-size:1rem">SQLite</div><div class="kpi-badge up">Real-time tracking</div></div>`;
}

// Product Card
function productCard(pid){
  const p=PRODUCTS[pid];
  if(!p)return"";
  const growth=p.lmv>0?((p.cmv/p.lmv-1)*100):0;
  const up=growth>=0;
  return`<div class="product-card">
    <div class="product-img" onclick="openPrediction('${pid}')" style="cursor:pointer">${ICONS[p.c]||"🛍️"}<div class="product-trend-badge ${up?"up":"down"}">${up?"↑":"↓"}${Math.abs(growth).toFixed(0)}%</div></div>
    <div class="product-info">
      <div class="product-name" onclick="openPrediction('${pid}')" style="cursor:pointer">${p.n}</div>
      <div class="product-cat">${p.c} · ${p.s}</div>
      <div class="product-price">${fmtRp(p.pr)}</div>
      <div class="product-sold">Terjual: ${fmtN(p.sp_qty)} · ⭐${p.rt}</div>
      <div style="display:flex;gap:5px;margin-top:8px">
        <button class="btn-sm btn-view" onclick="openPrediction('${pid}')">👁️ Prediksi</button>
        <button class="btn-sm btn-cart" onclick="addToCart('${pid}')">🛒 +Keranjang</button>
      </div>
    </div>
  </div>`;
}

// Products page with pagination
let currentCatFilter = '';
let currentStoreFilter = '';
let currentProductPage = 1;
const productsPerPage = 50;

function renderAllProducts(){
  // Category filter
  const cats=[...new Set(Object.values(PRODUCTS).map(p=>p.c))].sort();
  const sel=document.getElementById("cat-filter");
  sel.innerHTML='<option value="">Semua Kategori (50)</option>';
  cats.forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o);});
  // Store filter
  const stores=[...new Set(Object.values(PRODUCTS).map(p=>p.s))].sort();
  const selStore=document.getElementById("store-filter");
  if(selStore){
    selStore.innerHTML='<option value="">Semua Toko (100)</option>';
    stores.forEach(s=>{const o=document.createElement("option");o.value=s;o.textContent=s;selStore.appendChild(o);});
  }
  filterProducts();
}

function filterProducts(){
  currentCatFilter=document.getElementById("cat-filter").value;
  const sf=document.getElementById("store-filter");
  currentStoreFilter=sf?sf.value:'';
  currentProductPage=1;
  renderProductPage();
}

function renderProductPage(){
  const filtered=Object.keys(PRODUCTS).filter(pid=>{
    const p=PRODUCTS[pid];
    if(currentCatFilter&&p.c!==currentCatFilter)return false;
    if(currentStoreFilter&&p.s!==currentStoreFilter)return false;
    return true;
  });
  const total=filtered.length;
  const totalPages=Math.ceil(total/productsPerPage);
  const start=(currentProductPage-1)*productsPerPage;
  const pageItems=filtered.slice(start,start+productsPerPage);

  document.getElementById("all-product-grid").innerHTML=pageItems.map(productCard).join("");
  document.getElementById("product-count-info").textContent=`Menampilkan ${start+1}-${Math.min(start+productsPerPage,total)} dari ${total} produk`;

  // Pagination
  const pagEl=document.getElementById("product-pagination");
  if(pagEl){
    let pagHtml='';
    if(currentProductPage>1) pagHtml+=`<button class="btn-sm btn-view" onclick="currentProductPage--;renderProductPage()">◀ Prev</button>`;
    pagHtml+=`<span style="font-size:.8rem;font-weight:600;padding:0 .5rem">Hal ${currentProductPage}/${totalPages}</span>`;
    if(currentProductPage<totalPages) pagHtml+=`<button class="btn-sm btn-view" onclick="currentProductPage++;renderProductPage()">Next ▶</button>`;
    pagEl.innerHTML=pagHtml;
  }
}

// Prediction
function openPrediction(pid){
  showPage("prediction",document.querySelectorAll("nav button")[1]);
  document.getElementById("pred-select").value=pid;
  // renderPrediction sendiri sudah mengirim 'view' ke server,
  // jadi tidak perlu recordAction lagi di sini.
  renderPrediction();
}

function fillSelect(){
  const sel=document.getElementById("pred-select");
  // Group by category
  const grouped={};
  Object.entries(PRODUCTS).forEach(([pid,p])=>{
    if(!grouped[p.c])grouped[p.c]=[];
    grouped[p.c].push({pid,p});
  });
  Object.keys(grouped).sort().forEach(cat=>{
    const og=document.createElement("optgroup");
    og.label=`${ICONS[cat]||"🛍️"} ${cat} (${grouped[cat].length})`;
    grouped[cat].forEach(({pid,p})=>{
      const o=document.createElement("option");
      o.value=pid;
      o.textContent=`${p.n} — ${p.s}`;
      og.appendChild(o);
    });
    sel.appendChild(og);
  });
}

const charts={};
function dc(id){if(charts[id]){charts[id].destroy();delete charts[id];}}

async function renderPrediction(){
  const pid=document.getElementById("pred-select").value;
  if(!pid){document.getElementById("pred-content").style.display="none";document.getElementById("pred-empty").style.display="block";return;}
  document.getElementById("pred-content").style.display="block";
  document.getElementById("pred-empty").style.display="none";
  const p=PRODUCTS[pid];

  // Catat klik sebagai 'view' SEBELUM ambil prediksi, supaya angka yang
  // ditampilkan ke user sudah memasukkan klik mereka sendiri (views bulan ini bertambah).
  try{ await apiPost('/api/action',{pid,action:'view'}); }catch(e){}

  // Get predictions from API (sudah termasuk current_month_views user)
  let searchPred={tokens:0,search_boost:1,ctr:0,atc_rate:0,sales_rate:0,views:0,cart_adds:0,sales:0};
  try{searchPred=await apiGet(`/api/predict/${pid}`);}catch(e){}

  // Gunakan angka dari server bila tersedia (sudah augmented dengan aktivitas user)
  const lmv = (searchPred.last_month_views!=null) ? searchPred.last_month_views : (p.lmv||1);
  const lms = (searchPred.last_month_sales!=null) ? searchPred.last_month_sales : (p.lms||0);
  const cmv = (searchPred.current_month_views!=null) ? searchPred.current_month_views : (p.cmv||0);
  const cmvBase = (searchPred.current_month_views_base!=null) ? searchPred.current_month_views_base : (p.cmv||0);
  const cmvUser = (searchPred.current_month_views_user!=null) ? searchPred.current_month_views_user : 0;
  const convRate=lms/Math.max(1,lmv);
  const growthRate=cmv/Math.max(1,lmv);
  const growthPct=((growthRate-1)*100).toFixed(1);
  const predSales=Math.max(0,Math.round(lms*growthRate));
  const predDaily=Math.max(0,Math.round(predSales/30));
  const predWeekly=Math.max(0,Math.round(predSales/4));
  const predRevenue=predSales*p.pr;

  let trendLabel="Stabil", trendColor="#eab308";
  if(growthPct>50){trendLabel="Sangat Meningkat";trendColor="#16a34a";}
  else if(growthPct>10){trendLabel="Meningkat";trendColor="#22c55e";}
  else if(growthPct>-10){trendLabel="Stabil";trendColor="#eab308";}
  else if(growthPct>-30){trendLabel="Menurun";trendColor="#f97316";}
  else{trendLabel="Sangat Menurun";trendColor="#dc2626";}

  // Prediction cards
  document.getElementById("pred-cards").innerHTML=`
    <div class="pred-card" style="background:linear-gradient(135deg,#e0f2fe,#fff)"><div class="ico">📊</div><div class="period">Views Bulan Lalu</div><div class="qty">${fmtN(lmv)}</div><div class="unit">Total pencarian/views</div><div class="conf-bar"><div class="conf-fill" style="width:100%;background:#0ea5e9"></div></div><div class="conf-txt">Konversi: ${(convRate*100).toFixed(2)}%</div></div>
    <div class="pred-card" style="background:linear-gradient(135deg,#dcfce7,#fff)"><div class="ico">📈</div><div class="period">Views Bulan Ini</div><div class="qty">${fmtN(cmv)}</div><div class="unit" style="color:${trendColor};font-weight:700">${growthPct>0?"+":""}${growthPct}% ${trendLabel}</div><div class="conf-bar"><div class="conf-fill" style="width:${Math.min(100,Math.abs(growthPct))}%;background:${trendColor}"></div></div><div class="conf-txt">Base ${fmtN(cmvBase)} + Aktivitas Anda <b>${fmtN(cmvUser)}</b></div></div>
    <div class="pred-card" style="background:linear-gradient(135deg,#fef08a,#fff)"><div class="ico">🔮</div><div class="period">Prediksi Terjual Bulan Ini</div><div class="qty" style="color:${trendColor}">${fmtN(predSales)}</div><div class="unit">unit (dari ${fmtN(lms)} bulan lalu)</div><div class="conf-bar"><div class="conf-fill" style="width:${Math.min(100,(convRate*100)*10)}%;background:#eab308"></div></div><div class="conf-txt">Est. Revenue: ${fmtRp(predRevenue)}</div></div>`;

  // Revenue prediction detail
  document.getElementById("rev-pred").innerHTML=`
    <div style="background:#fff7f3;border:1.5px solid #ffd5c2;border-radius:12px;padding:1.2rem;margin-bottom:1rem">
      <h4 style="font-size:.9rem;margin-bottom:.8rem;color:var(--primary)">🔮 Detail Prediksi Real-Time — ${p.n} (${p.s})</h4>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin-bottom:.8rem">
        <div style="text-align:center;background:#fff;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2">
          <div style="font-size:.68rem;color:var(--text3)">Prediksi Harian</div>
          <div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${predDaily} /hari</div>
        </div>
        <div style="text-align:center;background:#fff;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2">
          <div style="font-size:.68rem;color:var(--text3)">Prediksi Mingguan</div>
          <div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${predWeekly} /minggu</div>
        </div>
        <div style="text-align:center;background:#fff;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2">
          <div style="font-size:.68rem;color:var(--text3)">Prediksi Bulanan</div>
          <div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${predSales} /bulan</div>
        </div>
        <div style="text-align:center;background:#fff;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2">
          <div style="font-size:.68rem;color:var(--text3)">Est. Revenue Bulan Ini</div>
          <div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${fmtRp(predRevenue)}</div>
        </div>
      </div>
      <div style="font-size:.75rem;color:var(--text2);line-height:1.6;background:#fff;padding:.8rem;border-radius:8px;border:1px solid #f0f0f0">
        <b>Rumus Prediksi:</b> Prediksi Terjual = Penjualan Bulan Lalu × (Views Bulan Ini / Views Bulan Lalu)<br>
        <b>Perhitungan:</b> ${fmtN(lms)} × (${fmtN(cmv)} / ${fmtN(lmv)}) = <b style="color:var(--primary)">${fmtN(predSales)} unit</b><br>
        <b>Tren:</b> <span style="color:${trendColor};font-weight:700">${trendLabel} (${growthPct>0?"+":""}${growthPct}%)</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:1rem">
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:.8rem">
        <div style="font-size:.75rem;font-weight:600;color:#166534;margin-bottom:.4rem">📦 Data Shopee (Total)</div>
        <div style="font-size:.8rem">Terjual: <b>${fmtN(p.sp_qty)}</b> · Revenue: <b>${fmtRp(p.sp_rev)}</b></div>
        <div style="font-size:.7rem;color:var(--text3);margin-top:.2rem">Rating: ⭐${p.rt}</div>
      </div>
      <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:.8rem">
        <div style="font-size:.75rem;font-weight:600;color:#1d4ed8;margin-bottom:.4rem">🔍 Data DB Pencarian</div>
        <div style="font-size:.8rem">Token: <b>${searchPred.tokens||0}</b> · Views: <b>${searchPred.views||0}</b></div>
        <div style="font-size:.7rem;color:var(--text3);margin-top:.2rem">CTR: ${searchPred.ctr||0}% · ATC: ${searchPred.atc_rate||0}%</div>
      </div>
    </div>`;

  // Prediction comparison chart
  dc("conv");
  charts["conv"]=new Chart(document.getElementById("chart-conversion"),{
    type:"bar",
    data:{
      labels:["Views Bln Lalu","Terjual Bln Lalu","Views Bln Ini","Prediksi Terjual"],
      datasets:[{
        label:"Jumlah",
        data:[lmv, lms, cmv, predSales],
        backgroundColor:["rgba(14,165,233,0.8)","rgba(34,197,94,0.8)","rgba(234,179,8,0.8)","rgba(238,77,45,0.8)"],
        borderRadius:5
      }]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true},x:{ticks:{font:{size:10,weight:'bold'}}}}}
  });
  document.getElementById("live-pred-badge").textContent="🔴 LIVE · "+new Date().toLocaleTimeString("id-ID");
}

// ══════════════════════════════════════════════
// ANALYTICS — 3 Tabel Utama + Prediksi
// ══════════════════════════════════════════════
let analyticsData = {categories:[], stores:[]};

async function renderAnalytics(){
  // Load data from APIs
  try{
    const[catData, storeData, trendData]=await Promise.all([
      apiGet('/api/category_summary'),
      apiGet('/api/store_summary'),
      apiGet('/api/trending')
    ]);
    analyticsData.categories=catData.categories||[];
    analyticsData.stores=storeData.stores||[];

    // === TABLE 1: Katalog Produk (Kategori) ===
    renderCatalogTable(analyticsData.categories);

    // === TABLE 2: Pencarian & Penjualan (per Kategori) ===
    renderSearchSalesTable(analyticsData.categories);

    // === TABLE 3: Shopee QTY & REV ===
    renderShopeeTable(analyticsData.categories);

    // === TABLE 4: Prediksi Bulan Ini ===
    renderPredictionTable(analyticsData.categories);

    // Charts
    renderAnalyticsCharts(analyticsData.categories, trendData.trending||[]);
  }catch(e){console.error("Analytics error:",e);}
}

function renderCatalogTable(categories){
  const tbl=document.getElementById("catalog-table");
  if(!tbl)return;
  let html=`<thead><tr><th>#</th><th>Jenis Produk</th><th>Jumlah Toko</th><th>Harga Rata-rata</th><th>Total Produk Terjual</th><th>Rating Avg</th></tr></thead><tbody>`;
  categories.forEach((c,i)=>{
    // Calculate avg rating from PRODUCTS
    let ratings=[];
    Object.values(PRODUCTS).forEach(p=>{if(p.c===c.cat)ratings.push(p.rt);});
    const avgRating=ratings.length?(ratings.reduce((a,b)=>a+b,0)/ratings.length).toFixed(1):"4.5";
    html+=`<tr>
      <td>${i+1}</td>
      <td><b style="color:var(--primary);cursor:pointer" onclick="filterAnalyticsByCat('${c.cat}')">${ICONS[c.cat]||"🛍️"} ${c.cat}</b></td>
      <td>${c.store_count} toko</td>
      <td>${fmtRp(c.avg_price)}</td>
      <td>${fmtN(c.total_sp_qty)}</td>
      <td>⭐${avgRating}</td>
    </tr>`;
  });
  html+='</tbody>';
  tbl.innerHTML=html;
}

function renderSearchSalesTable(categories){
  const tbl=document.getElementById("search-sales-table");
  if(!tbl)return;
  let html=`<thead><tr><th>#</th><th>Jenis Produk</th><th>Pencarian Bln Lalu</th><th>Terjual Bln Lalu</th><th>Konversi %</th><th>Views Bln Ini</th><th>Pertumbuhan</th></tr></thead><tbody>`;
  categories.forEach((c,i)=>{
    const growthClass=c.growth_pct>=0?"up":"down";
    const growthIcon=c.growth_pct>=0?"↑":"↓";
    html+=`<tr>
      <td>${i+1}</td>
      <td><b>${ICONS[c.cat]||"🛍️"} ${c.cat}</b></td>
      <td>${fmtN(c.total_lm_views)}</td>
      <td><b>${fmtN(c.total_lm_sales)}</b></td>
      <td><span class="kpi-badge ${c.conversion_rate>1.5?"up":"down"}">${c.conversion_rate}%</span></td>
      <td>${fmtN(c.total_cmv)}</td>
      <td><span class="kpi-badge ${growthClass}">${growthIcon} ${Math.abs(c.growth_pct).toFixed(1)}%</span></td>
    </tr>`;
  });
  html+='</tbody>';
  tbl.innerHTML=html;
}

function renderShopeeTable(categories){
  const tbl=document.getElementById("shopee-table");
  if(!tbl)return;
  let html=`<thead><tr><th>#</th><th>Jenis Produk</th><th>Shopee QTY (Terjual)</th><th>Shopee REV (Pendapatan)</th><th>Avg Harga</th><th>Toko</th></tr></thead><tbody>`;
  categories.forEach((c,i)=>{
    html+=`<tr>
      <td>${i+1}</td>
      <td><b>${ICONS[c.cat]||"🛍️"} ${c.cat}</b></td>
      <td style="font-weight:700;color:var(--primary)">${fmtN(c.total_sp_qty)}</td>
      <td style="font-weight:700;color:#16a34a">${fmtRp(c.total_sp_rev)}</td>
      <td>${fmtRp(c.avg_price)}</td>
      <td>${c.store_count}</td>
    </tr>`;
  });
  // Total row
  const totQty=categories.reduce((s,c)=>s+c.total_sp_qty,0);
  const totRev=categories.reduce((s,c)=>s+c.total_sp_rev,0);
  html+=`<tr style="background:#fff7f3;font-weight:700"><td></td><td>TOTAL (50 Kategori)</td><td style="color:var(--primary)">${fmtN(totQty)}</td><td style="color:#16a34a">${fmtRp(totRev)}</td><td></td><td>5000</td></tr>`;
  html+='</tbody>';
  tbl.innerHTML=html;
}

function renderPredictionTable(categories){
  const tbl=document.getElementById("prediction-table");
  if(!tbl)return;
  let html=`<thead><tr><th>#</th><th>Jenis Produk</th><th>Terjual Bln Lalu</th><th>Prediksi Bln Ini</th><th>Prediksi Revenue</th><th>Tren</th><th>Pertumbuhan</th></tr></thead><tbody>`;
  categories.forEach((c,i)=>{
    const growth=c.growth_pct;
    let trendLabel="Stabil", trendColor="#eab308";
    if(growth>50){trendLabel="🔥 Sangat Naik";trendColor="#16a34a";}
    else if(growth>10){trendLabel="📈 Naik";trendColor="#22c55e";}
    else if(growth>-10){trendLabel="➡️ Stabil";trendColor="#eab308";}
    else if(growth>-30){trendLabel="📉 Turun";trendColor="#f97316";}
    else{trendLabel="⬇️ Sangat Turun";trendColor="#dc2626";}
    html+=`<tr>
      <td>${i+1}</td>
      <td><b>${ICONS[c.cat]||"🛍️"} ${c.cat}</b></td>
      <td>${fmtN(c.total_lm_sales)}</td>
      <td style="font-weight:700;color:var(--primary)">${fmtN(c.total_predicted_sales)}</td>
      <td style="font-weight:700;color:#16a34a">${fmtRp(c.total_predicted_rev)}</td>
      <td><span style="color:${trendColor};font-weight:600">${trendLabel}</span></td>
      <td><span class="kpi-badge ${growth>=0?"up":"down"}">${growth>=0?"+":""}${growth.toFixed(1)}%</span></td>
    </tr>`;
  });
  html+='</tbody>';
  tbl.innerHTML=html;
}

function filterAnalyticsByCat(cat){
  showPage('products',document.querySelectorAll("nav button")[3]);
  document.getElementById("cat-filter").value=cat;
  filterProducts();
}

function renderAnalyticsCharts(categories, trending){
  // Category Revenue Chart
  dc("aCatRev");
  const topCats=categories.slice(0,15);
  charts["aCatRev"]=new Chart(document.getElementById("chart-cat-revenue"),{
    type:"bar",
    data:{
      labels:topCats.map(c=>c.cat),
      datasets:[{
        label:"Shopee Revenue",
        data:topCats.map(c=>c.total_sp_rev),
        backgroundColor:"rgba(238,77,45,0.7)",
        borderRadius:4
      }]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{y:{beginAtZero:true,ticks:{callback:v=>fmtRp(v)}},x:{ticks:{maxRotation:45,font:{size:9}}}}}
  });

  // Search vs Sales Chart
  dc("aSearchSales");
  charts["aSearchSales"]=new Chart(document.getElementById("chart-search-sales"),{
    type:"bar",
    data:{
      labels:topCats.map(c=>c.cat),
      datasets:[
        {label:"Pencarian Bln Lalu",data:topCats.map(c=>c.total_lm_views),backgroundColor:"rgba(14,165,233,0.6)",borderRadius:4},
        {label:"Terjual Bln Lalu",data:topCats.map(c=>c.total_lm_sales),backgroundColor:"rgba(34,197,94,0.6)",borderRadius:4},
      ]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10}}}},
      scales:{y:{beginAtZero:true},x:{ticks:{maxRotation:45,font:{size:9}}}}}
  });

  // Prediction Growth Chart
  dc("aPredGrowth");
  const sorted=[...categories].sort((a,b)=>b.growth_pct-a.growth_pct).slice(0,20);
  charts["aPredGrowth"]=new Chart(document.getElementById("chart-pred-growth"),{
    type:"bar",
    data:{
      labels:sorted.map(c=>c.cat),
      datasets:[{
        label:"Pertumbuhan %",
        data:sorted.map(c=>c.growth_pct),
        backgroundColor:sorted.map(c=>c.growth_pct>=0?"rgba(34,197,94,0.7)":"rgba(239,68,68,0.7)"),
        borderRadius:4
      }]
    },
    options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false}},
      scales:{x:{beginAtZero:false},y:{ticks:{font:{size:9}}}}}
  });

  // Token Doughnut
  dc("aTok");
  const top10=trending.filter(t=>t.tokens>0).slice(0,10);
  if(top10.length){
    charts["aTok"]=new Chart(document.getElementById("chart-search-tokens"),{
      type:"doughnut",
      data:{
        labels:top10.map(t=>(t.name||"").substring(0,20)),
        datasets:[{
          data:top10.map(t=>t.tokens),
          backgroundColor:["#ee4d2d","#ff6a2a","#ff8c57","#22c55e","#2196f3","#9c27b0","#ff9800","#00bcd4","#795548","#f06292"],
          borderWidth:2,borderColor:"#fff"
        }]
      },
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{font:{size:8},boxWidth:8}}}}
    });
  }
}

// ═══ CHATBOT ═══
let chatOpen=false;
let chatHistory=[];

function toggleChat(){
  chatOpen=!chatOpen;
  document.getElementById("chat-panel").classList.toggle("open",chatOpen);
  if(chatOpen)document.getElementById("chat-input").focus();
}
function sendChip(btn){document.getElementById("chat-input").value=btn.textContent;sendMsg();}

async function sendMsg(){
  const input=document.getElementById("chat-input");
  const msg=input.value.trim();
  if(!msg)return;
  input.value="";
  input.disabled=true;
  document.querySelector(".chat-send").disabled=true;
  appendMsg(msg,"user");
  chatHistory.push({role:"user",text:msg});
  showTyping();
  try{
    const res=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg,history:chatHistory.slice(0,-1)})});
    const data=await res.json();
    removeTyping();
    if(data.reply){
      appendMsg(formatMarkdown(data.reply),"bot");
      chatHistory.push({role:"bot",text:data.reply});
      if(chatHistory.length>20)chatHistory=chatHistory.slice(-20);
    }else{
      appendMsg("⚠️ "+(data.error||"Terjadi kesalahan. Coba lagi."),"bot");
    }
  }catch(e){
    removeTyping();
    appendMsg("⚠️ Tidak bisa menghubungi server.","bot");
  }
  input.disabled=false;
  document.querySelector(".chat-send").disabled=false;
  input.focus();
}

function formatMarkdown(text){
  return text.replace(/\*\*(.*?)\*\*/g,"<b>$1</b>").replace(/\*(.*?)\*/g,"<i>$1</i>").replace(/`(.*?)`/g,"<code style='background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:0.85em'>$1</code>").replace(/^- (.+)$/gm,"• $1").replace(/\n/g,"<br>");
}

function appendMsg(text,role){
  const msgs=document.getElementById("chat-msgs");
  const div=document.createElement("div");
  div.className="msg "+role;
  div.innerHTML=`<div class="msg-av">${role==="bot"?"🤖":"👤"}</div><div class="msg-bubble">${text}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop=msgs.scrollHeight;
}
function showTyping(){
  const msgs=document.getElementById("chat-msgs");
  const div=document.createElement("div");
  div.className="msg bot";div.id="typing";
  div.innerHTML='<div class="msg-av">🤖</div><div class="msg-bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
  msgs.appendChild(div);msgs.scrollTop=msgs.scrollHeight;
}
function removeTyping(){const t=document.getElementById("typing");if(t)t.remove();}

// Cart
let cart=[];
function toggleCart(){document.getElementById("cart-sidebar").classList.toggle("open");}
function addToCart(pid){
  const p=PRODUCTS[pid];
  const item=cart.find(x=>x.pid===pid);
  if(item)item.qty++;else cart.push({pid,qty:1,n:p.n,pr:p.pr,s:p.s});
  renderCart();
  recordAction(pid,'cart');
  document.getElementById("cart-badge").innerText=cart.reduce((s,c)=>s+c.qty,0);
  document.getElementById("cart-badge").style.display="block";
}
function renderCart(){
  const el=document.getElementById("cart-items");
  if(!cart.length){el.innerHTML="<p style='text-align:center;color:#999;margin-top:2rem'>Keranjang kosong</p>";document.getElementById("cart-total").innerText="Rp 0";return;}
  el.innerHTML=cart.map((c,i)=>`<div class="cart-item" style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding:10px 0;"><div><div style="font-weight:600;font-size:0.85rem;margin-bottom:4px">${c.n}</div><div style="font-size:0.75rem;color:#888">${c.s}</div><div style="font-size:0.8rem;color:#666">${fmtRp(c.pr)} x ${c.qty}</div></div><button onclick="cart.splice(${i},1);renderCart();document.getElementById('cart-badge').innerText=cart.reduce((s,c)=>s+c.qty,0);" style="border:none;background:none;color:red;cursor:pointer;font-size:1.2rem">🗑️</button></div>`).join("");
  document.getElementById("cart-total").innerText=fmtRp(cart.reduce((s,c)=>s+(c.pr*c.qty),0));
}
async function checkout(){
  if(!cart.length)return alert("Keranjang kosong!");
  for(let c of cart){for(let i=0;i<c.qty;i++)await apiPost('/api/action',{pid:c.pid,action:'buy'});}
  alert(`Checkout berhasil untuk ${cart.length} produk!`);
  cart=[];renderCart();
  document.getElementById("cart-badge").style.display="none";
  toggleCart();refreshDashboard();
}
async function recordAction(pid,action){try{await apiPost('/api/action',{pid,action});}catch(e){}}

// Init
window.addEventListener("load",()=>{
  fillSelect();
  renderKPI();
  renderAllProducts();
  refreshDashboard();
  setInterval(refreshDashboard,15000);
});
