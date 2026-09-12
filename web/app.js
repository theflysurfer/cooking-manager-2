'use strict';

var API = '/api';
var state = {
  recipes: [], filters: null, menu: null, compat: null,
  weekMenu: null,
  active: { status: null, family: null, tag: null, menu: null }, q: ''
};

function ignoreSecondaryFailure(err) {
  if (window.console && console.debug) console.debug('[cm2] echec secondaire ignore', err);
}

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
  if (!r.ok) {
    var err = new Error(r.status + ' ' + r.statusText);
    err.status = r.status;
    try { err.detail = (await r.json()).detail; } catch (e) { err.detail = null; }
    throw err;
  }
  return r.json();
}

function apiErrorText(e) {
  var d = e && e.detail;
  if (!d) return e && e.message ? e.message : 'Échec de l\'enregistrement';
  if (typeof d === 'string') return d;
  var text = d.reason || 'Refusé';
  if (d.candidates && d.candidates.length) text += ' — ' + d.candidates.join(', ');
  return text;
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

var SLOTS = [
  { key: 'breakfast', label: 'Petit-déj' },
  { key: 'lunch',     label: 'Déjeuner' },
  { key: 'snack',     label: 'Goûter' },
  { key: 'dinner',    label: 'Dîner' }
];

var SLOT_HOURS = [
  { key: 'breakfast', after: 0,  label: 'Petit-déj' },
  { key: 'lunch',     after: 10, label: 'Déjeuner' },
  { key: 'snack',     after: 14, label: 'Goûter' },
  { key: 'dinner',    after: 17, label: 'Dîner' }
];

function findNextMeal(meals, nowOverride) {
  if (!meals || !meals.length) return null;
  var now = nowOverride || new Date();
  var m2 = String(now.getMonth() + 1);
  var d2 = String(now.getDate());
  if (m2.length < 2) m2 = '0' + m2;
  if (d2.length < 2) d2 = '0' + d2;
  var today = now.getFullYear() + '-' + m2 + '-' + d2;
  var hour = now.getHours();

  var currentSlotIdx = 0;
  for (var s = SLOT_HOURS.length - 1; s >= 0; s--) {
    if (hour >= SLOT_HOURS[s].after) { currentSlotIdx = s; break; }
  }

  for (var i = 0; i < meals.length; i++) {
    var m = meals[i];
    if (m.date < today) continue;
    var isToday = m.date === today;
    var startSlot = isToday ? currentSlotIdx : 0;
    for (var si = startSlot; si < SLOT_HOURS.length; si++) {
      var sk = SLOT_HOURS[si].key;
      if (m[sk] && m[sk + '_served'] !== true && m[sk + '_served'] !== false) {
        return {
          day: m.day, date: m.date,
          slot: SLOT_HOURS[si].label, slotKey: sk,
          dish: m[sk], slug: m[sk + '_slug'],
          photo: m[sk + '_photo'],
          isLeftovers: m[sk + '_leftovers'],
          isToday: isToday
        };
      }
    }
  }
  return null;
}

function renderNextMeal(next) {
  if (!next) return '';
  var tag = next.slug ? 'a' : 'div';
  var link = next.slug
    ? ' href="#/recette/' + encodeURIComponent(next.slug) + '"'
    : '';
  var ariaLabel = next.slug
    ? ' aria-label="Voir la recette : ' + esc(next.dish) + '"'
    : '';
  var when = next.isToday
    ? next.slot + ' — aujourd\'hui'
    : next.slot + ' — ' + next.day;

  var media;
  if (next.photo) {
    media = '<div class="next-meal__media">' +
      '<img class="next-meal__photo" src="' + esc(next.photo) + '" alt="">' +
      '<div class="next-meal__overlay"></div>' +
    '</div>';
  } else {
    var initial = (next.dish || '?').charAt(0).toUpperCase();
    media = '<div class="next-meal__media next-meal__media--empty">' +
      '<span class="next-meal__initial">' + esc(initial) + '</span>' +
    '</div>';
  }

  return '<' + tag + ' class="next-meal"' + link + ariaLabel + '>' +
    media +
    '<div class="next-meal__info">' +
      '<span class="next-meal__when">' + esc(when) + '</span>' +
      '<span class="next-meal__dish">' + esc(next.dish) + '</span>' +
      (next.isLeftovers ? '<span class="next-meal__tag">restes</span>' : '') +
    '</div>' +
    (next.slug ? '<span class="next-meal__arrow">\u203A</span>' : '') +
  '</' + tag + '>';
}

function todayISO() {
  var d = new Date();
  var m = String(d.getMonth() + 1);
  var day = String(d.getDate());
  if (m.length < 2) m = '0' + m;
  if (day.length < 2) day = '0' + day;
  return d.getFullYear() + '-' + m + '-' + day;
}

function indexCompat(compat) {
  var idx = {};
  if (!compat || !compat.results) return idx;
  compat.results.forEach(function (r) {
    idx[r.day + '/' + r.slot] = r;
  });
  return idx;
}

function servedControl(served, position, slot, recipeSlug, date) {
  var eaten = served === true;
  var skipped = served === false;
  var html = '<div class="served" data-position="' + position +
             '" data-slot="' + esc(slot) + '">' +
    '<button class="served-btn' + (eaten ? ' served-btn--on' : '') +
      '" data-served="true" aria-pressed="' + (eaten ? 'true' : 'false') +
      '">Mangé</button>' +
    '<button class="served-btn' + (skipped ? ' served-btn--off' : '') +
      '" data-served="false" aria-pressed="' + (skipped ? 'true' : 'false') +
      '">Pas fait</button>';
  if (eaten && recipeSlug) {
    html += '<a class="served-note" href="#/recette/' +
      encodeURIComponent(recipeSlug) + '/retour/' + encodeURIComponent(date || '') +
      '">Noter ›</a>';
  }
  return html + '</div>';
}

async function toggleServed(btn) {
  var box = btn.closest('.served');
  if (!box || !state.weekMenu) return;
  var wanted = btn.getAttribute('data-served') === 'true';
  var served = btn.getAttribute('aria-pressed') === 'true' ? null : wanted;
  try {
    await api('/menus/' + encodeURIComponent(state.weekMenu.slug) + '/served', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        served: served,
        position: parseInt(box.getAttribute('data-position'), 10),
        slot: box.getAttribute('data-slot')
      })
    });
  } catch (e) {
    btn.textContent = 'Échec';
    return;
  }
  viewMenu();
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
    if (!atHome) { away = true; }

    var slug = meal[s.key + '_slug'];
    var isLeftovers = meal[s.key + '_leftovers'];
    var mealId = meal[s.key + '_meal_id'];

    slots += '<div class="slot' + (conflicts.length ? ' slot--conflict' : '') + '">' +
      '<span class="slot__label">' + esc(s.label) + '</span>';

    if (slug) {
      var photo = meal[s.key + '_photo'];
      slots += '<a class="slot__dish slot__dish--linked" href="#/recette/' +
        encodeURIComponent(slug) + '">' +
        (photo ? '<img class="slot__thumb" src="' + esc(photo) + '" alt="">' : '') +
        '<span class="slot__dish-name">' + esc(dish) + '</span>' +
        '<span class="slot__arrow">›</span></a>';
    } else if (isLeftovers) {
      slots += '<span class="slot__dish">' + esc(dish) +
        ' <span class="slot__tag">restes</span></span>';
    } else {
      slots += '<span class="slot__dish">' + esc(dish) + '</span>';
    }

    if (mealId && !isLeftovers) {
      var mealCovers = meal[s.key + '_covers'];
      slots += '<div class="slot__actions">' +
        '<button class="swap-btn" data-meal-id="' + mealId + '">Changer</button>' +
        '<button class="covers-btn" data-meal-id="' + mealId + '"' +
        ' data-covers="' + (mealCovers || '') + '">' +
        (mealCovers ? mealCovers + ' couv.' : 'Couverts') + '</button>' +
        '</div>';
    }

    if (mealId) {
      slots += servedControl(meal[s.key + '_served'], mealIndex + 1, s.key,
                             slug, meal.date);
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
  var withMeals = menus.filter(function (m) { return m.meals && m.meals.length; });
  var chosen = state.active.menu;
  var menu = null;
  if (chosen) {
    for (var i = 0; i < withMeals.length; i++) {
      if (withMeals[i].slug === chosen) { menu = withMeals[i]; break; }
    }
  }
  if (!menu) {
    for (var i = 0; i < withMeals.length; i++) {
      if (withMeals[i].status === 'active') { menu = withMeals[i]; break; }
    }
  }
  if (!menu && withMeals.length) { menu = withMeals[0]; }

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
      var day = meals[mm.position - 1];
      if (!day) return;
      day[mm.slot + '_meal_id'] = mm.id;
      if (mm.recipe_slug) day[mm.slot + '_slug'] = mm.recipe_slug;
      if (mm.recipe_photo) day[mm.slot + '_photo'] = mm.recipe_photo;
      if (mm.match_kind === 'leftovers') day[mm.slot + '_leftovers'] = true;
      if (mm.match_kind === 'manual') day[mm.slot] = mm.dish;
      if (mm.covers) day[mm.slot + '_covers'] = mm.covers;
      day[mm.slot + '_served'] = mm.served;
    });
  }

  var compat = null;
  try { compat = await api('/menus/' + encodeURIComponent(menu.slug) + '/compatibility'); }
  catch (e) { compat = null; }

  var idx = indexCompat(compat);
  var today = todayISO();
  var conflicts = compat ? compat.conflicts : 0;

  var picker = '';
  if (withMeals.length > 1) {
    picker = '<select id="menu-picker" class="menu-picker">';
    for (var p = 0; p < withMeals.length; p++) {
      var m = withMeals[p];
      var sel = m.slug === menu.slug ? ' selected' : '';
      picker += '<option value="' + esc(m.slug) + '"' + sel + '>' +
        esc(m.title) + '</option>';
    }
    picker += '</select>';
  }

  var html = picker +
    '<h1 class="page__title">' + esc(menu.title) + '</h1>' +
    '<p class="page__sub">' + esc(menu.week_start || '') + ' → ' + esc(menu.week_end || '') +
    (menu.configuration ? ' · ' + esc(label(menu.configuration)) : '') + '</p>';

  if (conflicts > 0) {
    html += '<div class="banner">' + conflicts + ' conflit' + (conflicts > 1 ? 's' : '') +
      ' alimentaire' + (conflicts > 1 ? 's' : '') + ' sur la semaine — voir les repas signalés.</div>';
  }

  var nextMeal = findNextMeal(menu.meals || []);
  html += renderNextMeal(nextMeal);

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

  var menuPicker = document.getElementById('menu-picker');
  if (menuPicker) {
    menuPicker.addEventListener('change', function () {
      state.active.menu = this.value;
      viewMenu();
    });
  }

  if (_menuClickBound) return;
  _menuClickBound = true;
  app.addEventListener('click', function (e) {
    var servedBtn = e.target.closest('.served-btn');
    if (servedBtn) {
      e.preventDefault();
      toggleServed(servedBtn);
      return;
    }
    var btn = e.target.closest('.swap-btn');
    if (btn) {
      e.preventDefault();
      openSwapPicker(btn.getAttribute('data-meal-id'));
    }
    var coversBtn = e.target.closest('.covers-btn');
    if (coversBtn) {
      e.preventDefault();
      promptCovers(coversBtn);
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

function promptCovers(btn) {
  var mealId = btn.getAttribute('data-meal-id');
  var current = btn.getAttribute('data-covers') || '4';
  var val = window.prompt('Nombre de couverts pour ce repas :', current);
  if (val === null) return;
  var n = parseInt(val, 10);
  if (!n || n < 1) return;
  var slug = state.weekMenu && state.weekMenu.slug;
  if (!slug) return;
  api('/menus/' + encodeURIComponent(slug) + '/meals/' + mealId, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ covers: n })
  }).then(function () {
    btn.setAttribute('data-covers', n);
    btn.textContent = n + ' couv.';
  });
}

