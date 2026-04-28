// YarsiMart App v4 — Flask + SQLite Search Engine
const ICONS={Kemeja:"👔",Kaos:"👕",Celana:"👖",Dress:"👗",Jaket:"🧥",Hijab:"🧕",Rok:"🩱",Sweater:"🧶",Koko:"🕌",Blouse:"👚",Gamis:"🥻",Hoodie:"🥷",Mukena:"🤍",Atasan:"👙",Outer:"🧣",Batik:"🎨","Pakaian Dalam":"🩲"};
const fmtRp=n=>"Rp "+Math.round(n).toLocaleString("id-ID");
const fmtN=n=>Math.round(n).toLocaleString("id-ID");

// ═══ CLOCK ═══
function updateClock(){const n=new Date(),D=["Minggu","Senin","Selasa","Rabu","Kamis","Jumat","Sabtu"],M=["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agt","Sep","Okt","Nov","Des"];document.getElementById("live-date").textContent=D[n.getDay()]+", "+n.getDate()+" "+M[n.getMonth()]+" "+n.getFullYear();document.getElementById("live-time").textContent=n.toLocaleTimeString("id-ID",{hour:"2-digit",minute:"2-digit",second:"2-digit"});}
setInterval(updateClock,1000);updateClock();

// ═══ NAV ═══
function showPage(name,btn){document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));document.getElementById("page-"+name).classList.add("active");if(btn){document.querySelectorAll("nav button").forEach(b=>b.classList.remove("active"));btn.classList.add("active");}if(name==="analytics")setTimeout(renderAnalytics,100);}

// ═══ PREDICTION ENGINE ═══
const PredEngine={
  seasonMonth:{1:.85,2:.8,3:.98,4:1.18,5:1.35,6:1.48,7:.92,8:.87,9:.92,10:.98,11:1.12,12:1.38},
  seasonDow:{0:.75,1:.8,2:.85,3:.9,4:1.12,5:1.38,6:1.28},
  ols(s,a=1){const n=s.length;if(n<3){const v=s.reduce((a,b)=>a+b,0)/Math.max(n,1);return Array(a).fill(Math.max(0,Math.round(v)));}const xm=(n-1)/2,ym=s.reduce((a,b)=>a+b,0)/n;const num=s.reduce((t,y,i)=>t+(i-xm)*(y-ym),0);const den=s.reduce((t,_,i)=>t+(i-xm)**2,0);const sl=den?num/den:0,ic=ym-sl*xm;return Array.from({length:a},(_,i)=>Math.max(0,Math.round(ic+sl*(n+i))));},
  seasonal(v,m,c){let mf=this.seasonMonth[m]||1,cf=1;if(["Koko","Gamis","Hijab","Kemeja","Batik","Mukena"].includes(c)&&[3,4,5].includes(m))cf=1.9;if(["Jaket","Sweater","Hoodie","Outer"].includes(c)&&[6,7,8].includes(m))cf=1.35;if(["Dress","Atasan"].includes(c)&&[12,1,2].includes(m))cf=1.22;return Math.max(0,Math.round(v*mf*cf));},
  predict(pid){const p=PRODUCTS[pid],now=new Date(),cm=now.getMonth()+1,nm=(cm%12)+1;const rd=this.ols(p.ws.slice(-7))[0]/7;const p1d=Math.max(1,Math.round(rd*this.seasonDow[now.getDay()]*this.seasonMonth[cm]));const p1w=this.seasonal(this.ols(p.ws.slice(-8))[0],cm,p.c);const p1m=this.seasonal(this.ols(p.ms.slice(-6))[0],nm,p.c);const w8=p.ws.slice(-8),avg=w8.reduce((a,b)=>a+b,0)/w8.length,va=w8.reduce((s,v)=>s+(v-avg)**2,0)/w8.length,cv=avg>0?Math.sqrt(va)/avg:0;const conf=Math.min(95,Math.max(60,Math.round((87-cv*10)*10)/10));return{p1d,p1w,p1m,conf};}
};

// ═══ API CALLS ═══
async function apiPost(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});return r.json();}
async function apiGet(url){const r=await fetch(url);return r.json();}

