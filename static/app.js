const $ = (sel) => document.querySelector(sel);
let current = { holdings: [] };
let sortKey = 'valueUsd';
let sortAsc = false; // default: highest value first
let chart = null;

function setStatus(msg, isError=false){
  const el = $('#status');
  el.textContent = msg || '';
  el.style.color = isError ? '#b00020' : '#444';
}

function fmtNum(s){
  if (s == null || s === '') return '';
  const n = Number(String(s).replace(/[$,\s]/g,''));
  if (!isFinite(n)) return s;
  return n.toLocaleString();
}
function parseNum(s){
  const n = Number(String(s||'').replace(/[$,\s]/g,''));
  return isFinite(n) ? n : 0;
}

function updateSortArrows(){
  document.querySelectorAll('th.sortable').forEach(th => {
    const key = th.getAttribute('data-key');
    const arrow = th.querySelector('.arrow');
    if (!arrow) return;
    if (key === sortKey){
      arrow.textContent = sortAsc ? '▲' : '▼';
      arrow.style.opacity = 1;
    } else {
      arrow.textContent = '';
      arrow.style.opacity = .5;
    }
  });
}

function renderTable(){
  const tbody = $('#tbl tbody');
  const filter = ($('#filter').value || '').toLowerCase();
  let rows = current.holdings || [];

  // filter
  if (filter) rows = rows.filter(h => (h.name||'').toLowerCase().includes(filter));

  // sort
  if (sortKey){
    rows = rows.slice().sort((a,b)=>{
      const A = a[sortKey] ?? '';
      const B = b[sortKey] ?? '';
      // numeric-aware
      const na = parseNum(A), nb = parseNum(B);
      if (!Number.isNaN(na) && !Number.isNaN(nb) && (na !== 0 || nb !== 0 || /\d/.test(A+B))){
        return sortAsc ? (na - nb) : (nb - na);
      }
      return sortAsc ? String(A).localeCompare(String(B)) : String(B).localeCompare(String(A));
    });
  }

  // totals
  const totalBalance = rows.reduce((acc,h)=> acc + parseNum(h.balance), 0);
  const totalValue = rows.reduce((acc,h)=> acc + parseNum(h.valueUsd), 0);
  $('#total-balance').textContent = fmtNum(totalBalance);
  $('#total-value').textContent = fmtNum(totalValue);

  // rows
  tbody.innerHTML = rows.map(h=>`
    <tr>
      <td>${h.cusip || ''}</td>
      <td>${h.name || ''}</td>
      <td class="right">${fmtNum(h.balance)}</td>
      <td class="right">${fmtNum(h.valueUsd)}</td>
    </tr>
  `).join('');
  $('#tbl').hidden = rows.length === 0;
  updateSortArrows();
}

function renderPie(){
  try{ if (chart){ chart.destroy(); } } catch{}
  const el = $('#pie');

  // Take top 12 by value
  const rows = (current.holdings||[]);
  const total = rows.reduce((acc,h)=> acc + parseNum(h.valueUsd), 0);
  const top = rows
    .map(h=>({ name: h.name || 'Unknown', value: parseNum(h.valueUsd) }))
    .filter(x=>x.value>0)
    .sort((a,b)=>b.value-a.value)
    .slice(0,12);

  if (top.length === 0){ el.style.display = 'none'; return; }
  el.style.display = 'block';

  const values = top.map(x=>x.value);
  const labels = top.map(x=>x.name.substring(0,60)); // slightly longer labels

  // Register plugin (Chart.js v4 requires it passed via options.plugins or registered globally)
  // Here we configure it per-chart.
  chart = new Chart(el, {
    type: 'pie',
    data: {
      labels,
      datasets: [{ data: values }]
    },
    options: {
      plugins: {
        legend: { position: 'right' },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed || 0;
              const pct = total ? (v/total*100) : 0;
              return `${ctx.label}: ${v.toLocaleString()} (${pct.toFixed(1)}%)`;
            }
          }
        },
        datalabels: {
          formatter: (v, ctx) => {
            const pct = total ? (v/total*100) : 0;
            // Show % only for slices >= 2% to reduce clutter
            return pct >= 2 ? `${pct.toFixed(1)}%` : '';
          },
          anchor: 'end',
          align: 'end',
          clamp: true,
          offset: 4
        }
      }
    },
    plugins: [ChartDataLabels]
  });
}

async function fetchHoldings(cik){
  setStatus('Loading…');
  try{
    const res = await fetch(`/api/holdings/${encodeURIComponent(cik)}`);
    const data = await res.json();
    if (!res.ok){ throw new Error(data.error || 'Request failed'); }
    current = data;
    const when = data.asOf ? ` as of ${data.asOf}` : '';
    setStatus(`Loaded ${data.count} holdings${when}. Click any column header to sort.`);
    renderPie();   // draw chart first (now above table)
    renderTable(); // then render table
  }catch(err){
    setStatus(err.message, true);
    current = { holdings: [] };
    renderPie();
    renderTable();
  }
}

$('#go').addEventListener('click', ()=>{
  const cik = $('#cik').value.trim();
  if (!cik){ setStatus('Enter a CIK.'); return; }
  fetchHoldings(cik);
});

$('#filter').addEventListener('input', ()=>{
  renderTable();
  renderPie(); // keep chart in sync with filter if you want; remove this line to keep chart on full set
});

Array.from(document.querySelectorAll('th.sortable')).forEach(th => {
  th.addEventListener('click', () => {
    const key = th.getAttribute('data-key');
    if (sortKey === key){ sortAsc = !sortAsc; }
    else { sortKey = key; sortAsc = (key !== 'valueUsd'); }
    renderTable();
  });
});
