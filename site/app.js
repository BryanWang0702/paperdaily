function esc(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function prettyDate(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'long', day: 'numeric', weekday: 'short'
  }).format(date);
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

    archive.innerHTML = days.map((day, index) => {
      const ai = day.ai || {};
      const costBadge = ai.daily_cost_cny !== null && ai.daily_cost_cny !== undefined
        ? `<span class="source-pill">API ${money(ai.daily_cost_cny)}</span>`
        : '';
      const rankedBadge = ai.enabled
        ? `<span class="ai-pill">${ai.ranked_count || 0} screened by AI</span>`
        : '';
      const version = day.generated_at ? `&v=${encodeURIComponent(day.generated_at)}` : '';
      return `
        <a class="day-card" href="day.html?date=${encodeURIComponent(day.date)}${version}">
          <div class="day-card-top">
            <span class="day-date">${esc(prettyDate(day.date))}</span>
            ${index === 0 ? '<span class="today-badge">LATEST</span>' : ''}
          </div>
          <div class="day-count">${day.count ?? 0}</div>
          <div class="day-label">recommended papers${day.candidate_count ? ` · ${day.candidate_count} candidates` : ''}${day.raw_count ? ` · ${day.raw_count} discovered` : ''}</div>
          ${topPreview(day.top_titles || [])}
          <div class="source-pills">${rankedBadge}${costBadge}</div>
          ${Object.keys(day.errors || {}).length ? '<div class="day-warning">Some sources reported errors</div>' : ''}
          <div class="open-day">Open daily digest →</div>
        </a>`;
    }).join('') || '<p class="empty">The first daily archive will appear after the pipeline runs.</p>';
  } catch (error) {
    status.innerHTML = `<div class="warning">Could not load archive: ${esc(String(error))}</div>`;
  }
}

boot();
