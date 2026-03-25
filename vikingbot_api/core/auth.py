from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
from fastapi import Request, HTTPException

ENCRYPT_KEY = b'askecho-experience-ai9176#!'[:16]  # AES requires 16/24/32 bytes key

def decrypt_token(encrypted_data: str) -> str:
    try:
        data = base64.b64decode(encrypted_data)
        cipher = AES.new(ENCRYPT_KEY, AES.MODE_ECB)
        decrypted = unpad(cipher.decrypt(data), AES.block_size)
        return decrypted.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

async def auth_middleware(request: Request, call_next):
    auth_key = request.headers.get("X-OpenViking-Bot-Key")
    if not auth_key:
        raise HTTPException(status_code=401, detail="X-OpenViking-Bot-Key header is required")

    decrypted = decrypt_token(auth_key)
    if decrypted != "ov-chat":
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    response = await call_next(request)
    return response
