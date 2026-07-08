import argparse

from pwdlib import PasswordHash


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Argon2 password hash for staff_users.password_hash.")
    parser.add_argument("password", help="Plain text password to hash")
    args = parser.parse_args()

    print(PasswordHash.recommended().hash(args.password))


if __name__ == "__main__":
    main()