var _swapMealId = null;
var _menuClickBound = false;

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

  return '<a class="card" href="#/recette/' + encodeURIComponent(r.slug) + '">' +
    '<div class="card__media">' + media + '</div>' +
    '<div class="card__title">' + esc(r.title) + '</div>' +
    (meta.length ? '<div class="card__meta"><span>' + meta.map(esc).join('</span><span>') + '</span></div>' : '') +
    (macros ? '<div class="card__macros">' + esc(macros) + '</div>' : '') +
    (r.occurrences ? '<div class="card__week">' +
       (r.occurrences > 1 ? r.occurrences + '× cette semaine' : 'Cette semaine') +
       (r.scheduled_at ? ' · ' + esc(r.scheduled_at.join(' · ')) : '') + '</div>' : '') +
  '</a>';
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

async function viewRecipe(slug, servedOn) {
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

  var subs = r.sub_recipes || [];
  if (subs.length) {
    html += '<h2 class="section-title">Sous-recettes</h2><ul class="sub-recipes">' +
      subs.map(function (s) {
        return '<li><a href="#/recette/' + encodeURIComponent(s) + '" class="sub-recipe__link">' +
               esc(s.replace(/-/g, ' ')) + '</a></li>';
      }).join('') + '</ul>';
  }

  html += '<div id="recipe-extras"></div>';

  html += '<h2 class="section-title">Historique</h2><div id="exec">' +
          emptyState('Chargement…') + '</div>';

  html += '<h2 class="section-title" id="retours">Retours de table</h2>' +
          '<div id="feedback">' + emptyState('Chargement…') + '</div>';

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
  } catch (e) { ignoreSecondaryFailure(e); }

  paintRecipeExtras(slug);

  await paintFeedback(slug, servedOn || todayISO());
  if (servedOn) {
    var anchor = document.getElementById('retours');
    if (anchor) anchor.scrollIntoView();
  }
}

function paintRecipeExtras(slug) {
  var box = document.getElementById('recipe-extras');
  if (!box) return;
  var enc = encodeURIComponent(slug);
  var html = '';
  var loaded = 0;
  var total = 3;
  function flush() {
    loaded++;
    if (loaded >= total && box) box.innerHTML = html || '';
  }
  api('/recipes/' + enc + '/tips').then(function (data) {
    var tips = data.tips || [];
    if (tips.length) {
      html += '<h2 class="section-title">Astuces</h2><ul class="recipe-extras">';
      tips.forEach(function (t) {
        html += '<li class="recipe-extra">' +
          '<span class="recipe-extra__kind">' + esc(label(t.kind || '')) + '</span>' +
          (t.step_number ? ' <span class="recipe-extra__step">étape ' + t.step_number + '</span>' : '') +
          '<div class="recipe-extra__text">' + esc(t.verbatim || '') + '</div></li>';
      });
      html += '</ul>';
    }
    flush();
  }).catch(function () { flush(); });
  api('/recipes/' + enc + '/substitutions').then(function (data) {
    var subs = data.substitutions || [];
    if (subs.length) {
      html += '<h2 class="section-title">Substitutions découvertes</h2><ul class="recipe-extras">';
      subs.forEach(function (s) {
        html += '<li class="recipe-extra">' +
          '<span class="recipe-extra__swap">' + esc(s.original_ingredient || '') +
          ' → ' + esc(s.substitute_ingredient || '') + '</span>' +
          ' <span class="recipe-extra__outcome">' + esc(label(s.outcome || '')) + '</span>' +
          (s.who_preferred ? ' <span class="recipe-extra__who">(' + esc(s.who_preferred) + ')</span>' : '') +
          (s.verbatim ? '<div class="recipe-extra__text">' + esc(s.verbatim) + '</div>' : '') +
          '</li>';
      });
      html += '</ul>';
    }
    flush();
  }).catch(function () { flush(); });
  api('/recipes/' + enc + '/service-contexts').then(function (data) {
    var ctxs = data.contexts || [];
    if (ctxs.length) {
      html += '<h2 class="section-title">Contextes de service</h2><ul class="recipe-extras">';
      ctxs.forEach(function (c) {
        html += '<li class="recipe-extra">' +
          '<span class="recipe-extra__kind">' + esc(label(c.context || '')) + '</span>' +
          (c.verbatim ? '<div class="recipe-extra__text">' + esc(c.verbatim) + '</div>' : '') +
          '</li>';
      });
      html += '</ul>';
    }
    flush();
  }).catch(function () { flush(); });
}

