(() => {
  const STORAGE_KEY = 'paperdaily-topic';

  async function load() {
    try {
      const response = await fetch('data/topics.json', { cache: 'no-cache' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (Array.isArray(data.topics) && data.topics.length) return data;
    } catch (_) {
      // Backward compatibility with older single-topic archives.
    }
    return {
      default_topic: 'default',
      topics: [{ id: 'default', label: 'All papers', description: '' }]
    };
  }

  function choose(index, requested = '') {
    const topics = index?.topics || [];
    const valid = new Set(topics.map(topic => topic.id));
    const stored = localStorage.getItem(STORAGE_KEY) || '';
    if (requested && valid.has(requested)) return requested;
    if (stored && valid.has(stored)) return stored;
    if (valid.has(index?.default_topic)) return index.default_topic;
    return topics[0]?.id || 'default';
  }

  function get(index, topicId) {
    return (index?.topics || []).find(topic => topic.id === topicId) || null;
  }

  function render(targetId, index, selectedId, onChange) {
    const target = document.querySelector(targetId);
    if (!target) return;
    const topics = index?.topics || [];
    if (topics.length <= 1) {
      target.innerHTML = topics.length
        ? `<span class="topic-static">${escapeHtml(topics[0].label)}</span>`
        : '';
      return;
    }
    target.innerHTML = `
      <label for="topicSelect">Topic</label>
      <select id="topicSelect" aria-label="Research topic">
        ${topics.map(topic => `<option value="${escapeHtml(topic.id)}" ${topic.id === selectedId ? 'selected' : ''}>${escapeHtml(topic.label)}</option>`).join('')}
      </select>`;
    const select = target.querySelector('select');
    select?.addEventListener('change', () => {
      const value = select.value;
      localStorage.setItem(STORAGE_KEY, value);
      onChange?.(value);
    });
  }

  function escapeHtml(value = '') {
    return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }

  window.PaperDailyTopics = { load, choose, get, render };
})();
