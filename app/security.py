import datetime as dt

import bcrypt
import jwt

from .config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, version: int = 0) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": user_id, "ver": version, "iat": now, "exp": now + dt.timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_token_full(token: str) -> tuple[str, int] | None:
    try:
        data = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
        return data["sub"], int(data.get("ver", 0))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def decode_token(token: str) -> str | None:
    d = decode_token_full(token)
    return d[0] if d else None


# ---------------------------------------------------------------- two-factor (TOTP, e.g. Google Authenticator)
def totp_new_secret() -> str:
    import pyotp

    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    import pyotp

    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="GST Billing")


def totp_ok(secret: str, code: str) -> bool:
    import pyotp

    return bool(code) and pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)


# ---------------------------------------------------------------- secrets at rest
def _fernet():
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    key = hashlib.sha256(("enc:" + get_settings().jwt_secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
