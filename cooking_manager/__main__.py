"""CLI: cooking-manager serve"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="cooking-manager", description="Cooking Manager CLI")
    sub = parser.add_subparsers(dest="command")

    s = sub.add_parser("serve", help="Run the web server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8795)

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn
        uvicorn.run("backend.app:app", host=args.host, port=args.port)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
