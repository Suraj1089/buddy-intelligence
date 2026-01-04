#!/usr/bin/env python3
"""
CLI utility for managing encrypted secrets.
Usage:
    python manage_secrets.py generate-key
    python manage_secrets.py encrypt <value>
    python manage_secrets.py decrypt <value> [--key <key>]
"""

import sys
import os
import argparse
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load env vars to get MASTER_KEY if available
load_dotenv(".env")


def generate_key():
    """Generates a new valid Fernet key."""
    key = Fernet.generate_key()
    print(f"Generated MASTER_KEY: {key.decode()}")
    print("\nAdd this to your .env file as:")
    print(f"MASTER_KEY={key.decode()}")


def encrypt_value(value, key=None):
    """Encrypts a value using the provided key or env MASTER_KEY."""
    if not key:
        key = os.getenv("MASTER_KEY")

    if not key:
        print("Error: No MASTER_KEY found in environment or provided as argument.")
        sys.exit(1)

    try:
        f = Fernet(key.encode())
        encrypted = f.encrypt(value.encode())
        print(f"Encrypted value:\n{encrypted.decode()}")
    except Exception as e:
        print(f"Encryption failed: {e}")
        sys.exit(1)


def decrypt_value(value, key=None):
    """Decrypts a value using the provided key or env MASTER_KEY."""
    if not key:
        key = os.getenv("MASTER_KEY")

    if not key:
        print("Error: No MASTER_KEY found in environment or provided as argument.")
        sys.exit(1)

    try:
        f = Fernet(key.encode())
        decrypted = f.decrypt(value.encode())
        print(f"Decrypted value:\n{decrypted.decode()}")
    except Exception as e:
        print(f"Decryption failed: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage encrypted secrets")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate Key
    subparsers.add_parser("generate-key", help="Generate a new MASTER_KEY")

    # Encrypt
    encrypt_parser = subparsers.add_parser("encrypt", help="Encrypt a string")
    encrypt_parser.add_argument("value", help="Value to encrypt")
    encrypt_parser.add_argument("--key", help="MASTER_KEY to use (optional if in env)")

    # Decrypt
    decrypt_parser = subparsers.add_parser("decrypt", help="Decrypt a string")
    decrypt_parser.add_argument("value", help="Value to decrypt")
    decrypt_parser.add_argument("--key", help="MASTER_KEY to use (optional if in env)")

    # Encrypt File
    encrypt_file_parser = subparsers.add_parser(
        "encrypt-file", help="Encrypt a file content"
    )
    encrypt_file_parser.add_argument("filepath", help="Path to file to encrypt")
    encrypt_file_parser.add_argument("--key", help="MASTER_KEY to use")

    args = parser.parse_args()

    if args.command == "generate-key":
        generate_key()
    elif args.command == "encrypt":
        encrypt_value(args.value, args.key)
    elif args.command == "decrypt":
        decrypt_value(args.value, args.key)
    elif args.command == "encrypt-file":
        encrypt_file(args.filepath, args.key)
    else:
        parser.print_help()


def encrypt_file(filepath, key=None):
    """Encrypts the content of a file."""
    if not key:
        key = os.getenv("MASTER_KEY")

    if not key:
        print("Error: No MASTER_KEY found.")
        sys.exit(1)

    try:
        with open(filepath, "r") as f:
            content = f.read()

        f = Fernet(key.encode())
        encrypted = f.encrypt(content.encode())
        print(f"Encrypted content of {filepath}:\n{encrypted.decode()}")
    except Exception as e:
        print(f"Encryption failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
