from cooking_manager.bans import find_ban, load_bans, recurrent_products

ROWS = [
    {"pref_type": "blacklist", "key": "C1195603",
     "value": "Pilons de poulet blanc france 1kg (PRIX BAS)",
     "reason": "Julien refuse le poulet bas de gamme", "active": True},
    {"pref_type": "blacklist", "key": "Pavés de saumon d'Atlantique sans peau et sans arêtes",
     "value": "Pavés de saumon d'Atlantique", "reason": "texture/goût", "active": True},
    {"pref_type": "blacklist_brand", "key": "PRIX BAS", "value": "animal_protein",
     "reason": "gamme refusée sur la chair", "active": True},
    {"pref_type": "favorite", "key": "Feta grecque AOP", "value": "x", "reason": "",
     "active": True},
]

class TestLoadBans:
    def test_ignores_other_pref_types(self):
        assert len(load_bans(ROWS)) == 3

    def test_brand_scope_comes_from_value(self):
        brand = [b for b in load_bans(ROWS) if b.kind == "brand"][0]
        assert brand.scope == "animal_protein"

    def test_inactive_row_is_dropped(self):
        rows = [dict(ROWS[0], active=False)]
        assert load_bans(rows) == []

class TestFindBan:
    def setup_method(self):
        self.bans = load_bans(ROWS)

    def test_exact_auchan_id(self):
        ban = find_ban("Pilons de poulet blanc france 1kg", self.bans,
                       auchan_id="C1195603")
        assert ban is not None and ban.kind == "product"

    def test_name_substring_without_id(self):
        ban = find_ban("Pavés de saumon d'Atlantique sans peau et sans arêtes 4pc",
                       self.bans)
        assert ban is not None and ban.kind == "product"

    def test_brand_ban_catches_a_different_id(self):
        ban = find_ban("Cuisses de poulet france 2kg", self.bans,
                       auchan_id="C9999999", brand="PRIX BAS")
        assert ban is not None and ban.kind == "brand"

    def test_brand_ban_spares_non_animal(self):
        assert find_ban("Papier toilette 12 rouleaux", self.bans,
                        auchan_id="C42", brand="PRIX BAS") is None
        assert find_ban("Pulpe de tomates concassées 400g", self.bans,
                        brand="PRIX BAS") is None

    def test_brand_read_from_the_label_when_brand_field_is_empty(self):
        ban = find_ban("Pilons de poulet blanc france 1kg (PRIX BAS)", self.bans,
                       auchan_id="C7777777")
        assert ban is not None and ban.kind == "brand"

    def test_clean_product_passes(self):
        assert find_ban("Poulet fermier label rouge 1,3kg (LOUÉ)", self.bans,
                        auchan_id="C1234567", brand="LOUÉ") is None

    def test_no_bans_means_no_violation(self):
        assert find_ban("Pilons de poulet (PRIX BAS)", [], auchan_id="C1195603") is None

RECURRENT_ROWS = [
    {"pref_type": "recurrent", "key": "fromage blanc",
     "value": "CALIN Extra - Fromage blanc nature 3,2% MG 850g",
     "reason": "5/7 commandes, dernière 2026-09-08", "active": True},
    {"pref_type": "recurrent", "key": "lait",
     "value": "Lait entier UHT 6x1L", "reason": "3/7 commandes", "active": True},
    {"pref_type": "blacklist", "key": "x", "value": "y", "reason": "", "active": True},
]

class TestRecurrentProducts:
    def test_ignores_other_pref_types(self):
        assert len(recurrent_products(RECURRENT_ROWS, set())) == 2

    def test_inactive_row_is_dropped(self):
        rows = [dict(RECURRENT_ROWS[0], active=False)]
        assert recurrent_products(rows, set()) == []

    def test_a_product_the_menu_already_buys_is_hidden(self):
        out = recurrent_products(RECURRENT_ROWS, {"fromage blanc"})
        assert [r["name"] for r in out] == ["lait"]

    def test_a_longer_recipe_line_still_covers_it(self):
        out = recurrent_products(RECURRENT_ROWS, {"fromage blanc de campagne"})
        assert [r["name"] for r in out] == ["lait"]

    def test_a_substring_is_not_a_cover(self):
        out = recurrent_products(RECURRENT_ROWS, {"laitue"})
        assert "lait" in [r["name"] for r in out]