async function feedbackVocabulary() {
  if (!state.feedbackVocab) {
    state.feedbackVocab = (await api('/vocabulary/feedback')).facets;
  }
  return state.feedbackVocab;
}

async function feedbackPersons() {
  if (!state.persons) {
    state.persons = await api('/persons?circle=household');
    if (!state.persons.length) state.persons = await api('/persons');
  }
  return state.persons;
}

function conceptOptions(concepts, placeholder) {
  var html = '<option value="">' + esc(placeholder) + '</option>';
  concepts.forEach(function (c) {
    html += '<option value="' + esc(c.key) + '">' + esc(c.label) + '</option>';
  });
  return html;
}

function conceptLabel(facet, key) {
  if (!key) return '';
  var concepts = (state.feedbackVocab && state.feedbackVocab[facet]) || [];
  for (var i = 0; i < concepts.length; i++) {
    if (concepts[i].key === key) return concepts[i].label;
  }
  return label(key);
}

function feedbackHistory(data) {
  var html = '';
  (data.verdicts || []).forEach(function (v) {
    var issues = (v.issue_kinds || []).map(function (k) {
      return conceptLabel('issue_kinds', k);
    }).join(' · ');
    html += '<div class="fb-row fb-row--verdict">' +
      '<span class="fb-row__date">' + esc(v.served_on) + '</span>' +
      '<span class="fb-row__value">' + esc(conceptLabel('replay_verdicts', v.verdict)) + '</span>' +
      (issues ? '<span class="fb-row__issues">' + esc(issues) + '</span>' : '') +
      (v.verbatim ? '<div class="fb-row__verbatim">« ' + esc(v.verbatim) + ' »</div>' : '') +
      '</div>';
  });
  (data.feedback || []).forEach(function (f) {
    html += '<div class="fb-row">' +
      '<span class="fb-row__date">' + esc(f.served_on) + '</span>' +
      '<span class="fb-row__who">' + esc(f.person) + '</span>' +
      '<span class="fb-row__value">' + esc(conceptLabel('appreciations', f.appreciation)) + '</span>' +
      (f.verbatim ? '<div class="fb-row__verbatim">« ' + esc(f.verbatim) + ' »</div>' : '') +
      '</div>';
  });
  return html;
}

async function paintFeedback(slug, servedOn) {
  var box = document.getElementById('feedback');
  if (!box) return;
  var vocab, persons, data;
  try {
    vocab = await feedbackVocabulary();
    persons = await feedbackPersons();
    data = await api('/recipes/' + encodeURIComponent(slug) + '/feedback');
  } catch (e) {
    box.innerHTML = emptyState('Retours indisponibles', apiErrorText(e));
    return;
  }

  var history = feedbackHistory(data);
  var html = history || '<p class="empty__hint">Aucun retour pour l\'instant.</p>';

  html += '<form class="fb-form" data-slug="' + esc(slug) + '">' +
    '<input class="fb-date" type="date" value="' + esc(servedOn) + '">' +
    '<div class="fb-field"><label class="fb-label">Qui</label>' +
      '<select class="fb-person">' +
      persons.map(function (p) {
        return '<option value="' + esc(p.name) + '">' + esc(p.name) + '</option>';
      }).join('') + '</select></div>' +
    '<div class="fb-field"><label class="fb-label">Ce qu\'il ou elle en a pensé</label>' +
      '<select class="fb-appreciation">' +
      conceptOptions(vocab.appreciations, 'À lire dans le commentaire') +
      '</select></div>' +
    '<div class="fb-field"><label class="fb-label">Commentaire</label>' +
      '<textarea class="fb-verbatim" rows="2" placeholder="Ce qui a été dit à table"></textarea></div>' +
    '<button type="button" class="btn fb-submit" data-kind="feedback">Enregistrer l\'avis</button>' +
    '<hr class="fb-sep">' +
    '<div class="fb-field"><label class="fb-label">Refaire ce plat ?</label>' +
      '<select class="fb-verdict">' +
      conceptOptions(vocab.replay_verdicts, 'À lire dans le commentaire') +
      '</select></div>' +
    '<div class="fb-field"><label class="fb-label">Ce qu\'il faudrait corriger</label>' +
      '<div class="fb-issues">' +
      vocab.issue_kinds.map(function (c) {
        return '<label class="fb-issue"><input type="checkbox" value="' + esc(c.key) +
               '"> ' + esc(c.label) + '</label>';
      }).join('') + '</div></div>' +
    '<button type="button" class="btn fb-submit" data-kind="verdict">Enregistrer le verdict</button>' +
    '<p class="fb-msg"></p>' +
    '</form>';

  box.innerHTML = html;
}

async function submitFeedback(btn) {
  var form = btn.closest('.fb-form');
  if (!form) return;
  var slug = form.getAttribute('data-slug');
  var kind = btn.getAttribute('data-kind');
  var servedOn = form.querySelector('.fb-date').value;
  var verbatim = form.querySelector('.fb-verbatim').value.trim();
  var msg = form.querySelector('.fb-msg');
  var body, path;

  if (!servedOn) {
    msg.textContent = 'Indiquez le jour où le plat a été mangé.';
    return;
  }

  if (kind === 'feedback') {
    path = '/recipes/' + encodeURIComponent(slug) + '/feedback';
    body = {
      person: form.querySelector('.fb-person').value,
      served_on: servedOn,
      source: 'app'
    };
    var appreciation = form.querySelector('.fb-appreciation').value;
    if (appreciation) body.appreciation = appreciation;
    if (verbatim) body.verbatim = verbatim;
  } else {
    path = '/recipes/' + encodeURIComponent(slug) + '/verdict';
    body = { served_on: servedOn };
    var verdict = form.querySelector('.fb-verdict').value;
    if (verdict) body.verdict = verdict;
    if (verbatim) body.verbatim = verbatim;
    var issues = [];
    form.querySelectorAll('.fb-issue input:checked').forEach(function (i) {
      issues.push(i.value);
    });
    if (issues.length) body.issue_kinds = issues;
  }

  btn.disabled = true;
  msg.textContent = 'Enregistrement…';
  try {
    await api(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  } catch (e) {
    msg.textContent = apiErrorText(e);
    btn.disabled = false;
    return;
  }
  await paintFeedback(slug, servedOn);
}

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

  if (data.pantry && data.pantry.is_stale) {
    html += '<div class="banner">Inventaire du garde-manger vieux de ' +
      esc(data.pantry.age_days) + ' jours — les produits frais sont supposés épuisés. ' +
      'Corrigez ce qui est faux plutôt que de faire confiance à cette liste.</div>';
  }
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
  var buyCount = 0;
  ORDER.forEach(function (key) {
    var group = lines.filter(function (l) { return l.outcome === key; });
    if (!group.length) return;
    if (key === 'absent' || key === 'insuffisant') buyCount += group.length;
    html += '<h2 class="section-title">' + esc(OUTCOMES[key].label) +
            ' <span class="section-count">' + group.length + '</span></h2>' +
            '<ul class="needs">' + group.map(needRow).join('') + '</ul>';
  });

  if (buyCount > 0) {
    html += '<div class="drive-cta">' +
      '<button class="btn btn--accent" onclick="location.hash=\'#/drive\'">' +
      'Envoyer au drive (' + buyCount + ' articles)</button></div>';
  }

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

async function viewDrive() {
  var data = state.shopping;
  if (!data) {
    render(emptyState('Calcul de la liste…'));
    var menus = (await api('/menus')).menus || [];
    var menu = null;
    for (var i = 0; i < menus.length; i++) {
      if (menus[i].meals && menus[i].meals.length) { menu = menus[i]; break; }
    }
    if (!menu) {
      render('<h1 class="page__title">Drive</h1>' +
        emptyState('Pas de menu actif', 'La liste de courses se calcule depuis le menu.'));
      return;
    }
    var today = new Date().toISOString().slice(0, 10);
    data = await api('/menus/' + encodeURIComponent(menu.slug) +
                     '/shopping-list?from_date=' + today);
    state.shopping = data;
  }

  var toBuy = (data.lines || []).filter(function (l) {
    return l.outcome === 'absent' || l.outcome === 'insuffisant';
  });

  if (!toBuy.length) {
    render('<h1 class="page__title">Drive</h1>' +
      emptyState('Rien à acheter', 'Tous les ingrédients sont en stock.') +
      '<div class="drive-actions"><button class="btn" ' +
      'onclick="location.hash=\'#/courses\'">Retour aux courses</button></div>');
    return;
  }

  var store = state.driveStore || 'auchan';
  render('<h1 class="page__title">Panier drive</h1>' +
    '<p class="page__sub">' + esc(data.title) + ' · ' + toBuy.length + ' ingrédients</p>' +
    _storePicker(store) +
    '<div class="drive-loading"><p class="empty__title">Recherche sur ' +
    esc(store.charAt(0).toUpperCase() + store.slice(1)) + '…</p></div>');

  var payload = toBuy.map(function (l) {
    return {
      name: l.name, name_normalized: l.name_normalized,
      qty: l.qty, unit: l.unit, recipes: l.recipes
    };
  });

  try {
    var result = await api('/drives/map-ingredients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ store: store, ingredients: payload })
    });
  } catch (e) {
    render('<h1 class="page__title">Panier drive</h1>' +
      '<div class="banner">Erreur : ' + esc(e.message) + '</div>' +
      '<div class="drive-actions"><button class="btn" ' +
      'onclick="location.hash=\'#/courses\'">Retour aux courses</button></div>');
    return;
  }

  state.driveMappings = result.mappings;
  _renderDrive(data, result.mappings, store);
}

