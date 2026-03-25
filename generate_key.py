from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

ENCRYPT_KEY = b'askecho-experience-ai9176#!'[:16]

def encrypt_token(data: str) -> str:
    cipher = AES.new(ENCRYPT_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))
    return base64.b64encode(encrypted).decode('utf-8')

if __name__ == "__main__":
    encrypted_key = encrypt_token("ov-chat")
    print(f"X-OpenViking-Bot-Key: {encrypted_key}")
