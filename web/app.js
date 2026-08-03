/* Cooking Manager — frontend */

const API = '/api';
const state = { recipes: [], filters: {}, active: { status: null, family: null, tag: null }, q: '' };

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ── Init ────────────────────────────────────────────────────

async function init() {
  const [filtersData, statsData] = await Promise.all([
    fetchJSON(`${API}/filters`),
    fetchJSON(`${API}/stats`),
  ]);
  state.filters = filtersData;
  renderFilters(filtersData);
  renderStats(statsData);
  await loadRecipes();
}

// ── Filters ─────────────────────────────────────────────────

function renderFilters({ statuses, families, tags }) {
  renderChipGroup('filter-status', statuses, 'status');
  renderChipGroup('filter-family', families, 'family');
  renderChipGroup('filter-tags', tags, 'tag');
}

function renderChipGroup(containerId, items, filterKey) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  for (const item of items) {
    const btn = document.createElement('button');
    btn.className = 'chip';
    btn.textContent = formatLabel(item);
    btn.setAttribute('role', 'button');
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => toggleFilter(filterKey, item, btn));
    el.appendChild(btn);
  }
}

function formatLabel(s) {
  if (!s) return '—';
  return s.replace(/[_-]/g, ' ');
}

function toggleFilter(key, value, btn) {
  if (state.active[key] === value) {
    state.active[key] = null;
    btn.setAttribute('aria-pressed', 'false');
  } else {
    const container = btn.parentElement;
    container.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', 'false'));
    state.active[key] = value;
    btn.setAttribute('aria-pressed', 'true');
  }
  loadRecipes();
}

// ── Load recipes ────────────────────────────────────────────

async function loadRecipes() {
  const params = new URLSearchParams();
  if (state.active.status) params.set('status', state.active.status);
  if (state.active.family) params.set('family', state.active.family);
  if (state.active.tag) params.set('tag', state.active.tag);
  if (state.q) params.set('q', state.q);

  const data = await fetchJSON(`${API}/recipes?${params}`);
  state.recipes = data.recipes;
  renderRecipes(data.recipes, data.total);
}

// ── Render recipes ──────────────────────────────────────────

function renderRecipes(recipes, total) {
  document.getElementById('result-count').textContent = `${total} recette${total !== 1 ? 's' : ''}`;
  const grid = document.getElementById('recipes');
  grid.innerHTML = '';

  for (const r of recipes) {
    const card = document.createElement('article');
    card.className = 'recipe-card';
    card.tabIndex = 0;

    const timeStr = r.total_time_min ? `${r.total_time_min} min` : '';
    const servingsStr = r.servings ? `${r.servings} pers.` : '';

    let macrosHTML = '';
    if (r.macros) {
      const parts = [];
      if (r.macros.kcal) parts.push(`<span>${r.macros.kcal} kcal</span>`);
      if (r.macros.protein) parts.push(`<span>${r.macros.protein}g P</span>`);
      if (r.macros.carbs) parts.push(`<span>${r.macros.carbs}g G</span>`);
      if (r.macros.fat) parts.push(`<span>${r.macros.fat}g L</span>`);
      if (parts.length) macrosHTML = `<div class="card-macros">${parts.join('')}</div>`;
    }

    const tagsHTML = (r.tags || []).slice(0, 5).map(t =>
      `<span class="card-tag">${formatLabel(t)}</span>`
    ).join('');

    card.innerHTML = `
      <div class="card-title">${esc(r.title)}</div>
      <div class="card-meta">
        <span class="status-dot" data-status="${r.status}" title="${formatLabel(r.status)}"></span>
        <span>${formatLabel(r.status)}</span>
        ${timeStr ? `<span>${timeStr}</span>` : ''}
        ${servingsStr ? `<span>${servingsStr}</span>` : ''}
        ${r.family ? `<span>${formatLabel(r.family)}</span>` : ''}
      </div>
      ${tagsHTML ? `<div class="card-tags">${tagsHTML}</div>` : ''}
      ${macrosHTML}
    `;

    card.addEventListener('click', () => openDetail(r.slug));
    card.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(r.slug); });
    grid.appendChild(card);
  }
}

// ── Detail dialog ───────────────────────────────────────────

