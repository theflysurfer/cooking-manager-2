from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Ingredient:
    position: int
    raw: str
    name: str = ""
    quantity: float | None = None
    quantity_max: float | None = None
    unit: str | None = None
    is_optional: bool = False
    parsed: bool = False


@dataclass
class Step:
    position: int
    text: str


@dataclass
class Recipe:
    title: str | None = None
    description: str | None = None
    image: str | None = None
    site_name: str | None = None
    url: str | None = None
    category: str | None = None
    base_servings: int | None = None
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    source_tier: str = "unknown"

    @property
    def parse_rate(self) -> float:
        if not self.ingredients:
            return 1.0
        return sum(1 for i in self.ingredients if i.parsed) / len(self.ingredients)
