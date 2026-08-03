"""Entry point: uvicorn runner."""

import uvicorn
from .config import HOST, PORT


def main():
    uvicorn.run("backend.app:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
