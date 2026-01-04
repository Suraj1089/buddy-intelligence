#!/usr/bin/env python3
"""
One-time script to migrate all secrets from .env and firebase-config.json to dev-config.yml
"""
import os
import json
import yaml
from cryptography.fernet import Fernet
from dotenv import dotenv_values

# Load MASTER_KEY
os.chdir(os.path.dirname(os.path.abspath(__file__)))
env_values = dotenv_values("../.env")
MASTER_KEY = env_values.get("MASTER_KEY")

if not MASTER_KEY:
    print("ERROR: MASTER_KEY not found in .env")
    exit(1)

cipher = Fernet(MASTER_KEY.encode())

def encrypt(value: str) -> str:
    return cipher.encrypt(value.encode()).decode()

# Secrets to migrate from .env (sensitive values only)
SECRETS_TO_MIGRATE = [
    "POSTGRES_PASSWORD",
    "SECRET_KEY",
    "FIRST_SUPERUSER_PASSWORD",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_JWT_SECRET",
]

# Non-secret config (keep as plaintext in dev-config.yml)
CONFIG_TO_MIGRATE = [
    "POSTGRES_SERVER",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_DB",
    "PROJECT_NAME",
    "FRONTEND_HOST",
    "FIRST_SUPERUSER",
    "SUPABASE_URL",
    "REDIS_URL",
]

# Build the new config
new_config = {
    "environment": "local",
    "debug": True,
    "config": {},
    "secrets": {}
}

# Migrate non-secret config
for key in CONFIG_TO_MIGRATE:
    if key in env_values and env_values[key]:
        new_config["config"][key] = env_values[key]
        print(f"✓ Config: {key}")

# Migrate and encrypt secrets
for key in SECRETS_TO_MIGRATE:
    if key in env_values and env_values[key]:
        encrypted = encrypt(env_values[key])
        new_config["secrets"][key] = encrypted
        print(f"🔒 Secret: {key} -> encrypted")

# Encrypt firebase-config.json
firebase_path = "firebase-config.json"
if os.path.exists(firebase_path):
    with open(firebase_path, 'r') as f:
        firebase_json = f.read()
    new_config["secrets"]["FIREBASE_CREDENTIALS_JSON"] = encrypt(firebase_json)
    print(f"🔒 Secret: FIREBASE_CREDENTIALS_JSON -> encrypted")

# Write to dev-config.yml
with open("dev-config.yml", 'w') as f:
    yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)

print("\n✅ Migration complete! dev-config.yml updated.")
print("\nNext steps:")
print("1. Remove sensitive values from .env (keep MASTER_KEY and non-sensitive vars)")
print("2. Delete firebase-config.json")
print("3. Add dev-config.yml to .gitignore if not already")
