// State management
let currentTab = 'orders';
let currentPeriod = 'all';
let currentExpensePeriod = 'all';
let currentPage = 1;
const pageSize = 50;
let debounceTimeout = null;
let debounceExpenseTimeout = null;
let currentOrdersCache = [];
let currentAdsCache = [];
let currentExpensesCache = [];

// Chart instances
let trendChartInstance = null;
let hourlyChartInstance = null;
let dayOfWeekChartInstance = null;
let monthlyChartInstance = null;
let cityChartInstance = null;

let adsRoasSalesChartInstance = null;
let adsPeriodTrendChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  setupDropZone();
  loadAllData();
});

function formatRp(val) {
  if (val === null || val === undefined || isNaN(val)) return 'Rp 0';
  return 'Rp ' + Math.round(val).toLocaleString('id-ID');
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  const bgColors = {
    success: 'bg-emerald-50 border-emerald-300 text-emerald-800 shadow-md',
    error: 'bg-rose-50 border-rose-300 text-rose-800 shadow-md',
    info: 'bg-slate-50 border-slate-300 text-slate-800 shadow-md'
  };
  const iconNames = {
    success: 'check-circle-2',
    error: 'alert-triangle',
    info: 'info'
  };

  toast.className = `flex items-center gap-2.5 px-4 py-3 rounded-xl border text-xs shadow-md backdrop-blur transition-all duration-300 transform translate-y-2 opacity-0 ${bgColors[type] || bgColors.info}`;
  toast.innerHTML = `
    <i data-lucide="${iconNames[type] || 'info'}" class="w-4 h-4 shrink-0"></i>
    <span>${message}</span>
  `;

  container.appendChild(toast);
  lucide.createIcons();

  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switcher (Orders vs Bookkeeping vs Ads)
function switchTab(tab) {
  currentTab = tab;
  const btnOrders = document.getElementById('tabBtnOrders');
  const btnBookkeeping = document.getElementById('tabBtnBookkeeping');
  const btnAds = document.getElementById('tabBtnAds');
  
  const contentOrders = document.getElementById('tabContentOrders');
  const contentBookkeeping = document.getElementById('tabContentBookkeeping');
  const contentAds = document.getElementById('tabContentAds');

  const activeClass = 'py-3 px-1 text-xs sm:text-sm font-bold border-b-2 border-amber-500 text-amber-600 flex items-center gap-2 transition-colors';
  const inactiveClass = 'py-3 px-1 text-xs sm:text-sm font-semibold border-b-2 border-transparent text-slate-500 hover:text-slate-900 flex items-center gap-2 transition-colors';

  // Reset all
  btnOrders.className = inactiveClass;
  if (btnBookkeeping) btnBookkeeping.className = inactiveClass;
  btnAds.className = inactiveClass;

  contentOrders.classList.add('hidden');
  if (contentBookkeeping) contentBookkeeping.classList.add('hidden');
  contentAds.classList.add('hidden');

  if (tab === 'orders') {
    btnOrders.className = activeClass;
    contentOrders.classList.remove('hidden');
  } else if (tab === 'bookkeeping') {
    if (btnBookkeeping) btnBookkeeping.className = activeClass;
    if (contentBookkeeping) contentBookkeeping.classList.remove('hidden');
    loadBookkeepingData();
  } else if (tab === 'ads') {
    btnAds.className = activeClass;
    contentAds.classList.remove('hidden');
    loadAdsData();
  }
  lucide.createIcons();
}

function loadAllData() {
  loadStats();
  loadOrders();
  loadCharts();
  loadBookkeepingData();
  loadAdsData();
}

function getFilterParams() {
  const bolt = document.getElementById('filterBolt').value;
  const model = document.getElementById('filterModel').value;
  const province = document.getElementById('filterProvince').value;
  const status = document.getElementById('filterStatus').value;
  const search = document.getElementById('searchInput').value;

  const params = new URLSearchParams({
    period: currentPeriod,
    bolt: bolt,
    model: model,
    province: province,
    status: status,
    search: search
  });
  return params;
}

async function loadStats() {
  try {
    const params = getFilterParams();
    const res = await fetch(`/api/stats?${params.toString()}`);
    const data = await res.json();

    document.getElementById('statOmzet').innerText = formatRp(data.total_omzet);
    document.getElementById('statOrdersCount').innerText = `${data.total_orders || 0} Transaksi (${data.total_items || 0} item)`;

    document.getElementById('statShopeeDeductions').innerText = `-` + formatRp(data.total_shopee_deductions);
    document.getElementById('statNetPayout').innerText = formatRp(data.total_net_payout);

    document.getElementById('statTotalHpp').innerText = formatRp(data.total_hpp);
    document.getElementById('subHppCover').innerText = formatRp(data.total_hpp_cover);
    document.getElementById('subHppBolt').innerText = formatRp(data.total_hpp_bolt);

    document.getElementById('statProfit').innerText = formatRp(data.total_profit);
    document.getElementById('statMargin').innerText = `${data.avg_margin_pct || 0}%`;

    document.getElementById('statCoverQty').innerText = data.total_cover_qty || 0;
    document.getElementById('statBoltQty').innerText = data.total_bolt_qty || 0;
    document.getElementById('statAvgProfit').innerText = `Rata-rata: ${formatRp(data.avg_profit_per_order)}/ord`;

    updateProvinceDropdown(data.available_provinces || []);
  } catch (err) {
    console.error('Error loading stats:', err);
  }
}

function updateProvinceDropdown(provinces) {
  const select = document.getElementById('filterProvince');
  const currentVal = select.value;
  
  let options = '<option value="all">📍 Semua Provinsi</option>';
  provinces.forEach(p => {
    options += `<option value="${p}">${p}</option>`;
  });
  select.innerHTML = options;
  select.value = currentVal;
}

async function loadOrders() {
  try {
    const params = getFilterParams();
    params.set('page', currentPage);
    params.set('limit', pageSize);

    const res = await fetch(`/api/orders?${params.toString()}`);
    const data = await res.json();
    currentOrdersCache = data.orders || [];

    document.getElementById('tableRecordCount').innerText = `Menampilkan ${data.orders.length} dari ${data.total} transaksi`;
    document.getElementById('paginationInfo').innerText = `Halaman ${data.page} dari ${data.total_pages || 1}`;
    
    document.getElementById('btnPrevPage').disabled = data.page <= 1;
    document.getElementById('btnNextPage').disabled = data.page >= data.total_pages;

    const tbody = document.getElementById('ordersTableBody');
    if (!data.orders || data.orders.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="12" class="py-12 text-center text-slate-500">
            <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
            Tidak ada transaksi yang cocok dengan filter.
          </td>
        </tr>
      `;
      lucide.createIcons();
      return;
    }

    tbody.innerHTML = data.orders.map((o, idx) => {
      const isBolt = o.has_bolt === 1;
      const boltBadge = isBolt
        ? '<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">🔩 + Baut</span>'
        : '<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">🛡️ Tanpa Baut</span>';

      const modelBadge = o.model_type === 'Model New'
        ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">New</span>'
        : (o.model_type === 'Model Old' ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200">Old</span>' : '');

      const packBadge = o.pack_type === 'Extra Bubble'
        ? '<span class="px-1.5 py-0.5 rounded text-[10px] text-slate-700 bg-slate-100 border border-slate-200 font-medium">Bubble</span>'
        : '';

      const statusColors = {
        'Selesai': 'bg-emerald-50 text-emerald-700 border-emerald-200',
        'Telah Dikirim': 'bg-blue-50 text-blue-700 border-blue-200',
        'Sedang Dikirim': 'bg-amber-50 text-amber-700 border-amber-200',
        'Perlu Dikirim': 'bg-purple-50 text-purple-700 border-purple-200',
        'Batal': 'bg-rose-50 text-rose-700 border-rose-200'
      };
      const statusColor = statusColors[o.order_status] || 'bg-slate-100 text-slate-700 border-slate-200';

      const dateParts = (o.order_created_at || '').split(' ');
      const dateStr = dateParts[0] || '-';
      const timeStr = dateParts[1] ? `${dateParts[1]} WIB` : '-';

      const deductionTooltip = `Admin 8.25%: -${formatRp(o.shopee_admin_fee)} | Proses: -${formatRp(o.shopee_process_fee)} | Ongkir XTRA 5.5%: -${formatRp(o.shopee_gratis_ongkir_xtra)} | Iklan 3.33%: -${formatRp(o.shopee_promo_fee)} | PPh 0.5%: -${formatRp(o.shopee_pph22)}`;

      return `
        <tr class="hover:bg-slate-50 transition group">
          <td class="py-3.5 px-4">
            <div class="font-mono-num font-bold text-slate-900">${o.order_no}</div>
            <div class="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
              ${o.tracking_no ? `<span class="text-slate-600 font-mono-num">${o.tracking_no}</span>` : '<span>-</span>'}
            </div>
            <span class="inline-block mt-1 px-2 py-0.5 rounded-full text-[9px] font-semibold border ${statusColor}">
              ${o.order_status || '-'}
            </span>
          </td>

          <td class="py-3.5 px-4">
            <div class="flex items-center gap-1.5 font-mono-num font-bold text-amber-700 text-xs">
              <i data-lucide="clock" class="w-3.5 h-3.5 text-amber-600"></i>
              ${timeStr}
            </div>
            <div class="text-[11px] text-slate-500 mt-0.5 font-medium">
              ${dateStr}
            </div>
          </td>

          <td class="py-3.5 px-4 max-w-[210px]">
            <div class="font-bold text-slate-900 flex items-center gap-1 truncate" title="${escapeHtml(o.city || '')}">
              <i data-lucide="map-pin" class="w-3.5 h-3.5 text-emerald-600 shrink-0"></i>
              <span>${escapeHtml(o.city || '-')}</span>
            </div>
            <div class="text-[11px] text-slate-500 font-medium truncate">
              ${escapeHtml(o.province || '-')}
            </div>
          </td>

          <td class="py-3.5 px-4">
            <div class="flex items-center gap-1.5 flex-wrap">
              ${modelBadge}
              ${boltBadge}
              ${packBadge}
            </div>
            <div class="text-[11px] text-slate-600 mt-1 truncate max-w-[170px]" title="${escapeHtml(o.variation_name)}">
              ${escapeHtml(o.variation_name)}
            </div>
          </td>

          <td class="py-3.5 px-3 text-center font-mono-num font-bold text-slate-900">${o.qty}</td>
          <td class="py-3.5 px-4 text-right font-mono-num font-bold text-slate-900">${formatRp(o.subtotal)}</td>
          <td class="py-3.5 px-4 text-right font-mono-num text-rose-600 font-medium cursor-help" title="${deductionTooltip}">
            -${formatRp(o.total_shopee_deductions)}
          </td>
          <td class="py-3.5 px-4 text-right font-mono-num font-semibold text-blue-700">${formatRp(o.net_payout)}</td>
          <td class="py-3.5 px-4 text-right font-mono-num text-slate-700 font-medium">
            ${formatRp(o.total_hpp)}
          </td>
          <td class="py-3.5 px-4 text-right font-mono-num font-black text-emerald-700">${formatRp(o.profit)}</td>
          <td class="py-3.5 px-3 text-center font-mono-num text-[11px]">
            <span class="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold">${Math.round(o.margin_pct)}%</span>
          </td>
          <td class="py-3.5 px-3 text-center">
            <button onclick="openDetailModalByIndex(${idx})" class="btn-tactile p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 border border-slate-200 transition" title="Lihat Jam, Lokasi & Rincian Potongan Shopee">
              <i data-lucide="eye" class="w-4 h-4"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Error loading orders:', err);
  }
}

async function loadCharts() {
  try {
    const params = getFilterParams();
    const res = await fetch(`/api/charts?${params.toString()}`);
    const data = await res.json();

    if (data.best_insights) {
      document.getElementById('pillBestDay').innerText = data.best_insights.best_day;
      document.getElementById('pillBestHour').innerText = data.best_insights.best_hour;
      document.getElementById('pillBestMonth').innerText = data.best_insights.best_month;
      document.getElementById('pillBestCity').innerText = data.best_insights.best_city;

      const pProd = document.getElementById('pillBestProduct');
      if (pProd) pProd.innerText = data.best_insights.best_product || '-';

      const pVar = document.getElementById('pillBestVariant');
      if (pVar) pVar.innerText = data.best_insights.best_variant || '-';

      document.getElementById('badgeBestDayHeader').innerText = data.best_insights.best_day;
      document.getElementById('badgeBestHourHeader').innerText = data.best_insights.best_hour;
      document.getElementById('badgeBestMonthHeader').innerText = data.best_insights.best_month;
      document.getElementById('badgeBestCityHeader').innerText = data.best_insights.best_city;
    }

    renderDayOfWeekChart(data.days_of_week || []);
    renderHourlyChart(data.hourly || []);
    renderMonthlyChart(data.monthly || []);
    renderCityChart(data.cities || []);

    // Render Produk & Varian Terlaris
    renderTopProducts(data.top_products || [], data.models_summary || []);
    renderTopVariants(data.top_variants || [], data.bolts_summary || []);

  } catch (err) {
    console.error('Error loading charts:', err);
  }
}

// 0. Render Top Products & Top Variants (Light Mode)
function renderTopProducts(products, modelsSummary) {
  const container = document.getElementById('topProductsList');
  const countBadge = document.getElementById('badgeTopProductCount');
  if (!container) return;

  if (countBadge) countBadge.innerText = `${products.length} Produk`;

  if (!products || products.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-400 text-center py-6">Belum ada data produk.</p>';
    return;
  }

  const maxQty = Math.max(...products.map(p => p.total_qty), 1);
  const totalAllQty = products.reduce((sum, p) => sum + p.total_qty, 0) || 1;

  let html = '';
  products.forEach((p, idx) => {
    const rank = idx + 1;
    const rankBadgeClass = rank === 1 
      ? 'bg-amber-500 text-white font-extrabold shadow-sm' 
      : (rank === 2 ? 'bg-slate-200 text-slate-800 font-bold' : 'bg-slate-100 text-slate-600 font-semibold border border-slate-200');
    
    const pctShare = Math.round((p.total_qty / totalAllQty) * 100);
    const barWidth = Math.max(Math.round((p.total_qty / maxQty) * 100), 5);

    html += `
      <div class="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200 hover:border-amber-400 transition group">
        <div class="flex items-start gap-3 justify-between">
          <div class="flex items-start gap-2.5 min-w-0 flex-1">
            <span class="w-5 h-5 rounded-md flex items-center justify-center text-[10px] shrink-0 ${rankBadgeClass}">
              #${rank}
            </span>
            <div class="min-w-0 flex-1">
              <h4 class="text-xs font-bold text-slate-900 group-hover:text-amber-700 transition truncate" title="${escapeHtml(p.product_name)}">
                ${escapeHtml(p.product_name)}
              </h4>
              <div class="flex items-center gap-3 text-[11px] text-slate-500 mt-1 font-medium">
                <span><b class="text-slate-800">${p.orders_count}</b> transaksi</span>
                <span>•</span>
                <span>Omzet: <b class="text-slate-800">${formatRp(p.total_omzet)}</b></span>
                <span>•</span>
                <span>Laba: <b class="text-emerald-700 font-mono-num font-bold">${formatRp(p.total_profit)}</b> (${p.margin_pct}%)</span>
              </div>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="text-sm font-bold font-mono-num text-amber-600">${p.total_qty}</span>
            <span class="text-[10px] text-slate-500 block font-medium">${pctShare}% share</span>
          </div>
        </div>
        
        <!-- Progress Bar -->
        <div class="w-full bg-slate-200 rounded-full h-1.5 mt-2.5 overflow-hidden">
          <div class="bg-amber-500 h-1.5 rounded-full" style="width: ${barWidth}%"></div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;

  // Render Model Summary Pills
  const modelContainer = document.getElementById('modelSummaryPills');
  if (modelContainer && modelsSummary) {
    let pillsHtml = '';
    modelsSummary.forEach(m => {
      const share = Math.round((m.total_qty / totalAllQty) * 100);
      pillsHtml += `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-sm font-medium">
          <span class="font-bold text-amber-700">${m.model_type}</span>: 
          <b class="text-slate-900">${m.total_qty} unit</b> <span class="text-[10px] text-slate-500">(${share}%)</span>
        </span>
      `;
    });
    modelContainer.innerHTML = pillsHtml || '<span class="text-slate-400">-</span>';
  }
}

function renderTopVariants(variants, boltsSummary) {
  const container = document.getElementById('topVariantsList');
  const countBadge = document.getElementById('badgeTopVariantCount');
  if (!container) return;

  if (countBadge) countBadge.innerText = `${variants.length} Variasi`;

  if (!variants || variants.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-400 text-center py-6">Belum ada data variasi.</p>';
    return;
  }

  const maxQty = Math.max(...variants.map(v => v.total_qty), 1);
  const totalAllQty = variants.reduce((sum, v) => sum + v.total_qty, 0) || 1;

  let html = '';
  variants.forEach((v, idx) => {
    const rank = idx + 1;
    const rankBadgeClass = rank === 1 
      ? 'bg-cyan-600 text-white font-extrabold shadow-sm' 
      : (rank === 2 ? 'bg-slate-200 text-slate-800 font-bold' : 'bg-slate-100 text-slate-600 font-semibold border border-slate-200');

    const boltBadge = v.has_bolt === 1 
      ? '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">🔩 + Baut</span>' 
      : '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-200 text-slate-700 border border-slate-300">🛡️ Tanpa Baut</span>';

    const packBadge = v.pack_type 
      ? `<span class="px-1.5 py-0.5 rounded text-[10px] bg-white text-slate-700 border border-slate-200 shadow-sm font-medium">${v.pack_type}</span>` 
      : '';

    const modelBadge = v.model_type
      ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">${v.model_type}</span>`
      : '';

    const pctShare = Math.round((v.total_qty / totalAllQty) * 100);
    const barWidth = Math.max(Math.round((v.total_qty / maxQty) * 100), 5);

    html += `
      <div class="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200 hover:border-cyan-500 transition group">
        <div class="flex items-start gap-3 justify-between">
          <div class="flex items-start gap-2.5 min-w-0 flex-1">
            <span class="w-5 h-5 rounded-md flex items-center justify-center text-[10px] shrink-0 ${rankBadgeClass}">
              #${rank}
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-1.5 mb-1">
                ${modelBadge}
                ${boltBadge}
                ${packBadge}
              </div>
              <h4 class="text-xs font-bold text-slate-900 group-hover:text-cyan-700 transition truncate" title="${escapeHtml(v.variation_name)}">
                ${escapeHtml(v.variation_name)}
              </h4>
              <div class="flex items-center gap-3 text-[11px] text-slate-500 mt-1 font-medium">
                <span>Omzet: <b class="text-slate-800">${formatRp(v.total_omzet)}</b></span>
                <span>•</span>
                <span>Laba: <b class="text-emerald-700 font-mono-num font-bold">${formatRp(v.total_profit)}</b> (${v.margin_pct}%)</span>
              </div>
            </div>
          </div>
          <div class="text-right shrink-0">
            <span class="text-sm font-bold font-mono-num text-cyan-700">${v.total_qty}</span>
            <span class="text-[10px] text-slate-500 block font-medium">${pctShare}% share</span>
          </div>
        </div>
        
        <!-- Progress Bar -->
        <div class="w-full bg-slate-200 rounded-full h-1.5 mt-2.5 overflow-hidden">
          <div class="bg-cyan-600 h-1.5 rounded-full" style="width: ${barWidth}%"></div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;

  // Render Bolt Summary Pills
  const boltContainer = document.getElementById('boltSummaryPills');
  if (boltContainer && boltsSummary) {
    let pillsHtml = '';
    boltsSummary.forEach(b => {
      const share = Math.round((b.total_qty / totalAllQty) * 100);
      const label = b.has_bolt === 1 ? '🔩 Dengan Baut' : '🛡️ Tanpa Baut';
      const color = b.has_bolt === 1 ? 'text-amber-800' : 'text-slate-700';
      pillsHtml += `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-sm font-medium">
          <span class="font-bold ${color}">${label}</span>: 
          <b class="text-slate-900">${b.total_qty} unit</b> <span class="text-[10px] text-slate-500">(${share}%)</span>
        </span>
      `;
    });
    boltContainer.innerHTML = pillsHtml || '<span class="text-slate-400">-</span>';
  }
}

// 1. Day of Week Chart (Light Mode)
function renderDayOfWeekChart(dowData) {
  const ctx = document.getElementById('dayOfWeekChart').getContext('2d');
  const labels = dowData.map(d => d.day_name);
  const qtyData = dowData.map(d => d.total_qty);
  const profitData = dowData.map(d => d.profit);

  if (dayOfWeekChartInstance) dayOfWeekChartInstance.destroy();

  dayOfWeekChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Unit Terjual',
          data: qtyData,
          backgroundColor: function(c) { return c.raw > 0 ? '#F59E0B' : '#E2E8F0'; },
          borderRadius: 6,
          barPercentage: 0.6
        },
        {
          label: 'Laba Bersih Real (Rp)',
          data: profitData,
          type: 'line',
          borderColor: '#059669',
          borderWidth: 2.5,
          tension: 0.3,
          yAxisID: 'yProfit'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 10, weight: 'bold' } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, color: '#64748B', font: { size: 9 } }, grid: { color: 'rgba(0, 0, 0, 0.05)' } },
        yProfit: { position: 'right', beginAtZero: true, grid: { display: false }, ticks: { color: '#059669', font: { size: 9 } } }
      }
    }
  });
}

// 2. Hourly Chart (Light Mode)
function renderHourlyChart(hourlySlots) {
  const ctx = document.getElementById('hourlyChart').getContext('2d');
  const labels = hourlySlots.map(h => `${h.hour}:00`);
  const qtyData = hourlySlots.map(h => h.total_qty);

  if (hourlyChartInstance) hourlyChartInstance.destroy();

  hourlyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Unit Terjual',
        data: qtyData,
        backgroundColor: function(c) { return c.raw > 0 ? '#3B82F6' : '#E2E8F0'; },
        borderRadius: 4,
        barPercentage: 0.7
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 9 }, maxRotation: 0, callback: function(val, idx) { return idx % 3 === 0 ? labels[idx] : ''; } } },
        y: { beginAtZero: true, ticks: { stepSize: 1, color: '#64748B', font: { size: 9 } }, grid: { color: 'rgba(0, 0, 0, 0.05)' } }
      }
    }
  });
}

// 3. Monthly Chart (Light Mode)
function renderMonthlyChart(monthData) {
  const ctx = document.getElementById('monthlyChart').getContext('2d');
  const labels = monthData.map(m => m.label || m.month);
  const omzetData = monthData.map(m => m.omzet);
  const profitData = monthData.map(m => m.profit);

  if (monthlyChartInstance) monthlyChartInstance.destroy();

  monthlyChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        { label: 'Omzet Subtotal', data: omzetData, backgroundColor: '#8B5CF6', borderRadius: 6, barPercentage: 0.5 },
        { label: 'Laba Bersih Real', data: profitData, backgroundColor: '#059669', borderRadius: 6, barPercentage: 0.5 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 10, weight: 'bold' } } },
        y: { grid: { color: 'rgba(0, 0, 0, 0.05)' }, ticks: { color: '#64748B', font: { size: 9 }, callback: function(v) { return 'Rp ' + (v / 1000) + 'k'; } } }
      }
    }
  });
}

// 4. City Chart (Light Mode)
function renderCityChart(cities) {
  const ctx = document.getElementById('cityChart').getContext('2d');
  const labels = cities.map(c => c.city.replace('KAB. ', '').replace('KOTA ', ''));
  const qtyData = cities.map(c => c.total_qty);

  if (cityChartInstance) cityChartInstance.destroy();

  cityChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{ label: 'Unit Terjual', data: qtyData, backgroundColor: '#059669', borderRadius: 4, barPercentage: 0.65 }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 1, color: '#64748B', font: { size: 9 } }, grid: { color: 'rgba(0, 0, 0, 0.05)' } },
        y: { grid: { display: false }, ticks: { color: '#0F172A', font: { size: 10, weight: 'bold' } } }
      }
    }
  });
}

// ==================== SHOPEE ADS MODULE ====================

async function loadAdsData() {
  try {
    await Promise.all([
      loadAdsStats(),
      loadAdsHistory(),
      loadAdsCharts()
    ]);
  } catch (err) {
    console.error('Error loading ads data:', err);
  }
}

async function loadAdsStats() {
  try {
    const res = await fetch('/api/ads/stats');
    const d = await res.json();

    document.getElementById('adsTotalSpend').innerText = formatRp(d.total_ad_spend);
    document.getElementById('adsCampaignCount').innerText = `${d.total_campaign_records || 0} Riwayat Iklan (${d.total_periods || 0} Periode)`;

    document.getElementById('adsTotalGmv').innerText = formatRp(d.total_ad_gmv);
    document.getElementById('adsTotalUnits').innerText = `${d.total_units_sold || 0} Unit`;
    document.getElementById('adsTotalConversions').innerText = `${d.total_conversions || 0} Pesanan dari Iklan`;

    document.getElementById('adsOverallRoas').innerText = `${d.overall_roas || 0}x`;
    document.getElementById('adsOverallAcos').innerText = `${d.overall_acos_pct || 0}%`;

    document.getElementById('adsOverallCpa').innerText = formatRp(d.overall_cpa);
    document.getElementById('adsOverallCpc').innerText = formatRp(d.overall_cpc);
  } catch (err) {
    console.error('Error loading ads stats:', err);
  }
}

async function loadAdsHistory() {
  const period = document.getElementById('filterAdsPeriod') ? document.getElementById('filterAdsPeriod').value : 'all';
  try {
    const res = await fetch(`/api/ads/history?period=${encodeURIComponent(period)}`);
    const data = await res.json();
    currentAdsCache = data.records || [];

    // Populate Period Dropdown
    const select = document.getElementById('filterAdsPeriod');
    if (select && data.available_periods) {
      const cur = select.value;
      let opts = '<option value="all">Semua Periode Iklan</option>';
      data.available_periods.forEach(p => {
        opts += `<option value="${p}">${p}</option>`;
      });
      select.innerHTML = opts;
      select.value = cur;
    }

    const tbody = document.getElementById('adsTableBody');
    if (!data.records || data.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" class="py-8 text-center text-slate-500">Tidak ada data riwayat iklan.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.records.map((r, idx) => {
      // Evaluation badge based on actual ROAS vs Target ROAS
      let evalBadge = '';
      const targetVal = r.target_roas !== null && r.target_roas !== undefined ? r.target_roas : '';
      
      if (r.target_roas !== null && r.target_roas !== undefined && r.target_roas > 0) {
        if (r.actual_roas >= r.target_roas) {
          evalBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Tercapai ✅ (+${(r.actual_roas - r.target_roas).toFixed(1)}x)</span>`;
        } else {
          evalBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300">Di Bawah Target ⚠️ (${(r.actual_roas - r.target_roas).toFixed(1)}x)</span>`;
        }
      } else {
        if (r.actual_roas >= 3.5) {
          evalBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">🔥 Profitabel</span>';
        } else if (r.actual_roas > 0) {
          evalBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-700">Berjalan</span>';
        } else {
          evalBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-500">Belum Ada Sales</span>';
        }
      }

      return `
        <tr class="hover:bg-slate-50 transition">
          <td class="py-3.5 px-4 font-mono-num font-semibold text-slate-700 whitespace-nowrap">
            ${r.period_raw}
          </td>
          <td class="py-3.5 px-4 max-w-[220px]">
            <div class="font-bold text-slate-900 truncate" title="${escapeHtml(r.ad_name)}">${escapeHtml(r.ad_name)}</div>
            <div class="text-[10px] text-slate-500 font-mono-num mt-0.5">ID: ${r.product_id} • ${r.bidding_mode}</div>
          </td>
          <td class="py-3.5 px-3 text-center font-mono-num text-slate-600">
            ${r.impressions} <span class="text-slate-400">/</span> <b class="text-slate-900">${r.clicks}</b>
          </td>
          <td class="py-3.5 px-3 text-center font-mono-num text-[11px] text-slate-700 font-medium">
            ${r.ctr_pct.toFixed(2)}%
          </td>
          <td class="py-3.5 px-4 text-right font-mono-num text-rose-600 font-medium">
            -${formatRp(r.ad_spend)}
          </td>
          <td class="py-3.5 px-4 text-right font-mono-num font-bold text-slate-900">
            ${formatRp(r.ad_gmv)}
          </td>
          <td class="py-3.5 px-3 text-center font-mono-num font-bold text-slate-900">
            ${r.units_sold}
          </td>
          <td class="py-3.5 px-3 text-center font-mono-num font-black text-xs ${r.actual_roas >= 3.0 ? 'text-amber-700' : (r.actual_roas > 0 ? 'text-slate-800' : 'text-slate-400')}">
            ${r.actual_roas.toFixed(2)}x
          </td>
          <td class="py-3.5 px-4 text-center">
            <div class="inline-flex items-center gap-1">
              <input type="number" step="0.1" min="0" placeholder="Set"
                     value="${targetVal}"
                     onchange="saveTargetRoas(${r.id}, this.value, '${r.product_id}')"
                     class="w-16 px-1.5 py-1 text-center font-mono-num font-bold text-xs bg-white border border-slate-300 rounded focus:border-amber-500 outline-none text-amber-700 shadow-sm"
                     title="Target ROAS produk ini (Enter untuk simpan)">
              <span class="text-slate-400 text-[10px] font-semibold">x</span>
            </div>
          </td>
          <td class="py-3.5 px-3 text-center whitespace-nowrap">
            ${evalBadge}
          </td>
          <td class="py-3.5 px-3 text-center font-mono-num text-[11px] text-slate-600">
            ${r.acos_pct > 0 ? `${r.acos_pct.toFixed(1)}%` : '-'}
          </td>
        </tr>
      `;
    }).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Error loading ads history:', err);
  }
}

