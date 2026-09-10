"""Génère un lot de fiches aliments génériques (staples) dans le référentiel du vault.

Valeurs pour 100 g, standard ANSES Ciqual / étiquette. statut: partiel (à confirmer).
Un tuple = (dossier, slug, titre, kcal, P, G, L, source).
Ne réécrit jamais une fiche déjà présente.
"""

from pathlib import Path
import os

ROOT = Path(os.environ["FOOD"])

FICHES = [
    # dossier, slug, titre, kcal, P, G, L, source
    # --- matières grasses / oléagineux ---
    ("matieres-grasses", "beurre", "Beurre doux", 753, 0.7, 0.6, 83, "ANSES Ciqual — Beurre doux, 82% MG."),
    ("matieres-grasses", "huile-coco", "Huile de coco", 900, 0, 0, 100, "Étiquette — huile de coco vierge."),
    ("matieres-grasses", "huile-sesame", "Huile de sésame", 900, 0, 0, 100, "Étiquette — huile de sésame."),
    ("matieres-grasses", "huile-arachide", "Huile d'arachide", 900, 0, 0, 100, "Étiquette — huile d'arachide."),
    ("matieres-grasses", "huile-noix", "Huile de noix", 900, 0, 0, 100, "Étiquette — huile de noix."),
    ("matieres-grasses", "beurre-cacahuete", "Beurre de cacahuète", 600, 25, 12, 50, "Étiquette — beurre de cacahuète 100%."),
    ("matieres-grasses", "pate-arachide", "Pâte d'arachide", 600, 25, 12, 50, "Étiquette — pâte d'arachide 100%."),
    ("matieres-grasses", "cacahuete", "Cacahuète", 600, 26, 12, 49, "ANSES Ciqual — Arachide/cacahuète grillée."),
    ("matieres-grasses", "noisette", "Noisette", 650, 15, 7, 61, "ANSES Ciqual — Noisette."),
    ("matieres-grasses", "graine-courge", "Graines de courge", 560, 30, 10, 49, "ANSES Ciqual — Graines de courge."),
    ("matieres-grasses", "graine-sesame", "Graines de sésame", 570, 18, 12, 50, "ANSES Ciqual — Graines de sésame."),
    ("matieres-grasses", "graine-chia", "Graines de chia", 490, 17, 8, 31, "Étiquette — graines de chia (glucides nets)."),
    ("matieres-grasses", "tahini", "Tahini (purée de sésame)", 600, 17, 21, 54, "Étiquette — purée de sésame."),
    ("matieres-grasses", "puree-sesame", "Purée de sésame", 600, 17, 21, 54, "Étiquette — purée de sésame."),
    ("matieres-grasses", "olive-noire", "Olive noire", 294, 1.5, 1, 29, "ANSES Ciqual — Olive noire."),
    ("matieres-grasses", "olive-grecque", "Olive grecque (kalamata)", 270, 1.4, 1, 27, "Étiquette — olive kalamata."),
    ("matieres-grasses", "pignon-pin", "Pignon de pin", 673, 13.7, 4, 68.4, "ANSES Ciqual — Pignon de pin."),
    # --- œufs & laitages ---
    ("oeufs-laitages", "lait-entier", "Lait entier", 64, 3.2, 4.8, 3.6, "ANSES Ciqual — Lait entier UHT."),
    ("oeufs-laitages", "lait-demi-ecreme", "Lait demi-écrémé", 46, 3.3, 4.8, 1.5, "ANSES Ciqual — Lait demi-écrémé UHT."),
    ("oeufs-laitages", "creme-fraiche-epaisse", "Crème fraîche épaisse", 300, 2.4, 3, 30, "ANSES Ciqual — Crème fraîche 30% MG."),
    ("oeufs-laitages", "creme-fraiche", "Crème fraîche", 300, 2.4, 3, 30, "ANSES Ciqual — Crème fraîche 30% MG."),
    ("oeufs-laitages", "ricotta", "Ricotta", 146, 7, 3, 11, "Étiquette — ricotta."),
    ("oeufs-laitages", "cottage-cheese", "Cottage cheese", 98, 11, 3.4, 4.3, "Étiquette — cottage cheese."),
    ("oeufs-laitages", "fromage-frais", "Fromage frais nature", 160, 8, 4, 12, "Étiquette — fromage frais nature."),
    ("oeufs-laitages", "saint-moret", "Saint Moret", 215, 6.5, 3.5, 19, "Étiquette — Saint Moret."),
    ("oeufs-laitages", "fromage-rape", "Fromage râpé (emmental)", 370, 27, 1, 29, "ANSES Ciqual — Emmental râpé."),
    ("oeufs-laitages", "scamorza", "Scamorza fumée", 334, 25, 2, 25, "Étiquette — scamorza fumée."),
    # --- sucres, desserts, pâtisserie ---
    ("desserts-patisseries", "sucre-blanc", "Sucre blanc", 400, 0, 100, 0, "Étiquette — saccharose."),
    ("desserts-patisseries", "sucre-roux", "Sucre roux", 380, 0, 95, 0, "Étiquette — sucre roux/cassonade."),
    ("desserts-patisseries", "sucre-coco", "Sucre de coco", 380, 1, 92, 0, "Étiquette — sucre de fleur de coco."),
    ("desserts-patisseries", "miel", "Miel", 320, 0.4, 80, 0, "ANSES Ciqual — Miel."),
    ("desserts-patisseries", "chocolat-noir-patissier", "Chocolat noir pâtissier", 500, 6, 45, 32, "Étiquette — chocolat noir dessert ~52%."),
    ("desserts-patisseries", "chocolat-noir-70", "Chocolat noir 70%", 580, 9, 33, 42, "Étiquette — chocolat noir 70%."),
    ("desserts-patisseries", "pepite-chocolat-noir", "Pépites de chocolat noir", 480, 5, 55, 27, "Étiquette — pépites chocolat noir."),
    ("desserts-patisseries", "cacao", "Cacao non sucré", 350, 20, 15, 22, "ANSES Ciqual — Cacao poudre non sucré."),
    ("desserts-patisseries", "confiture", "Confiture", 250, 0.5, 60, 0, "Étiquette — confiture 60% fruits."),
    ("desserts-patisseries", "compote-sans-sucre", "Compote sans sucre ajouté", 50, 0.3, 12, 0.1, "Étiquette — compote pomme sans sucre ajouté."),
    ("desserts-patisseries", "chapelure", "Chapelure", 350, 12, 70, 3, "Étiquette — chapelure."),
    # --- féculents / légumineuses ---
    ("feculents-legumineuses", "farine", "Farine de blé", 364, 10, 74, 1, "ANSES Ciqual — Farine de blé T55."),
    ("feculents-legumineuses", "riz-basmati", "Riz basmati (cru)", 350, 7.5, 78, 0.6, "ANSES Ciqual — Riz basmati, cru."),
    ("feculents-legumineuses", "riz-sushi", "Riz à sushi (cru)", 355, 6.5, 79, 0.6, "Étiquette — riz rond à sushi, cru."),
    ("feculents-legumineuses", "riz-risotto", "Riz à risotto (arborio, cru)", 350, 7, 78, 0.9, "Étiquette — riz arborio, cru."),
    ("feculents-legumineuses", "couscous-perle", "Couscous perlé (cru)", 360, 12, 72, 1.5, "Étiquette — perles de couscous, cru."),
    ("feculents-legumineuses", "polenta", "Polenta (semoule de maïs, crue)", 355, 8.5, 73, 3.4, "Étiquette — polenta précuite, sèche."),
    ("feculents-legumineuses", "vermicelle-riz", "Vermicelles de riz (crus)", 360, 6, 84, 0.5, "Étiquette — vermicelles de riz, secs."),
    ("feculents-legumineuses", "feuille-lasagne", "Feuilles de lasagne (crues)", 360, 12, 72, 1.5, "Étiquette — pâtes à lasagne, sèches."),
    ("feculents-legumineuses", "tagliatelle", "Tagliatelles (crues)", 360, 12, 72, 1.5, "Étiquette — tagliatelles sèches."),
    ("feculents-legumineuses", "houmous", "Houmous", 300, 8, 15, 22, "ANSES Ciqual — Houmous."),
    # --- poissons ---
    ("poissons", "thon-naturel", "Thon au naturel (égoutté)", 116, 26, 0, 1, "Étiquette — thon listao au naturel, égoutté."),
    ("poissons", "cabillaud", "Cabillaud (filet cru)", 76, 18, 0, 0.7, "ANSES Ciqual — Cabillaud, cru."),
    ("poissons", "dorade-royale", "Dorade royale (crue)", 133, 20, 0, 6, "ANSES Ciqual — Dorade royale, crue."),
    # --- volailles / viandes ---
    ("volailles-viandes", "pilon-poulet", "Pilon de poulet (sans peau, cru)", 121, 19.7, 0, 4.7, "ANSES Ciqual — Cuisse/pilon de poulet, chair, cru."),
    ("volailles-viandes", "lardon-vegetarien", "Lardons végétariens", 130, 15, 5, 6, "Étiquette — lardons végétaux (soja)."),
    # --- légumes ---
    ("legumes", "champignon", "Champignon de Paris (cru)", 22, 3, 1, 0.3, "ANSES Ciqual — Champignon de Paris, cru."),
    ("legumes", "edamame", "Edamame (fèves de soja, cuites)", 120, 11, 9, 5, "ANSES Ciqual — Fèves de soja edamame."),
    ("legumes", "chou-rouge", "Chou rouge (cru)", 31, 1.4, 5, 0.2, "ANSES Ciqual — Chou rouge, cru."),
    # --- fruits ---
    ("fruits", "pomme", "Pomme (crue)", 54, 0.3, 12, 0.2, "ANSES Ciqual — Pomme, crue, pulpe et peau."),
    ("fruits", "mangue", "Mangue (crue)", 62, 0.7, 14, 0.4, "ANSES Ciqual — Mangue, crue."),
    ("fruits", "nectarine", "Nectarine (crue)", 44, 1.1, 8.9, 0.3, "ANSES Ciqual — Nectarine, crue."),
    ("fruits", "abricot", "Abricot", 48, 0.9, 9, 0.4, "ANSES Ciqual — Abricot."),
    ("fruits", "fruit-rouge", "Fruits rouges", 45, 1, 8, 0.4, "ANSES Ciqual — Fruits rouges mélangés."),
    # --- sauces & condiments ---
    ("sauces-condiments", "sauce-soja", "Sauce soja", 60, 8, 5, 0, "Étiquette — sauce soja salée."),
    ("sauces-condiments", "moutarde", "Moutarde", 150, 6, 6, 10, "ANSES Ciqual — Moutarde de Dijon."),
    ("sauces-condiments", "capre", "Câpres", 25, 2, 1, 0.9, "ANSES Ciqual — Câpres au vinaigre."),
    ("sauces-condiments", "cornichon", "Cornichon", 12, 0.7, 1.5, 0.2, "ANSES Ciqual — Cornichon au vinaigre."),
    ("sauces-condiments", "bouillon-legume", "Bouillon de légumes (reconstitué)", 4, 0.2, 0.5, 0.1, "Étiquette — bouillon cube dilué."),
    # --- suppléments ---
    ("supplements", "whey", "Whey (protéine en poudre)", 373, 80, 8, 6, "Étiquette — whey concentrée."),
    ("supplements", "whey-isolate", "Whey isolate", 373, 90, 1, 1.5, "Étiquette — whey isolate."),
]

TEMPLATE = """---
type: generique
categorie: {cat}
marque: null
statut: partiel
source: ANSES-Ciqual
date: 2026-09-11
---

# {title}

## Macros pour 100 g

| Nutriment | Valeur |
|---|---|
| Énergie | {kcal} kcal |
| Protéines | {p} g |
| Glucides | {g} g |
| Lipides | {l} g |

> Source : {src}
"""

def main() -> None:
    written, skipped = 0, 0
    for cat, slug, title, kcal, p, g, l, src in FICHES:
        path = ROOT / "generiques" / cat / f"{slug}.md"
        if path.exists():
            skipped += 1
            print(f"  skip (existe) : {cat}/{slug}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            TEMPLATE.format(cat=cat, title=title, kcal=kcal, p=p, g=g, l=l, src=src),
            encoding="utf-8",
        )
        written += 1
    print(f"\n{written} fiches écrites, {skipped} ignorées (déjà présentes).")

if __name__ == "__main__":
    main()