function _storePicker(active) {
  var stores = [
    { id: 'auchan', label: 'Auchan' },
    { id: 'leclerc', label: 'Leclerc' }
  ];
  var html = '<div class="store-picker">';
  for (var i = 0; i < stores.length; i++) {
    var s = stores[i];
    var cls = s.id === active ? 'store-pill store-pill--active' : 'store-pill';
    html += '<button class="' + cls + '" data-store="' + s.id + '">' +
      esc(s.label) + '</button>';
  }
  return html + '</div>';
}

function _renderDrive(data, mappings, store) {
  var html = '<h1 class="page__title">Panier drive</h1>' +
    '<p class="page__sub">' + esc(data.title) + ' · ' + mappings.length + ' ingrédients</p>' +
    _storePicker(store);

  var total = 0;
  var matched = 0;

  html += '<ul class="drive-list">';
  for (var i = 0; i < mappings.length; i++) {
    var m = mappings[i];
    var sel = m.selected;
    var product = (sel >= 0 && m.results.length > sel) ? m.results[sel] : null;
    var expanded = state.driveExpanded === i;

    html += '<li class="drive-row' + (product ? '' : ' drive-row--empty') +
            '" data-idx="' + i + '">';

    html += '<div class="drive-row__need">' +
      '<strong class="drive-row__ing">' + esc(m.ingredient) + '</strong>';
    if (m.qty !== null && m.qty !== undefined) {
      html += ' <span class="drive-row__qty">' + m.qty +
        (m.unit ? ' ' + esc(m.unit) : '') + '</span>';
    }
    if (m.recipes && m.recipes.length) {
      html += '<div class="drive-row__recipes">' + esc(m.recipes.join(' · ')) + '</div>';
    }
    html += '</div>';

    if (product) {
      matched++;
      if (product.price) total += product.price;

      html += '<div class="drive-row__product">';
      if (product.image_url) {
        html += '<div class="drive-row__thumb">' +
          '<img src="' + esc(product.image_url) +
          '" alt="" width="56" height="56"></div>';
      }
      html += '<div class="drive-row__detail">' +
        '<span class="drive-row__pname">' + esc(product.name) + '</span>';
      if (product.price !== null && product.price !== undefined) {
        html += '<span class="drive-row__price">' +
          product.price.toFixed(2) + ' €</span>';
      }
      if (product.price_per_unit) {
        html += '<span class="drive-row__ppu">' +
          esc(product.price_per_unit) + '</span>';
      }
      if (product.nutriscore) {
        html += ' ' + nutriscoreBadge(product.nutriscore);
      }
      html += '</div>';
      html += '<button class="mini drive-row__swap" data-swap="' + i +
        '">' + (expanded ? '▲' : 'Changer') + '</button>';
      html += '</div>';
    } else {
      html += '<div class="drive-row__product drive-row__product--miss">' +
        '<span class="drive-row__miss">Aucun résultat</span>' +
        '<button class="mini drive-row__swap" data-swap="' + i +
        '">Chercher</button></div>';
    }

    if (expanded) {
      html += '<div class="drive-alts">';
      if (m.results.length > 1) {
        for (var j = 0; j < m.results.length; j++) {
          if (j === sel) continue;
          var alt = m.results[j];
          html += '<button class="drive-alt" data-pick="' + i + '-' + j + '">';
          if (alt.image_url) {
            html += '<img class="drive-alt__img" src="' + esc(alt.image_url) +
              '" alt="" width="40" height="40">';
          }
          html += '<span class="drive-alt__name">' + esc(alt.name) + '</span>';
          if (alt.price !== null && alt.price !== undefined) {
            html += '<span class="drive-alt__price">' +
              alt.price.toFixed(2) + ' €</span>';
          }
          if (alt.nutriscore) html += ' ' + nutriscoreBadge(alt.nutriscore);
          html += '</button>';
        }
      }
      html += '<div class="drive-search-box">' +
        '<input class="drive-search__input" type="text" ' +
        'placeholder="Chercher un produit…" data-search-idx="' + i + '">' +
        '</div>';
      if (state.driveSearchResults && state.driveSearchResults.idx === i) {
        var sr = state.driveSearchResults.products;
        for (var k = 0; k < sr.length; k++) {
          html += '<button class="drive-alt" data-search-pick="' + i + '-' + k + '">';
          if (sr[k].image_url) {
            html += '<img class="drive-alt__img" src="' + esc(sr[k].image_url) +
              '" alt="" width="40" height="40">';
          }
          html += '<span class="drive-alt__name">' + esc(sr[k].name) + '</span>';
          if (sr[k].price !== null && sr[k].price !== undefined) {
            html += '<span class="drive-alt__price">' +
              sr[k].price.toFixed(2) + ' €</span>';
          }
          html += '</button>';
        }
      }
      html += '</div>';
    }

    html += '</li>';
  }
  html += '</ul>';

  html += '<div class="drive-summary">' +
    '<span class="drive-summary__count">' + matched + '/' + mappings.length +
    ' trouvés</span>';
  if (total > 0) {
    html += '<span class="drive-summary__total">≈ ' +
      total.toFixed(2) + ' €</span>';
  }
  html += '</div>';

  html += '<div class="drive-actions">' +
    '<button class="btn btn--accent" onclick="_driveCompare()">Comparer Auchan vs Leclerc</button>' +
    '<button class="btn" onclick="location.hash=\'#/courses\'">← Courses</button>' +
    '</div>';

  render(html);
}

function _driveSwap(idx) {
  state.driveExpanded = (state.driveExpanded === idx) ? null : idx;
  state.driveSearchResults = null;
  _renderDrive(state.shopping, state.driveMappings, state.driveStore || 'auchan');
}

function _drivePick(idx, altIdx) {
  var m = state.driveMappings[idx];
  if (m) m.selected = altIdx;
  state.driveExpanded = null;
  _renderDrive(state.shopping, state.driveMappings, state.driveStore || 'auchan');
}

