const EN_LOCALE = 'en-US';

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function prettyDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short', timeZone: 'UTC'
  }).format(date);
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    month: 'short', day: 'numeric', timeZone: 'UTC'
  }).format(date);
}

function updatedTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(EN_LOCALE, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
  }).format(date);
}

function sourceName(value = '') {
  const names = { pubmed: 'PubMed', biorxiv: 'bioRxiv', medrxiv: 'medRxiv', arxiv: 'arXiv' };
  return names[String(value).toLowerCase()] || value;
}

function money(value) {
  const number = Number(value || 0);
  if (number < 0.01) return `¥${number.toFixed(4)}`;
  return `¥${number.toFixed(2)}`;
}

function topPreview(titles = []) {
  if (!titles.length) return '';
  return `<ol class="top-preview">${titles.slice(0, 5).map(title => `<li>${esc(title)}</li>`).join('')}</ol>`;
}

function renderRanking(targetId, ranking) {
  const target = document.querySelector(targetId);
  const papers = ranking?.papers || [];
  if (!papers.length) {
    target.innerHTML = '<li class="ranking-empty">More papers are needed to build this ranking.</li>';
    return;
  }
  target.innerHTML = papers.map(paper => `
    <li class="ranking-item">
      <a href="${esc(paper.url || '#')}" target="_blank" rel="noopener">${esc(paper.title)}</a>
      <div class="ranking-meta">
        <span>${esc(sourceName(paper.source))} · ${esc(shortDate(paper.date || ''))}</span>
        <span class="ranking-score">${esc(paper.score)} / 100</span>
      </div>
    </li>`).join('');
}

async function boot() {
  const archive = document.querySelector('#archive');
  const status = document.querySelector('#status');
  try {
    const response = await fetch('data/archive.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const days = data.days || [];
    const billing = data.billing || {};
    const billingText = billing.tracked_days
      ? ` · API ${money(billing.total_cost_cny)} total · ~${money(billing.annual_estimate_cny)}/year`
      : '';
    document.querySelector('#meta').textContent = days.length
      ? `${days.length} archived day${days.length === 1 ? '' : 's'}${billingText}`
      : 'No archived days yet';

    renderRanking('#monthlyRanking', data.rankings?.monthly);

    archive.innerHTML = days.map((day, index) => {
      const ai = day.ai || {};
      const featured = Number(day.featured_count || 0);
      const additional = Number(day.additional_count || 0);
      const updated = updatedTime(day.generated_at || '');
      const costBadge = ai.daily_cost_cny !== null && ai.daily_cost_cny !== undefined
        ? `<span class="source-pill">API ${money(ai.daily_cost_cny)}</span>`
        : '';
      const version = day.generated_at ? `&v=${encodeURIComponent(day.generated_at)}` : '';
      return `
        <a class="day-card" href="day.html?date=${encodeURIComponent(day.date)}${version}">
          <div class="day-card-top">
            <span class="day-date">${esc(prettyDate(day.date))}</span>
            ${index === 0 ? '<span class="today-badge">LATEST</span>' : ''}
          </div>
          <div class="day-count">${day.total_count ?? 0}</div>
          <div class="day-label">unique papers discovered</div>
          <div class="day-presets">
            <span><strong>${featured}</strong> highlighted</span>
            <span><strong>${additional}</strong> more</span>
            ${updated ? `<span>Updated ${esc(updated)}</span>` : ''}
          </div>
          ${topPreview(day.top_titles || [])}
          <div class="source-pills">${costBadge}</div>
          ${Object.keys(day.errors || {}).length ? '<div class="day-warning">Some sources reported errors</div>' : ''}
          <div class="open-day">Open daily digest →</div>
        </a>`;
    }).join('') || '<p class="empty">The first daily archive will appear after the pipeline runs.</p>';
  } catch (error) {
    status.innerHTML = `<div class="warning">Could not load archive: ${esc(String(error))}</div>`;
  }
}

boot();
