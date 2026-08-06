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

function renderDay(meal, compatIdx, today, mealIndex) {
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

    var slug = meal[s.key + '_slug'];
    var isLeftovers = meal[s.key + '_leftovers'];
    var mealId = meal[s.key + '_meal_id'];

    slots += '<div class="slot' + (conflicts.length ? ' slot--conflict' : '') + '">' +
      '<span class="slot__label">' + esc(s.label) + '</span>';

    if (slug) {
      slots += '<a class="slot__dish slot__dish--linked" href="#/recette/' +
        encodeURIComponent(slug) + '">' + esc(dish) +
        ' <span class="slot__arrow">›</span></a>';
    } else if (isLeftovers) {
      slots += '<span class="slot__dish">' + esc(dish) +
        ' <span class="slot__tag">restes</span></span>';
    } else {
      slots += '<span class="slot__dish">' + esc(dish) + '</span>';
    }

    if (mealId && !isLeftovers) {
      slots += '<button class="swap-btn" data-meal-id="' + mealId + '">Changer</button>';
    }

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

  state.weekMenu = menu;

  var mealsData = null;
  try { mealsData = await api('/menus/' + encodeURIComponent(menu.slug) + '/meals'); }
  catch (e) { mealsData = null; }

  if (mealsData && mealsData.meals) {
    var meals = menu.meals || [];
    mealsData.meals.forEach(function (mm) {
      var day = meals[mm.position];
      if (!day) return;
      day[mm.slot + '_meal_id'] = mm.id;
      if (mm.recipe_slug) day[mm.slot + '_slug'] = mm.recipe_slug;
      if (mm.match_kind === 'leftovers') day[mm.slot + '_leftovers'] = true;
      if (mm.match_kind === 'manual') day[mm.slot] = mm.dish;
    });
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
  (menu.meals || []).forEach(function (m, mi) { html += renderDay(m, idx, today, mi); });
  html += '</div>';

  html += '<div id="swap-picker" class="picker" style="display:none">' +
    '<div class="picker__backdrop"></div>' +
    '<div class="picker__panel">' +
      '<div class="picker__head"><h2>Choisir une recette</h2>' +
        '<button class="picker__close" aria-label="Fermer">✕</button></div>' +
      '<input class="picker__search" type="text" placeholder="Rechercher…">' +
      '<div class="picker__list"></div>' +
    '</div></div>';

  render(html);

  app.addEventListener('click', function (e) {
    var btn = e.target.closest('.swap-btn');
    if (btn) {
      e.preventDefault();
      openSwapPicker(btn.getAttribute('data-meal-id'));
    }
    var close = e.target.closest('.picker__close') || e.target.closest('.picker__backdrop');
    if (close) closeSwapPicker();
    var pick = e.target.closest('.picker__item');
    if (pick) {
      e.preventDefault();
      confirmSwap(pick.getAttribute('data-slug'));
    }
  });
}

var _swapMealId = null;

function openSwapPicker(mealId) {
  _swapMealId = mealId;
  var picker = document.getElementById('swap-picker');
  if (!picker) return;
  picker.style.display = '';
  var list = picker.querySelector('.picker__list');
  var input = picker.querySelector('.picker__search');
  input.value = '';
  list.innerHTML = '<p style="padding:1rem;opacity:.6">Chargement…</p>';
  api('/recipes?limit=500').then(function (data) {
    var recipes = data.recipes || [];
    renderPickerList(recipes, '');
    input.oninput = function () { renderPickerList(recipes, input.value); };
  });
}

function renderPickerList(recipes, q) {
  var picker = document.getElementById('swap-picker');
  if (!picker) return;
  var list = picker.querySelector('.picker__list');
  var query = (q || '').toLowerCase();
  var filtered = recipes.filter(function (r) {
    if (!query) return true;
    return (r.title || '').toLowerCase().indexOf(query) >= 0 ||
           (r.slug || '').toLowerCase().indexOf(query) >= 0;
  });
  if (!filtered.length) {
    list.innerHTML = '<p style="padding:1rem;opacity:.6">Aucun résultat.</p>';
    return;
  }
  var html = '';
  filtered.forEach(function (r) {
    var photo = r.photo_url
      ? '<img class="picker__thumb" src="' + esc(r.photo_url) + '" alt="">'
      : '<span class="picker__thumb picker__thumb--empty">' +
        esc((r.title || '?').charAt(0).toUpperCase()) + '</span>';
    html += '<button class="picker__item" data-slug="' + esc(r.slug) + '">' +
      photo + '<span class="picker__name">' + esc(r.title) + '</span></button>';
  });
  list.innerHTML = html;
}

function closeSwapPicker() {
  var picker = document.getElementById('swap-picker');
  if (picker) picker.style.display = 'none';
  _swapMealId = null;
}

async function confirmSwap(recipeSlug) {
  if (!_swapMealId || !state.weekMenu) return;
  var slug = state.weekMenu.slug;
  try {
    await api('/menus/' + encodeURIComponent(slug) + '/meals/' + _swapMealId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipe_slug: recipeSlug })
    });
  } catch (e) {
    closeSwapPicker();
    return;
  }
  closeSwapPicker();
  viewMenu();
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