function _driveSearchPick(idx, searchIdx) {
  if (!state.driveSearchResults) return;
  var product = state.driveSearchResults.products[searchIdx];
  if (!product) return;
  var m = state.driveMappings[idx];
  if (m) {
    m.results.push(product);
    m.selected = m.results.length - 1;
  }
  state.driveExpanded = null;
  state.driveSearchResults = null;
  _renderDrive(state.shopping, state.driveMappings, state.driveStore || 'auchan');
}

var _driveSearchTimer = null;

function _driveSearchKeyup(input) {
  var idx = parseInt(input.getAttribute('data-search-idx'), 10);
  var q = input.value.trim();
  if (q.length < 2) return;
  if (_driveSearchTimer) clearTimeout(_driveSearchTimer);
  _driveSearchTimer = setTimeout(function () {
    var store = state.driveStore || 'auchan';
    api('/drives/' + encodeURIComponent(store) + '/search?q=' + encodeURIComponent(q))
      .then(function (res) {
        state.driveSearchResults = { idx: idx, products: res.products || [] };
        _renderDrive(state.shopping, state.driveMappings, store);
        var el = document.querySelector('[data-search-idx="' + idx + '"]');
        if (el) { el.value = q; el.focus(); }
      });
  }, 400);
}

async function _driveCompare() {
  var data = state.shopping;
  if (!data) return;

  var toBuy = (data.lines || []).filter(function (l) {
    return l.outcome === 'absent' || l.outcome === 'insuffisant';
  });
  if (!toBuy.length) return;

  render('<h1 class="page__title">Comparaison des prix</h1>' +
    '<p class="page__sub">' + esc(data.title) + ' · ' + toBuy.length + ' ingrédients</p>' +
    '<div class="drive-loading"><p class="empty__title">Recherche en parallèle sur Auchan et Leclerc…</p></div>');

  var payload = toBuy.map(function (l) {
    return { name: l.name, name_normalized: l.name_normalized,
             qty: l.qty, unit: l.unit, recipes: l.recipes };
  });

  try {
    var result = await api('/drives/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ingredients: payload })
    });
  } catch (e) {
    render('<h1 class="page__title">Comparaison</h1>' +
      '<div class="banner">Erreur : ' + esc(e.message) + '</div>' +
      '<div class="drive-actions"><button class="btn" ' +
      'onclick="location.hash=\'#/drive\'">Retour</button></div>');
    return;
  }

  _renderCompare(result, data);
}

function _renderCompare(result, data) {
  var auchan = result.auchan;
  var leclerc = result.leclerc;
  var diff = auchan.total - leclerc.total;
  var cheaperLabel = diff > 0 ? 'Leclerc' : 'Auchan';
  var saving = Math.abs(diff).toFixed(2);

  var html = '<h1 class="page__title">Comparaison des prix</h1>' +
    '<p class="page__sub">' + esc(data.title) + '</p>';

  html += '<div class="compare-summary">' +
    '<div class="compare-summary__store">' +
      '<strong>Auchan</strong>' +
      '<span class="compare-summary__total' +
        (diff > 0 ? '' : ' compare-summary__total--cheap') + '">' +
        auchan.total.toFixed(2) + ' €</span></div>' +
    '<div class="compare-summary__vs">vs</div>' +
    '<div class="compare-summary__store">' +
      '<strong>Leclerc</strong>' +
      '<span class="compare-summary__total' +
        (diff > 0 ? ' compare-summary__total--cheap' : '') + '">' +
        leclerc.total.toFixed(2) + ' €</span></div>' +
    '</div>';

  if (Math.abs(diff) >= 0.01) {
    html += '<div class="compare-winner">' + esc(cheaperLabel) +
      ' moins cher de ' + saving + ' €</div>';
  }

  html += '<ul class="compare-list">';
  var len = Math.max(auchan.mappings.length, leclerc.mappings.length);
  for (var i = 0; i < len; i++) {
    var mA = auchan.mappings[i];
    var mL = leclerc.mappings[i];
    var pA = _selectedProduct(mA);
    var pL = _selectedProduct(mL);
    var priceA = pA && pA.price ? pA.price : null;
    var priceL = pL && pL.price ? pL.price : null;
    var cheaper = (priceA !== null && priceL !== null)
      ? (priceA < priceL ? 'a' : priceL < priceA ? 'l' : '')
      : '';

    html += '<li class="compare-row">';
    html += '<div class="compare-row__ing">' +
      '<strong>' + esc((mA || mL).ingredient) + '</strong>';
    var qty = (mA || mL).qty;
    var unit = (mA || mL).unit;
    if (qty !== null && qty !== undefined) {
      html += ' <span class="drive-row__qty">' + qty +
        (unit ? ' ' + esc(unit) : '') + '</span>';
    }
    html += '</div>';

    html += '<div class="compare-row__stores">';
    html += _compareCell(pA, 'Auchan', cheaper === 'a');
    html += _compareCell(pL, 'Leclerc', cheaper === 'l');
    html += '</div></li>';
  }
  html += '</ul>';

  html += '<div class="drive-actions">' +
    '<button class="btn" onclick="location.hash=\'#/drive\'">← Retour au drive</button></div>';

  render(html);
}

function _selectedProduct(mapping) {
  if (!mapping) return null;
  var sel = mapping.selected;
  if (sel < 0 || !mapping.results || sel >= mapping.results.length) return null;
  return mapping.results[sel];
}

function _compareCell(product, label, isCheap) {
  var html = '<div class="compare-cell' + (isCheap ? ' compare-cell--cheap' : '') + '">';
  html += '<span class="compare-cell__label">' + esc(label) + '</span>';
  if (product) {
    if (product.image_url) {
      html += '<img class="compare-cell__img" src="' + esc(product.image_url) +
        '" alt="" width="40" height="40">';
    }
    html += '<span class="compare-cell__name">' + esc(product.name) + '</span>';
    if (product.price !== null && product.price !== undefined) {
      html += '<span class="compare-cell__price">' +
        product.price.toFixed(2) + ' €</span>';
    }
  } else {
    html += '<span class="compare-cell__miss">—</span>';
  }
  return html + '</div>';
}

var STATUS_COLORS = { ok: '#4caf50', low: '#ff9800', out: '#f44336' };
var STATUS_LABELS = { ok: 'En stock', low: 'Peu', out: 'Épuisé' };

async function viewPantry() {
  render('<div class="section-head"><h2 class="section-title">Garde-manger</h2></div>' +
    skeletonGrid(6));
  var data = await api('/pantry');

  var html = '<div class="section-head"><h2 class="section-title">Garde-manger</h2>';
  if (data.updated) {
    var staleClass = data.is_stale ? ' pantry-age--stale' : '';
    html += '<span class="pantry-age' + staleClass + '">' +
      'Inventaire du ' + data.updated +
      (data.age_days !== null ? ' (' + data.age_days + ' j)' : '') + '</span>';
  }
  html += '</div>';

  if (!data.rayons || !data.rayons.length) {
    render(html + emptyState('Garde-manger vide', 'Aucun article dans l\'inventaire.'));
    return;
  }

  if (data.is_stale) {
    html += '<div class="alert alert--warn">Inventaire vieux de ' +
      data.age_days + ' jours — les produits frais sont supposés épuisés.</div>';
  }

  html += '<div class="pantry-stats">' + data.total + ' articles</div>';

  for (var i = 0; i < data.rayons.length; i++) {
    var rayon = data.rayons[i];
    html += '<section class="pantry-rayon">';
    html += '<h3 class="pantry-rayon__title">' + esc(rayon.name) + '</h3>';
    html += '<ul class="pantry-list">';
    for (var j = 0; j < rayon.items.length; j++) {
      var item = rayon.items[j];
      var statusColor = STATUS_COLORS[item.status] || '#999';
      var statusLabel = STATUS_LABELS[item.status] || item.status;
      html += '<li class="pantry-item pantry-item--' + esc(item.status) + '">';
      html += '<span class="pantry-item__dot" style="background:' + statusColor + '" title="' + esc(statusLabel) + '"></span>';
      html += '<span class="pantry-item__name">' + esc(item.name) + '</span>';
      if (item.qty_text) {
        html += '<span class="pantry-item__qty">' + esc(item.qty_text) + '</span>';
      }
      if (item.xstatus && item.xstatus !== 'ok' && item.xstatus !== item.status) {
        html += '<span class="pantry-item__xstatus">' + esc(item.xstatus) + '</span>';
      }
      html += '</li>';
    }
    html += '</ul></section>';
  }

  render(html);
}