async function saveTargetRoas(id, val, productId) {
  const target = parseFloat(val);
  if (isNaN(target)) return;

  try {
    const payload = productId 
      ? { product_id: productId, target_roas: target }
      : { id: id, target_roas: target };

    const res = await fetch('/api/ads/target-roas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (d.status === 'success') {
      showToast(`Target ROAS ${target}x disimpan untuk produk ini!`, 'success');
      loadAdsHistory();
      loadAdsCharts();
    }
  } catch (err) {
    showToast('Gagal menyimpan target ROAS.', 'error');
  }
}

async function loadAdsCharts() {
  try {
    const res = await fetch('/api/ads/charts');
    const data = await res.json();

    renderAdsRoasSalesChart(data.roas_correlation || []);
    renderAdsPeriodTrendChart(data.period_trends || []);
  } catch (err) {
    console.error('Error loading ads charts:', err);
  }
}

// 1. ROAS vs Penjualan (Units Sold & GMV)
function renderAdsRoasSalesChart(roasData) {
  const ctx = document.getElementById('adsRoasSalesChart').getContext('2d');
  
  // Filter out 0-spend campaigns and sort by ROAS
  const validData = roasData.filter(d => d.ad_spend > 0).sort((a, b) => a.actual_roas - b.actual_roas);
  const labels = validData.map(d => `${d.actual_roas.toFixed(2)}x (${d.period_raw.split(' - ')[0]})`);
  const unitsData = validData.map(d => d.units_sold);
  const gmvData = validData.map(d => d.ad_gmv);
  const spendData = validData.map(d => d.ad_spend);

  if (adsRoasSalesChartInstance) adsRoasSalesChartInstance.destroy();

  adsRoasSalesChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Unit Terjual (Qty)',
          data: unitsData,
          backgroundColor: 'rgba(251, 191, 36, 0.9)',
          borderRadius: 4,
          barPercentage: 0.6,
          yAxisID: 'yUnits'
        },
        {
          label: 'Omzet Iklan (Rp)',
          data: gmvData,
          type: 'line',
          borderColor: '#3b82f6',
          borderWidth: 2.5,
          tension: 0.3,
          pointBackgroundColor: '#3b82f6',
          pointRadius: 4,
          yAxisID: 'yGmv'
        },
        {
          label: 'Biaya Iklan (Rp)',
          data: spendData,
          type: 'line',
          borderColor: '#f43f5e',
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 3,
          yAxisID: 'yGmv'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { color: '#334155', font: { family: 'Plus Jakarta Sans', size: 10, weight: 'bold' }, boxWidth: 10 } },
        tooltip: {
          callbacks: {
            title: function(items) {
              const idx = items[0].dataIndex;
              return `${validData[idx].ad_name} [ROAS: ${validData[idx].actual_roas.toFixed(2)}x]`;
            },
            label: function(c) {
              if (c.dataset.yAxisID === 'yGmv') return ` ${c.dataset.label}: ${formatRp(c.raw)}`;
              return ` ${c.dataset.label}: ${c.raw} Unit`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 9 }, maxRotation: 45 } },
        yUnits: {
          beginAtZero: true,
          position: 'left',
          ticks: { stepSize: 1, color: '#D97706', font: { size: 9, weight: 'bold' } },
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          title: { display: true, text: 'Unit', color: '#D97706', font: { size: 9, weight: 'bold' } }
        },
        yGmv: {
          beginAtZero: true,
          position: 'right',
          grid: { display: false },
          ticks: { color: '#64748B', font: { size: 9 }, callback: function(v) { return 'Rp ' + (v / 1000) + 'k'; } }
        }
      }
    }
  });
}

