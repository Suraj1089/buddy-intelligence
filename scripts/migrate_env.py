import os
import yaml
from pathlib import Path
from cryptography.fernet import Fernet
import glob


def load_env_file(filepath):
    """Simple .env parser"""
    vars = {}
    if not os.path.exists(filepath):
        return vars
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                vars[k.strip()] = v.strip()
    return vars


def encrypt_value(value, key):
    f = Fernet(key.encode())
    return f.encrypt(value.encode()).decode()


def migrate():
    # 1. Load Keys
    master_key = (
        "kp_d12hmqz5n7ypu52qMcLTPtmmucRIpbQNuX-6QPgE="  # Hardcoded from inspection
    )

    # 2. Config Structure
    config = {
        "project": {"name": "Buddy Intelligence", "version": "0.1.0"},
        "environment": "local",
        "public": {},
        "secrets": {},
    }

    # 3. Read Backend .env
    backend_env = load_env_file("../.env")

    # 4. Read Frontend .env
    frontend_env = load_env_file("../../buddy/.env.development")

    all_vars = {**backend_env, **frontend_env}

    # Sensible lists
    sensitive_keywords = ["KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIALS", "DSN"]

    for k, v in all_vars.items():
        if k in ["MASTER_KEY"]:  # Don't encrypt the master key itself in the file
            continue

        is_sensitive = any(s in k for s in sensitive_keywords)

        if is_sensitive and v and v != "changethis" and not v.startswith("http"):
            # Encrypt
            try:
                encrypted = encrypt_value(v, master_key)
                config["secrets"][k] = encrypted
            except Exception as e:
                print(f"Error encrypting {k}: {e}")
                config["public"][k] = v
        else:
            config["public"][k] = v

    # Write to local-config.yml
    output_path = "../local-config.yml"
    with open(output_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)

    print(
        f"Successfully migrated {len(config['public'])} public vars and {len(config['secrets'])} secrets to {output_path}"
    )

    # Create copy for frontend if needed (as requested "same local-config")
    # In a real setup, frontend usually needs JSON or env vars during build.
    # But we will create the file as requested.
    frontend_output_path = "../../buddy/local-config.yml"
    with open(frontend_output_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"Created frontend config copy at {frontend_output_path}")


if __name__ == "__main__":
    migrate()