async function openDetail(slug) {
  const r = await fetchJSON(`${API}/recipes/${slug}`);
  const dialog = document.getElementById('detail');
  const content = document.getElementById('detail-content');

  let html = `<h2 class="detail-title">${esc(r.title)}</h2>`;

  // Stats row
  const stats = [];
  if (r.total_time_min) stats.push({ val: `${r.total_time_min}'`, label: 'Temps' });
  if (r.servings) stats.push({ val: r.servings, label: 'Portions' });
  if (r.execution_count) stats.push({ val: r.execution_count, label: 'Faite' });
  if (r.protein_density) stats.push({ val: r.protein_density.toFixed(3), label: 'P/kcal' });

  if (stats.length) {
    html += `<div class="detail-row">${stats.map(s =>
      `<div class="detail-stat"><span class="val">${s.val}</span><span class="label">${s.label}</span></div>`
    ).join('')}</div>`;
  }

  // Macros
  if (r.macros) {
    const m = r.macros;
    html += `<div class="detail-section"><h3>Macros par portion</h3><div class="detail-row">`;
    if (m.kcal) html += `<div class="detail-stat"><span class="val">${m.kcal}</span><span class="label">kcal</span></div>`;
    if (m.protein) html += `<div class="detail-stat"><span class="val">${m.protein}g</span><span class="label">Protéines</span></div>`;
    if (m.carbs) html += `<div class="detail-stat"><span class="val">${m.carbs}g</span><span class="label">Glucides</span></div>`;
    if (m.fat) html += `<div class="detail-stat"><span class="val">${m.fat}g</span><span class="label">Lipides</span></div>`;
    html += '</div></div>';
  }

  // Tags
  if (r.tags && r.tags.length) {
    html += `<div class="detail-section"><h3>Tags</h3><div class="detail-tags">${
      r.tags.map(t => `<span class="detail-tag">${formatLabel(t)}</span>`).join('')
    }</div></div>`;
  }

  // Constraints
  if (r.compatible_constraints && r.compatible_constraints.length) {
    html += `<div class="detail-section"><h3>Contraintes compatibles</h3><ul class="detail-constraints">${
      r.compatible_constraints.map(c => `<li>${formatLabel(c)}</li>`).join('')
    }</ul></div>`;
  }

  // Substitutions
  if (r.applied_substitutions && r.applied_substitutions.length) {
    html += `<div class="detail-section"><h3>Substitutions appliquées</h3><ul class="detail-constraints">${
      r.applied_substitutions.map(s => `<li>${esc(s)}</li>`).join('')
    }</ul></div>`;
  }

  // Sources
  if (r.sources && r.sources.length) {
    html += `<div class="detail-section"><h3>Sources</h3><ul class="detail-sources">${
      r.sources.map(s => {
        try { const u = new URL(s); return `<li><a href="${esc(s)}" target="_blank" rel="noopener">${esc(u.hostname)}</a></li>`; }
        catch { return `<li>${esc(s)}</li>`; }
      }).join('')
    }</ul></div>`;
  }

  // Meta
  const meta = [];
  if (r.family) meta.push(`Famille : ${formatLabel(r.family)}`);
  if (r.construction_regime) meta.push(`Régime : ${r.construction_regime}`);
  if (r.lieu_execution) meta.push(`Lieu : ${r.lieu_execution}`);
  if (r.appreciated_by && r.appreciated_by.length) meta.push(`Apprécié par : ${r.appreciated_by.join(', ')}`);
  if (r.created) meta.push(`Créée : ${r.created}`);
  if (r.updated && r.updated !== r.created) meta.push(`Modifiée : ${r.updated}`);

  if (meta.length) {
    html += `<div class="detail-section"><h3>Infos</h3><ul class="detail-constraints">${
      meta.map(m => `<li>${m}</li>`).join('')
    }</ul></div>`;
  }

  content.innerHTML = html;
  dialog.showModal();
}

// ── Stats ───────────────────────────────────────────────────

function renderStats(data) {
  const el = document.getElementById('stats');
  const parts = [`${data.total_recipes} recettes`];
  for (const [status, count] of Object.entries(data.by_status || {})) {
    parts.push(`${count} ${formatLabel(status)}`);
  }
  el.textContent = parts.join(' · ');
}

// ── Ingest ──────────────────────────────────────────────────

document.getElementById('btn-ingest').addEventListener('click', async function() {
  this.classList.add('syncing');
  this.textContent = '↻ Sync…';
  try {
    const result = await fetch(`${API}/ingest`, { method: 'POST' }).then(r => r.json());
    this.textContent = `✓ ${result.recipes_ingested} recettes`;
    await Promise.all([
      loadRecipes(),
      fetchJSON(`${API}/filters`).then(renderFilters),
      fetchJSON(`${API}/stats`).then(renderStats),
    ]);
    setTimeout(() => { this.textContent = '↻ Sync vault'; }, 2000);
  } catch (e) {
    this.textContent = '✗ Erreur';
    setTimeout(() => { this.textContent = '↻ Sync vault'; }, 3000);
  } finally {
    this.classList.remove('syncing');
  }
});

// ── Search ──────────────────────────────────────────────────

let searchTimeout;
document.getElementById('search').addEventListener('input', function() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    state.q = this.value.trim();
    loadRecipes();
  }, 250);
});

// ── Dialog close ────────────────────────────────────────────

document.getElementById('detail-close').addEventListener('click', () => {
  document.getElementById('detail').close();
});
document.getElementById('detail').addEventListener('click', function(e) {
  if (e.target === this) this.close();
});

// ── Mobile sidebar toggle ───────────────────────────────────

document.getElementById('btn-toggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});

// ── Helpers ─────────────────────────────────────────────────

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ── Boot ────────────────────────────────────────────────────

init().catch(err => {
  document.getElementById('recipes').innerHTML =
    `<p style="color:var(--text-soft);padding:40px">Impossible de charger les recettes. Le serveur est-il démarré ?</p>`;
});
