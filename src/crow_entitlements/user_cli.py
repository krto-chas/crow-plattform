from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from .auth import UserRecord, hash_password, write_user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or replace a Crow Platform user")
    parser.add_argument("username")
    parser.add_argument("--customer", required=True)
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--config-root", type=Path, default=Path(".crow-workbench/config"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match")
    salt, digest = hash_password(password)
    user = UserRecord(
        username=args.username.strip().lower(),
        customer_id=args.customer.strip().lower(),
        roles=tuple(sorted(set(args.role))),
        password_salt=salt,
        password_hash=digest,
    )
    path = write_user(args.config_root, user, overwrite=args.replace)
    print(path)


if __name__ == "__main__":
    main()
