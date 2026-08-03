"""CLI: cooking-manager build|serve"""

import argparse
import sys
from pathlib import Path

from .build import build


def main():
    parser = argparse.ArgumentParser(prog="cooking-manager", description="Cooking Manager CLI")
    sub = parser.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Compile vault → cuisine.json")
    b.add_argument("--vault", type=Path, required=True, help="Path to Cuisine/ vault folder")
    b.add_argument("--output", type=Path, default=Path("cuisine.json"), help="Output path")

    s = sub.add_parser("serve", help="Run the web server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8795)

    args = parser.parse_args()

    if args.command == "build":
        artifact = build(args.vault, args.output)
        n_recipes = artifact["counts"]["recipes"]
        n_menus = artifact["counts"]["menus"]
        n_warnings = len(artifact.get("warnings", []))
        print(f"cuisine.json written: {n_recipes} recipes, {n_menus} menus, {n_warnings} warnings")
        if artifact.get("warnings"):
            for w in artifact["warnings"]:
                print(f"  ⚠ {w}")

    elif args.command == "serve":
        import uvicorn
        uvicorn.run("backend.app:app", host=args.host, port=args.port)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
