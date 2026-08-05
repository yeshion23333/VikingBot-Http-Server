import base64
import os

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from vikingbot_api.core.config import get_config


AUTH_KEY_ENV = "VIKINGBOT_ENCRYPT_KEY"
VALID_AES_KEY_LENGTHS = {16, 24, 32}


def get_auth_encryption_key() -> bytes:
    configured_key = os.environ.get(AUTH_KEY_ENV) or get_config(
        "server.auth.encrypt_key",
        "",
    )
    key = configured_key.encode("utf-8")
    if len(key) not in VALID_AES_KEY_LENGTHS:
        raise RuntimeError(
            f"Set {AUTH_KEY_ENV} or server.auth.encrypt_key to a "
            "16, 24, or 32-byte secret"
        )
    return key


def encrypt_auth_token(data: str, key: bytes | None = None) -> str:
    encryption_key = key or get_auth_encryption_key()
    cipher = AES.new(encryption_key, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_auth_token(data: str, key: bytes | None = None) -> str:
    encryption_key = key or get_auth_encryption_key()
    encrypted = base64.b64decode(data, validate=True)
    cipher = AES.new(encryption_key, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
    return decrypted.decode("utf-8")
