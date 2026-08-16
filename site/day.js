const EN_LOCALE = 'en-US';
const SOURCE_ORDER = ['pubmed', 'biorxiv', 'medrxiv', 'arxiv'];
const state = { data: null, query: '' };

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function sourceName(value = '') {
  const names = { pubmed: 'PubMed', biorxiv: 'bioRxiv', medrxiv: 'medRxiv', arxiv: 'arXiv' };
  return names[String(value).toLowerCase()] || value;
}

function prettyDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long', timeZone: 'UTC'
  }).format(date);
}

function updatedTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
  }).format(date);
}

function money(value) {
  const number = Number(value || 0);
  if (number < 0.01) return `¥${number.toFixed(4)}`;
  return `¥${number.toFixed(2)}`;
}

function paperCard(p, rank) {
  const score = p.score === null || p.score === undefined ? '' : `<span class="score-badge">${esc(p.score)} / 100</span>`;
  return `
    <article class="paper digest-paper">
      <div class="paper-top">
        <span class="rank-number">#${rank}</span>
        <span class="source">${esc(sourceName(p.source))}</span>
        ${score}
      </div>
      <h2><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      ${p.summary ? `<p class="digest-summary">${esc(p.summary)}</p>` : '<p class="digest-summary muted-text">Summary unavailable.</p>'}
      <a class="read-link" href="${esc(p.url || '#')}" target="_blank" rel="noopener">Read paper →</a>
    </article>`;
}

function renderSourceSummary() {
  const counts = state.data?.retrieved_source_counts || {};
  const pills = SOURCE_ORDER.map(source => `
    <span class="source-total-pill"><strong>${esc(sourceName(source))}</strong> ${Number(counts[source] || 0)}</span>
  `).join('');
  document.querySelector('#sourceSummary').innerHTML = `<div class="source-summary">${pills}</div>`;
}

function renderPapers() {
  const papers = state.data?.papers || [];
  const featuredCount = Math.min(Number(state.data?.featured_count || 25), papers.length);
  const q = state.query.trim().toLowerCase();
  const ranked = papers.map((paper, index) => ({ paper, rank: index + 1 }));
  const matches = ranked.filter(({ paper }) => !q || `${paper.title} ${paper.summary || ''} ${paper.source || ''}`.toLowerCase().includes(q));
  const featured = matches.filter(({ rank }) => rank <= featuredCount);
  const additional = matches.filter(({ rank }) => rank > featuredCount);

  const featuredHtml = featured.map(({ paper, rank }) => paperCard(paper, rank)).join('');
  const additionalHtml = additional.map(({ paper, rank }) => paperCard(paper, rank)).join('');
  const section = document.querySelector('#papers');

  if (!matches.length) {
    section.innerHTML = '<p class="empty">No papers match this filter.</p>';
    return;
  }

  const extraBlock = additional.length ? `
    <details class="more-papers" ${q ? 'open' : ''}>
      <summary>Show ${additional.length} more paper${additional.length === 1 ? '' : 's'}${q ? ' matching this search' : ` · ranks ${featuredCount + 1}–${papers.length}`}</summary>
      <div class="more-papers-list">${additionalHtml}</div>
    </details>` : '';

  section.innerHTML = `
    <div class="digest-heading">
      <div>
        <p class="eyebrow">TOP ${featuredCount}</p>
        <h2 class="section-title">Highest relevance</h2>
      </div>
      <span>Sorted from highest to lowest relevance</span>
    </div>
    <div class="featured-papers">${featuredHtml}</div>
    ${extraBlock}`;
}

async function boot() {
  const params = new URLSearchParams(window.location.search);
  const date = params.get('date') || '';
  const version = params.get('v') || '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    document.querySelector('#status').innerHTML = '<div class="warning">Invalid or missing archive date.</div>';
    return;
  }

  document.querySelector('#dayTitle').textContent = prettyDate(date);
  document.title = `PaperDaily · ${prettyDate(date)}`;
  try {
    const suffix = version ? `?v=${encodeURIComponent(version)}` : '';
    const response = await fetch(`data/days/${encodeURIComponent(date)}.json${suffix}`, {
      cache: version ? 'force-cache' : 'no-cache'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    const d = state.data;
    const updated = updatedTime(d.generated_at || '');
    document.querySelector('#meta').textContent = `${d.total_count ?? 0} unique papers${updated ? ` · Updated ${updated}` : ''}`;
    renderSourceSummary();

    const ai = d.ai || {};
    const billing = ai.billing || {};
    if (ai.enabled) {
      const cost = billing.daily_cost_cny !== undefined ? ` · ${money(billing.daily_cost_cny)} today` : '';
      document.querySelector('#aiStatus').innerHTML = `<div class="ai-banner"><strong>Personalized daily digest</strong><span>${d.featured_count ?? 0} highlighted · ${d.additional_count ?? 0} more · ${esc(ai.model || '')}${cost}</span></div>`;
    } else if (ai.status) {
      document.querySelector('#aiStatus').innerHTML = `<div class="ai-banner muted"><strong>Compact feed</strong><span>AI status: ${esc(ai.status)}</span></div>`;
    }

    const errors = Object.entries(d.errors || {});
    const aiErrors = (ai.errors || []).length;
    document.querySelector('#status').innerHTML = errors.length || aiErrors
      ? `<div class="warning">${errors.length ? `Source issues: ${errors.map(([k,v]) => `${esc(sourceName(k))} (${esc(v)})`).join(' · ')}` : ''}${errors.length && aiErrors ? '<br>' : ''}${aiErrors ? `AI reported ${aiErrors} error(s).` : ''}</div>`
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
