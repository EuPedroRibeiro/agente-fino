from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.auth import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera hash PBKDF2 para AGENTE_FINO_ADMIN_PASSWORD_HASH.")
    parser.add_argument("password", nargs="?", help="Senha admin. Se omitida, pede de forma interativa.")
    args = parser.parse_args()
    password = args.password or getpass.getpass("Senha admin: ")
    print(hash_password(password))


if __name__ == "__main__":
    main()