var NUTRISCORE_COLORS = { A: '#038141', B: '#85bb2f', C: '#fecb02', D: '#ee8100', E: '#e63e11' };

function nutriscoreBadge(grade) {
  if (!grade) return '';
  var upper = grade.toUpperCase();
  var color = NUTRISCORE_COLORS[upper] || '#999';
  return '<span class="nutriscore" style="background:' + color + '">' + upper + '</span>';
}

async function viewShopping() {
  render('<div class="section-head"><h2 class="section-title">Historique des achats</h2></div>' +
    skeletonGrid(4));
  var data = await api('/shopping/sessions');

  if (!data.sessions || !data.sessions.length) {
    render(emptyState('Aucun achat enregistré', 'Les sessions apparaîtront ici après un drive.'));
    return;
  }

  var html = '<div class="section-head"><h2 class="section-title">Historique des achats</h2></div>';
  html += '<div class="sessions-list">';
  for (var i = 0; i < data.sessions.length; i++) {
    var s = data.sessions[i];
    html += '<div class="session-card" data-session-id="' + s.id + '">';
    html += '<div class="session-card__head">';
    html += '<strong>' + esc(s.store) + '</strong>';
    html += '<span class="session-card__date">' + esc(s.date) + '</span>';
    html += '</div>';
    html += '<div class="session-card__meta">';
    if (s.items_count) html += s.items_count + ' articles';
    if (s.total) html += ' · ' + Number(s.total).toFixed(2) + ' €';
    html += '</div>';
    html += '<button class="btn btn--sm session-card__expand">Voir les produits</button>';
    html += '<div class="session-card__products" style="display:none"></div>';
    html += '</div>';
  }
  html += '</div>';

  render(html);
}

async function expandSession(card) {
  var sid = card.getAttribute('data-session-id');
  var container = card.querySelector('.session-card__products');
  var btn = card.querySelector('.session-card__expand');

  if (container.style.display !== 'none') {
    container.style.display = 'none';
    btn.textContent = 'Voir les produits';
    return;
  }

  btn.textContent = 'Chargement…';
  var data = await api('/shopping/sessions/' + sid + '/products');
  btn.textContent = 'Masquer';
  container.style.display = '';

  if (!data.products || !data.products.length) {
    container.innerHTML = '<p class="empty__hint">Aucun produit</p>';
    return;
  }

  var html = '<table class="products-table"><thead><tr>' +
    '<th>Produit</th><th>Qté</th><th>Prix</th><th>NS</th><th>Allergènes</th>' +
    '</tr></thead><tbody>';
  for (var i = 0; i < data.products.length; i++) {
    var p = data.products[i];
    html += '<tr class="product-row">';
    html += '<td class="product-row__name">';
    if (p.photo_url) {
      html += '<img class="product-row__img" src="' + esc(p.photo_url) + '" alt="" loading="lazy">';
    }
    html += '<div>';
    html += '<div>' + esc(p.product_name) + '</div>';
    if (p.brand) html += '<div class="product-row__brand">' + esc(p.brand) + '</div>';
    if (p.weight) html += '<div class="product-row__weight">' + esc(p.weight) + '</div>';
    html += '</div></td>';
    html += '<td>' + (p.quantity_bought || 1) + '</td>';
    html += '<td>';
    if (p.total_price) html += Number(p.total_price).toFixed(2) + ' €';
    if (p.price_per_kg) html += '<div class="product-row__ppkg">' + Number(p.price_per_kg).toFixed(2) + ' €/kg</div>';
    html += '</td>';
    html += '<td>' + nutriscoreBadge(p.nutriscore) + '</td>';
    html += '<td class="product-row__allergens">' + esc(p.allergens || '') + '</td>';
    html += '</tr>';
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

async function viewImport() {
  render('<h1 class="title">Importer une recette</h1>' +
         '<div class="skeleton skeleton--card"></div>');

  var data = await api('/api/recipes/import/drafts?status=pending');
  var drafts = data.drafts || [];

  var html = '<h1 class="title">Importer une recette</h1>' +
    '<p class="lede">Photographiez la page du livre. La fiche sera relue avant ' +
    'd\'être ajoutée.</p>' +
    '<div class="import__capture">' +
    '<label class="btn btn--accent import__shoot">' +
    '<input type="file" accept="image/*" capture="environment" multiple ' +
    'id="import-file" class="import__input">' +
    'Photographier une page</label>' +
    '<input class="input import__source" id="import-source" ' +
    'placeholder="Source (ex. Livre de fromages, p. 130)">' +
    '</div>' +
    '<div id="import-status"></div>';

  if (drafts.length) {
    html += '<h2 class="section-title">À valider <span class="badge">' +
            drafts.length + '</span></h2><div class="draft-list">';
    for (var i = 0; i < drafts.length; i++) {
      var d = drafts[i];
      var unparsed = (d.draft && d.draft.unparsed_count) || 0;
      html += '<button class="draft-row" data-draft="' + d.id + '">' +
        '<span class="draft-row__title">' + esc(d.title || 'Sans titre') + '</span>' +
        '<span class="draft-row__meta">' +
        ((d.draft && d.draft.ingredients) ? d.draft.ingredients.length : 0) +
        ' ingrédients' +
        (unparsed ? ' · <span class="draft-row__warn">' + unparsed +
                    ' à vérifier</span>' : '') +
        '</span></button>';
    }
    html += '</div>';
  } else {
    html += emptyState('Aucun brouillon en attente',
                       'Les pages photographiées apparaissent ici jusqu\'à leur validation.');
  }
  render(html);
}

async function uploadImportPages(files) {
  var status = document.getElementById('import-status');
  var sourceEl = document.getElementById('import-source');
  status.innerHTML = '<p class="import__working">Lecture de la page…</p>';

  var fd = new FormData();
  for (var i = 0; i < files.length; i++) fd.append('files', files[i]);
  fd.append('source', sourceEl ? sourceEl.value : '');

  try {
    var r = await fetch(API + '/api/recipes/import', { method: 'POST', body: fd });
    if (!r.ok) {
      var detail = await r.text();
      throw new Error(detail.slice(0, 200));
    }
    var draft = await r.json();
    location.hash = '#/import/' + draft.id;
  } catch (e) {
    status.innerHTML = '<p class="import__error">Lecture impossible : ' +
                       esc(e.message) + '</p>';
  }
}

var CURRENT_DRAFT = null;

async function viewImportDraft(id) {
  var row = await api('/api/recipes/import/drafts/' + id);
  CURRENT_DRAFT = row.draft;
  CURRENT_DRAFT._id = row.id;

  var d = CURRENT_DRAFT;
  var html = '<button class="btn" onclick="location.hash=\'#/import\'">← Imports</button>' +
    '<h1 class="title">Relire avant d\'ajouter</h1>';

  if (d.unparsed_count) {
    html += '<p class="import__flag">' + d.unparsed_count +
            ' ligne(s) sans quantité comprise — vérifiez-les ci-dessous.</p>';
  }

  html += '<div class="draft-form">' +
    field('Titre', 'title', d.title) +
    field('Type', 'recipe_type', d.recipe_type) +
    field('Rendement', 'yield_raw', d.yield_raw) +
    field('Préparation (min)', 'prep_time_min', d.prep_time_min) +
    field('Cuisson (min)', 'cook_time_min', d.cook_time_min) +
    '</div>';

  html += '<h2 class="section-title">Ce que j\'ai compris</h2><ul class="draft-ing">';
  for (var i = 0; i < d.ingredients.length; i++) {
    var ing = d.ingredients[i];
    html += '<li class="draft-ing__row' + (ing.parsed ? '' : ' draft-ing__row--warn') + '">' +
      (ing.section ? '<span class="draft-ing__sec">' + esc(ing.section) + '</span>' : '') +
      '<input class="input draft-ing__raw" data-ing="' + i + '" value="' +
      esc(ing.raw) + '">' +
      '<span class="draft-ing__parsed">' +
      (ing.parsed
        ? esc((ing.qty_min || '') + ' ' + (ing.unit || '') + ' · ' + (ing.name || ''))
        : 'quantité non comprise') +
      '</span></li>';
  }
  html += '</ul>';

  if (d.steps && d.steps.length) {
    html += '<h2 class="section-title">Étapes</h2><ol class="draft-steps">';
    for (var s = 0; s < d.steps.length; s++) {
      html += '<li>' + esc(d.steps[s].text) + '</li>';
    }
    html += '</ol>';
  }

  html += '<div class="draft-actions">' +
    '<button class="btn btn--accent" id="draft-commit">Ajouter au vault</button>' +
    '<button class="btn" id="draft-discard">Jeter</button>' +
    '</div><div id="draft-status"></div>';

  render(html);
}

function field(labelText, key, value) {
  return '<label class="draft-field"><span class="draft-field__label">' +
         esc(labelText) + '</span>' +
         '<input class="input" data-field="' + key + '" value="' +
         esc(value === null || value === undefined ? '' : value) + '"></label>';
}

function collectDraft() {
  var d = CURRENT_DRAFT;
  document.querySelectorAll('[data-field]').forEach(function (el) {
    var k = el.getAttribute('data-field');
    var v = el.value.trim();
    if (k === 'prep_time_min' || k === 'cook_time_min') {
      d[k] = v ? parseInt(v, 10) : null;
    } else {
      d[k] = v || null;
    }
  });
  document.querySelectorAll('[data-ing]').forEach(function (el) {
    var i = parseInt(el.getAttribute('data-ing'), 10);
    d.ingredients[i].raw = el.value;
  });
  return d;
}

async function commitDraft() {
  var status = document.getElementById('draft-status');
  status.innerHTML = '<p class="import__working">Enregistrement…</p>';
  var d = collectDraft();
  try {
    await api('/api/recipes/import/drafts/' + d._id, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ draft: d })
    });
    var res = await api('/api/recipes/import/drafts/' + d._id + '/commit',
                        { method: 'POST' });
    if (res.visible) {
      location.hash = '#/recette/' + res.slug;
    } else {
      status.innerHTML = '<p class="import__working">Ajoutée au vault. ' +
        'Elle apparaîtra dans les recettes d\'ici une minute.</p>';
      setTimeout(function () { location.hash = '#/import'; }, 2500);
    }
  } catch (e) {
    status.innerHTML = '<p class="import__error">' + esc(e.message) + '</p>';
  }
}

