const $ = (sel) => document.querySelector(sel);
let current = { holdings: [] };
let sortKey = "percentValue";   // default sort: percent total
let sortAsc = false;            // highest first
let chart = null;

function setStatus(msg, isError = false) {
  const el = $("#status");
  el.textContent = msg || "";
  el.style.color = isError ? "#b00020" : "#444";
}

function parseMoney(s) {
  if (!s) return 0;
  return +(String(s).replace(/[$,]/g, "")) || 0;
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

function renderTable() {
  const tbody = $("#tbl tbody");
  const filter = ($("#filter").value || "").toLowerCase();
  let rows = current.holdings || [];
  if (filter) rows = rows.filter((h) => (h.name || "").toLowerCase().includes(filter));

  const totalValue = rows.reduce((sum, h) => sum + parseMoney(h.valueUsd), 0);

  let enriched = rows
    .filter(h => !(h.name || "").toLowerCase().startsWith("total"))
    .map(h => {
      const valueNum = parseMoney(h.valueUsd);
      const balanceNum = parseMoney(h.balance);
      const percentValueNum = totalValue ? (valueNum / totalValue) * 100 : 0;
      return {
        ...h,
        valueNum,
        balanceNum,
        percentValueNum,
        percentValue: totalValue ? percentValueNum.toFixed(2) + "%" : "",
      };
    });

  // Sort logic
  if (sortKey) {
    enriched = enriched.slice().sort((a, b) => {
      const aVal = a[sortKey + "Num"] ?? (a[sortKey] || "").toLowerCase();
      const bVal = b[sortKey + "Num"] ?? (b[sortKey] || "").toLowerCase();
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
  }

  // Totals
  const totalBalance = enriched.reduce((sum, h) => sum + (h.balanceNum || 0), 0);
  const totalVal = enriched.reduce((sum, h) => sum + (h.valueNum || 0), 0);

  // Render table
  tbody.innerHTML =
    enriched
      .map(
        (h) => `
      <tr>
        <td>${h.cusip || ""}</td>
        <td>${h.name || ""}</td>
        <td>${h.balance || ""}</td>
        <td>${h.valueUsd || ""}</td>
        <td>${h.percentValue || ""}</td>
      </tr>`
      )
      .join("") +
    (enriched.length > 1
      ? `
      <tr style="font-weight:bold; background:#f9f9f9;">
        <td colspan="2">TOTAL</td>
        <td>${totalBalance.toLocaleString()}</td>
        <td>$${totalVal.toLocaleString()}</td>
        <td>100%</td>
      </tr>`
      : "");

  $("#tbl").hidden = enriched.length === 0;
  $("#filterBox").style.display = enriched.length === 0 ? "none" : "flex";
}

function renderPie() {
  try {
    if (chart) chart.destroy();
  } catch {}
  const ctx = $("#pie");
  const titleEl = $("#chart-title");

  const filter = ($("#filter").value || "").toLowerCase();
  let rows = current.holdings || [];
  if (filter) rows = rows.filter((h) => (h.name || "").toLowerCase().includes(filter));

  const items = rows
    .map((h) => ({
      name: h.name || "Unknown",
      value: +(String(h.valueUsd || "").replace(/[$,]/g, "")) || 0,
    }))
    .filter((x) => x.value > 0)
    .sort((a, b) => b.value - a.value);

  if (!items.length) {
    ctx.style.display = "none";
    titleEl.style.display = "none";
    return;
  }

  const MAX_SLICES = 30;
  const head = items.slice(0, MAX_SLICES);
  const othersTotal = items.slice(MAX_SLICES).reduce((sum, x) => sum + x.value, 0);

  const labels = head.map((x) => x.name.substring(0, 40));
  const data = head.map((x) => x.value);
  if (othersTotal > 0) {
    labels.push("Others");
    data.push(othersTotal);
  }

  ctx.style.display = "block";
  titleEl.style.display = "block";

  chart = new Chart(ctx, {
    type: "pie",
    data: { labels, datasets: [{ data }] },
    options: {
      plugins: {
        legend: { position: "right" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const v = ctx.raw;
              const pct = total ? ((v / total) * 100).toFixed(1) : "0.0";
              return `${ctx.label}: ${v.toLocaleString()} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

async function fetchHoldings(cik) {
  setStatus("Loading…");
  try {
    const res = await fetch(`/api/holdings/${encodeURIComponent(cik)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    current = data;
    const when = data.asOf ? ` as of ${data.asOf}` : "";
    setStatus(`Loaded ${data.count} holdings${when}.`);
    renderTable();
    renderPie();

    // Default sort: Percent of Total descending
    const percentHeader = document.querySelector('th[data-key="percentValue"]');
    if (percentHeader) {
      percentHeader.click(); // ascending
      percentHeader.click(); // descending
    }
  } catch (err) {
    setStatus(err.message, true);
    current = { holdings: [] };
    renderTable();
    renderPie();
  }
}

$("#go").addEventListener("click", () => {
  const cik = $("#cik").value.trim();
  if (!cik) {
    setStatus("Enter a CIK.");
    return;
  }
  fetchHoldings(cik);
});

$("#filter").addEventListener("input", () => {
  renderTable();
  renderPie();
});

Array.from(document.querySelectorAll('th[data-key]')).forEach(th => {
  th.classList.add('sortable');
  // Inject arrow span once
  if (!th.querySelector('.arrow')) {
    th.insertAdjacentHTML('beforeend', ' <span class="arrow" style="opacity:.5;"></span>');
  }

  th.addEventListener('click', () => {
    const key = th.getAttribute('data-key');
    sortAsc = (sortKey === key) ? !sortAsc : true;
    sortKey = key;

    renderTable();
    renderPie();
    updateSortArrows();
  });
});


updateSortArrows();
