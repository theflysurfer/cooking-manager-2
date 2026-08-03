"""CLI: python -m cooking_manager build [--vault PATH] [--output PATH]"""

import argparse
import sys
from pathlib import Path

from .build import build


def main():
    parser = argparse.ArgumentParser(prog="cooking-manager", description="Build cuisine.json from vault")
    sub = parser.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Compile vault → cuisine.json")
    b.add_argument("--vault", type=Path, required=True, help="Path to Cuisine/ vault folder")
    b.add_argument("--output", type=Path, default=Path("cuisine.json"), help="Output path (default: cuisine.json)")

    args = parser.parse_args()
    if args.command != "build":
        parser.print_help()
        sys.exit(1)

    artifact = build(args.vault, args.output)

    n_recipes = artifact["counts"]["recipes"]
    n_menus = artifact["counts"]["menus"]
    n_warnings = len(artifact.get("warnings", []))
    print(f"cuisine.json written: {n_recipes} recipes, {n_menus} menus, {n_warnings} warnings")

    if artifact.get("warnings"):
        for w in artifact["warnings"]:
            print(f"  ⚠ {w}")


if __name__ == "__main__":
    main()
