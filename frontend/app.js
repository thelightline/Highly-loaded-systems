const API = (window.API_BASE || 'http://localhost:8081').replace(/\/$/, '');
document.getElementById('apiBasePill').textContent = API.replace(/^https?:\/\//, '');


const el = id => document.getElementById(id);
const symbolSelect = el('symbolSelect');
const userInput    = el('userInput');
const priceInput   = el('priceInput');
const qtyInput     = el('qtyInput');
const bookBody     = el('bookBody');
const profileBox   = el('profileBox');
const balanceLine  = el('balanceLine');
const tradeMsg     = el('tradeMsg');
const addSymbolMsg = el('addSymbolMsg');
const txBox        = el('txBox');
const userPill     = el('userPill');


const fmtMoney = n => Number(n).toLocaleString('ru-RU', {minimumFractionDigits:2, maximumFractionDigits:2});
const fmtInt   = n => Number(n).toLocaleString('ru-RU', {maximumFractionDigits:0});

function setMsg(node, text, ok=false, err=false) {
  node.className = ok ? 'ok' : err ? 'err' : 'muted';
  node.textContent = text;
}

async function apiGet(path) {
  const r = await fetch(API + path, { headers: {'Cache-Bypass':'1'} });
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return r.json();
}
async function apiPost(path) {
  const r = await fetch(API + path, { method:'POST', headers: {'Cache-Bypass':'1'} });
  const txt = await r.text();
  let data = null;
  try { data = JSON.parse(txt); } catch (_) {}
  if (!r.ok) {
    const msg = data?.detail || txt || `HTTP ${r.status}`;
    throw new Error(msg);
  }
  return data ?? {};
}


async function loadSymbols() {
  const list = await apiGet('/api/products/symbols');
  symbolSelect.innerHTML = '';
  for (const it of list) {
    const opt = document.createElement('option');
    opt.value = it.symbol;
    opt.textContent = it.symbol;
    symbolSelect.appendChild(opt);
  }
  if (!symbolSelect.value && list.length) symbolSelect.value = list[0].symbol;
  await refreshAll();
}

async function addSymbol() {
  const s = el('newSymbol').value.trim().toUpperCase();
  const lot = Number(el('newLot').value || 1);
  if (!s) { setMsg(addSymbolMsg, 'Введите символ', false, true); return; }
  try {
    await apiPost(`/api/products/add_symbol?symbol=${encodeURIComponent(s)}&lot_size=${lot}`);
    setMsg(addSymbolMsg, `Символ ${s} добавлен`, true, false);
    el('newSymbol').value = '';
    await loadSymbols();
    symbolSelect.value = s;
  } catch (e) {
    setMsg(addSymbolMsg, String(e.message || e), false, true);
  }
}


async function airdrop() {
  const sym = symbolSelect.value;
  if (!sym) return;
  try {
    const r = await apiPost(`/api/admin/airdrop?user=alice&symbol=${encodeURIComponent(sym)}&qty=100`);
    setMsg(addSymbolMsg, `Выдали alice 100 ${sym}: ${JSON.stringify(r)}`, true, false);
    await refreshProfile();
  } catch (e) {
    setMsg(addSymbolMsg, String(e.message || e), false, true);
  }
}


async function refreshBook() {
  const sym = symbolSelect.value;
  const data = await apiGet(`/api/orderbook?symbol=${encodeURIComponent(sym)}&depth=15`);
  bookBody.innerHTML = '';
  if (!data.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 3; td.className = 'muted'; td.textContent = 'Пусто';
    tr.appendChild(td); bookBody.appendChild(tr);
    return;
  }
  for (const row of data) {
    const tr = document.createElement('tr');
    const tdBid = document.createElement('td');
    tdBid.className = 'bid';
    const bq = Number(row.buy_qty||0);
    const ba = Number(row.buy_amount||0);
    tdBid.textContent = bq ? `${fmtInt(bq)} / ${fmtMoney(ba)}` : '—';
    tr.appendChild(tdBid);

    const tdPx = document.createElement('td');
    tdPx.className = 'price center-col';
    tdPx.textContent = fmtMoney(row.price);
    tr.appendChild(tdPx);

    const tdAsk = document.createElement('td');
    tdAsk.className = 'ask';
    const sq = Number(row.sell_qty||0);
    const sa = Number(row.sell_amount||0);
    tdAsk.textContent = sq ? `${fmtInt(sq)} / ${fmtMoney(sa)}` : '—';
    tr.appendChild(tdAsk);

    bookBody.appendChild(tr);
  }
}


async function refreshProfile() {
  const user = userInput.value.trim() || 'alice';
  userPill.textContent = user;
  const prof = await apiGet(`/api/user/profile?name=${encodeURIComponent(user)}`);
  balanceLine.textContent = `${fmtMoney(prof.balance)} $`;
  const box = [];
  box.push(`ID: ${prof.id}`);
  box.push(`Имя: ${prof.name}`);
  if (prof.positions?.length) {
    box.push('Позиции:');
    for (const p of prof.positions) box.push(`• ${p.symbol}: ${fmtInt(p.qty)} шт`);
  } else {
    box.push('Позиции: —');
  }
  profileBox.innerHTML = '<div class="grid-gap">' + box.map(t=>`<div>${t}</div>`).join('') + '</div>';
}


async function refreshTx() {
  const u = el('txUser').value.trim();
  const s = el('txSymbol').value.trim().toUpperCase();
  let q = [];
  if (u) q.push(`user=${encodeURIComponent(u)}`);
  if (s) q.push(`symbol=${encodeURIComponent(s)}`);
  const rows = await apiGet('/api/transactions' + (q.length ? `?${q.join('&')}` : ''));
  if (!rows.length) { txBox.innerHTML = '<div class="muted" style="padding-top:6px;">Нет записей</div>'; return; }
  const html = ['<table><thead><tr><th>Время (UTC)</th><th>Событие</th><th>Пользователь</th><th>Сторона</th><th>Тикер</th><th>Цена</th><th>Кол-во</th><th>Сумма</th><th>Примечание</th></tr></thead><tbody>'];
  for (const r of rows) {
    html.push(`<tr>
<td>${r.ts?.replace('T',' ').replace('Z','')}</td>
<td>${r.event_type||''}</td>
<td>${r.username||''}</td>
<td>${r.side||''}</td>
<td>${r.symbol||''}</td>
<td style="text-align:right">${r.price!=null?fmtMoney(r.price):''}</td>
<td style="text-align:right">${r.qty!=null?fmtInt(r.qty):''}</td>
<td style="text-align:right">${r.amount!=null?fmtMoney(r.amount):''}</td>
<td style="text-align:left">${r.note||''}</td>
</tr>`);
  }
  html.push('</tbody></table>');
  txBox.innerHTML = html.join('');
}

async function api(path, opts={}) {
  const res = await fetch(`http://localhost:8081${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers||{}) }
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function createUser(name, balance) {
  return api(`/api/users/create?name=${encodeURIComponent(name)}&balance=${balance}`, { method: 'POST' });
}
async function addSymbol(symbol, lotSize=1) {
  return api(`/api/products/add_symbol?symbol=${encodeURIComponent(symbol)}&lot_size=${lotSize}`, { method: 'POST' });
}
async function grantStock(user, symbol, qty) {
  return api(`/api/admin/grant_stock?user=${encodeURIComponent(user)}&symbol=${encodeURIComponent(symbol)}`, {
    method: 'POST', body: JSON.stringify({ qty: Number(qty) })
  });
}
async function placeOrder(side, user, symbol, price, qty) {
  const qs = `user=${encodeURIComponent(user)}&symbol=${encodeURIComponent(symbol)}&price=${price}&qty=${qty}`;
  return api(`/api/orders/${side.toLowerCase()}?${qs}`, { method: 'POST' });
}


async function submit(side) {
  const user = userInput.value.trim() || 'alice';
  const sym  = symbolSelect.value;
  const px   = Number(priceInput.value);
  const qty  = Number(qtyInput.value);

  if (!sym) { setMsg(tradeMsg, 'Выберите символ', false, true); return; }
  if (!Number.isFinite(px) || px <= 0) { setMsg(tradeMsg, 'Цена должна быть > 0', false, true); return; }
  if (!Number.isInteger(qty) || qty <= 0) { setMsg(tradeMsg, 'Кол-во — целое положительное', false, true); return; }

  try {
    const path = `/api/orders/${side.toLowerCase()}?user=${encodeURIComponent(user)}&symbol=${encodeURIComponent(sym)}&price=${px}&qty=${qty}`;
    const r = await apiPost(path);
    setMsg(tradeMsg, `Заявка отправлена: ${JSON.stringify(r)}`, true, false);
    priceInput.value = '';
    qtyInput.value = '';
    await Promise.all([refreshBook(), refreshProfile(), refreshTx()]);
  } catch (e) {
    setMsg(tradeMsg, String(e.message || e), false, true);
  }
}


el('btnReloadSymbols').onclick = () => loadSymbols();
el('btnAddSymbol').onclick     = () => addSymbol();
el('btnAirdrop').onclick       = () => airdrop();
el('btnBuy').onclick           = () => submit('BUY');
el('btnSell').onclick          = () => submit('SELL');
el('btnRefreshAll').onclick    = () => refreshAll();
el('btnTxFilter').onclick      = () => refreshTx();
el('btnTxReset').onclick       = () => { el('txUser').value=''; el('txSymbol').value=''; refreshTx(); };
symbolSelect.onchange          = () => { refreshBook(); el('txSymbol').value = symbolSelect.value; refreshTx(); };


async function refreshAll() {
  await Promise.all([refreshBook(), refreshProfile(), refreshTx()]);
}


(async function init() {
  try { await loadSymbols(); }
  catch (e) {
    console.error(e);
    setMsg(addSymbolMsg, 'Ошибка загрузки символов. Проверь /api/products/symbols', false, true);
  }
})();