var ROUTES = {
  menu: viewMenu, recettes: viewRecipes, courses: viewCourses,
  'garde-manger': viewPantry, achats: viewShopping, drive: viewDrive,
  import: viewImport
};

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
      var servedOn = (parts[2] === 'retour' && parts[3])
        ? decodeURIComponent(parts[3]) : null;
      await viewRecipe(decodeURIComponent(parts[1]), servedOn);
    } else if (parts[0] === 'import' && parts[1]) {
      await viewImportDraft(parts[1]);
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

document.addEventListener('change', function (e) {
  if (e.target && e.target.id === 'import-file' && e.target.files.length) {
    uploadImportPages(e.target.files);
  }
});

document.addEventListener('click', function (e) {
  var nav = e.target.closest('.nav__link');
  if (nav) { location.hash = '#/' + nav.getAttribute('data-route'); return; }

  var draftRow = e.target.closest('.draft-row[data-draft]');
  if (draftRow) {
    location.hash = '#/import/' + draftRow.getAttribute('data-draft');
    return;
  }
  if (e.target.id === 'draft-commit') { commitDraft(); return; }
  if (e.target.id === 'draft-discard') {
    api('/api/recipes/import/drafts/' + CURRENT_DRAFT._id, { method: 'DELETE' })
      .then(function () { location.hash = '#/import'; });
    return;
  }

  var fbBtn = e.target.closest('.fb-submit');
  if (fbBtn) { submitFeedback(fbBtn); return; }

  var mini = e.target.closest('.mini[data-act]');
  if (mini) {
    var li = mini.closest('.need');
    if (li) applyPantryGesture(li, mini.getAttribute('data-act'));
    return;
  }

  var sessionExpand = e.target.closest('.session-card__expand');
  if (sessionExpand) {
    var sessionCard = sessionExpand.closest('.session-card');
    if (sessionCard) expandSession(sessionCard);
    return;
  }

  var storePill = e.target.closest('.store-pill');
  if (storePill) {
    var sid = storePill.getAttribute('data-store');
    if (sid && sid !== state.driveStore) {
      state.driveStore = sid;
      state.driveMappings = null;
      state.driveExpanded = null;
      state.driveSearchResults = null;
      viewDrive();
    }
    return;
  }

  var swapBtn = e.target.closest('[data-swap]');
  if (swapBtn) {
    _driveSwap(parseInt(swapBtn.getAttribute('data-swap'), 10));
    return;
  }

  var pickBtn = e.target.closest('[data-pick]');
  if (pickBtn) {
    var parts2 = pickBtn.getAttribute('data-pick').split('-');
    _drivePick(parseInt(parts2[0], 10), parseInt(parts2[1], 10));
    return;
  }

  var spickBtn = e.target.closest('[data-search-pick]');
  if (spickBtn) {
    var sp = spickBtn.getAttribute('data-search-pick').split('-');
    _driveSearchPick(parseInt(sp[0], 10), parseInt(sp[1], 10));
    return;
  }

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

document.addEventListener('keyup', function (e) {
  var input = e.target.closest('.drive-search__input');
  if (input) _driveSearchKeyup(input);
});

var THEME_KEY = 'cm2-theme';
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem(THEME_KEY, t); } catch (e) { ignoreSecondaryFailure(e); }
}
document.getElementById('theme-toggle').addEventListener('click', function () {
  var cur = document.documentElement.getAttribute('data-theme');
  applyTheme(cur === 'dark' ? 'light' : 'dark');
});
try {
  var saved = localStorage.getItem(THEME_KEY);
  applyTheme(saved || 'light');
} catch (e) { applyTheme('light'); }

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
    // eslint-disable-next-line compat/compat
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

function currentRecipeSlug() {
  var h = location.hash.replace(/^#\/?/, '');
  var parts = h.split('/');
  if (parts[0] === 'recette' && parts[1]) return decodeURIComponent(parts[1]);
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

  if (action === 'pantry_bulk_update') {
    var items = intent.items;
    if (items && items.length) {
      showBulkConfirm(items);
    }
    return;
  }

  if (action === 'product_blacklist') {
    api('/shopping/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product: intent.product, reason: intent.reason || null })
    }).then(function () {
      showMicPanel('success', 'Produit blacklisté : ' + (intent.product || ''), intent);
    }).catch(function () {
      showMicPanel('error', 'Erreur lors du blacklist', null);
    });
    return;
  }

  if (action === 'recipe_note') {
    var noteSlug = currentRecipeSlug();
    if (!noteSlug) {
      showMicPanel('error', 'Ouvrez une recette pour ajouter une note', null);
      return;
    }
    api('/recipes/' + encodeURIComponent(noteSlug) + '/note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: intent.note })
    }).then(function () {
      showMicPanel('success', 'Note ajoutée', intent);
    }).catch(function () {
      showMicPanel('error', 'Erreur lors de l\'ajout de la note', null);
    });
    return;
  }

  if (action === 'recipe_edit_step') {
    var stepSlug = currentRecipeSlug();
    if (!stepSlug) {
      showMicPanel('error', 'Ouvrez une recette pour modifier une étape', null);
      return;
    }
    api('/recipes/' + encodeURIComponent(stepSlug) + '/steps/' + (intent.step || 1), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: intent.modification })
    }).then(function () {
      showMicPanel('success', 'Étape ' + (intent.step || 1) + ' modifiée', intent);
      viewRecipe(stepSlug);
    }).catch(function () {
      showMicPanel('error', 'Erreur lors de la modification', null);
    });
    return;
  }

  if (action === 'meal_feedback') {
    api('/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dish: intent.dish,
        convive: intent.convive || null,
        liked: intent.liked !== false,
        comment: intent.comment || null
      })
    }).then(function (res) {
      if (res.ok) {
        showMicPanel('success', 'Retour enregistré pour ' + (intent.dish || ''), intent);
      } else {
        showMicPanel('error', res.reason || 'Recette introuvable', null);
      }
    }).catch(function () {
      showMicPanel('error', 'Erreur lors de l\'enregistrement', null);
    });
    return;
  }

  if (action === 'product_remark') {
    api('/product-remarks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_ref: intent.product || null,
        quality: intent.quality || 'correct',
        channel: intent.channel || null,
        aspect: intent.aspect || 'general',
        verbatim: intent.comment || t,
        person: intent.person || null
      })
    }).then(function () {
      showMicPanel('success', 'Retour produit enregistré', intent);
    }).catch(function (e) {
      showMicPanel('error', 'Erreur : ' + apiErrorText(e), null);
    });
    return;
  }

  if (action === 'cooking_tip') {
    var tipSlug = intent.recipe_slug || currentRecipeSlug();
    if (!tipSlug) {
      showMicPanel('error', 'Ouvrez une recette pour ajouter une astuce', null);
      return;
    }
    api('/recipes/' + encodeURIComponent(tipSlug) + '/tips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: intent.kind || 'general',
        step_number: intent.step || null,
        verbatim: intent.tip || t
      })
    }).then(function () {
      showMicPanel('success', 'Astuce enregistrée', intent);
      paintRecipeExtras(tipSlug);
    }).catch(function (e) {
      showMicPanel('error', 'Erreur : ' + apiErrorText(e), null);
    });
    return;
  }

  if (action === 'substitution_discovery') {
    var subSlug = intent.recipe_slug || currentRecipeSlug();
    if (!subSlug) {
      showMicPanel('error', 'Ouvrez une recette pour noter une substitution', null);
      return;
    }
    api('/recipes/' + encodeURIComponent(subSlug) + '/substitutions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        original_ingredient: intent.original || '',
        substitute_ingredient: intent.substitute || '',
        outcome: intent.outcome || 'acceptable',
        who_preferred: intent.who || null,
        verbatim: intent.comment || null
      })
    }).then(function () {
      showMicPanel('success', 'Substitution notée', intent);
      paintRecipeExtras(subSlug);
    }).catch(function (e) {
      showMicPanel('error', 'Erreur : ' + apiErrorText(e), null);
    });
    return;
  }

  if (action === 'service_context') {
    var ctxSlug = intent.recipe_slug || currentRecipeSlug();
    if (!ctxSlug) {
      showMicPanel('error', 'Ouvrez une recette pour ajouter un contexte', null);
      return;
    }
    api('/recipes/' + encodeURIComponent(ctxSlug) + '/service-contexts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context: intent.context || 'everyday',
        verbatim: intent.verbatim || t
      })
    }).then(function () {
      showMicPanel('success', 'Contexte enregistré', intent);
      paintRecipeExtras(ctxSlug);
    }).catch(function (e) {
      showMicPanel('error', 'Erreur : ' + apiErrorText(e), null);
    });
    return;
  }

  if (action === 'pantry_leftover') {
    api('/pantry/leftover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ingredient: intent.ingredient,
        quantity: intent.quantity || null,
        shelf_life_days: intent.shelf_life_days || null
      })
    }).then(function () {
      showMicPanel('success', 'Reste enregistré : ' + (intent.ingredient || ''), intent);
    }).catch(function () {
      showMicPanel('error', 'Erreur lors de l\'enregistrement', null);
    });
    return;
  }
}