// ═══ SEARCH ENGINE ═══
function showSuggestions(){
  const q=document.getElementById("search-input").value.trim().toLowerCase();
  const box=document.getElementById("search-suggestions");
  if(q.length<2){box.classList.remove("show");return;}
  const matches=[];
  for(const[pid,p]of Object.entries(PRODUCTS)){
    if(p.n.toLowerCase().includes(q)||p.c.toLowerCase().includes(q))matches.push({pid,p});
    if(matches.length>=6)break;
  }
  if(!matches.length){box.classList.remove("show");return;}
  box.innerHTML=matches.map(({pid,p})=>`<div class="sug-item" onclick="document.getElementById('search-input').value='${p.n}';performSearch()"><div class="sug-icon">${ICONS[p.c]||"👔"}</div><div class="sug-info"><div class="sug-name">${p.n}</div><div class="sug-meta">${p.c} · ${fmtRp(p.pr)}</div></div></div>`).join("");
  box.classList.add("show");
}

async function performSearch(){
  const input=document.getElementById("search-input");
  const q=input.value.trim();
  if(!q)return;
  document.getElementById("search-suggestions").classList.remove("show");
  // Call Flask API
  const res=await apiPost('/api/search',{query:q});
  // Show results
  document.getElementById("search-query-display").textContent=q;
  document.getElementById("search-results").style.display="block";
  document.getElementById("search-result-info").innerHTML=`<div class="db-status" style="margin-bottom:1rem"><div class="db-indicator">✅ ${res.message}</div><div>Search ID: #${res.search_id} · ${res.count} produk ditemukan</div></div>`;
  if(res.results&&res.results.length){
    document.getElementById("search-results-grid").innerHTML=res.results.map(r=>{
      const p=PRODUCTS[r.pid];if(!p)return"";
      return productCard(r.pid);
    }).join("");
  }else{
    document.getElementById("search-results-grid").innerHTML='<div class="empty-keywords">Tidak ada produk ditemukan untuk "'+q+'"</div>';
  }
  input.value="";
  // Refresh all real-time sections
  refreshDashboard();
}

function closeSearchResults(){document.getElementById("search-results").style.display="none";}

// ═══ DASHBOARD REFRESH (from SQLite) ═══
async function refreshDashboard(){
  try{
    const[stats,kw,trend,best]=await Promise.all([apiGet('/api/stats'),apiGet('/api/keywords'),apiGet('/api/trending'),apiGet('/api/bestsellers')]);
    // Stats
    document.getElementById("stat-searches").textContent=fmtN(stats.total_searches);
    document.getElementById("stat-tokens").textContent=fmtN(stats.total_tokens);
    document.getElementById("db-msg").textContent=`${stats.total_searches} pencarian · ${stats.total_tokens} token · ${stats.products_searched}/25 produk dicari`;
    // Keywords
    renderKeywords(kw.keywords);
    // Trending
    renderTrending(trend.trending);
    // Bestsellers
    renderBestsellers(best.bestsellers);
    // Recent
    renderRecent(stats.recent_searches);
    // KW count
    document.getElementById("kw-count-tag").textContent=`Database: ${stats.unique_keywords} kata kunci`;
  }catch(e){console.error("Dashboard refresh error:",e);}
}

function renderKeywords(keywords){
  const el=document.getElementById("top-keywords");
  if(!keywords||!keywords.length){el.innerHTML='<div class="empty-keywords">🔍 Belum ada pencarian. Cari produk di search bar untuk memulai!</div>';return;}
  el.innerHTML='<div class="keywords-grid">'+keywords.map((k,i)=>`<div class="keyword-chip" onclick="document.getElementById('search-input').value='${k.keyword}';performSearch()"><span class="kw-rank">#${i+1}</span><span class="kw-text">${k.keyword}</span><span class="kw-count">${k.count}</span></div>`).join("")+'</div>';
}

