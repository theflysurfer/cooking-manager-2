from cooking_manager.packaging import Pack, split_packaging


class TestCount:
    def test_x_suffix_leaves_the_name_clean(self):
        name, pack = split_packaging("Auchan Bio Plein Air Oeufs x12")
        assert name == "Auchan Bio Plein Air Oeufs"
        assert pack.count == 12

    def test_uppercase_x_too(self):
        assert split_packaging("Oeufs plein air X10")[1].count == 10

    def test_leading_count(self):
        name, pack = split_packaging("2 boîtes de thon listao")
        assert pack.count == 2
        assert name == "thon listao"


class TestSize:
    def test_weight_in_the_name(self):
        name, pack = split_packaging("Comté Juraflore AOP 250 g")
        assert name == "Comté Juraflore AOP"
        assert (pack.size_value, pack.size_unit) == (250.0, "g")

    def test_pack_of_size(self):
        name, pack = split_packaging("Poêlée méditerranéenne sachet 750 g")
        assert name == "Poêlée méditerranéenne"
        assert (pack.count, pack.size_value, pack.size_unit) == (1.0, 750.0, "g")

    def test_volume(self):
        assert split_packaging("Lait de coco 400 ml")[1].size_unit == "ml"


class TestLeaveAlone:
    def test_a_number_that_belongs_to_the_food(self):
        """« 5 baies » et « 4 fromages » nomment l'aliment, pas son emballage."""
        name, pack = split_packaging("Poivre 5 baies")
        assert name == "Poivre 5 baies"
        assert pack == Pack(None, None, None)

    def test_percentage_is_not_a_size(self):
        name, pack = split_packaging("Chocolat noir 70% cacao")
        assert name == "Chocolat noir 70% cacao"
        assert pack.size_value is None

    def test_plain_name_untouched(self):
        assert split_packaging("Comté") == ("Comté", Pack(None, None, None))
