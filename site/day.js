const state = { data: null, source: 'all', query: '' };

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function renderFilters(data) {
  const wrap = document.querySelector('#sourceFilters');
  const sources = ['all', ...Object.keys(data.source_counts || {})];
  wrap.innerHTML = sources.map(source => {
    const count = source === 'all' ? data.count : data.source_counts[source];
    return `<button data-source="${esc(source)}" class="${state.source === source ? 'active' : ''}">${esc(source)} <span>${count ?? 0}</span></button>`;
  }).join('');
  wrap.querySelectorAll('button').forEach(btn => btn.addEventListener('click', () => {
    state.source = btn.dataset.source;
    renderFilters(data);
    renderPapers();
  }));
}

function renderPapers() {
  const papers = state.data?.papers || [];
  const q = state.query.trim().toLowerCase();
  const filtered = papers.filter(p => {
    const sourceOK = state.source === 'all' || p.source === state.source;
    const hay = `${p.title} ${p.abstract} ${(p.authors || []).join(' ')}`.toLowerCase();
    return sourceOK && (!q || hay.includes(q));
  });

  document.querySelector('#papers').innerHTML = filtered.map(p => `
    <article class="paper">
      <div class="paper-top">
        <span class="source">${esc(p.source)}</span>
        <span>${esc(p.published_date || p.indexed_date || '')}</span>
      </div>
      <h2><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      <p class="authors">${esc((p.authors || []).slice(0, 8).join(', '))}${(p.authors || []).length > 8 ? ' et al.' : ''}</p>
      ${p.journal ? `<p class="journal">${esc(p.journal)}</p>` : ''}
      ${p.abstract ? `<p class="abstract">${esc(p.abstract)}</p>` : ''}
      <div class="paper-links">
        ${p.doi ? `<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">DOI</a>` : '<span></span>'}
        <span>${esc((p.categories || []).slice(0, 3).join(' · '))}</span>
      </div>
    </article>
  `).join('') || '<p class="empty">No papers match this filter.</p>';
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const date = params.get('date') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    document.querySelector('#status').innerHTML = '<div class="warning">Invalid or missing archive date.</div>';
    return;
  }

  document.querySelector('#dayTitle').textContent = date;
  document.title = `PaperDaily · ${date}`;
  try {
    const response = await fetch(`data/days/${encodeURIComponent(date)}.json?v=${Date.now()}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    const d = state.data;
    document.querySelector('#meta').textContent = `${d.count ?? 0} candidates · ${d.window?.start ?? ''} → ${d.window?.end ?? ''}`;
    const errors = Object.entries(d.errors || {});
    document.querySelector('#status').innerHTML = errors.length
      ? `<div class="warning">Some sources failed: ${errors.map(([k,v]) => `${esc(k)} (${esc(v)})`).join(' · ')}</div>`
      : '';
    renderFilters(d);
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