function roundQty(n) {
  if (n === 0) return '0';
  if (n >= 100) return '' + Math.round(n);
  if (n >= 10) return '' + (Math.round(n * 10) / 10);
  if (n >= 1) return '' + (Math.round(n * 100) / 100);
  var r = Math.round(n * 100) / 100;
  var thirds = [0.33, 0.67];
  for (var i = 0; i < thirds.length; i++) {
    if (Math.abs(r - thirds[i]) < 0.04) return thirds[i].toString();
  }
  return r.toString();
}

function qtyText(ing, ratio) {
  if (ing.qty_min === null || ing.qty_min === undefined) return '';
  var m = ratio || 1;
  var q = roundQty(ing.qty_min * m);
  if (ing.qty_max && ing.qty_max !== ing.qty_min) q += '–' + roundQty(ing.qty_max * m);
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

  var tags = r.tags || [];
  if (tags.length) {
    html += '<div class="recipe__tags">' + tags.map(function (t) {
      return '<span class="recipe__tag">' + esc(label(t)) + '</span>';
    }).join(' ') + '</div>';
  }

  if (r.appreciated_by && r.appreciated_by.length) {
    html += '<p class="recipe__love">Appréciée par ' +
      esc(r.appreciated_by.join(', ')) + '</p>';
  }

  var baseServings = r.servings || 0;
  var curServings = baseServings;
  var ratio = 1;

  var stats = [];
  if (r.prep_time_min || r.cook_time_min) {
    if (r.prep_time_min) stats.push({ v: r.prep_time_min + "'", l: 'Préparation' });
    if (r.cook_time_min) stats.push({ v: r.cook_time_min + "'", l: 'Cuisson' });
  } else if (r.total_time_min) {
    stats.push({ v: r.total_time_min + "'", l: 'Temps' });
  }
  if (baseServings) {
    stats.push({
      v: '<button class="srv-btn" data-srv="-1">−</button>' +
         '<span id="srv-count">' + baseServings + '</span>' +
         '<button class="srv-btn" data-srv="+1">+</button>',
      l: 'Portions', raw: true
    });
  }
  if (r.macros && r.macros.kcal) stats.push({ v: r.macros.kcal, l: 'kcal / portion' });
  if (r.macros && r.macros.protein) stats.push({ v: r.macros.protein + ' g', l: 'Protéines' });
  if (stats.length) {
    html += '<div class="stats">' + stats.map(function (s) {
      var valHtml = s.raw ? s.v : esc(s.v);
      var idAttr = s.id ? ' id="' + s.id + '"' : '';
      return '<div class="stat"><span class="stat__val"' + idAttr + '>' + valHtml +
             '</span><span class="stat__label">' + esc(s.l) + '</span></div>';
    }).join('') + '</div>';
  }

  var ings = r.ingredients || [];

  function renderIngredients(mult) {
    var h = '';
    ings.forEach(function (i) {
      var cls = 'ingredient';
      if (i.is_optional) cls += ' ingredient--optional';
      if (!i.parsed) cls += ' ingredient--raw';
      var name = i.parsed ? i.name : i.raw;
      var showOpt = i.is_optional && !/optionnel|facultatif|au choix/i.test(name);
      h += '<li class="' + cls + '">' +
           '<span class="ingredient__qty">' + esc(qtyText(i, mult)) + '</span>' +
           '<span class="ingredient__name">' + esc(name) +
           (showOpt ? ' (optionnel)' : '') + '</span></li>';
    });
    return h;
  }

  if (ings.length) {
    html += '<h2 class="section-title">Ingrédients</h2><ul class="ingredients" id="ing-list">' +
            renderIngredients(1) + '</ul>';
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

  if (baseServings) {
    document.querySelectorAll('.srv-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var delta = parseInt(btn.getAttribute('data-srv'));
        curServings = Math.max(1, curServings + delta);
        ratio = curServings / baseServings;
        var counter = document.getElementById('srv-count');
        if (counter) counter.textContent = curServings;
        var list = document.getElementById('ing-list');
        if (list) list.innerHTML = renderIngredients(ratio);
      });
    });
  }

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

  var showRemaining = state.coursesRemaining !== false;
  var today = new Date().toISOString().slice(0, 10);
  var qs = showRemaining ? '?from_date=' + today : '';
  var data = await api('/menus/' + encodeURIComponent(menu.slug) + '/shopping-list' + qs);
  state.shopping = data;

  var toggleLabel = showRemaining ? 'Semaine complète' : 'Reste de la semaine';
  var html = '<h1 class="page__title">Courses</h1>' +
    '<div class="toggle-bar"><button class="btn btn--toggle" onclick="toggleCoursesScope()">' +
    esc(toggleLabel) + '</button></div>' +
    '<p class="page__sub">' + esc(data.title) +
    (showRemaining ? ' · à partir d\'aujourd\'hui' : '') +
    ' · ' + esc(data.covers) + ' couverts · ' +
    esc(data.recipes_matched) + ' recettes reliées</p>';

  // L'âge de l'inventaire est une donnée de premier plan, pas une note de bas
  // de page : c'est lui qui décide si le frais est encore crédible.
  if (data.pantry && data.pantry.is_stale) {
    html += '<div class="banner">Inventaire du garde-manger vieux de ' +
      esc(data.pantry.age_days) + ' jours — les produits frais sont supposés épuisés. ' +
      'Corrigez ce qui est faux plutôt que de faire confiance à cette liste.</div>';
  }
  // Les restes ne sont pas un manque : les afficher dans la même bannière que
  // les repas sans fiche ferait clignoter une alerte qu'on ne peut pas éteindre.
  if (data.meals_leftovers && data.meals_leftovers.length) {
    html += '<p class="page__sub">' + data.meals_leftovers.length +
      ' repas de restes — rien à acheter pour eux : ' +
      esc(data.meals_leftovers.map(function (m) { return m.dish; }).join(' · ')) + '</p>';
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

function toggleCoursesScope() {
  state.coursesRemaining = state.coursesRemaining === false;
  viewCourses();
}

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
                      e.message || 'Le serveur est peut-être indisponible.'));
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

