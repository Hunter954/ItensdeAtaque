(() => {
  const table = document.getElementById('gridTable');
  if (!table) return;

  const teamId = table.dataset.teamId;
  const periodId = table.dataset.periodId;

  const statusEl = document.getElementById('saveStatus');
  const metaEl = document.getElementById('saveMeta');

  const sellerSearch = document.getElementById('searchSeller');
  const itemSearch = document.getElementById('searchItem');
  const focusSelect = document.getElementById('focusItem');

  let saveTimer = null;
  let pending = null;
  let inFlight = false;

  function setStatus(kind, text) {
    statusEl.textContent = text;
    statusEl.className = 'badge';
    statusEl.classList.add(kind === 'ok' ? 'text-bg-primary' : kind === 'saving' ? 'text-bg-warning' : kind === 'error' ? 'text-bg-danger' : 'text-bg-secondary');
  }

  function clampInt(n) {
    const v = parseInt(n, 10);
    return Number.isFinite(v) && v >= 0 ? v : 0;
  }

  function updateRemainingForInput(inp) {
  const target = clampInt(inp.dataset.target || 0);
  if (!target) return;
  const v = clampInt(inp.value);
        updateRemainingForInput(inp);
  const td = inp.closest('td');
  if (!td) return;
  const label = td.querySelector('.remaining');
  if (!label) return;

  const remaining = target - v;
  if (remaining > 0) {
    label.textContent = `Faltam ${remaining}`;
    label.classList.remove('d-none');
    label.classList.add('text-danger');
  } else {
    // Meta batida: some a mensagem, fica só o saldo vendido (o input)
    label.textContent = '';
    label.classList.add('d-none');
  }
}

function recalcTotals() {
    const bodyRows = table.querySelectorAll('tbody tr.seller-row');
    const itemCols = table.querySelectorAll('thead .item-col');
    const colTotals = {};
    itemCols.forEach(th => colTotals[th.dataset.itemId] = 0);

    let grand = 0;

    bodyRows.forEach(tr => {
      let rowTotal = 0;
      tr.querySelectorAll('input.qty').forEach(inp => {
        const itemId = inp.dataset.itemId;
        const v = clampInt(inp.value);
        updateRemainingForInput(inp);
        rowTotal += v;
        colTotals[itemId] = (colTotals[itemId] || 0) + v;
      });
      tr.querySelector('.row-total').textContent = rowTotal;
      grand += rowTotal;
    });

    table.querySelectorAll('tfoot .col-total').forEach(th => {
      const itemId = th.dataset.itemId;
      th.textContent = colTotals[itemId] || 0;
    });

    document.getElementById('grandTotal').textContent = grand;
  }

  function applyFilters() {
    const sTerm = (sellerSearch.value || '').trim().toLowerCase();
    const iTerm = (itemSearch.value || '').trim().toLowerCase();
    const focus = (focusSelect.value || '').trim();

    // Rows filter
    table.querySelectorAll('tbody tr.seller-row').forEach(tr => {
      const name = (tr.querySelector('.seller-name')?.textContent || '').toLowerCase();
      tr.style.display = (!sTerm || name.includes(sTerm)) ? '' : 'none';
    });

    // Columns filter: by item search + focus
    const itemHeaders = table.querySelectorAll('thead th.item-col');
    itemHeaders.forEach(th => {
      const itemId = th.dataset.itemId;
      const itemName = (th.querySelector('.item-name')?.textContent || '').toLowerCase();
      let show = true;
      if (iTerm && !itemName.includes(iTerm)) show = false;
      if (focus && itemId !== focus) show = false;

      const display = show ? '' : 'none';
      th.style.display = display;
      table.querySelectorAll(`tbody td.item-col[data-item-id="${itemId}"]`).forEach(td => td.style.display = display);
      table.querySelectorAll(`tfoot th.item-col[data-item-id="${itemId}"]`).forEach(td => td.style.display = display);
    });

    recalcTotals();
  }

  async function flushSave() {
    if (!pending || inFlight) return;
    inFlight = true;
    setStatus('saving', 'Salvando…');

    const payload = pending;
    pending = null;

    try {
      const res = await fetch('/api/cell', {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao salvar');
      setStatus('ok', 'Salvo');
      metaEl.textContent = data.updated_at ? `Atualizado: ${data.updated_at}` : '';
    } catch (e) {
      console.error(e);
      setStatus('error', 'Erro');
      // keep last payload to retry on next change
      pending = payload;
    } finally {
      inFlight = false;
    }
  }

  function queueSave(sellerId, itemId, value) {
    pending = { team_id: teamId, period_id: periodId, seller_id: sellerId, item_id: itemId, value: value };
    setStatus('saving', 'Salvando…');
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSave, 450);
  }

  function setInputValue(inp, value) {
    inp.value = clampInt(value);
  }

  function wireCell(td) {
    const dec = td.querySelector('button.dec');
    const inc = td.querySelector('button.inc');
    const inp = td.querySelector('input.qty');
    if (!inp) return;

    function push() {
      const v = clampInt(inp.value);
        updateRemainingForInput(inp);
      inp.value = v;
      queueSave(inp.dataset.sellerId, inp.dataset.itemId, v);
      recalcTotals();
    }

    inc?.addEventListener('click', () => { setInputValue(inp, clampInt(inp.value) + 1); push(); });
    dec?.addEventListener('click', () => { setInputValue(inp, Math.max(0, clampInt(inp.value) - 1)); push(); });
    inp.addEventListener('change', push);
    inp.addEventListener('input', () => {
      // realtime totals, save on debounce
      const v = clampInt(inp.value);
        updateRemainingForInput(inp);
      inp.value = v;
      queueSave(inp.dataset.sellerId, inp.dataset.itemId, v);
      recalcTotals();
    });
  }

  function init() {
    setStatus('idle', 'Pronto');
    table.querySelectorAll('tbody td.item-col').forEach(wireCell);

    sellerSearch.addEventListener('input', applyFilters);
    itemSearch.addEventListener('input', applyFilters);
    focusSelect.addEventListener('change', applyFilters);

    recalcTotals();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
