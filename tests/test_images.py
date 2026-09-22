"""Garde-fous sur la génération d'images — partie déterministe, sans réseau."""

import io

from PIL import Image

from backend import images


def test_prompt_carries_the_framing_that_makes_the_grid_hold():
    prompt = images.build_prompt("Mafé au poulet")
    assert "REMPLIT 90 % du cadre" in prompt
    assert "Fond uni beige très clair" in prompt
    assert "Avoid:" in prompt
    assert "watermark" in prompt


def test_prompt_names_the_dish_and_its_visible_ingredients():
    prompt = images.build_prompt("Poke bowl", ["saumon", "riz", "avocat"])
    assert "Poke bowl" in prompt
    assert "saumon, riz, avocat" in prompt


def test_prompt_caps_ingredients_so_the_dish_stays_the_subject():
    prompt = images.build_prompt("Salade", ["a", "b", "c", "d", "e", "f", "g"])
    assert "f" not in prompt.split("(")[1].split(")")[0]


def test_empty_ingredients_do_not_leave_dangling_parentheses():
    assert images.build_prompt("Crêpes", ["", "  "]) == images.build_prompt("Crêpes")


def test_output_is_jpeg_because_binding_only_scans_that_extension():
    src = io.BytesIO()
    Image.new("RGBA", (32, 18), (200, 180, 150, 255)).save(src, format="PNG")

    out = images._to_jpeg(src.getvalue())

    assert Image.open(io.BytesIO(out)).format == "JPEG"
    assert Image.open(io.BytesIO(out)).mode == "RGB"


def test_write_uses_the_slug_as_filename(tmp_path):
    path = images.write("mafe-poulet", b"\xff\xd8\xff", media_root=tmp_path)
    assert path.name == "mafe-poulet.jpg"
    assert path.read_bytes() == b"\xff\xd8\xff"


def test_missing_image_in_response_is_an_error_not_an_empty_success():
    """Un 200 sans image signale un blocage de sécurité, pas une réussite."""
    try:
        images._extract_image({"candidates": [{"content": {"parts": [{"text": "nope"}]}}]})
    except images.ImageGenerationError as exc:
        assert "no image" in str(exc)
    else:
        raise AssertionError("expected ImageGenerationError")


def test_extract_accepts_both_camel_and_snake_case_payloads():
    payload = {"candidates": [{"content": {"parts": [{"inline_data": {"data": "aGk="}}]}}]}
    assert images._extract_image(payload) == b"hi"