/* ── Bouton micro (STT) — visible seulement si MediaRecorder existe ── */

var _micRecording = false;
var _micRecorder = null;
var _micChunks = [];

function initMic() {
  if (typeof MediaRecorder === 'undefined' ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia) return;

  var fab = document.createElement('button');
  fab.className = 'mic-fab';
  fab.setAttribute('aria-label', 'Commande vocale');
  fab.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor">' +
    '<path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>' +
    '<path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>' +
    '</svg>';
  document.body.appendChild(fab);

  var panel = document.createElement('div');
  panel.id = 'mic-panel';
  panel.className = 'mic-panel';
  panel.style.display = 'none';
  panel.innerHTML =
    '<div class="mic-panel__head">' +
      '<span class="mic-panel__title">Commande vocale</span>' +
      '<button class="mic-panel__close" aria-label="Fermer">✕</button>' +
    '</div>' +
    '<div class="mic-panel__status"></div>' +
    '<div class="mic-panel__transcript"></div>' +
    '<div class="mic-panel__intent"></div>';
  document.body.appendChild(panel);

  panel.querySelector('.mic-panel__close').addEventListener('click', function () {
    panel.style.display = 'none';
  });

  fab.addEventListener('click', function () {
    if (_micRecording) {
      stopMic();
    } else {
      startMic(fab);
    }
  });
}