function renderTrending(trending){
  const el=document.getElementById("trending-grid");
  const ranks=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"];
  if(!trending||!trending.length){el.innerHTML='<div class="empty-keywords" style="grid-column:1/-1">Belum ada data trending. Cari produk untuk mengisi!</div>';return;}
  el.innerHTML=trending.map((t,i)=>{
    const p=PRODUCTS[t.pid];if(!p)return"";
    const hasTokens=t.tokens>0;
    return`<div class="trend-card ${hasTokens?"":"no-tokens"}" onclick="openPrediction('${t.pid}')"><div class="trend-rank">${ranks[i]||"#"+(i+1)} #${i+1}</div><div class="trend-icon">${ICONS[p.c]||"👔"}</div><div class="trend-name">${p.n}</div><div class="trend-fire">${fmtRp(p.pr)}</div>${hasTokens?`<div class="trend-tokens">🎯 ${t.tokens} token</div>`:`<div style="font-size:.6rem;color:var(--text3);margin-top:.3rem">belum dicari</div>`}</div>`;
  }).join("");
}

function renderBestsellers(bestsellers){
  const el=document.getElementById("bestseller-grid");
  if(!bestsellers||!bestsellers.length){el.innerHTML='<div class="empty-keywords">Cari produk untuk melihat prediksi terlaris!</div>';return;}
  el.innerHTML=bestsellers.map(b=>{
    const p=PRODUCTS[b.pid];if(!p)return"";
    return`<div class="bs-card" onclick="openPrediction('${b.pid}')"><div class="bs-icon">${ICONS[p.c]||"👔"}</div><div class="bs-info"><div class="bs-name">${b.name}</div><div class="bs-cat">${b.cat} · 🎯 ${b.tokens} token · boost ${b.search_boost}x</div><div class="bs-stats"><div class="bs-stat">📅 <b>${b.pred_daily}</b>/hari</div><div class="bs-stat">📆 <b>${b.pred_weekly}</b>/minggu</div><div class="bs-stat">🗓️ <b>${b.pred_monthly}</b>/bulan</div></div></div><div class="bs-pred"><div class="bs-pred-val">${fmtRp(b.est_revenue)}</div><div class="bs-pred-lbl">Est. Revenue/bln</div></div></div>`;
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

// ═══ KPI ═══
function renderKPI(){
  document.getElementById("kpi-grid").innerHTML=`
    <div class="kpi-card"><div class="kpi-label">🟠 Unit Shopee</div><div class="kpi-val" style="color:var(--primary)">${fmtN(TOTALS.qty)}</div><div class="kpi-badge up">Data Shopee Indonesia</div></div>
    <div class="kpi-card"><div class="kpi-label">💰 Pendapatan Shopee</div><div class="kpi-val" style="font-size:1rem">${fmtRp(TOTALS.rev)}</div><div class="kpi-badge up">Apr 2025–Apr 2026</div></div>
    <div class="kpi-card"><div class="kpi-label">📦 Produk Terdaftar</div><div class="kpi-val">25</div><div class="kpi-badge up">Fashion Category</div></div>
    <div class="kpi-card"><div class="kpi-label">🗄️ Database Engine</div><div class="kpi-val" style="font-size:1rem">SQLite</div><div class="kpi-badge up">Real-time tracking</div></div>`;
}

// ═══ PRODUCT CARD ═══
function productCard(pid){
  const p=PRODUCTS[pid],up=p.wt>=0;
  return`<div class="product-card">
    <div class="product-img" onclick="openPrediction('${pid}')" style="cursor:pointer">${ICONS[p.c]||"👔"}<div class="product-trend-badge ${up?"up":"down"}">${up?"↑":"↓"}${Math.abs(p.wt)}%</div></div>
    <div class="product-info">
      <div class="product-name" onclick="openPrediction('${pid}')" style="cursor:pointer">${p.n}</div>
      <div class="product-cat">${p.c}</div>
      <div class="product-price">${fmtRp(p.pr)}</div>
      <div style="display:flex;gap:5px;margin-top:8px">
        <button class="btn-sm btn-view" onclick="openPrediction('${pid}')">👁️ Lihat</button>
        <button class="btn-sm btn-cart" onclick="addToCart('${pid}')">🛒 +Keranjang</button>
      </div>
    </div>
  </div>`;
}

function renderAllProducts(){
  const cats=[...new Set(Object.values(PRODUCTS).map(p=>p.c))].sort();
  const sel=document.getElementById("cat-filter");
  cats.forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o);});
  filterProducts();
}
function filterProducts(){
  const f=document.getElementById("cat-filter").value;
  document.getElementById("all-product-grid").innerHTML=Object.keys(PRODUCTS).filter(pid=>!f||PRODUCTS[pid].c===f).map(productCard).join("");
}

