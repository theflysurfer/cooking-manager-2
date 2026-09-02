# Corpus web — ce que vaut vraiment l'extraction JSON-LD

> Gisement (b) du handoff : 34 URLs de recettes passées à `fetch_structured_recipe()`
> (deep-research#49, ADR 0020), plus 2 pages de liste en contrôle négatif.
> **Mesuré le 2026-09-02.** Reproductible : `python scripts/measure_recipe_jsonld.py`
> (exige le repo `deep-research` en local, chemin en tête du script).
>
> Le corpus du vault (`CORPUS_ACCOMMODATIONS.md`) mesure la **pratique du foyer**.
> Celui-ci sert à autre chose : éprouver le moteur sur des recettes **hostiles** —
> carnées, rédigées par d'autres, non adaptées.

## Ce que #49 rend — présence et complétude

**Présence du JSON-LD `schema.org/Recipe` : 34/34.** Aucun échec d'extraction sur les
quatre sites. Le repli navigateur fonctionne et il est nécessaire.

| Champ | Rendu | Détail |
|---|---|---|
| ingrédients | 34/34 | mais voir « quantités » ci-dessous |
| portions | 34/34 | |
| **étapes** | **25/34** | les 9 manquantes sont **toutes** de papillesetpupilles.fr |
| temps total | 25/34 | même partage |
| nutrition | 4/34 | Ricardo uniquement |

| Site | n | méthode | étapes | temps | nutrition |
|---|---|---|---|---|---|
| 750g.com | 18 | `jsonld` (HTML) | 18 | 18 | 0 |
| ricardocuisine.com | 5 | `jsonld` (HTML) | 5 | 5 | 4 |
| hervecuisine.com | 2 | `jsonld` (HTML) | 2 | 2 | 0 |
| papillesetpupilles.fr | 9 | **`jsonld_via_hydra`** | **0** | **0** | 0 |

## Trois constats qui changent l'usage qu'on peut en faire

### 1. `ok=True` ne veut pas dire « recette utilisable »

Les 9 recettes de papillesetpupilles sont extraites **avec succès** et sont
**inexploitables** : le JSON-LD rendu ne porte que des noms d'ingrédients nus — « Ail »,
« Citron », « Coulis de tomates » — sans quantité, et **aucune étape**.

Sans quantités : ni courses ni macros. Sans étapes : pas de détection de contexte, donc
pas de substitution. Ce n'est pas un défaut du parseur — vérifié, le site publie un
JSON-LD SEO dégradé.

⚠️ **C'est exactement la famille de panne que ce projet traque** : un booléen `ok` qui se
lit comme un succès alors que la donnée manque. Un consommateur de `fetch_structured_recipe()`
doit trancher sur `n_steps` et sur la présence de quantités, jamais sur `ok`.

### 2. Le repli Hydra est ce qui sauve un site sur quatre

papillesetpupilles ne publie **aucun** bloc `ld+json` dans son HTML — vérifié par GET
direct : 0 bloc. Le JSON-LD n'existe qu'après rendu JS. Sans le repli navigateur, ce site
rendrait 0/9 au lieu de 9/9 (fussent-elles partielles). Le repli n'est pas un confort.

### 3. Une page de liste peut se déclarer `Recipe` — 1 contrôle négatif sur 2 est passé

`750g.com/recettes-salades/composees/lentilles/` est une page de **catégorie**. Elle rend
un objet Recipe intitulé « Salades maison de lentilles », avec 14 ingrédients et 15 étapes
— agrégés de plusieurs recettes.

`fetch_structured_recipe()` ne peut pas distinguer une recette d'une page de liste : le
site ment dans son balisage. Une ingestion automatique depuis une URL de recherche
avalerait ces objets composites sans un signal. **À remonter à deep-research#49.**

## Ce que le corpus a révélé du moteur de substitutions

25 recettes exploitables : **21 déjà pescétariennes**, 4 carnées. Les carnées sont le vrai
test, et elles ont trouvé deux défauts qu'aucune recette du vault ne pouvait montrer.

### Défaut 1 — une règle de cuisine débordait sur les autres · CORRIGÉ

`score_rule()` ajoutait un bonus quand la cuisine d'une règle matchait, mais **ne
pénalisait pas** le cas contraire : la priorité de base décidait seule. La règle
ouest-africaine ajoutée ce jour (priorité 97) s'appliquait donc à **tout** mijoté de
poulet — rendant sur un « Poulet en cocotte au vin blanc » la raison visible
« *Le mafé du foyer se fait déjà au cabillaud* ».

Corrigé par `rule_applies()` : une règle qui **déclare** des cuisines ne vaut que dans
ces cuisines, dès lors que le plat en nomme une. Une règle sans cuisine déclarée reste le
filet, et un plat sans cuisine détectée ne perd aucune règle.

### Défaut 2 — « faire revenir » fait gagner la mauvaise règle · NON CORRIGÉ

« Cocotte de poulet mijoté de ma grand-mère » rend **dorade**, « poisson méditerranéen
classique ». Le décompte :

| Règle | priorité | bonus cuisine | bonus cuisson | total |
|---|---|---|---|---|
| dorade *(grilled, oven, **pan-fried**)* | 90 | +20 | **+40** | **150** |
| lotte *(**stew**, slow-cooked)* | 95 | +0 | +40 | 135 |

Le contexte détecte `('stew', 'slow-cooked', 'pan-fried')` : `pan-fried` vient de
« **faites revenir** les morceaux de poulet », l'étape de saisie que porte **tout** mijoté.
Une dorade grillée gagne donc sur une lotte mijotée, dans une cocotte.

C'est le même défaut structurel que « l'étape de garniture pilote le plat », corrigé côté
accommodation : **une étape préparatoire n'est pas le mode de cuisson du plat.** La parade
demande de hiérarchiser les modes — une saisie suivie d'une cuisson longue est un mijoté,
pas un poêlé — ce qui est une décision de conception, pas un réglage de priorité.

### Manque de lexique constaté

`canard` (« Salade de lentilles aux crevettes », qui contient du magret) n'est **aucune**
`source` de règle : la recette ressort sans réparation possible, sans que rien ne le dise.

## Filtrage selon les profils — attention au faux positif

Le tri par `person.dislikes` est piégeux. Un premier passage signalait **15 recettes sur 25**
portant des « olives ». Après vérification : **1 seule** en porte vraiment
(« Poulet aux olives », 100 g d'olives noires). Les autres étaient de l'**huile** d'olive —
`olive oil` chez Ricardo, que l'exclusion française ne rattrapait pas.

Une aversion se cherche sur l'**ingrédient**, jamais sur une sous-chaîne du texte. Même
famille que « citron » qui matchait « citronnelle », et que « Julien » dans « julienne ».

## Ce que ce corpus ne dit pas

Quatre sites, tous francophones grand public ou québécois. Le taux de présence de 100 %
vaut **pour eux**, pas pour le web : les blogs personnels et les sites étrangers n'ont pas
été éprouvés. Élargir avant d'en tirer une règle générale.