// 2. Tren Biaya vs Omzet Iklan per Periode
function renderAdsPeriodTrendChart(periodTrends) {
  const ctx = document.getElementById('adsPeriodTrendChart').getContext('2d');
  const labels = periodTrends.map(p => p.period_raw);
  const spendData = periodTrends.map(p => p.total_spend);
  const gmvData = periodTrends.map(p => p.total_gmv);
  const roasData = periodTrends.map(p => p.roas);

  if (adsPeriodTrendChartInstance) adsPeriodTrendChartInstance.destroy();

  adsPeriodTrendChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Biaya Iklan (Rp)',
          data: spendData,
          backgroundColor: '#F43F5E',
          borderRadius: 6,
          barPercentage: 0.55
        },
        {
          label: 'Omzet Iklan (Rp)',
          data: gmvData,
          backgroundColor: '#3B82F6',
          borderRadius: 6,
          barPercentage: 0.55
        },
        {
          label: 'ROAS Rata-rata',
          data: roasData,
          type: 'line',
          borderColor: '#D97706',
          borderWidth: 2.5,
          tension: 0.3,
          pointBackgroundColor: '#D97706',
          pointRadius: 4,
          yAxisID: 'yRoas'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top', labels: { color: '#334155', font: { family: 'Plus Jakarta Sans', size: 10, weight: 'bold' }, boxWidth: 10 } },
        tooltip: {
          callbacks: {
            label: function(c) {
              if (c.dataset.yAxisID === 'yRoas') return ` ROAS: ${c.raw}x`;
              return ` ${c.dataset.label}: ${formatRp(c.raw)}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748B', font: { size: 9, weight: 'bold' } } },
        y: {
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: { color: '#64748B', font: { size: 9 }, callback: function(v) { return 'Rp ' + (v / 1000) + 'k'; } }
        },
        yRoas: {
          position: 'right',
          beginAtZero: true,
          grid: { display: false },
          ticks: { color: '#D97706', font: { size: 9, weight: 'bold' }, callback: function(v) { return v + 'x'; } }
        }
      }
    }
  });
}

async function syncAdsData() {
  const icon = document.getElementById('iconSyncAds');
  if (icon) icon.classList.add('animate-spin');

  try {
    const res = await fetch('/api/ads/sync?force=true', { method: 'POST' });
    const data = await res.json();

    if (data.status === 'success') {
      showToast(`Data iklan Shopee berhasil disinkronkan dari folder /Downloads/iklan!`, 'success');
      loadAdsData();
    } else {
      showToast(data.message || 'Gagal sinkronisasi data iklan.', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan koneksi saat sinkronisasi iklan.', 'error');
  } finally {
    if (icon) icon.classList.remove('animate-spin');
  }
}

async function syncAllData() {
  const icon = document.getElementById('iconSync');
  if (icon) icon.classList.add('animate-spin');

  try {
    await fetch('/api/import/sync?force=true', { method: 'POST' });
    await fetch('/api/ads/sync?force=true', { method: 'POST' });
    showToast('Seluruh data pesanan & data iklan berhasil disinkronkan!', 'success');
    loadAllData();
  } catch (err) {
    showToast('Gagal sinkronisasi data.', 'error');
  } finally {
    if (icon) icon.classList.remove('animate-spin');
  }
}

// ==================== GENERAL BOOKKEEPING & EXPENSES MODULE ====================

async function loadBookkeepingData() {
  try {
    const res = await fetch(`/api/bookkeeping/pnl?period=${currentExpensePeriod}`);
    const data = await res.json();
    const pnl = data.pnl || {};
    const sales = data.sales || {};
    const expenses = data.expenses || {};

    // 1. KPI Cards
    const elOmzet = document.getElementById('pnlOmzet');
    if (elOmzet) {
      elOmzet.innerText = formatRp(pnl.total_omzet);
      document.getElementById('pnlOrdersCount').innerText = `${sales.total_orders || 0} Transaksi (${sales.total_qty || 0} Unit)`;
      document.getElementById('pnlDeductions').innerText = `-${formatRp(pnl.total_deductions)}`;
      document.getElementById('pnlHpp').innerText = `-${formatRp(pnl.total_hpp)}`;
      document.getElementById('pnlGrossProfit').innerText = formatRp(pnl.gross_profit);
      document.getElementById('pnlGrossMargin').innerText = `Margin Kotor: ${pnl.gross_margin_pct || 0}%`;
      document.getElementById('pnlTotalExpenses').innerText = `-${formatRp(pnl.total_extra_expenses)}`;
      document.getElementById('pnlExpenseCount').innerText = `${expenses.total_count || 0} Biaya Tercatat`;

      const elNetProfit = document.getElementById('pnlNetBusinessProfit');
      elNetProfit.innerText = formatRp(pnl.net_business_profit);
      if (pnl.net_business_profit < 0) {
        elNetProfit.className = 'text-xl sm:text-2xl font-black font-mono-num text-rose-600';
      } else {
        elNetProfit.className = 'text-xl sm:text-2xl font-black font-mono-num text-emerald-700';
      }

      document.getElementById('pnlNetBusinessMargin').innerText = `${pnl.net_business_margin_pct || 0}%`;
      document.getElementById('pnlCategoryTotalHeader').innerText = `Total: ${formatRp(pnl.total_extra_expenses)}`;
    }

    // 2. Category Breakdown Grid
    renderExpenseCategoryGrid(expenses.categories || [], pnl.total_extra_expenses || 0);

    // 3. Render Sold Items & Transactions with Net Profit
    renderBookkeepingSoldItems(data.sold_items || []);
    renderBookkeepingSoldTransactions(data.sold_transactions || []);

    // 4. Table of expenses
    await loadExpensesData();
    lucide.createIcons();

  } catch (err) {
    console.error('Error loading bookkeeping data:', err);
  }
}

let currentBookkeepingItemView = 'summary';

function switchBookkeepingItemView(view) {
  currentBookkeepingItemView = view;
  const btnSummary = document.getElementById('btnViewItemSummary');
  const btnTransactions = document.getElementById('btnViewItemTransactions');
  const viewSummary = document.getElementById('viewBookkeepingItemSummary');
  const viewTransactions = document.getElementById('viewBookkeepingItemTransactions');

  if (!btnSummary || !btnTransactions) return;

  if (view === 'summary') {
    btnSummary.className = 'px-2.5 py-1 rounded-md bg-white text-slate-900 shadow-sm transition-all';
    btnTransactions.className = 'px-2.5 py-1 rounded-md text-slate-600 hover:text-slate-900 transition-all';
    if (viewSummary) viewSummary.classList.remove('hidden');
    if (viewTransactions) viewTransactions.classList.add('hidden');
  } else {
    btnSummary.className = 'px-2.5 py-1 rounded-md text-slate-600 hover:text-slate-900 transition-all';
    btnTransactions.className = 'px-2.5 py-1 rounded-md bg-white text-slate-900 shadow-sm transition-all';
    if (viewSummary) viewSummary.classList.add('hidden');
    if (viewTransactions) viewTransactions.classList.remove('hidden');
  }
}

function renderBookkeepingSoldItems(items) {
  const tbody = document.getElementById('pnlSoldItemsTableBody');
  const tfoot = document.getElementById('pnlSoldItemsTableFoot');
  const totalProfitBadge = document.getElementById('pnlSoldItemsTotalProfit');
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="py-8 text-center text-slate-400">
          Belum ada item terjual pada periode ini.
        </td>
      </tr>
    `;
    if (tfoot) tfoot.innerHTML = '';
    if (totalProfitBadge) totalProfitBadge.innerText = 'Total Laba: Rp 0';
    return;
  }

  let totalQty = 0;
  let totalOmzet = 0;
  let totalDeductions = 0;
  let totalHpp = 0;
  let totalNetProfit = 0;

  let html = '';
  items.forEach(it => {
    totalQty += it.total_qty || 0;
    totalOmzet += it.total_omzet || 0;
    totalDeductions += it.total_deductions || 0;
    totalHpp += it.total_hpp || 0;
    totalNetProfit += it.total_net_profit || 0;

    const isModelNew = (it.model_type || '').toLowerCase().includes('new');
    const modelBadge = isModelNew
      ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">New</span>'
      : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">Old</span>';

    const boltBadge = it.has_bolt
      ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">+ Baut</span>'
      : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">Tanpa Baut</span>';

    const marginPct = it.profit_margin_pct || 0;
    const marginBadgeClass = marginPct >= 35
      ? 'bg-emerald-100 text-emerald-800'
      : marginPct >= 20
      ? 'bg-amber-100 text-amber-800'
      : 'bg-rose-100 text-rose-800';

    html += `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-3 px-4 font-medium text-slate-900 max-w-xs">
          <div class="line-clamp-1 font-semibold text-xs" title="${it.product_name}">${it.product_name}</div>
          <div class="text-[11px] text-slate-500 mt-0.5 font-normal">${it.variation_name || '-'}</div>
        </td>
        <td class="py-3 px-3 text-center">${modelBadge}</td>
        <td class="py-3 px-3 text-center">${boltBadge}</td>
        <td class="py-3 px-3 text-center font-bold font-mono-num text-slate-900">${it.total_qty} <span class="text-[10px] font-normal text-slate-500">pcs</span></td>
        <td class="py-3 px-4 text-right font-bold font-mono-num text-slate-900">${formatRp(it.total_omzet)}</td>
        <td class="py-3 px-4 text-right font-mono-num text-rose-600">-${formatRp(it.total_deductions)}</td>
        <td class="py-3 px-4 text-right font-mono-num text-slate-700">-${formatRp(it.total_hpp)}</td>
        <td class="py-3 px-4 text-right font-black font-mono-num text-emerald-700 bg-emerald-50/50">+${formatRp(it.total_net_profit)}</td>
        <td class="py-3 px-3 text-center">
          <span class="px-1.5 py-0.5 rounded font-bold text-[11px] font-mono-num ${marginBadgeClass}">
            ${marginPct}%
          </span>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;

  if (totalProfitBadge) {
    totalProfitBadge.innerText = `Total Laba Produk: ${formatRp(totalNetProfit)}`;
  }

  const avgMargin = totalOmzet > 0 ? (totalNetProfit / totalOmzet * 100).toFixed(1) : 0;
  if (tfoot) {
    tfoot.innerHTML = `
      <tr>
        <td colspan="3" class="py-3 px-4 text-slate-900 font-extrabold text-xs">
          TOTAL (${items.length} Item Varian Terjual)
        </td>
        <td class="py-3 px-3 text-center font-extrabold font-mono-num text-slate-900">${totalQty} pcs</td>
        <td class="py-3 px-4 text-right font-extrabold font-mono-num text-slate-900">${formatRp(totalOmzet)}</td>
        <td class="py-3 px-4 text-right font-bold font-mono-num text-rose-600">-${formatRp(totalDeductions)}</td>
        <td class="py-3 px-4 text-right font-bold font-mono-num text-slate-700">-${formatRp(totalHpp)}</td>
        <td class="py-3 px-4 text-right font-black font-mono-num text-emerald-700 bg-emerald-100/70 text-sm">+${formatRp(totalNetProfit)}</td>
        <td class="py-3 px-3 text-center">
          <span class="px-2 py-0.5 rounded-full font-black text-xs bg-emerald-200 text-emerald-900 font-mono-num">
            ${avgMargin}%
          </span>
        </td>
      </tr>
    `;
  }
}

function renderBookkeepingSoldTransactions(transactions) {
  const tbody = document.getElementById('pnlSoldTransactionsTableBody');
  if (!tbody) return;

  if (!transactions || transactions.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="9" class="py-8 text-center text-slate-400">
          Belum ada riwayat pesanan pada periode ini.
        </td>
      </tr>
    `;
    return;
  }

  let html = '';
  transactions.forEach(tx => {
    const marginPct = (tx.margin_pct || 0).toFixed(1);
    const marginBadgeClass = marginPct >= 35
      ? 'bg-emerald-100 text-emerald-800'
      : marginPct >= 20
      ? 'bg-amber-100 text-amber-800'
      : 'bg-rose-100 text-rose-800';

    html += `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="py-3 px-4">
          <div class="font-bold text-slate-900 font-mono-num">${tx.order_no}</div>
          <div class="text-[10px] text-slate-500">${tx.order_created_at || '-'}</div>
        </td>
        <td class="py-3 px-4 max-w-xs">
          <div class="line-clamp-1 font-semibold text-slate-800 text-xs" title="${tx.product_name}">${tx.product_name}</div>
          <div class="text-[11px] text-slate-500 mt-0.5">${tx.variation_name || '-'}</div>
        </td>
        <td class="py-3 px-3 text-center text-[11px] text-slate-600">
          <div>${tx.city || '-'}</div>
          <div class="text-[9px] text-slate-400">${tx.province || ''}</div>
        </td>
        <td class="py-3 px-2 text-center font-bold font-mono-num">${tx.qty}</td>
        <td class="py-3 px-4 text-right font-bold font-mono-num text-slate-900">${formatRp(tx.subtotal)}</td>
        <td class="py-3 px-4 text-right font-mono-num text-rose-600">-${formatRp(tx.total_shopee_deductions)}</td>
        <td class="py-3 px-4 text-right font-mono-num text-slate-700">-${formatRp(tx.total_hpp)}</td>
        <td class="py-3 px-4 text-right font-black font-mono-num text-emerald-700 bg-emerald-50/50">+${formatRp(tx.net_profit)}</td>
        <td class="py-3 px-3 text-center">
          <span class="px-1.5 py-0.5 rounded font-bold text-[10px] font-mono-num ${marginBadgeClass}">
            ${marginPct}%
          </span>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

function renderExpenseCategoryGrid(categories, totalAmount) {
  const container = document.getElementById('expenseCategoryGrid');
  if (!container) return;

  if (!categories || categories.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-6 text-center text-xs text-slate-400">
        Belum ada biaya pengeluaran tambahan yang dicatat untuk periode ini.
      </div>
    `;
    return;
  }

  const icons = {
    'Iklan / Ads': 'target',
    'Bahan Packing': 'package',
    'Operasional & Toko': 'store',
    'Logistik & Transport': 'truck',
    'Gaji & Upah': 'users',
    'Retur & Ganti Rugi': 'alert-circle',
    'Lain-lain': 'more-horizontal'
  };

  const colors = {
    'Iklan / Ads': 'text-amber-700 bg-amber-50 border-amber-200',
    'Bahan Packing': 'text-blue-700 bg-blue-50 border-blue-200',
    'Operasional & Toko': 'text-purple-700 bg-purple-50 border-purple-200',
    'Logistik & Transport': 'text-emerald-700 bg-emerald-50 border-emerald-200',
    'Gaji & Upah': 'text-cyan-700 bg-cyan-50 border-cyan-200',
    'Retur & Ganti Rugi': 'text-rose-700 bg-rose-50 border-rose-200',
    'Lain-lain': 'text-slate-700 bg-slate-50 border-slate-200'
  };

  let html = '';
  categories.forEach(c => {
    const iconName = icons[c.category] || 'credit-card';
    const colorClass = colors[c.category] || 'text-slate-700 bg-slate-50 border-slate-200';
    const pct = totalAmount > 0 ? Math.round((c.amount / totalAmount) * 100) : 0;

    html += `
      <div class="p-3 rounded-xl border ${colorClass} flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-bold truncate">${escapeHtml(c.category)}</span>
          <i data-lucide="${iconName}" class="w-3.5 h-3.5 shrink-0 opacity-80"></i>
        </div>
        <div class="mt-2">
          <div class="font-mono-num font-bold text-slate-900 text-sm">${formatRp(c.amount)}</div>
          <p class="text-[10px] text-slate-500 mt-0.5">${c.count} catatan (${pct}%)</p>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  lucide.createIcons();
}

async function loadExpensesData() {
  const category = document.getElementById('filterExpenseCategory') ? document.getElementById('filterExpenseCategory').value : 'all';
  const search = document.getElementById('searchExpenseInput') ? document.getElementById('searchExpenseInput').value : '';

  try {
    const params = new URLSearchParams({
      period: currentExpensePeriod,
      category: category,
      search: search
    });

    const res = await fetch(`/api/expenses?${params.toString()}`);
    const data = await res.json();
    currentExpensesCache = data.expenses || [];

    const countEl = document.getElementById('expenseRecordCount');
    if (countEl) countEl.innerText = `Menampilkan ${data.expenses.length} pengeluaran (Total: ${formatRp(data.total_amount)})`;

    const tbody = document.getElementById('expenseTableBody');
    if (!tbody) return;

    if (!data.expenses || data.expenses.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="py-8 text-center text-slate-400">
            <i data-lucide="receipt" class="w-8 h-8 mx-auto mb-2 opacity-30 text-slate-400"></i>
            Belum ada catatan biaya untuk filter ini. Klik <b>"Catat Biaya Baru"</b> untuk menambahkan.
          </td>
        </tr>
      `;
      lucide.createIcons();
      return;
    }

    const catBadges = {
      'Iklan / Ads': 'bg-amber-100 text-amber-800 border-amber-200',
      'Bahan Packing': 'bg-blue-100 text-blue-800 border-blue-200',
      'Operasional & Toko': 'bg-purple-100 text-purple-800 border-purple-200',
      'Logistik & Transport': 'bg-emerald-100 text-emerald-800 border-emerald-200',
      'Gaji & Upah': 'bg-cyan-100 text-cyan-800 border-cyan-200',
      'Retur & Ganti Rugi': 'bg-rose-100 text-rose-800 border-rose-200',
      'Lain-lain': 'bg-slate-100 text-slate-700 border-slate-200'
    };

    tbody.innerHTML = data.expenses.map((e, idx) => {
      const badgeClass = catBadges[e.category] || 'bg-slate-100 text-slate-700 border-slate-200';
      return `
        <tr class="hover:bg-slate-50 transition group">
          <td class="py-3.5 px-4 font-mono-num font-semibold text-slate-700 whitespace-nowrap">
            ${e.expense_date}
          </td>
          <td class="py-3.5 px-4">
            <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClass}">
              ${escapeHtml(e.category)}
            </span>
          </td>
          <td class="py-3.5 px-4 font-bold text-slate-900">
            ${escapeHtml(e.title)}
          </td>
          <td class="py-3.5 px-4 text-slate-500 text-xs max-w-[260px] truncate" title="${escapeHtml(e.notes || '')}">
            ${escapeHtml(e.notes || '-')}
          </td>
          <td class="py-3.5 px-4 text-right font-mono-num font-black text-rose-600 text-sm">
            -${formatRp(e.amount)}
          </td>
          <td class="py-3.5 px-3 text-center">
            <div class="flex items-center justify-center gap-1.5">
              <button onclick="openExpenseModal(${e.id})" class="btn-tactile p-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 border border-slate-200" title="Edit Biaya">
                <i data-lucide="edit-2" class="w-3.5 h-3.5"></i>
              </button>
              <button onclick="deleteExpense(${e.id})" class="btn-tactile p-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200" title="Hapus Biaya">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    lucide.createIcons();
  } catch (err) {
    console.error('Error loading expenses data:', err);
  }
}

function openExpenseModal(expenseId = null) {
  const modal = document.getElementById('expenseModal');
  const titleEl = document.getElementById('expenseModalTitle');
  
  if (expenseId) {
    const item = currentExpensesCache.find(x => x.id === expenseId);
    if (item) {
      document.getElementById('expId').value = item.id;
      document.getElementById('expDate').value = item.expense_date;
      document.getElementById('expCategory').value = item.category;
      document.getElementById('expTitle').value = item.title;
      document.getElementById('expAmount').value = item.amount;
      document.getElementById('expNotes').value = item.notes || '';
      titleEl.innerHTML = '<i data-lucide="edit" class="w-5 h-5 text-amber-600"></i><span>Edit Catatan Biaya</span>';
    }
  } else {
    document.getElementById('expId').value = '';
    document.getElementById('expDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('expCategory').value = 'Iklan / Ads';
    document.getElementById('expTitle').value = '';
    document.getElementById('expAmount').value = '';
    document.getElementById('expNotes').value = '';
    titleEl.innerHTML = '<i data-lucide="plus-circle" class="w-5 h-5 text-emerald-600"></i><span>Catat Biaya Pengeluaran Baru</span>';
  }

  modal.classList.remove('hidden');
  lucide.createIcons();
}

function closeExpenseModal() {
  document.getElementById('expenseModal').classList.add('hidden');
}

async function handleSaveExpense(e) {
  e.preventDefault();
  const id = document.getElementById('expId').value;
  const payload = {
    expense_date: document.getElementById('expDate').value,
    category: document.getElementById('expCategory').value,
    title: document.getElementById('expTitle').value.trim(),
    amount: parseFloat(document.getElementById('expAmount').value),
    notes: document.getElementById('expNotes').value.trim()
  };

  try {
    let res;
    if (id) {
      res = await fetch(`/api/expenses/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch('/api/expenses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
    const d = await res.json();
    if (d.status === 'success') {
      showToast(id ? 'Biaya berhasil diperbarui!' : 'Biaya berhasil dicatat!', 'success');
      closeExpenseModal();
      loadBookkeepingData();
    } else {
      showToast(d.detail || 'Gagal menyimpan biaya.', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan saat menyimpan biaya.', 'error');
  }
}

async function deleteExpense(expenseId) {
  if (!confirm('Apakah Anda yakin ingin menghapus catatan biaya ini?')) return;

  try {
    const res = await fetch(`/api/expenses/${expenseId}`, { method: 'DELETE' });
    const d = await res.json();
    if (d.status === 'success') {
      showToast('Catatan biaya berhasil dihapus.', 'success');
      loadBookkeepingData();
    } else {
      showToast('Gagal menghapus biaya.', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan saat menghapus biaya.', 'error');
  }
}

function setExpensePeriod(period) {
  currentExpensePeriod = period;
  document.querySelectorAll('.exp-period-btn').forEach(b => {
    if (b.dataset.period === period) {
      b.className = 'exp-period-btn px-3 py-1.5 rounded-lg font-bold text-slate-900 bg-white shadow-sm';
    } else {
      b.className = 'exp-period-btn px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:text-slate-900';
    }
  });
  loadBookkeepingData();
}

function debounceSearchExpense() {
  clearTimeout(debounceExpenseTimeout);
  debounceExpenseTimeout = setTimeout(() => {
    loadExpensesData();
  }, 250);
}

// Detail Modal Handler
function openDetailModalByIndex(idx) {
  const o = currentOrdersCache[idx];
  if (!o) return;

  const content = document.getElementById('detailModalContent');
  content.innerHTML = `
    <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
      <div>
        <span class="text-slate-500 block text-[11px] font-medium">No. Pesanan</span>
        <span class="font-mono-num font-bold text-slate-900 text-sm">${o.order_no}</span>
      </div>
      <div class="text-right">
        <span class="text-slate-500 block text-[11px] font-medium">Status</span>
        <span class="font-bold text-amber-700">${o.order_status}</span>
      </div>
    </div>

    <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
      <div class="font-bold text-slate-900 flex items-center gap-1.5 text-xs text-amber-600">
        <i data-lucide="clock" class="w-4 h-4"></i>
        Informasi Jam & Waktu Transaksi
      </div>
      <div class="grid grid-cols-2 gap-3 pt-1">
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Waktu Pesanan Dibuat</span>
          <span class="font-mono-num font-bold text-slate-800 text-xs">${o.order_created_at || '-'} WIB</span>
        </div>
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Waktu Pembayaran Dilakukan</span>
          <span class="font-mono-num font-bold text-slate-800 text-xs">${o.order_paid_at || '-'} WIB</span>
        </div>
      </div>
    </div>

    <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
      <div class="font-bold text-slate-900 flex items-center gap-1.5 text-xs text-emerald-600">
        <i data-lucide="map-pin" class="w-4 h-4"></i>
        Tujuan Pengiriman & Data Pembeli
      </div>
      <div class="grid grid-cols-2 gap-2 pt-1">
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Kota / Kabupaten</span>
          <span class="font-bold text-slate-900">${o.city || '-'}</span>
        </div>
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Provinsi</span>
          <span class="font-bold text-slate-900">${o.province || '-'}</span>
        </div>
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Nama Penerima</span>
          <span class="text-slate-800 font-medium">${o.recipient_name || '-'}</span>
        </div>
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Username Pembeli</span>
          <span class="text-slate-800 font-medium">${o.buyer_username || '-'}</span>
        </div>
      </div>
      <div class="pt-2 border-t border-slate-200">
        <span class="text-slate-500 block text-[10px] mb-0.5 font-medium">Alamat Lengkap</span>
        <div class="p-2 rounded bg-white border border-slate-200 text-slate-700 text-[11px] leading-relaxed">
          ${o.raw_address || 'Tidak ada catatan alamat'}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 pt-1">
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">No. Resi Pengiriman</span>
          <span class="font-mono-num text-slate-800">${o.tracking_no || '-'}</span>
        </div>
        <div>
          <span class="text-slate-500 block text-[10px] font-medium">Opsi / Jasa Kirim</span>
          <span class="text-slate-800">${o.shipping_option || '-'}</span>
        </div>
      </div>
    </div>

    <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5">
      <div class="font-bold text-slate-900 flex items-center justify-between text-xs pb-1.5 border-b border-slate-200">
        <span class="flex items-center gap-1.5 text-blue-700">
          <i data-lucide="receipt" class="w-4 h-4"></i>
          Rincian Potongan Shopee & Laba Real
        </span>
        <span class="font-mono-num font-bold text-slate-700">${o.qty} Unit</span>
      </div>

      <div class="space-y-1.5 pt-1 text-[11px]">
        <div class="flex justify-between">
          <span class="text-slate-500">Produk:</span>
          <span class="text-slate-900 font-bold text-right max-w-[280px] truncate" title="${escapeHtml(o.product_name)}">${escapeHtml(o.product_name)}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-500">Variasi:</span>
          <span class="text-amber-700 font-bold text-right">${escapeHtml(o.variation_name)}</span>
        </div>

        <div class="flex justify-between pt-2 border-t border-slate-200 text-xs font-semibold">
          <span class="text-slate-900">Subtotal Pesanan:</span>
          <span class="font-mono-num font-bold text-slate-900">${formatRp(o.subtotal)}</span>
        </div>

        <!-- Breakdown Potongan Shopee Sesuai Permintaan -->
        <div class="p-2.5 rounded-lg bg-rose-50/70 border border-rose-200 space-y-1 my-1 text-[11px]">
          <div class="text-[10px] uppercase font-bold text-rose-700 tracking-wider">Potongan Resmi Shopee:</div>
          <div class="flex justify-between text-slate-600">
            <span>• Biaya Administrasi (8.25%):</span>
            <span class="font-mono-num text-rose-600 font-semibold">-${formatRp(o.shopee_admin_fee)}</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>• Biaya Proses Pesanan:</span>
            <span class="font-mono-num text-rose-600 font-semibold">-${formatRp(o.shopee_process_fee)}</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>• Biaya Gratis Ongkir XTRA (5.50%):</span>
            <span class="font-mono-num text-rose-600 font-semibold">-${formatRp(o.shopee_gratis_ongkir_xtra)}</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>• Biaya Promosi / Isi Saldo (3.33%):</span>
            <span class="font-mono-num text-rose-600 font-semibold">-${formatRp(o.shopee_promo_fee)}</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>• Pajak PPh 22 (0.50%):</span>
            <span class="font-mono-num text-rose-600 font-semibold">-${formatRp(o.shopee_pph22)}</span>
          </div>
          <div class="flex justify-between pt-1 border-t border-rose-200 font-bold text-rose-700">
            <span>Total Potongan Shopee:</span>
            <span class="font-mono-num">-${formatRp(o.total_shopee_deductions)}</span>
          </div>
        </div>

        <div class="flex justify-between text-blue-700 font-semibold">
          <span>Pencairan Bersih dari Shopee:</span>
          <span class="font-mono-num font-bold">${formatRp(o.net_payout)}</span>
        </div>

        <!-- Breakdown Modal HPP -->
        <div class="p-2.5 rounded-lg bg-amber-50/70 border border-amber-200 space-y-1 my-1 text-[11px]">
          <div class="text-[10px] uppercase font-bold text-amber-800 tracking-wider">Modal Pokok (HPP):</div>
          <div class="flex justify-between text-slate-600">
            <span>• HPP Cover Knalpot (${o.qty} x Rp 6.000):</span>
            <span class="font-mono-num text-amber-700 font-semibold">-${formatRp(o.total_hpp_cover)}</span>
          </div>
          <div class="flex justify-between text-slate-600">
            <span>• HPP Baut (${o.has_bolt ? `${o.qty} pasang x Rp 2.000` : 'Tanpa Baut'}):</span>
            <span class="font-mono-num text-amber-700 font-semibold">-${formatRp(o.total_hpp_bolt)}</span>
          </div>
          <div class="flex justify-between pt-1 border-t border-amber-200 font-bold text-amber-800">
            <span>Total Modal HPP:</span>
            <span class="font-mono-num">-${formatRp(o.total_hpp)}</span>
          </div>
        </div>

        <div class="flex justify-between pt-2 border-t border-slate-200 text-sm font-bold text-emerald-700">
          <span>Keuntungan Bersih Real:</span>
          <span class="font-mono-num text-base font-black">${formatRp(o.profit)} (${Math.round(o.margin_pct)}%)</span>
        </div>
      </div>
    </div>
  `;

  document.getElementById('detailModal').classList.remove('hidden');
  lucide.createIcons();
}

function closeDetailModal() {
  document.getElementById('detailModal').classList.add('hidden');
}

// Filter Actions for Orders
function setPeriod(period) {
  currentPeriod = period;
  currentPage = 1;

  document.querySelectorAll('.period-btn').forEach(b => {
    if (b.dataset.period === period) {
      b.className = 'period-btn px-3 py-1.5 rounded-lg font-medium text-amber-400 bg-white/10';
    } else {
      b.className = 'period-btn px-3 py-1.5 rounded-lg font-medium text-slate-400 hover:text-white';
    }
  });

  loadAllData();
}

function applyFilters() {
  currentPage = 1;
  loadAllData();
}

function debounceSearch() {
  clearTimeout(debounceTimeout);
  debounceTimeout = setTimeout(() => {
    currentPage = 1;
    loadAllData();
  }, 350);
}

function prevPage() {
  if (currentPage > 1) {
    currentPage--;
    loadOrders();
  }
}

function nextPage() {
  currentPage++;
  loadOrders();
}

// Upload Modal & Drag-and-drop
function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.add('hidden');
  document.getElementById('uploadProgress').classList.add('hidden');
  document.getElementById('fileInput').value = '';
}

function setupDropZone() {
  const zone = document.getElementById('dropZone');
  const input = document.getElementById('fileInput');

  zone.addEventListener('click', () => input.click());

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('border-amber-400', 'bg-amber-400/5');
  });

  zone.addEventListener('dragleave', () => {
    zone.classList.remove('border-amber-400', 'bg-amber-400/5');
  });

  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('border-amber-400', 'bg-amber-400/5');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });
}

function handleFileSelect(e) {
  if (e.target.files && e.target.files[0]) {
    uploadFile(e.target.files[0]);
  }
}

async function uploadFile(file) {
  const name = file.name.toLowerCase();
  if (!name.endsWith('.xlsx') && !name.endsWith('.xls') && !name.endsWith('.csv')) {
    showToast('Hanya file Excel (.xlsx / .xls) atau CSV (.csv) yang didukung.', 'error');
    return;
  }

  const progress = document.getElementById('uploadProgress');
  progress.classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/import/upload', {
      method: 'POST',
      body: formData
    });
    const result = await res.json();

    if (result.status === 'success') {
      showToast(`Berhasil mengimpor ${result.file}: ${result.inserted} baru, ${result.updated} diperbarui!`, 'success');
      closeUploadModal();
      loadAllData();
    } else {
      showToast(result.message || 'Gagal memproses file.', 'error');
    }
  } catch (err) {
    showToast('Terjadi kesalahan saat mengunggah file.', 'error');
  } finally {
    progress.classList.add('hidden');
  }
}

// Settings Modal
async function openSettingsModal() {
  try {
    const res = await fetch('/api/settings');
    const cfg = await res.json();

    const elCover = document.getElementById('cfgHppCover');
    const elBolt = document.getElementById('cfgHppBolt');
    const elWatch = document.getElementById('cfgWatchFolder');
    const elWatchAds = document.getElementById('cfgWatchFolderIklan') || document.getElementById('cfgWatchFolderAds');

    if (elCover) elCover.value = cfg.hpp_cover ?? 6000;
    if (elBolt) elBolt.value = cfg.hpp_bolt ?? 2000;
    if (elWatch) elWatch.value = cfg.watch_folder || '/Users/risanggalih/Desktop/shopee/penjualan';
    if (elWatchAds) elWatchAds.value = cfg.watch_folder_iklan || '/Users/risanggalih/Desktop/shopee/iklan';

    const modal = document.getElementById('settingsModal');
    if (modal) {
      modal.classList.remove('hidden');
      lucide.createIcons();
    }
  } catch (err) {
    console.error('Error opening settings modal:', err);
    showToast('Gagal memuat pengaturan: ' + err.message, 'error');
  }
}

function closeSettingsModal() {
  const modal = document.getElementById('settingsModal');
  if (modal) modal.classList.add('hidden');
}

async function saveSettings(e) {
  if (e) e.preventDefault();
  const elCover = document.getElementById('cfgHppCover');
  const elBolt = document.getElementById('cfgHppBolt');
  const elWatch = document.getElementById('cfgWatchFolder');
  const elWatchAds = document.getElementById('cfgWatchFolderIklan') || document.getElementById('cfgWatchFolderAds');

  const hppCoverVal = parseFloat(elCover ? elCover.value : 6000);
  const hppBoltVal = parseFloat(elBolt ? elBolt.value : 2000);

  if (isNaN(hppCoverVal) || hppCoverVal < 0) {
    showToast('Nilai HPP Cover Knalpot tidak valid!', 'error');
    return;
  }
  if (isNaN(hppBoltVal) || hppBoltVal < 0) {
    showToast('Nilai HPP Baut tidak valid!', 'error');
    return;
  }

  const data = {
    hpp_cover: hppCoverVal,
    hpp_bolt: hppBoltVal,
    watch_folder: elWatch ? elWatch.value : '',
    watch_folder_iklan: elWatchAds ? elWatchAds.value : ''
  };

  try {
    showToast('Menyimpan pengaturan HPP & menghitung ulang...', 'info');
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await res.json();
    if (result.status === 'success') {
      showToast('Pengaturan HPP berhasil disimpan & dihitung ulang!', 'success');
      closeSettingsModal();
      loadAllData();
      if (typeof loadBookkeepingData === 'function') {
        loadBookkeepingData();
      }
    } else {
      showToast('Gagal: ' + (result.message || 'Error server'), 'error');
    }
  } catch (err) {
    console.error('Error saving settings:', err);
    showToast('Gagal menyimpan pengaturan: ' + err.message, 'error');
  }
}

function exportExcel() {
  const params = getFilterParams();
  window.location.href = `/api/export?${params.toString()}`;
}

const SHOPEE_DIRECT_URLS = {
  order: 'https://seller.shopee.co.id/portal/sale/order',
  ads: 'https://seller.shopee.co.id/portal/marketing/pas/index?source_page_id=1&view_mode=classic&type=new_cpc_homepage',
  finance: 'https://seller.shopee.co.id/portal/finance/wallet/shopeepay'
};

async function openShopeePage(target = 'order', event = null) {
  if (event) event.preventDefault();
  const url = SHOPEE_DIRECT_URLS[target] || SHOPEE_DIRECT_URLS.order;
  const labelMap = { order: 'Penjualan (Pesanan)', ads: 'Iklan Shopee', finance: 'Pemasukan (Saldo Saya)' };
  const label = labelMap[target] || 'Shopee Seller';

  try {
    showToast(`Membuka Shopee ${label} di Brave (sdrisanggalih)...`, 'info');
    const res = await fetch('/api/open-shopee-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, url })
    });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(data.message, 'success');
    } else {
      window.open(url, '_blank');
    }
  } catch (err) {
    window.open(url, '_blank');
  }
}

async function openShopeeSeller(event) {
  return openShopeePage('ads', event);
}

async function launchBraveDirectly() {
  return openShopeePage('ads');
}
