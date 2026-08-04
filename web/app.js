/* Cooking Manager — front
 *
 * CIBLE : iPad mini 2 / Safari 12.5.8. Syntaxe limitée à ES2019 :
 *   ❌ ?.  ??  ||=  champs de classe  Array.at()  replaceAll()
 *   ✅ fetch, async/await, template literals, spread, URLSearchParams
 * Vérifié par eslint (ecmaVersion 2019) + eslint-plugin-compat.
 *
 * Pas de <dialog> : il n'existe pas avant Safari 15.4, et l'élément inconnu
 * affiche son contenu en permanence dans le flux. Les vues sont routées.
 */

'use strict';

var API = '/api';
var state = {
  recipes: [], filters: null, menu: null, compat: null,
  weekMenu: null,
  active: { status: null, family: null, tag: null, menu: null }, q: ''
};

/* ── Utilitaires ───────────────────────────────────────────────────── */

function esc(s) {
  if (s === null || s === undefined) return '';
  var d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function label(s) {
  if (!s) return '';
  return String(s).replace(/[_-]/g, ' ');
}

async function api(path, opts) {
  var r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
  return r.json();
}

var app = document.getElementById('app');
function render(html) { app.innerHTML = '<div class="view">' + html + '</div>'; }

function emptyState(title, hint) {
  return '<div class="empty"><p class="empty__title">' + esc(title) + '</p>' +
         (hint ? '<p class="empty__hint">' + esc(hint) + '</p>' : '') + '</div>';
}

function skeletonGrid(n) {
  var out = '<div class="grid">';
  for (var i = 0; i < n; i++) {
    out += '<div><div class="skeleton skeleton--card"></div>' +
           '<div class="skeleton skeleton--line"></div></div>';
  }
  return out + '</div>';
}

/* ── Vue : menu de la semaine ──────────────────────────────────────── */

var SLOTS = [
  { key: 'breakfast', label: 'Petit-déj' },
  { key: 'lunch',     label: 'Déjeuner' },
  { key: 'snack',     label: 'Goûter' },
  { key: 'dinner',    label: 'Dîner' }
];

function todayISO() {
  var d = new Date();
  var m = String(d.getMonth() + 1);
  var day = String(d.getDate());
  if (m.length < 2) m = '0' + m;
  if (day.length < 2) day = '0' + day;
  return d.getFullYear() + '-' + m + '-' + day;
}

/* Index des contrôles de compatibilité, par « jour/créneau ». */
function indexCompat(compat) {
  var idx = {};
  if (!compat || !compat.results) return idx;
  compat.results.forEach(function (r) {
    idx[r.day + '/' + r.slot] = r;
  });
  return idx;
}

function renderDay(meal, compatIdx, today) {
  var isToday = meal.date === today;
  var cls = 'day' + (isToday ? ' day--today' : '');

  var slots = '';
  var away = false;
  SLOTS.forEach(function (s) {
    var dish = meal[s.key];
    if (!dish) return;
    var check = compatIdx[meal.day + '/' + s.key];
    var conflicts = (check && check.conflicts) ? check.conflicts : [];
    var atHome = check ? check.at_home : true;
    if (!atHome) { away = true; return; }

    slots += '<div class="slot' + (conflicts.length ? ' slot--conflict' : '') + '">' +
      '<span class="slot__label">' + esc(s.label) + '</span>' +
      '<span class="slot__dish">' + esc(dish) + '</span>';

    if (check && check.attendees && check.attendees.length) {
      slots += '<div class="slot__who">' + esc(check.attendees.join(' · ')) + '</div>';
    }
    conflicts.forEach(function (c) {
      slots += '<div class="conflict">⚠ <strong>' + esc(c.convive) + '</strong> — ' +
               esc(c.reason) + ' : ' + esc(c.matched) + '</div>';
    });
    slots += '</div>';
  });

  if (away && !slots) {
    return '<article class="day day--away"><div class="day__head">' +
      '<span class="day__name">' + esc(meal.day) + '</span></div>' +
      '<p class="day__away-note">Hors foyer — pas de repas à préparer.</p></article>';
  }

  return '<article class="' + cls + '">' +
    '<div class="day__head">' +
      '<span class="day__name">' + esc(meal.day) + '</span>' +
      (isToday ? '<span class="day__badge">Aujourd\'hui</span>'
               : '<span class="day__date">' + esc(meal.date || '') + '</span>') +
    '</div>' + (slots || '<p class="day__away-note">Rien de planifié.</p>') +
  '</article>';
}

async function viewMenu() {
  render(emptyState('Chargement de la semaine…'));
  var data = await api('/menus');
  var menus = data.menus || [];
  // Le menu actif d'abord, sinon le plus récent qui porte une structure jour.
  var menu = null;
  for (var i = 0; i < menus.length; i++) {
    if (menus[i].status === 'active' && menus[i].meals) { menu = menus[i]; break; }
  }
  if (!menu) {
    for (var j = 0; j < menus.length; j++) {
      if (menus[j].meals && menus[j].meals.length) { menu = menus[j]; break; }
    }
  }

  if (!menu) {
    render(emptyState(
      'Pas encore de menu pour cette semaine',
      'Ajoutez un bloc meals: dans une fiche de Menus/ puis lancez la synchronisation.'
    ));
    return;
  }

  var compat = null;
  try { compat = await api('/menus/' + encodeURIComponent(menu.slug) + '/compatibility'); }
  catch (e) { compat = null; }

  var idx = indexCompat(compat);
  var today = todayISO();
  var conflicts = compat ? compat.conflicts : 0;

  var html = '<h1 class="page__title">' + esc(menu.title) + '</h1>' +
    '<p class="page__sub">' + esc(menu.week_start || '') + ' → ' + esc(menu.week_end || '') +
    (menu.configuration ? ' · ' + esc(label(menu.configuration)) : '') + '</p>';

  if (conflicts > 0) {
    html += '<div class="banner">' + conflicts + ' conflit' + (conflicts > 1 ? 's' : '') +
      ' alimentaire' + (conflicts > 1 ? 's' : '') + ' sur la semaine — voir les repas signalés.</div>';
  }

  html += '<div class="week">';
  (menu.meals || []).forEach(function (m) { html += renderDay(m, idx, today); });
  html += '</div>';

  render(html);
}

/* ── Vue : catalogue de recettes ───────────────────────────────────── */

function recipeCard(r) {
  var media = r.photo_url
    ? '<img src="' + esc(r.photo_url) + '" alt="' + esc(r.title) + '">'
    : '<div class="card__fallback">' + esc((r.title || '?').charAt(0).toUpperCase()) + '</div>';

  var meta = [];
  if (r.total_time_min) meta.push(r.total_time_min + ' min');
  if (r.servings) meta.push(r.servings + ' pers.');
  if (r.family) meta.push(label(r.family));

  var macros = '';
  if (r.macros && r.macros.kcal) {
    macros = r.macros.kcal + ' kcal';
    if (r.macros.protein) macros += ' · ' + r.macros.protein + ' g de protéines';
  }

  return '<button class="card" data-slug="' + esc(r.slug) + '">' +
    '<div class="card__media">' + media + '</div>' +
    '<div class="card__title">' + esc(r.title) + '</div>' +
    (meta.length ? '<div class="card__meta"><span>' + meta.map(esc).join('</span><span>') + '</span></div>' : '') +
    (macros ? '<div class="card__macros">' + esc(macros) + '</div>' : '') +
    // « 2× » est l'information qui manque le plus quand on planifie : une
    // recette peut revenir plusieurs fois dans la même semaine.
    (r.occurrences ? '<div class="card__week">' +
       (r.occurrences > 1 ? r.occurrences + '× cette semaine' : 'Cette semaine') +
       (r.scheduled_at ? ' · ' + esc(r.scheduled_at.join(' · ')) : '') + '</div>' : '') +
  '</button>';
}

function chipGroup(items, key) {
  return items.map(function (item) {
    var on = state.active[key] === item;
    return '<button class="chip" data-filter="' + esc(key) + '" data-value="' + esc(item) +
           '" aria-pressed="' + (on ? 'true' : 'false') + '">' + esc(label(item)) + '</button>';
  }).join('');
}

async function loadRecipes() {
  var params = new URLSearchParams();
  if (state.active.status) params.set('status', state.active.status);
  if (state.active.family) params.set('family', state.active.family);
  if (state.active.tag) params.set('tag', state.active.tag);
  if (state.q) params.set('q', state.q);
  if (state.active.menu) params.set('menu', state.active.menu);
  params.set('limit', '500');
  var data = await api('/recipes?' + params.toString());
  state.recipes = data.recipes || [];
  return data;
}

function paintRecipes(total) {
  var host = document.getElementById('recipe-grid');
  if (!host) return;
  var count = document.getElementById('recipe-count');
  if (count) count.textContent = total + ' recette' + (total !== 1 ? 's' : '');
  if (!state.recipes.length) {
    host.innerHTML = emptyState('Aucune recette ne correspond',
                                'Essayez un autre mot-clé ou retirez un filtre.');
    return;
  }
  // ⚠️ Le wrapper .grid doit être RÉÉCRIT ici : le squelette de chargement le
  // portait, mais les cartes le remplaçaient et atterrissaient dans un
  // conteneur sans grille — elles flottaient et leurs métadonnées se touchaient.
  host.innerHTML = '<div class="grid">' + state.recipes.map(recipeCard).join('') + '</div>';
}

async function viewRecipes() {
  render('<h1 class="page__title">Recettes</h1>' +
    '<div class="toolbar">' +
      '<input class="search" id="search" type="search" placeholder="Chercher une recette…" autocomplete="off">' +
      '<span class="card__meta" id="recipe-count"></span>' +
    '</div><div id="filters"></div>' +
    '<div id="recipe-grid">' + skeletonGrid(6) + '</div>');

  if (!state.filters) state.filters = await api('/filters');
  var f = state.filters;
  // La puce « Cette semaine » relie le catalogue au menu courant. Sans elle,
  // les 22 recettes se valent toutes et rien ne dit lesquelles sont au programme.
  var weekChip = '';
  if (!state.weekMenu) {
    var menus = (await api('/menus')).menus || [];
    for (var mi = 0; mi < menus.length; mi++) {
      if (menus[mi].meals && menus[mi].meals.length) { state.weekMenu = menus[mi]; break; }
    }
  }
  if (state.weekMenu) {
    weekChip = '<button class="chip chip--week" data-filter="menu" data-value="' +
      esc(state.weekMenu.slug) + '" aria-pressed="' +
      (state.active.menu ? 'true' : 'false') + '">Cette semaine</button>';
  }

  document.getElementById('filters').innerHTML =
    '<div class="chips">' + weekChip + chipGroup(f.statuses || [], 'status') +
    chipGroup(f.families || [], 'family') + '</div>';

  var data = await loadRecipes();
  paintRecipes(data.total);

  var search = document.getElementById('search');
  search.value = state.q;
  var timer;
  search.addEventListener('input', function () {
    clearTimeout(timer);
    var self = this;
    timer = setTimeout(async function () {
      state.q = self.value.trim();
      var d = await loadRecipes();
      paintRecipes(d.total);
    }, 250);
  });
}

/* ── Vue : fiche recette ───────────────────────────────────────────── */

function qtyText(ing) {
  if (ing.qty_min === null || ing.qty_min === undefined) return '';
  var q = ing.qty_min;
  if (ing.qty_max && ing.qty_max !== ing.qty_min) q += '–' + ing.qty_max;
  return q + (ing.unit ? ' ' + ing.unit : '');
}

async function viewRecipe(slug) {
  render(emptyState('Chargement…'));
  var r = await api('/recipes/' + encodeURIComponent(slug));

  var html = '<button class="btn btn--ghost btn--back" data-back="1">← Retour</button>';

  html += '<div class="recipe__hero">' + (r.photo_url
    ? '<img src="' + esc(r.photo_url) + '" alt="' + esc(r.title) + '">'
    : '<div class="card__fallback">' + esc((r.title || '?').charAt(0).toUpperCase()) + '</div>') + '</div>';

  html += '<h1 class="recipe__title">' + esc(r.title) + '</h1>';

  var stats = [];
  if (r.total_time_min) stats.push({ v: r.total_time_min + "'", l: 'Temps' });
  if (r.servings) stats.push({ v: r.servings, l: 'Portions' });
  if (r.macros && r.macros.kcal) stats.push({ v: r.macros.kcal, l: 'kcal / portion' });
  if (r.macros && r.macros.protein) stats.push({ v: r.macros.protein + ' g', l: 'Protéines' });
  if (stats.length) {
    html += '<div class="stats">' + stats.map(function (s) {
      return '<div class="stat"><span class="stat__val">' + esc(s.v) +
             '</span><span class="stat__label">' + esc(s.l) + '</span></div>';
    }).join('') + '</div>';
  }

  var ings = r.ingredients || [];
  if (ings.length) {
    html += '<h2 class="section-title">Ingrédients</h2><ul class="ingredients">';
    ings.forEach(function (i) {
      var cls = 'ingredient';
      if (i.is_optional) cls += ' ingredient--optional';
      if (!i.parsed) cls += ' ingredient--raw';
      // Une ligne non structurée s'affiche telle quelle : jamais perdue.
      var name = i.parsed ? i.name : i.raw;
      // Ne pas doubler la mention : le nom la porte déjà souvent
      // (« gomme xanthane (texture, optionnel) »).
      var showOpt = i.is_optional && !/optionnel|facultatif|au choix/i.test(name);
      html += '<li class="' + cls + '">' +
              '<span class="ingredient__qty">' + esc(qtyText(i)) + '</span>' +
              '<span class="ingredient__name">' + esc(name) +
              (showOpt ? ' (optionnel)' : '') + '</span></li>';
    });
    html += '</ul>';
  }

  var steps = r.steps || [];
  if (steps.length) {
    html += '<h2 class="section-title">Préparation</h2><ol class="steps">' +
      steps.map(function (s) { return '<li class="step">' + esc(s.text) + '</li>'; }).join('') +
      '</ol>';
  }

  if (!ings.length && !steps.length) {
    html += emptyState('Cette fiche n\'a pas encore d\'ingrédients structurés',
                       'Ajoutez une section « ## Ingrédients » puis relancez la synchronisation.');
  }

  html += '<h2 class="section-title">Historique</h2><div id="exec">' +
          emptyState('Chargement…') + '</div>';

  render(html);

  try {
    var ex = await api('/recipes/' + encodeURIComponent(slug) + '/executions');
    var box = document.getElementById('exec');
    if (!box) return;
    if (!ex.executions || !ex.executions.length) {
      box.innerHTML = emptyState('Jamais cuisinée',
                                 'Ce sera peut-être pour cette semaine.');
      return;
    }
    box.innerHTML = ex.executions.map(function (e) {
      var stars = e.rating ? '★'.repeat(e.rating) + '☆'.repeat(5 - e.rating) : '';
      var who = e.appreciated_by && e.appreciated_by.length
        ? ' · apprécié par ' + e.appreciated_by.join(', ') : '';
      return '<div class="slot"><span class="slot__label">' + esc(e.date) +
             (e.cooked_by ? ' — ' + esc(e.cooked_by) : '') + '</span>' +
             '<span class="slot__dish">' + esc(stars) + esc(who) + '</span>' +
             (e.notes ? '<div class="slot__who">' + esc(e.notes) + '</div>' : '') + '</div>';
    }).join('');
  } catch (e) { /* l'historique est secondaire : son échec ne casse pas la fiche */ }
}

/* ── Vue : courses ─────────────────────────────────────────────────── */

/* Les 4 issues du différentiel. `inconnu` n'est PAS un raté du système : c'est
   l'app qui refuse de deviner, parce qu'un faux « tu en as » fait sauter un
   achat et ne se découvre qu'en cuisine. */
var OUTCOMES = {
  absent:      { label: 'À acheter',    cls: 'need--buy' },
  insuffisant: { label: 'À compléter',  cls: 'need--partial' },
  inconnu:     { label: 'À confirmer',  cls: 'need--ask' },
  suffisant:   { label: 'Déjà en stock', cls: 'need--have' }
};

var ORDER = ['absent', 'insuffisant', 'inconnu', 'suffisant'];

function qtyLabel(line) {
  if (line.qty === null || line.qty === undefined) return '';
  return line.qty + (line.unit ? ' ' + line.unit : '');
}

function needRow(line) {
  var o = OUTCOMES[line.outcome] || OUTCOMES.inconnu;
  var html = '<li class="need ' + o.cls + '" data-name="' + esc(line.name) + '"' +
             (line.pantry ? ' data-pantry="' + esc(line.pantry.name) + '"' : '') + '>' +
    '<div class="need__head">' +
      '<span class="need__qty">' + esc(qtyLabel(line)) + '</span>' +
      '<span class="need__name">' + esc(line.name) +
        (line.is_optional ? ' <em>(optionnel)</em>' : '') + '</span>' +
    '</div>';

  if (line.recipes && line.recipes.length) {
    html += '<div class="need__why">' + esc(line.recipes.join(' · ')) +
      (line.shared ? ' <span class="need__shared">utilisé dans plusieurs recettes</span>' : '') +
      '</div>';
  }
  if (line.pantry) {
    html += '<div class="need__pantry">D\'après le garde-manger : ' +
            esc(line.reason) + '</div>';
  } else if (line.reason) {
    html += '<div class="need__pantry">' + esc(line.reason) + '</div>';
  }

  // Les 4 gestes ne s'affichent que là où ils ont un sens : inutile de demander
  // « tu en as ? » pour un ingrédient dont on sait déjà qu'il manque.
  if (line.pantry) {
    html += '<div class="need__actions">' +
      '<button class="mini" data-act="have">Oui, j\'en ai</button>' +
      '<button class="mini" data-act="missing">Non, je n\'en ai pas</button>' +
      '<button class="mini" data-act="partial">Compléter</button>' +
      '<button class="mini mini--ghost" data-act="update">Mettre à jour</button>' +
      '</div>';
  }
  return html + '</li>';
}

async function viewCourses() {
  render(emptyState('Calcul de la liste…'));

  var menus = (await api('/menus')).menus || [];
  var menu = null;
  for (var i = 0; i < menus.length; i++) {
    if (menus[i].meals && menus[i].meals.length) { menu = menus[i]; break; }
  }
  if (!menu) {
    render('<h1 class="page__title">Courses</h1>' +
      emptyState('Pas de menu à convertir en courses',
                 'La liste se calcule depuis le menu de la semaine.'));
    return;
  }

  var data = await api('/menus/' + encodeURIComponent(menu.slug) + '/shopping-list');
  state.shopping = data;

  var html = '<h1 class="page__title">Courses</h1>' +
    '<p class="page__sub">' + esc(data.title) + ' · ' + esc(data.covers) + ' couverts · ' +
    esc(data.recipes_matched) + ' recettes reliées</p>';

  // L'âge de l'inventaire est une donnée de premier plan, pas une note de bas
  // de page : c'est lui qui décide si le frais est encore crédible.
  if (data.pantry && data.pantry.is_stale) {
    html += '<div class="banner">Inventaire du garde-manger vieux de ' +
      esc(data.pantry.age_days) + ' jours — les produits frais sont supposés épuisés. ' +
      'Corrigez ce qui est faux plutôt que de faire confiance à cette liste.</div>';
  }
  if (data.meals_unmatched && data.meals_unmatched.length) {
    html += '<div class="banner">' + data.meals_unmatched.length +
      ' repas sans fiche recette — leurs ingrédients ne sont pas dans cette liste : ' +
      esc(data.meals_unmatched.map(function (m) { return m.dish; }).slice(0, 3).join(' · ')) +
      '</div>';
  }

  var c = data.counts || {};
  html += '<div class="stats">' + ORDER.map(function (k) {
    return '<div class="stat"><span class="stat__val">' + (c[k] || 0) +
           '</span><span class="stat__label">' + esc(OUTCOMES[k].label) + '</span></div>';
  }).join('') + '</div>';

  var lines = data.lines || [];
  ORDER.forEach(function (key) {
    var group = lines.filter(function (l) { return l.outcome === key; });
    if (!group.length) return;
    html += '<h2 class="section-title">' + esc(OUTCOMES[key].label) +
            ' <span class="section-count">' + group.length + '</span></h2>' +
            '<ul class="needs">' + group.map(needRow).join('') + '</ul>';
  });

  render(html);
}

/* Les 4 gestes écrivent dans le vault. Le retour porte `needs_bisync` : sans
   bisync, l'écriture reste locale (l'app Dropbox desktop est désactivée). */
async function applyPantryGesture(li, action) {
  var pantryName = li.getAttribute('data-pantry');
  if (!pantryName) return;

  var payload = { item_name: pantryName, action: action };
  if (action === 'update') {
    var current = window.prompt('Nouvelle quantité pour « ' + pantryName + ' » :', '');
    if (current === null || !current.trim()) return;
    payload.qty_text = current.trim();
  }

  var box = li.querySelector('.need__actions');
  box.innerHTML = '<span class="need__pending">Enregistrement…</span>';
  try {
    var res = await api('/pantry', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    li.className = 'need need--done';
    box.innerHTML = '<span class="need__done">' +
      (res.changed ? 'Garde-manger mis à jour' : 'Confirmé') +
      (res.needs_bisync ? ' — pensez au bisync du vault' : '') + '</span>';
  } catch (e) {
    box.innerHTML = '<span class="need__error">Échec de l\'enregistrement — réessayez</span>';
  }
}

/* ── Routeur ───────────────────────────────────────────────────────── */

var ROUTES = { menu: viewMenu, recettes: viewRecipes, courses: viewCourses };

function currentRoute() {
  var h = location.hash.replace(/^#\/?/, '');
  return h || 'menu';
}

async function route() {
  var path = currentRoute();
  var parts = path.split('/');

  document.querySelectorAll('.nav__link').forEach(function (b) {
    if (b.getAttribute('data-route') === parts[0]) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  });

  try {
    if (parts[0] === 'recette' && parts[1]) {
      await viewRecipe(decodeURIComponent(parts[1]));
    } else {
      var fn = ROUTES[parts[0]] || viewMenu;
      await fn();
    }
    window.scrollTo(0, 0);
  } catch (e) {
    render(emptyState('Impossible de charger cette page',
                      'Le serveur est peut-être indisponible. Réessayez dans un instant.'));
  }
}

window.addEventListener('hashchange', route);

/* Délégation d'événements : le contenu est réécrit à chaque vue. */
document.addEventListener('click', function (e) {
  var nav = e.target.closest('.nav__link');
  if (nav) { location.hash = '#/' + nav.getAttribute('data-route'); return; }

  var mini = e.target.closest('.mini[data-act]');
  if (mini) {
    var li = mini.closest('.need');
    if (li) applyPantryGesture(li, mini.getAttribute('data-act'));
    return;
  }

  var card = e.target.closest('.card');
  if (card) { location.hash = '#/recette/' + encodeURIComponent(card.getAttribute('data-slug')); return; }

  var back = e.target.closest('[data-back]');
  if (back) { history.back(); return; }

  var chip = e.target.closest('.chip');
  if (chip) {
    var key = chip.getAttribute('data-filter');
    var value = chip.getAttribute('data-value');
    state.active[key] = (state.active[key] === value) ? null : value;
    document.querySelectorAll('.chip[data-filter="' + key + '"]').forEach(function (c) {
      c.setAttribute('aria-pressed', c.getAttribute('data-value') === state.active[key] ? 'true' : 'false');
    });
    loadRecipes().then(function (d) { paintRecipes(d.total); });
  }
});

/* Thème : pas de @media prefers-color-scheme (iOS 13) — attribut sur <html>. */
var THEME_KEY = 'cm2-theme';
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem(THEME_KEY, t); } catch (e) { /* mode privé */ }
}
document.getElementById('theme-toggle').addEventListener('click', function () {
  var cur = document.documentElement.getAttribute('data-theme');
  applyTheme(cur === 'dark' ? 'light' : 'dark');
});
try {
  var saved = localStorage.getItem(THEME_KEY);
  applyTheme(saved || 'light');
} catch (e) { applyTheme('light'); }

route();
