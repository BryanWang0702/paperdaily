const EN_LOCALE = 'en-US';
const DISPLAY_TIME_ZONE = 'Asia/Shanghai';
const SOURCE_ORDER = ['pubmed', 'biorxiv', 'medrxiv', 'arxiv'];
const state = { data: null, query: '', keyword: '' };

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function sourceName(value = '') {
  const names = { pubmed: 'PubMed', biorxiv: 'bioRxiv', medrxiv: 'medRxiv', arxiv: 'arXiv' };
  return names[String(value).toLowerCase()] || value;
}

function prettyDate(value) {
  const date = new Date(`${value}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'long', timeZone: DISPLAY_TIME_ZONE
  }).format(date);
}

function updatedTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const formatted = new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: DISPLAY_TIME_ZONE
  }).format(date);
  return `${formatted} Beijing time`;
}

function paperCard(p, rank) {
  const score = p.score === null || p.score === undefined ? '' : `<span class="score-badge">${esc(p.score)} / 100</span>`;
  const paperType = p.paper_type ? `<span class="type-badge">${esc(p.paper_type)}</span>` : '';
  const journalHtml = p.journal
    ? `<p class="paper-journal"><strong>Journal</strong> ${esc(p.journal)}</p>`
    : '';
  const authors = Array.isArray(p.authors) ? p.authors.filter(Boolean) : [];
  const authorHtml = authors.length
    ? `<p class="paper-authors"><strong>Authors</strong> ${authors.map(esc).join(', ')}</p>`
    : '<p class="paper-authors muted-text"><strong>Authors</strong> Not available</p>';
  const keywords = Array.isArray(p.keywords) ? p.keywords.filter(Boolean) : [];
  const keywordHtml = keywords.length
    ? `<div class="keyword-list">${keywords.map(keyword => `<span class="keyword-pill">${esc(keyword)}</span>`).join('')}</div>`
    : '';

  return `
    <article class="paper digest-paper">
      <div class="paper-top">
        <span class="rank-number">#${rank}</span>
        <span class="source">${esc(sourceName(p.source))}</span>
        ${paperType}
        ${score}
      </div>
      <h2><a href="${esc(p.url || '#')}" target="_blank" rel="noopener">${esc(p.title)}</a></h2>
      ${journalHtml}
      ${authorHtml}
      ${keywordHtml}
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

function topKeywords(limit = 7) {
  const counts = new Map();
  const labels = new Map();
  for (const paper of state.data?.papers || []) {
    for (const raw of paper.keywords || []) {
      const label = String(raw || '').trim();
      const key = label.toLowerCase();
      if (!key) continue;
      counts.set(key, (counts.get(key) || 0) + 1);
      if (!labels.has(key)) labels.set(key, label);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || labels.get(a[0]).localeCompare(labels.get(b[0])))
    .slice(0, limit)
    .map(([key, count]) => ({ key, label: labels.get(key), count }));
}

function renderKeywordFilters() {
  const target = document.querySelector('#keywordFilters');
  const keywords = topKeywords();
  if (!keywords.length) {
    target.innerHTML = '<span class="muted-text filter-empty">No keyword shortcuts available.</span>';
    return;
  }
  const allClass = state.keyword ? '' : ' active';
  target.innerHTML = `<button type="button" class="quick-filter${allClass}" data-keyword="">All</button>` +
    keywords.map(({ key, label, count }) => {
      const active = state.keyword === key ? ' active' : '';
      return `<button type="button" class="quick-filter${active}" data-keyword="${esc(key)}">${esc(label)} <span>${count}</span></button>`;
    }).join('');

  target.querySelectorAll('[data-keyword]').forEach(button => {
    button.addEventListener('click', () => {
      state.keyword = button.dataset.keyword || '';
      renderKeywordFilters();
      renderPapers();
    });
  });
}

function renderPapers() {
  const papers = state.data?.papers || [];
  const featuredCount = Math.min(Number(state.data?.featured_count || 25), papers.length);
  const q = state.query.trim().toLowerCase();
  const ranked = papers.map((paper, index) => ({ paper, rank: index + 1 }));
  const matches = ranked.filter(({ paper }) => {
    const authors = Array.isArray(paper.authors) ? paper.authors.join(' ') : '';
    const keywords = Array.isArray(paper.keywords) ? paper.keywords.join(' ') : '';
    const keywordKeys = Array.isArray(paper.keywords) ? paper.keywords.map(value => String(value).toLowerCase()) : [];
    const text = `${paper.title} ${paper.journal || ''} ${paper.summary || ''} ${paper.source || ''} ${paper.paper_type || ''} ${authors} ${keywords}`.toLowerCase();
    const matchesText = !q || text.includes(q);
    const matchesKeyword = !state.keyword || keywordKeys.includes(state.keyword);
    return matchesText && matchesKeyword;
  });
  const featured = matches.filter(({ rank }) => rank <= featuredCount);
  const additional = matches.filter(({ rank }) => rank > featuredCount);

  const featuredHtml = featured.map(({ paper, rank }) => paperCard(paper, rank)).join('');
  const additionalHtml = additional.map(({ paper, rank }) => paperCard(paper, rank)).join('');
  const section = document.querySelector('#papers');

  if (!matches.length) {
    section.innerHTML = '<p class="empty">No papers match these filters.</p>';
    return;
  }

  const filtered = Boolean(q || state.keyword);
  const extraBlock = additional.length ? `
    <details class="more-papers" ${filtered ? 'open' : ''}>
      <summary>Show ${additional.length} more paper${additional.length === 1 ? '' : 's'}${filtered ? ' matching these filters' : ` · ranks ${featuredCount + 1}–${papers.length}`}</summary>
      <div class="more-papers-list">${additionalHtml}</div>
    </details>` : '';

  section.innerHTML = `
    <div class="digest-heading">
      <div>
        <p class="eyebrow">TOP ${featuredCount}</p>
        <h2 class="section-title">Highest relevance</h2>
      </div>
      <span>${matches.length} paper${matches.length === 1 ? '' : 's'} shown · sorted by relevance</span>
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
    renderKeywordFilters();

    const ai = d.ai || {};
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