function showBulkConfirm(items) {
  var existing = document.getElementById('bulk-confirm');
  if (existing) existing.parentNode.removeChild(existing);

  var overlay = document.createElement('div');
  overlay.id = 'bulk-confirm';
  overlay.className = 'bulk-overlay';

  var html = '<div class="bulk-panel">' +
    '<div class="bulk-panel__head">' +
      '<span class="bulk-panel__title">Inventaire vocal</span>' +
      '<span class="bulk-panel__count">' + items.length + ' produit' + (items.length > 1 ? 's' : '') + '</span>' +
    '</div>' +
    '<ul class="bulk-list">';

  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    html += '<li class="bulk-item" data-idx="' + i + '">' +
      '<span class="bulk-item__name">' + esc(it.name) + '</span>' +
      (it.qty_text ? '<span class="bulk-item__qty">' + esc(it.qty_text) + '</span>' : '') +
      '<span class="bulk-item__section">' + esc(it.section) + '</span>' +
      '<button class="bulk-item__rm" data-idx="' + i + '" aria-label="Retirer">✕</button>' +
    '</li>';
  }

  html += '</ul>' +
    '<div class="bulk-panel__actions">' +
      '<button class="bulk-btn bulk-btn--cancel">Annuler</button>' +
      '<button class="bulk-btn bulk-btn--ok">Valider</button>' +
    '</div>' +
  '</div>';

  overlay.innerHTML = html;
  document.body.appendChild(overlay);

  var _items = items.slice();

  overlay.querySelector('.bulk-btn--cancel').addEventListener('click', function () {
    overlay.parentNode.removeChild(overlay);
  });

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) overlay.parentNode.removeChild(overlay);
  });

  overlay.addEventListener('click', function (e) {
    var rm = e.target.closest && e.target.closest('.bulk-item__rm');
    if (!rm) {
      if (e.target.className === 'bulk-item__rm' || (e.target.getAttribute && e.target.getAttribute('class') === 'bulk-item__rm')) {
        rm = e.target;
      }
    }
    if (!rm) return;
    var idx = parseInt(rm.getAttribute('data-idx'), 10);
    var li = overlay.querySelector('.bulk-item[data-idx="' + idx + '"]');
    if (li) li.parentNode.removeChild(li);
    _items[idx] = null;
    var remaining = _items.filter(function (x) { return x !== null; });
    var countEl = overlay.querySelector('.bulk-panel__count');
    if (countEl) countEl.textContent = remaining.length + ' produit' + (remaining.length > 1 ? 's' : '');
  });

  overlay.querySelector('.bulk-btn--ok').addEventListener('click', function () {
    var toSend = _items.filter(function (x) { return x !== null; });
    if (!toSend.length) {
      overlay.parentNode.removeChild(overlay);
      return;
    }
    var btn = overlay.querySelector('.bulk-btn--ok');
    btn.textContent = 'Envoi…';
    btn.disabled = true;

    fetch(API + '/pantry/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(toSend)
    })
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + '');
      return r.json();
    })
    .then(function (data) {
      overlay.parentNode.removeChild(overlay);
      var msg = data.created + ' ajouté' + (data.created > 1 ? 's' : '') +
                ', ' + data.updated + ' mis à jour';
      showMicPanel('success', msg, { action: 'pantry_bulk_update' });
      if (window.location.hash === '#/garde-manger') route();
    })
    .catch(function (e) {
      btn.textContent = 'Erreur';
      setTimeout(function () {
        btn.textContent = 'Valider';
        btn.disabled = false;
      }, 2000);
    });
  });
}

var ACTION_LABELS = {
  search_recipe: 'Rechercher',
  adjust_servings: 'Portions',
  product_blacklist: 'Exclure produit',
  product_remark: 'Retour produit',
  cooking_tip: 'Astuce',
  substitution_discovery: 'Substitution',
  service_context: 'Contexte',
  recipe_note: 'Note recette',
  recipe_edit_step: 'Modifier étape',
  meal_feedback: 'Avis repas',
  pantry_leftover: 'Reste',
  swap_recipe: 'Changer recette',
  pantry_bulk_update: 'Inventaire',
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
  if (intent.items && intent.items.length) parts.push(intent.items.length + ' produits');
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