// ═══ PREDICTION ═══
function openPrediction(pid){
  showPage("prediction",document.querySelectorAll("nav button")[1]);
  document.getElementById("pred-select").value=pid;
  renderPrediction();
  recordAction(pid, 'view');
}
function fillSelect(){const sel=document.getElementById("pred-select");Object.entries(PRODUCTS).forEach(([pid,p])=>{const o=document.createElement("option");o.value=pid;o.textContent=p.n+" ("+p.c+")";sel.appendChild(o);});}

const charts={};
function dc(id){if(charts[id]){charts[id].destroy();delete charts[id];}}

async function renderPrediction(){
  const pid=document.getElementById("pred-select").value;
  if(!pid){document.getElementById("pred-content").style.display="none";document.getElementById("pred-empty").style.display="block";return;}
  document.getElementById("pred-content").style.display="block";
  document.getElementById("pred-empty").style.display="none";
  const p=PRODUCTS[pid];
  const live=PredEngine.predict(pid);
  // Get search-enhanced prediction from API
  let searchPred={tokens:0,search_boost:1};
  try{searchPred=await apiGet(`/api/predict/${pid}`);}catch(e){}

  document.getElementById("pred-cards").innerHTML=`
    <div class="pred-card" style="background:linear-gradient(135deg,#e0f2fe,#fff)"><div class="ico">👁️</div><div class="period">CTR (Klik)</div><div class="qty">${searchPred.ctr||0}%</div><div class="unit">Dari ${searchPred.tokens||0} pencarian</div><div class="conf-bar"><div class="conf-fill" style="width:${searchPred.ctr||0}%;background:#0ea5e9"></div></div><div class="conf-txt">Dilihat: ${searchPred.views||0} kali</div></div>
    <div class="pred-card" style="background:linear-gradient(135deg,#fef08a,#fff)"><div class="ico">🛒</div><div class="period">ATC Rate (Minat)</div><div class="qty">${searchPred.atc_rate||0}%</div><div class="unit">Masuk keranjang</div><div class="conf-bar"><div class="conf-fill" style="width:${searchPred.atc_rate||0}%;background:#eab308"></div></div><div class="conf-txt">Diminati: ${searchPred.cart_adds||0} kali</div></div>
    <div class="pred-card" style="background:linear-gradient(135deg,#dcfce7,#fff)"><div class="ico">💰</div><div class="period">Sales Rate</div><div class="qty">${searchPred.sales_rate||0}%</div><div class="unit">Konversi Terjual</div><div class="conf-bar"><div class="conf-fill" style="width:${searchPred.sales_rate||0}%;background:#22c55e"></div></div><div class="conf-txt">Terjual: ${searchPred.sales||0} unit</div></div>`;

  let labelHtml = "";
  if(searchPred.label_prediksi === 'Potensi Tinggi') {
    labelHtml = `<div style="background:#fef08a;color:#854d0e;padding:1rem;border-radius:8px;margin-bottom:1rem;font-weight:bold;display:flex;align-items:center;gap:10px">
      <span style="font-size:1.5rem">✨</span> 
      <div>Produk berstatus "Potensi Tinggi"! Banyak diminati tapi konversi penjualan masih rendah. <br><span style="font-size:0.8rem;font-weight:normal">💡 Solusi: Coba berikan promo diskon atau optimasi halaman checkout produk.</span></div>
    </div>`;
  }

  document.getElementById("rev-pred").innerHTML= labelHtml + `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin-bottom:.8rem">
    <div style="text-align:center;background:#fff7f3;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2"><div style="font-size:.68rem;color:var(--text3)">Prediksi Unit Harian</div><div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${live.p1d} / hari</div></div>
    <div style="text-align:center;background:#fff3e8;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2"><div style="font-size:.68rem;color:var(--text3)">Prediksi Unit Mingguan</div><div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${live.p1w} / minggu</div></div>
    <div style="text-align:center;background:#fff0de;border-radius:8px;padding:.7rem;border:1px solid #ffd5c2"><div style="font-size:.68rem;color:var(--text3)">Estimasi Revenue Bln</div><div style="font-size:.95rem;font-weight:800;color:var(--primary);font-family:'Space Grotesk'">${fmtRp(live.p1m*p.pr)}</div></div></div>`;

  // Conversion chart
  dc("conv");
  charts["conv"]=new Chart(document.getElementById("chart-conversion"),{
    type:"bar",
    data:{
      labels:["👁️ Klik (Views)","🛒 Minat (Cart)","💰 Hasil (Sales)"],
      datasets:[{
        label:"Jumlah",
        data:[searchPred.views||0, searchPred.cart_adds||0, searchPred.sales||0],
        backgroundColor:["rgba(14, 165, 233, 0.8)","rgba(234, 179, 8, 0.8)","rgba(34, 197, 94, 0.8)"],
        borderRadius:5
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{
        y:{beginAtZero:true},
        x:{ticks:{font:{size:11,weight:'bold'}}}
      }
    }
  });
  document.getElementById("live-pred-badge").textContent="🔴 LIVE · "+new Date().toLocaleTimeString("id-ID");
}

// ═══ ANALYTICS ═══
async function renderAnalytics(){
  // Shopee monthly
  dc("aPlat");
  charts["aPlat"]=new Chart(document.getElementById("chart-plat-monthly"),{type:"line",data:{labels:ML,datasets:[{label:"Shopee Unit",data:ML.map(m=>SHOPEE_MONTHLY[m]?.qty||0),borderColor:"#ee4d2d",backgroundColor:"rgba(238,77,45,0.08)",fill:true,tension:.4,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10}}}},scales:{y:{beginAtZero:true},x:{ticks:{maxRotation:45,font:{size:9}}}}}});
  // Token chart
  dc("aTok");
  let trendData = {};
  try{
    const trend=await apiGet('/api/trending');
    trend.trending.forEach(r => { trendData[r.pid] = r.tokens; });
    const top10=trend.trending.filter(t=>t.tokens>0).slice(0,10);
    charts["aTok"]=new Chart(document.getElementById("chart-search-tokens"),{type:"doughnut",data:{labels:top10.map(t=>t.name.substring(0,15)),datasets:[{data:top10.map(t=>t.tokens),backgroundColor:["#ee4d2d","#ff6a2a","#ff8c57","#22c55e","#2196f3","#9c27b0","#ff9800","#00bcd4","#795548","#f06292"],borderWidth:2,borderColor:"#fff"}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{font:{size:8},boxWidth:8}}}}});
  }catch(e){}

  // Correlation Chart: Search Tokens vs Prediction (Kompleks: Line + Bar + Area + Multiplier)
  dc("aCorr");
  try {
    let bestData = [];
    try { const b = await apiGet('/api/bestsellers'); bestData = b.bestsellers || []; } catch(e){}
    
    let corrData = [];
    Object.entries(PRODUCTS).forEach(([pid, p]) => {
      let b = bestData.find(x => x.pid === pid);
      if (b) {
        corrData.push({ name: p.n, tokens: b.tokens, pred: b.pred_monthly, boost: b.search_boost });
      } else {
        let tk = trendData[pid] || 0;
        let basePred = PredEngine.predict(pid).p1m;
        corrData.push({ name: p.n, tokens: tk, pred: basePred, boost: 1.0 });
      }
    });

    // Sort by tokens ascending to visually show that MORE TOKENS = HIGHER PREDICTION
    corrData.sort((a,b) => a.tokens - b.tokens || a.pred - b.pred);
    const displayData = corrData.slice(-20); // Ambil 20 data teratas agar lebih rapi

    charts["aCorr"] = new Chart(document.getElementById("chart-search-vs-pred"), {
      type: "line",
      data: {
        labels: displayData.map(c => c.name.substring(0,15)),
        datasets: [
          {
            type: "bar",
            label: "Jumlah Pencarian (Token)",
            data: displayData.map(c => c.tokens),
            backgroundColor: "rgba(34, 197, 94, 0.35)",
            borderColor: "rgba(34, 197, 94, 0.8)",
            borderWidth: 1,
            borderRadius: 4,
            yAxisID: "y",
            order: 2
          },
          {
            type: "line",
            label: "Prediksi Terjual (Unit/Bulan)",
            data: displayData.map(c => c.pred),
            borderColor: "#ee4d2d",
            backgroundColor: "rgba(238, 77, 45, 0.15)",
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: "#fff",
            pointBorderColor: "#ee4d2d",
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            yAxisID: "y1",
            order: 1
          },
          {
            type: "line",
            label: "AI Boost Multiplier (x)",
            data: displayData.map(c => c.boost),
            borderColor: "#3b82f6",
            borderWidth: 2,
            borderDash: [5, 5],
            pointRadius: 0,
            yAxisID: "y2",
            order: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", labels: { usePointStyle: true, boxWidth: 8, font: { size: 11 } } },
          tooltip: {
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            titleColor: '#1f2937',
            bodyColor: '#4b5563',
            borderColor: '#e5e7eb',
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: function(ctx) {
                let d = ctx.raw;
                if (ctx.datasetIndex === 0) return ` 🔍 Pencarian: ${d} kali (Tokens)`;
                if (ctx.datasetIndex === 1) return ` 📦 Prediksi: ${d} unit terjual`;
                if (ctx.datasetIndex === 2) return ` 🚀 AI Boost: ${d}x multiplier`;
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45 } },
          y: { 
            type: "linear", display: true, position: "left", 
            title: { display: true, text: "Jumlah Pencarian", font: { weight: 'bold', size: 11, color: "#16a34a" } }, 
            beginAtZero: true 
          },
          y1: { 
            type: "linear", display: true, position: "right", 
            title: { display: true, text: "Prediksi Terjual", font: { weight: 'bold', size: 11, color: "#ee4d2d" } }, 
            beginAtZero: true, 
            grid: { drawOnChartArea: false } 
          },
          y2: { 
            type: "linear", display: false, min: 0, max: 8
          }
        }
      }
    });
  } catch(e) { console.error("Error drawing correlation chart", e); }

  // Summary table
  const tbl=document.getElementById("summary-table");
  tbl.innerHTML=`<thead><tr><th>Produk</th><th>Kat.</th><th>Shopee Qty</th><th>Shopee Rev</th><th>🎯 Token</th><th>Pred/bln</th><th>Tren</th></tr></thead>
  <tbody>${Object.entries(PRODUCTS).sort((a,b)=>(trendData[b[0]]||0)-(trendData[a[0]]||0)).map(([pid,p])=>{const l=PredEngine.predict(pid);const tk=trendData[pid]||0;return`<tr><td><b style="cursor:pointer;color:var(--primary)" onclick="openPrediction('${pid}')">${p.n}</b></td><td>${p.c}</td><td>${fmtN(p.sp_qty)}</td><td style="font-size:.7rem">${fmtRp(p.sp_rev)}</td><td style="font-weight:700;color:var(--primary)">${tk}</td><td><b>${l.p1m}</b></td><td style="color:${p.wt>=0?"#16a34a":"#dc2626"}">${p.wt>=0?"↑":"↓"}${Math.abs(p.wt)}%</td></tr>`;}).join("")}</tbody>`;
}

