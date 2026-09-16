import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


KEY_SIZE = 32
NONCE_SIZE = 12


class EncryptionService:
    def __init__(self, key: bytes):
        if len(key) != KEY_SIZE:
            raise ValueError("AES-256 key must be exactly 32 bytes")

        self.cipher = AESGCM(key)

    def encrypt(self, value: str, key_id: str) -> dict[str, str]:
        nonce = os.urandom(NONCE_SIZE)
        plaintext = json.dumps(value).encode("utf-8")

        encrypted_data = self.cipher.encrypt(
            nonce,
            plaintext,
            key_id.encode("utf-8"),
        )

        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]

        return {
            "key_id": key_id,
            "nonce": base64.b64encode(nonce).decode("utf-8"),
            "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8"),
        }

    def decrypt(self, encrypted_value: dict[str, str]) -> str:
        key_id = encrypted_value["key_id"]

        nonce = base64.b64decode(encrypted_value["nonce"])
        ciphertext = base64.b64decode(encrypted_value["ciphertext"])
        tag = base64.b64decode(encrypted_value["tag"])

        plaintext = self.cipher.decrypt(
            nonce,
            ciphertext + tag,
            key_id.encode("utf-8"),
        )

        return json.loads(plaintext.decode("utf-8"))


class EncryptionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    pii_key_id: str
    pii_key_base64: str
    pii_previous_keys: dict[str, SecretStr] = Field(default_factory=dict)


class EmployeeKeyRing:
    def __init__(self, settings: EncryptionSettings):
        self.active_key_id = settings.pii_key_id
        self.services = {
            key_id: EncryptionService(base64.b64decode(key.get_secret_value(), validate=True))
            for key_id, key in settings.pii_previous_keys.items()
        }
        if self.active_key_id in self.services:
            raise ValueError("Active key ID must not also appear in previous keys")
        self.services[self.active_key_id] = EncryptionService(
            base64.b64decode(settings.pii_key_base64, validate=True)
        )

    def encrypt(self, value: str):
        return self.services[self.active_key_id].encrypt(value, self.active_key_id)

    def decrypt(self, envelope):
        key_id = envelope["key_id"]
        return self.services[key_id].decrypt(envelope)


def get_employee_key_ring():
    return EmployeeKeyRing(EncryptionSettings())
