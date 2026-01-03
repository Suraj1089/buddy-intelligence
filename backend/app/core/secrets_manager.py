
import os
import yaml
from cryptography.fernet import Fernet
from typing import Any, Dict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("../.env")

class SecretManager:
    _instance = None
    _config: Dict[str, Any] = {}
    _secrets: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecretManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """
        Load configuration from YAML file based on environment.
        """
        env = os.getenv("ENVIRONMENT", "local")
        config_file = f"{env}-config.yml"
        
        # Look in backend root or current dir
        path = Path(config_file)
        if not path.exists():
            # Try looking one directory up if running from app/
            path = Path(f"../{config_file}")
            
        if not path.exists():
            print(f"Warning: Config file {config_file} not found. Using defaults.")
            return

        with open(path, "r") as f:
            self._config = yaml.safe_load(f) or {}

        # Decrypt secrets
        key = os.getenv("MASTER_KEY")
        if key and "secrets" in self._config:
            try:
                f = Fernet(key.encode())
                for k, v in self._config["secrets"].items():
                    try:
                        decrypted_val = f.decrypt(v.encode()).decode()
                        self._secrets[k] = decrypted_val
                    except Exception as e:
                        print(f"Failed to decrypt secret {k}: {e}")
            except Exception as e:
                print(f"Error initializing cipher suite: {e}")
        elif "secrets" in self._config:
             print("Warning: MASTER_KEY not found in env. Secrets cannot be decrypted.")
             # Keep encrypted values or skip? 
             # For safety, we verify keys exist but values remain encrypted/unusable if no key

    def get(self, key: str, default: Any = None) -> Any:
        # Check decrypted secrets first
        if key in self._secrets:
            return self._secrets[key]
        
        # Check non-secret config
        if key in self._config:
            return self._config.get(key)
            
        # Check environment variables as fallback
        return os.getenv(key, default)

    @property
    def all_secrets(self) -> Dict[str, Any]:
        return self._secrets

# Global instance
secrets = SecretManager()