// ═══ CHATBOT (Gemini AI) ═══
let chatOpen = false;
let chatHistory = []; // [{role, text}]

function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById("chat-panel").classList.toggle("open", chatOpen);
  if (chatOpen) document.getElementById("chat-input").focus();
}

function sendChip(btn) {
  document.getElementById("chat-input").value = btn.textContent;
  sendMsg();
}

async function sendMsg() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  input.disabled = true;
  document.querySelector(".chat-send").disabled = true;

  appendMsg(msg, "user");
  chatHistory.push({ role: "user", text: msg });
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history: chatHistory.slice(0, -1) })
    });
    const data = await res.json();
    removeTyping();

    if (data.reply) {
      const formatted = formatMarkdown(data.reply);
      appendMsg(formatted, "bot");
      chatHistory.push({ role: "bot", text: data.reply });
      // Batasi history agar tidak terlalu besar
      if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
    } else {
      appendMsg("⚠️ " + (data.error || "Terjadi kesalahan. Coba lagi."), "bot");
    }
  } catch (e) {
    removeTyping();
    appendMsg("⚠️ Tidak bisa menghubungi server. Pastikan server berjalan.", "bot");
  }

  input.disabled = false;
  document.querySelector(".chat-send").disabled = false;
  input.focus();
}

