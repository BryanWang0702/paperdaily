const PAPERDAILY_THEME_PRESETS = new Set(['khaki', 'black', 'navy', 'forest', 'burgundy']);

window.PaperDailyTheme = {
  settings: { theme: { preset: 'khaki', custom: {} }, billing: { show: true } },
  async apply() {
    try {
      const response = await fetch('data/settings.json', { cache: 'no-cache' });
      if (response.ok) this.settings = await response.json();
    } catch (_) {
      // Keep the built-in default theme when settings are unavailable.
    }

    const theme = this.settings?.theme || {};
    let preset = String(theme.preset || 'khaki').toLowerCase();
    if (preset !== 'custom' && !PAPERDAILY_THEME_PRESETS.has(preset)) preset = 'khaki';
    document.documentElement.dataset.theme = preset;

    if (preset === 'custom') {
      const mapping = {
        background: '--bg',
        surface: '--surface',
        text: '--text',
        muted: '--muted',
        border: '--border',
        accent: '--accent',
        accent_text: '--accent-text'
      };
      const custom = theme.custom || {};
      for (const [key, variable] of Object.entries(mapping)) {
        if (custom[key]) document.documentElement.style.setProperty(variable, String(custom[key]));
      }
    }
    return this.settings;
  }
};
