BEGIN;

CREATE TEMP TABLE part_migration (slug TEXT, position INT, replaces INT, person TEXT) ON COMMIT DROP;

INSERT INTO part_migration VALUES
    ('boulettes-boeuf-tomate-riz-complet-courgettes', 2, 1, 'Clémence'),
    ('chili-con-carne-facile',                       5, 4, 'Clémence'),
    ('mafe-poulet',                                  2, 1, 'Clémence'),
    ('pilons-poulet-paprika-citron-patates-douces',  2, 1, 'Clémence'),
    ('poulet-roti-citron-herbes-quinoa-legumes',     2, 1, 'Clémence'),
    ('risotto-champignons-poivrons-poulet-fermier',  2, 1, 'Clémence'),
    ('salade-vietnamienne',                          3, NULL, 'Léa');

DO $check$
DECLARE missing INT;
BEGIN
  SELECT count(*) INTO missing
    FROM part_migration m
    LEFT JOIN recipe r ON r.slug = m.slug
    LEFT JOIN recipe_ingredient ri ON ri.recipe_id = r.id AND ri.position = m.position
   WHERE ri.id IS NULL;
  IF missing > 0 THEN
    RAISE EXCEPTION '% ligne(s) de la migration ne visent aucun ingredient reel', missing;
  END IF;
  SELECT count(*) INTO missing FROM part_migration m
   WHERE NOT EXISTS (SELECT 1 FROM person p WHERE p.name = m.person);
  IF missing > 0 THEN
    RAISE EXCEPTION '% convive(s) de la migration absent(s) de person', missing;
  END IF;
END
$check$;

UPDATE recipe_ingredient ri
   SET for_person_id     = p.id,
       replaces_position = m.replaces,
       raw  = regexp_replace(ri.raw,  '\s*\((?:servi à |)part[^)]*\)|\s*\(surgelé, pour [^)]*\)', '', 'gi'),
       name = regexp_replace(ri.name, '\s*\((?:servi à |)part[^)]*\)|\s*\(surgelé, pour [^)]*\)', '', 'gi')
  FROM part_migration m
  JOIN recipe r ON r.slug = m.slug
  JOIN person p ON p.name = m.person
 WHERE ri.recipe_id = r.id AND ri.position = m.position;

UPDATE recipe_ingredient ri SET name_normalized = v.norm
  FROM (VALUES
    ('boulettes-boeuf-tomate-riz-complet-courgettes', 2, 'pois chiche cuit'),
    ('chili-con-carne-facile',                        5, 'haricot rouge egoutte'),
    ('mafe-poulet',                                   2, 'crevette decortiquee'),
    ('pilons-poulet-paprika-citron-patates-douces',   2, 'pois chiche cuit'),
    ('poulet-roti-citron-herbes-quinoa-legumes',      2, 'pave de saumon'),
    ('risotto-champignons-poivrons-poulet-fermier',   2, 'crevette decortiquee'),
    ('salade-vietnamienne',                           3, 'concombre')
  ) AS v(slug, position, norm)
  JOIN recipe r ON r.slug = v.slug
 WHERE ri.recipe_id = r.id AND ri.position = v.position;

SELECT r.slug, ri.position, ri.for_person_id, ri.replaces_position,
       ri.name, ri.name_normalized, ri.raw
  FROM recipe_ingredient ri JOIN recipe r ON r.id = ri.recipe_id
 WHERE ri.for_person_id IS NOT NULL
 ORDER BY r.slug;

COMMIT;
