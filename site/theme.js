const PAPERDAILY_THEME_LABELS = {
  khaki: 'Khaki',
  black: 'Black',
  navy: 'Navy',
  forest: 'Forest',
  burgundy: 'Burgundy',
  custom: 'Custom'
};
const PAPERDAILY_THEME_PRESETS = new Set(['khaki', 'black', 'navy', 'forest', 'burgundy']);
const PAPERDAILY_THEME_STORAGE_KEY = 'paperdaily-theme';
const PAPERDAILY_CUSTOM_VARIABLES = ['--bg', '--surface', '--text', '--muted', '--border', '--accent', '--accent-text'];
let PAPERDAILY_ARCHIVE_STAMP = null;

function paperDailyStoredTheme() {
  try {
    return String(window.localStorage.getItem(PAPERDAILY_THEME_STORAGE_KEY) || '').toLowerCase();
  } catch (_) {
    return '';
  }
}

function paperDailyStoreTheme(value) {
  try {
    window.localStorage.setItem(PAPERDAILY_THEME_STORAGE_KEY, value);
  } catch (_) {
    // Theme persistence is optional; the current page can still change theme.
  }
}

window.PaperDailyTheme = {
  settings: { theme: { preset: 'khaki', custom: {} }, billing: { show: false } },
  current: 'khaki',
  _applyPromise: null,

  async apply() {
    if (this._applyPromise) return this._applyPromise;
    this._applyPromise = (async () => {
      try {
        const response = await fetch('data/settings.json', { cache: 'no-cache' });
        if (response.ok) this.settings = await response.json();
      } catch (_) {
        // Keep built-in defaults when settings are unavailable.
      }

      const configured = String(this.settings?.theme?.preset || 'khaki').toLowerCase();
      const customAvailable = Object.keys(this.settings?.theme?.custom || {}).length > 0;
      const allowed = new Set(PAPERDAILY_THEME_PRESETS);
      if (customAvailable) allowed.add('custom');

      const stored = paperDailyStoredTheme();
      const selected = allowed.has(stored)
        ? stored
        : (allowed.has(configured) ? configured : 'khaki');
      this.setTheme(selected, false);
      this.mountSelector();
      return this.settings;
    })();
    return this._applyPromise;
  },

  setTheme(preset, persist = true) {
    const value = String(preset || 'khaki').toLowerCase();
    const custom = this.settings?.theme?.custom || {};
    const customAvailable = Object.keys(custom).length > 0;
    const selected = value === 'custom' && customAvailable
      ? 'custom'
      : (PAPERDAILY_THEME_PRESETS.has(value) ? value : 'khaki');

    for (const variable of PAPERDAILY_CUSTOM_VARIABLES) {
      document.documentElement.style.removeProperty(variable);
    }
    document.documentElement.dataset.theme = selected;

    if (selected === 'custom') {
      const mapping = {
        background: '--bg',
        surface: '--surface',
        text: '--text',
        muted: '--muted',
        border: '--border',
        accent: '--accent',
        accent_text: '--accent-text'
      };
      for (const [key, variable] of Object.entries(mapping)) {
        if (custom[key]) document.documentElement.style.setProperty(variable, String(custom[key]));
      }
    }

    this.current = selected;
    if (persist) paperDailyStoreTheme(selected);
    const select = document.querySelector('#paperdailyThemeSelect');
    if (select) select.value = selected;
  },

  mountSelector() {
    const target = document.querySelector('#themeControl');
    if (!target) return;
    const customAvailable = Object.keys(this.settings?.theme?.custom || {}).length > 0;
    const options = [...PAPERDAILY_THEME_PRESETS];
    if (customAvailable) options.push('custom');
    target.innerHTML = `
      <label for="paperdailyThemeSelect">Theme</label>
      <select id="paperdailyThemeSelect" aria-label="Choose color theme">
        ${options.map(value => `<option value="${value}">${PAPERDAILY_THEME_LABELS[value]}</option>`).join('')}
      </select>`;
    const select = target.querySelector('select');
    select.value = this.current;
    select.addEventListener('change', event => this.setTheme(event.target.value, true));
  }
};

async function paperDailyWatchArchive() {
  try {
    const response = await fetch(`data/archive.json?watch=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) return;
    const data = await response.json();
    const stamp = String(data.generated_at || '');
    if (!stamp) return;
    if (PAPERDAILY_ARCHIVE_STAMP && stamp !== PAPERDAILY_ARCHIVE_STAMP) {
      window.location.reload();
      return;
    }
    PAPERDAILY_ARCHIVE_STAMP = stamp;
  } catch (_) {
    // The dashboard remains usable if polling is temporarily unavailable.
  }
}

window.PaperDailyTheme.apply();
setTimeout(paperDailyWatchArchive, 1500);
setInterval(paperDailyWatchArchive, 60000);
