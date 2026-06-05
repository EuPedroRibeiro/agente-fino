from __future__ import annotations

import sys
from pathlib import Path


REQUIRED_PATHS = (
    "vercel.json",
    "api/index.py",
    "app/application.py",
    "requirements.txt",
    "README_DEPLOY.md",
)


def validate_project_root(root: Path) -> list[str]:
    return [relative for relative in REQUIRED_PATHS if not (root / relative).exists()]


def main() -> int:
    root = Path.cwd().resolve()
    missing = validate_project_root(root)
    if missing:
        print(f"PROJECT_ROOT_INVALID: {root}")
        for relative in missing:
            print(f"  missing: {relative}")
        print("Execute este script na pasta que contem vercel.json.")
        return 1
    print(f"PROJECT_ROOT_OK: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
