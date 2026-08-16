const state = { data: null, source: 'all', query: '', showAll: false };

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function aiInfo(paper) {
  return paper?.extra?.ai || null;
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

function paperCard(p) {
  const ai = aiInfo(p);
  return `
    <article class="paper ${ai?.top_pick ? 'top-paper' : ''}">
      <div class="paper-top">
        <span class="source">${esc(p.source)}</span>
        <span>${esc(p.published_date || p.indexed_date || '')}</span>
        ${ai ? `<span class="score-badge">${esc(ai.score)} / 100</span>` : ''}
        ${ai?.topic ? `<span class="topic-badge">${esc(ai.topic)}</span>` : ''}
      </div>
      <h2><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      <p class="authors">${esc((p.authors || []).slice(0, 8).join(', '))}${(p.authors || []).length > 8 ? ' et al.' : ''}</p>
      ${p.journal ? `<p class="journal">${esc(p.journal)}</p>` : ''}
      ${ai?.top_pick && ai.summary ? `<div class="ai-note"><strong>Summary</strong><p>${esc(ai.summary)}</p>${ai.key_finding ? `<strong>Key finding</strong><p>${esc(ai.key_finding)}</p>` : ''}${ai.why_relevant ? `<strong>Why relevant</strong><p>${esc(ai.why_relevant)}</p>` : ''}</div>` : ''}
      ${ai?.reason && !ai?.top_pick ? `<p class="rank-reason">${esc(ai.reason)}</p>` : ''}
      ${p.abstract ? `<p class="abstract">${esc(p.abstract)}</p>` : ''}
      <div class="paper-links">
        ${p.doi ? `<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">DOI</a>` : '<span></span>'}
        <span>${esc((p.categories || []).slice(0, 3).join(' · '))}</span>
      </div>
    </article>`;
}

function renderPapers() {
  const papers = state.data?.papers || [];
  const q = state.query.trim().toLowerCase();
  const filtered = papers.filter(p => {
    const sourceOK = state.source === 'all' || p.source === state.source;
    const hay = `${p.title} ${p.abstract} ${(p.authors || []).join(' ')} ${aiInfo(p)?.topic || ''}`.toLowerCase();
    return sourceOK && (!q || hay.includes(q));
  });

  const aiActive = Boolean(state.data?.ai?.enabled && state.data?.ai?.ranked_count);
  const defaultView = aiActive && state.source === 'all' && !q;
  if (defaultView) {
    const top = filtered.filter(p => aiInfo(p)?.top_pick);
    const rest = filtered.filter(p => !aiInfo(p)?.top_pick);
    let html = `<div class="digest-heading"><div><p class="eyebrow">FOR YOU</p><h2 class="section-title">Top picks</h2></div><span>${top.length} papers</span></div>`;
    html += top.map(paperCard).join('') || '<p class="empty">No AI top picks were produced.</p>';
    if (state.showAll) {
      html += `<div class="digest-heading secondary"><div><p class="eyebrow">FULL FEED</p><h2 class="section-title">Other candidates</h2></div><span>${rest.length} papers</span></div>`;
      html += rest.map(paperCard).join('');
    } else if (rest.length) {
      html += `<button id="showAll" class="show-all">Show all ${rest.length} other candidates</button>`;
    }
    document.querySelector('#papers').innerHTML = html;
    document.querySelector('#showAll')?.addEventListener('click', () => {
      state.showAll = true;
      renderPapers();
    });
    return;
  }

  document.querySelector('#papers').innerHTML = filtered.map(paperCard).join('') || '<p class="empty">No papers match this filter.</p>';
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

    const ai = d.ai || {};
    if (ai.enabled) {
      document.querySelector('#aiStatus').innerHTML = `<div class="ai-banner"><strong>Personalized ranking active</strong><span>${ai.ranked_count ?? 0} candidates scored · top ${ai.top_n ?? 0} summarized · ${esc(ai.model || '')}</span></div>`;
    } else if (ai.requested && ai.status === 'missing_api_key') {
      document.querySelector('#aiStatus').innerHTML = '<div class="ai-banner muted"><strong>Raw feed</strong><span>Add the OPENAI_API_KEY GitHub secret to enable personalized ranking.</span></div>';
    }

    const errors = Object.entries(d.errors || {});
    const aiErrors = (ai.errors || []).length;
    document.querySelector('#status').innerHTML = errors.length || aiErrors
      ? `<div class="warning">${errors.length ? `Source issues: ${errors.map(([k,v]) => `${esc(k)} (${esc(v)})`).join(' · ')}` : ''}${errors.length && aiErrors ? '<br>' : ''}${aiErrors ? `AI ranking reported ${aiErrors} error(s); raw papers remain available.` : ''}</div>`
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
