import sys
import os
from cryptography.fernet import Fernet


def generate_key():
    key = Fernet.generate_key()
    print(f"Generated Key (Save this as MASTER_KEY in .env):")
    print(key.decode())


def encrypt(value, key):
    f = Fernet(key.encode())
    encrypted = f.encrypt(value.encode())
    print(f"Encrypted value:")
    print(encrypted.decode())


def decrypt(value, key):
    f = Fernet(key.encode())
    decrypted = f.decrypt(value.encode())
    print(f"Decrypted value:")
    print(decrypted.decode())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python manage_secrets.py [generate_key|encrypt|decrypt] [value] [key]"
        )
        sys.exit(1)

    command = sys.argv[1]

    if command == "generate_key":
        generate_key()
    elif command == "encrypt":
        if len(sys.argv) < 4:
            print("Usage: encrypt <value> <key>")
            sys.exit(1)
        encrypt(sys.argv[2], sys.argv[3])
    elif command == "decrypt":
        if len(sys.argv) < 4:
            print("Usage: decrypt <value> <key>")
            sys.exit(1)
        decrypt(sys.argv[2], sys.argv[3])
