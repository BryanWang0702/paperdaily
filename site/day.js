const state = { data: null, query: '' };

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#039;'}[c]));
}

function money(value) {
  const number = Number(value || 0);
  if (number < 0.01) return `¥${number.toFixed(4)}`;
  return `¥${number.toFixed(2)}`;
}

function paperCard(p) {
  return `
    <article class="paper digest-paper">
      <h2><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      ${p.summary ? `<p class="digest-summary">${esc(p.summary)}</p>` : '<p class="digest-summary muted-text">Summary unavailable.</p>'}
      <a class="read-link" href="${esc(p.url || '#')}" target="_blank" rel="noopener">Read paper →</a>
    </article>`;
}

function renderPapers() {
  const papers = state.data?.papers || [];
  const q = state.query.trim().toLowerCase();
  const filtered = papers.filter(p => !q || `${p.title} ${p.summary || ''}`.toLowerCase().includes(q));
  document.querySelector('#papers').innerHTML = filtered.map(paperCard).join('') || '<p class="empty">No papers match this filter.</p>';
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const date = params.get('date') || '';
  const version = params.get('v') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    document.querySelector('#status').innerHTML = '<div class="warning">Invalid or missing archive date.</div>';
    return;
  }

  document.querySelector('#dayTitle').textContent = date;
  document.title = `PaperDaily · ${date}`;
  try {
    const suffix = version ? `?v=${encodeURIComponent(version)}` : '';
    const response = await fetch(`data/days/${encodeURIComponent(date)}.json${suffix}`, {
      cache: version ? 'force-cache' : 'no-cache'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    const d = state.data;
    document.querySelector('#meta').textContent = `${d.count ?? 0} recommended · ${d.candidate_count ?? 0} candidates · ${d.raw_count ?? 0} discovered`;

    const ai = d.ai || {};
    const billing = ai.billing || {};
    if (ai.enabled) {
      const cost = billing.daily_cost_cny !== undefined ? ` · ${money(billing.daily_cost_cny)} today` : '';
      document.querySelector('#aiStatus').innerHTML = `<div class="ai-banner"><strong>Personalized digest</strong><span>${ai.ranked_count ?? 0} candidates analyzed · ${d.count ?? 0} summarized · ${esc(ai.model || '')}${cost}</span></div>`;
    } else if (ai.status) {
      document.querySelector('#aiStatus').innerHTML = `<div class="ai-banner muted"><strong>Compact feed</strong><span>AI status: ${esc(ai.status)}</span></div>`;
    }

    const errors = Object.entries(d.errors || {});
    const aiErrors = (ai.errors || []).length;
    document.querySelector('#status').innerHTML = errors.length || aiErrors
      ? `<div class="warning">${errors.length ? `Source issues: ${errors.map(([k,v]) => `${esc(k)} (${esc(v)})`).join(' · ')}` : ''}${errors.length && aiErrors ? '<br>' : ''}${aiErrors ? `AI reported ${aiErrors} error(s).` : ''}</div>`
      : '';
    renderPapers();
  } catch (error) {
    document.querySelector('#status').innerHTML = `<div class="warning">Could not load this day's data: ${esc(String(error))}</div>`;
  }
}

document.querySelector('#search').addEventListener('input', event => {
  state.query = event.target.value;
  renderPapers();
});

boot();
