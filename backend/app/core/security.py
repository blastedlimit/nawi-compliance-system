import hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.core.config import settings

ALGORITHM="HS256"
def hash_password(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,260000)
    return "pbkdf2_sha256$260000$%s$%s"%(salt.hex(),digest.hex())
def verify_password(password, stored):
    try:
        _, rounds, salt, digest=stored.split("$")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),int(rounds)).hex(),digest)
    except Exception: return False
def create_token(subject):
    return jwt.encode({"sub":str(subject),"exp":datetime.now(timezone.utc)+timedelta(minutes=settings.jwt_expire_minutes)},settings.jwt_secret,algorithm=ALGORITHM)
def decode_token(token):
    try: return jwt.decode(token,settings.jwt_secret,algorithms=[ALGORITHM])
    except JWTError: return None
