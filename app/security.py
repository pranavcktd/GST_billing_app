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


def create_token(user_id: str) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + dt.timedelta(minutes=s.jwt_expire_minutes)}
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])["sub"]
    except jwt.PyJWTError:
        return None
