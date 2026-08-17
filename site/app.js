const EN_LOCALE = 'en-US';
const DISPLAY_TIME_ZONE = 'Asia/Shanghai';

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function prettyDate(value) {
  const date = new Date(`${value}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short', timeZone: DISPLAY_TIME_ZONE
  }).format(date);
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00+08:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(EN_LOCALE, {
    month: 'short', day: 'numeric', timeZone: DISPLAY_TIME_ZONE
  }).format(date);
}

function updatedTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const formatted = new Intl.DateTimeFormat(EN_LOCALE, {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: DISPLAY_TIME_ZONE
  }).format(date);
  return `${formatted} Beijing time`;
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
  if (!titles.length) return '<p class="ranking-empty">No ranked preview yet.</p>';
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

async function renderLocalStatus() {
  const target = document.querySelector('#localStatus');
  try {
    const response = await fetch('data/local_status.json', { cache: 'no-cache' });
    if (!response.ok) return;
    const status = await response.json();
    if (!status.current_version) return;
    if (status.update_available) {
      const link = status.download_url
        ? `<a href="${esc(status.download_url)}" target="_blank" rel="noopener">Download latest</a>`
        : '';
      target.innerHTML = `<div class="update-banner"><strong>Update available:</strong> PaperDaily ${esc(status.latest_version)} is available; this copy is ${esc(status.current_version)}. ${link}</div>`;
    } else if (status.check_status === 'ok') {
      target.innerHTML = `<div class="version-status">Local edition ${esc(status.current_version)} · Up to date</div>`;
    }
  } catch (_) {
    // Hosted Pages has no local version file; keep the page silent.
  }
}

async function fetchTopicArchive(topicId) {
  const topicUrl = `data/topics/${encodeURIComponent(topicId)}/archive.json`;
  const response = await fetch(topicUrl, { cache: 'no-cache' });
  if (response.ok) return response.json();
  if (topicId === 'default') {
    const fallback = await fetch('data/archive.json', { cache: 'no-cache' });
    if (fallback.ok) return fallback.json();
  }
  throw new Error(`HTTP ${response.status}`);
}

async function boot() {
  const settings = await window.PaperDailyTheme.apply();
  renderLocalStatus();
  const archive = document.querySelector('#archive');
  const status = document.querySelector('#status');
  try {
    const topicIndex = await window.PaperDailyTopics.load();
    const params = new URLSearchParams(window.location.search);
    const selectedTopic = window.PaperDailyTopics.choose(topicIndex, params.get('topic') || '');
    const topic = window.PaperDailyTopics.get(topicIndex, selectedTopic);
    window.PaperDailyTopics.render('#topicControl', topicIndex, selectedTopic, value => {
      const next = new URL(window.location.href);
      next.searchParams.set('topic', value);
      window.location.href = next.toString();
    });
    document.querySelector('#topicDescription').textContent = topic?.description || 'A new research digest every day. Open a date to read that day\'s papers.';

    const data = await fetchTopicArchive(selectedTopic);
    const days = data.days || [];
    const billing = data.billing || {};
    const showBilling = settings?.billing?.show === true;

    if (showBilling && billing.total_cost_cny !== undefined) {
      document.querySelector('#meta').textContent = `Last run ${money(billing.last_run_cost_cny)} · Total ${money(billing.total_cost_cny)} · ~${money(billing.annual_estimate_cny)}/year`;
    } else {
      document.querySelector('#meta').textContent = days.length
        ? `${days.length} archived day${days.length === 1 ? '' : 's'}`
        : 'No archived days yet';
    }

    renderRanking('#monthlyRanking', data.rankings?.monthly);

    archive.innerHTML = days.map((day, index) => {
      const featured = Number(day.featured_count || 0);
      const additional = Number(day.additional_count || 0);
      const updated = updatedTime(day.generated_at || '');
      const version = day.generated_at ? `&v=${encodeURIComponent(day.generated_at)}` : '';
      return `
        <a class="day-card" href="day.html?topic=${encodeURIComponent(selectedTopic)}&date=${encodeURIComponent(day.date)}${version}">
          <div class="day-card-main">
            <div class="day-card-top">
              <span class="day-date">${esc(prettyDate(day.date))}</span>
              ${index === 0 ? '<span class="today-badge">LATEST</span>' : ''}
            </div>
            <div class="day-count-row">
              <span class="day-count">${day.total_count ?? 0}</span>
              <span class="day-label">topic-matching papers</span>
            </div>
            <div class="day-presets">
              <span><strong>${featured}</strong> highlighted</span>
              <span><strong>${additional}</strong> more</span>
              ${updated ? `<span>Updated ${esc(updated)}</span>` : ''}
            </div>
            ${Object.keys(day.errors || {}).length ? '<div class="day-warning">Some sources reported errors</div>' : ''}
            <div class="open-day">Open daily papers →</div>
          </div>
          <div class="day-card-preview">
            <div class="day-card-preview-label">Top papers</div>
            ${topPreview(day.top_titles || [])}
          </div>
        </a>`;
    }).join('') || '<p class="empty">The first daily archive for this topic will appear after the pipeline runs.</p>';
  } catch (error) {
    status.innerHTML = `<div class="warning">Could not load archive: ${esc(String(error))}</div>`;
  }
}

boot();
