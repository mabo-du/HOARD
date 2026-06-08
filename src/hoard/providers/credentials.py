"""credentials.py — Encrypted credential store for API keys.

Implements AES-256-GCM encryption with PBKDF2 key derivation, matching
the Kryptis vault parameters exactly for cross-compatibility. Stores
keys in ~/.config/hoard/credentials.yaml.enc.

Schema (matches Kryptis):
    base64(salt(16) || nonce(12) || aes256_gcm_ciphertext)

exports: CredentialStore
"""

from __future__ import annotations

import os
from pathlib import Path

from hoard.providers.protocol import AuthenticationError

PBKDF2_ITERATIONS = 100_000
SALT_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32


class CredentialStore:
    def __init__(self, vault_path: Path | None = None, master_password: str | None = None) -> None:
        self.vault_path = vault_path or Path.home() / ".config" / "hoard" / "credentials.yaml.enc"
        self._keys: dict[str, dict[str, str]] = {}
        self._unlocked = False
        self._master_password = master_password or os.environ.get("HOARD_VAULT_KEY", "")

    def is_initialised(self) -> bool:
        return self.vault_path.exists()

    def initialise(self, master_password: str | None = None) -> None:
        if master_password:
            self._master_password = master_password
        if not self._master_password:
            raise ValueError("Master password required via argument or HOARD_VAULT_KEY env var")
        self._keys = {}
        self._unlocked = True
        self._flush()

    def unlock(self, master_password: str | None = None) -> bool:
        if master_password:
            self._master_password = master_password
        if not self._master_password:
            self._master_password = os.environ.get("HOARD_VAULT_KEY", "")
        if not self.vault_path.exists() or not self._master_password:
            return False
        try:
            encrypted = self.vault_path.read_text().strip()
            plaintext = self._decrypt(encrypted, self._master_password)
            import yaml
            self._keys = yaml.safe_load(plaintext) or {}
            self._unlocked = True
            return True
        except Exception:
            self._keys = {}
            self._unlocked = False
            return False

    def lock(self) -> None:
        self._keys = {}
        self._unlocked = False

    def get_key(self, provider: str, profile: str = "default") -> str:
        if not self._unlocked:
            raise AuthenticationError("Vault locked — run 'hoard keys unlock' first", provider=provider)
        provider_keys = self._keys.get(provider, {})
        key = provider_keys.get(profile)
        if not key:
            raise AuthenticationError(f"No key for '{provider}' (profile: '{profile}')", provider=provider)
        return key

    def set_key(self, provider: str, key: str, profile: str = "default") -> None:
        if not self._unlocked:
            raise AuthenticationError("Vault locked", provider=provider)
        self._keys.setdefault(provider, {})[profile] = key
        self._flush()

    def remove_key(self, provider: str, profile: str = "default") -> bool:
        if not self._unlocked:
            return False
        provider_keys = self._keys.get(provider, {})
        if profile not in provider_keys:
            return False
        del provider_keys[profile]
        if not provider_keys:
            del self._keys[provider]
        self._flush()
        return True

    def list_providers(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for provider, profiles in self._keys.items():
            for profile, key in profiles.items():
                prefix = key[:8] + "..." if len(key) > 8 else "***"
                result.append({"provider": provider, "profile": profile, "key_prefix": prefix})
        return result

    def _encrypt(self, plaintext: str, password: str) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64
        salt = os.urandom(SALT_LEN)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LEN, salt=salt, iterations=PBKDF2_ITERATIONS)
        key = kdf.derive(password.encode("utf-8"))
        aesgcm = AESGCM(key)
        nonce = os.urandom(NONCE_LEN)
        return base64.b64encode(salt + nonce + aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)).decode("ascii")

    def _decrypt(self, encrypted_b64: str, password: str) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64
        combined = base64.b64decode(encrypted_b64)
        if len(combined) < SALT_LEN + NONCE_LEN + 1:
            raise ValueError("Encrypted data too short")
        salt, nonce, ciphertext = combined[:SALT_LEN], combined[SALT_LEN:SALT_LEN + NONCE_LEN], combined[SALT_LEN + NONCE_LEN:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LEN, salt=salt, iterations=PBKDF2_ITERATIONS)
        return AESGCM(kdf.derive(password.encode("utf-8"))).decrypt(nonce, ciphertext, None).decode("utf-8")

    def _flush(self) -> None:
        import yaml
        encrypted = self._encrypt(yaml.dump(self._keys, default_flow_style=False), self._master_password)
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault_path.write_text(encrypted + "\n")
        try:
            self.vault_path.chmod(0o600)
        except OSError:
            pass