function startMic(fab) {
  navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
    _micChunks = [];
    _micRecorder = new MediaRecorder(stream);
    _micRecorder.ondataavailable = function (e) {
      if (e.data && e.data.size > 0) _micChunks.push(e.data);
    };
    _micRecorder.onstop = function () {
      stream.getTracks().forEach(function (t) { t.stop(); });
      var blob = new Blob(_micChunks, { type: 'audio/webm' });
      uploadAudio(blob);
    };
    _micRecorder.start();
    _micRecording = true;
    fab.classList.add('mic-fab--active');
    showMicPanel('recording', 'Parlez…', null);
  }).catch(function () {
    showMicPanel('error', 'Micro refusé', null);
  });
}

function stopMic() {
  if (_micRecorder && _micRecorder.state === 'recording') {
    _micRecorder.stop();
  }
  _micRecording = false;
  var fab = document.querySelector('.mic-fab');
  if (fab) fab.classList.remove('mic-fab--active');
  showMicPanel('processing', 'Traitement…', null);
}

function uploadAudio(blob) {
  var form = new FormData();
  form.append('file', blob, 'voice.webm');
  fetch(API + '/audio', { method: 'POST', body: form })
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + '');
      return r.json();
    })
    .then(function (data) {
      handleVoiceResult(data);
    })
    .catch(function (e) {
      showMicPanel('error', 'Erreur : ' + e.message, null);
    });
}

var DAY_NAMES = ['dimanche','lundi','mardi','mercredi','jeudi','vendredi','samedi'];

function findMealId(dayHint, slotHint) {
  var meals = state.weekMenu && state.weekMenu.meals;
  if (!meals || !meals.length) return null;

  var slot = (slotHint || 'dinner').toLowerCase();
  if (slot === 'petit-déjeuner' || slot === 'petit-dej' || slot === 'petit déj' || slot === 'matin') slot = 'breakfast';
  if (slot === 'déjeuner' || slot === 'midi') slot = 'lunch';
  if (slot === 'goûter') slot = 'snack';
  if (slot === 'dîner' || slot === 'soir') slot = 'dinner';

  var targetDay = null;
  var hint = (dayHint || '').toLowerCase();
  if (hint === 'demain') {
    var tom = new Date();
    tom.setDate(tom.getDate() + 1);
    targetDay = DAY_NAMES[tom.getDay()];
  } else if (hint === "aujourd'hui" || hint === 'aujourd hui' || hint === 'ce soir' || hint === 'ce midi') {
    targetDay = DAY_NAMES[new Date().getDay()];
  } else if (hint) {
    targetDay = hint;
  }

  for (var i = 0; i < meals.length; i++) {
    var m = meals[i];
    var mDay = (m.day || '').toLowerCase();
    if (targetDay && mDay !== targetDay) continue;
    if (m[slot + '_meal_id']) return m[slot + '_meal_id'];
  }
  return null;
}