function formatMarkdown(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "<b>$1</b>")
    .replace(/\*(.*?)\*/g, "<i>$1</i>")
    .replace(/`(.*?)`/g, "<code style='background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:0.85em'>$1</code>")
    .replace(/^- (.+)$/gm, "• $1")
    .replace(/\n/g, "<br>");
}

function appendMsg(text, role) {
  const msgs = document.getElementById("chat-msgs");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.innerHTML = `<div class="msg-av">${role === "bot" ? "🤖" : "👤"}</div><div class="msg-bubble">${text}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function showTyping() {
  const msgs = document.getElementById("chat-msgs");
  const div = document.createElement("div");
  div.className = "msg bot";
  div.id = "typing";
  div.innerHTML = '<div class="msg-av">🤖</div><div class="msg-bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById("typing");
  if (t) t.remove();
}

// ═══ KERANJANG BELANJA (CART) ═══
let cart = [];
function toggleCart() {
  document.getElementById("cart-sidebar").classList.toggle("open");
}
function addToCart(pid) {
  const p = PRODUCTS[pid];
  const item = cart.find(x => x.pid === pid);
  if(item) item.qty++; else cart.push({pid, qty:1, n:p.n, pr:p.pr});
  renderCart();
  recordAction(pid, 'cart');
  document.getElementById("cart-badge").innerText = cart.reduce((s,c)=>s+c.qty, 0);
  document.getElementById("cart-badge").style.display = "block";
}
function renderCart() {
  const el = document.getElementById("cart-items");
  if(!cart.length) { 
    el.innerHTML = "<p style='text-align:center;color:#999;margin-top:2rem'>Keranjang kosong</p>"; 
    document.getElementById("cart-total").innerText="Rp 0"; 
    return; 
  }
  
  el.innerHTML = cart.map((c, i) => `
    <div class="cart-item" style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding:10px 0;">
      <div>
        <div style="font-weight:600;font-size:0.85rem;margin-bottom:4px">${c.n}</div>
        <div style="font-size:0.8rem;color:#666">${fmtRp(c.pr)} x ${c.qty}</div>
      </div>
      <button onclick="cart.splice(${i},1);renderCart();document.getElementById('cart-badge').innerText=cart.reduce((s,c)=>s+c.qty,0);" style="border:none;background:none;color:red;cursor:pointer;font-size:1.2rem">🗑️</button>
    </div>
  `).join("");
  const total = cart.reduce((s, c) => s + (c.pr * c.qty), 0);
  document.getElementById("cart-total").innerText = fmtRp(total);
}
async function checkout() {
  if(!cart.length) return alert("Keranjang kosong!");
  for(let c of cart) {
    for(let i=0; i<c.qty; i++) await apiPost('/api/action', {pid: c.pid, action: 'buy'});
  }
  alert(`✅ Checkout berhasil untuk ${cart.length} produk!\n\nSales Rate produk telah diperbarui di analitik.`);
  cart = [];
  renderCart();
  document.getElementById("cart-badge").style.display = "none";
  toggleCart();
  refreshDashboard();
}
async function recordAction(pid, action) {
  try { await apiPost('/api/action', {pid, action}); } catch(e){}
}

// ═══ INIT ═══
window.addEventListener("load",()=>{
  fillSelect();
  renderKPI();
  renderAllProducts();
  refreshDashboard();
  // Auto-refresh every 10 seconds
  setInterval(refreshDashboard,10000);
});