function handleVoiceResult(data) {
  var t = data.transcript || '';
  var intent = data.intent || {};
  var action = intent.action || 'unknown';

  if (action === 'unknown') {
    showMicPanel('error', t || 'Rien entendu', {action: 'unknown'});
    return;
  }

  showMicPanel('success', t, intent);

  if (action === 'search_recipe') {
    window.location.hash = '#/recettes';
    setTimeout(function () {
      state.q = intent.query || '';
      var searchEl = document.getElementById('search');
      if (searchEl) searchEl.value = state.q;
      loadRecipes().then(function (d) { paintRecipes(d.total); });
    }, 100);
    return;
  }

  if (action === 'adjust_servings') {
    var delta = intent.delta || 0;
    var srvBtn = document.querySelector('.srv-btn[data-srv="' +
      (delta > 0 ? '+1' : '-1') + '"]');
    if (srvBtn && delta) {
      var clicks = Math.abs(delta);
      for (var ci = 0; ci < clicks; ci++) srvBtn.click();
    }
    return;
  }

  if (action === 'swap_recipe') {
    var mealId = findMealId(intent.day, intent.slot);
    if (mealId) {
      openSwapPicker(mealId);
      if (intent.recipe) {
        setTimeout(function () {
          var inp = document.querySelector('.picker__search');
          if (inp) {
            inp.value = intent.recipe;
            if (inp.oninput) inp.oninput();
          }
        }, 300);
      }
    }
    return;
  }
}

var ACTION_LABELS = {
  search_recipe: 'Rechercher',
  adjust_servings: 'Portions',
  product_blacklist: 'Exclure produit',
  recipe_note: 'Note recette',
  recipe_edit_step: 'Modifier étape',
  meal_feedback: 'Avis repas',
  pantry_leftover: 'Reste',
  swap_recipe: 'Changer recette',
  unknown: 'Non reconnu'
};

function formatIntentDetail(intent) {
  if (!intent) return '';
  var parts = [];
  var action = intent.action || 'unknown';
  if (intent.query) parts.push(intent.query);
  if (intent.product) parts.push(intent.product);
  if (intent.ingredient) parts.push(intent.ingredient);
  if (intent.dish) parts.push(intent.dish);
  if (intent.note) parts.push(intent.note);
  if (intent.convive) parts.push(intent.convive);
  if (intent.recipe) parts.push(intent.recipe);
  if (intent.delta) parts.push((intent.delta > 0 ? '+' : '') + intent.delta);
  if (intent.servings) parts.push(intent.servings + ' pers.');
  if (intent.step) parts.push('étape ' + intent.step);
  if (intent.slot) parts.push(intent.slot);
  if (intent.day) parts.push(intent.day);
  if (intent.liked === true) parts.push('👍');
  if (intent.liked === false) parts.push('👎');
  return parts.join(' · ');
}

function showMicPanel(status, transcript, intent) {
  var panel = document.getElementById('mic-panel');
  if (!panel) return;
  panel.style.display = '';

  var statusEl = panel.querySelector('.mic-panel__status');
  var transcriptEl = panel.querySelector('.mic-panel__transcript');
  var intentEl = panel.querySelector('.mic-panel__intent');

  panel.className = 'mic-panel mic-panel--' + status;

  if (status === 'recording') {
    statusEl.innerHTML = '<span class="mic-panel__dot"></span> Enregistrement…';
    transcriptEl.textContent = '';
    intentEl.textContent = '';
    return;
  }
  if (status === 'processing') {
    statusEl.innerHTML = '<span class="mic-panel__spinner"></span> Analyse…';
    transcriptEl.textContent = transcript || '';
    intentEl.textContent = '';
    return;
  }

  statusEl.textContent = '';
  transcriptEl.textContent = transcript ? '« ' + transcript + ' »' : '';

  if (intent && intent.action) {
    var label = ACTION_LABELS[intent.action] || intent.action;
    var detail = formatIntentDetail(intent);
    intentEl.innerHTML = '<span class="mic-panel__action">' + label + '</span>' +
      (detail ? ' <span class="mic-panel__detail">' + detail + '</span>' : '');
  } else {
    intentEl.textContent = '';
  }
}

initMic();

route();
