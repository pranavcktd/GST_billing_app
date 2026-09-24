from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import DB, CurrentUser
from ..models import Membership, User
from ..schemas import LoginIn, MeOut, MyBusinessOut, RegisterIn, TokenOut, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def me_payload(db, user: User) -> MeOut:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    return MeOut(
        user=UserOut.model_validate(user),
        businesses=[
            MyBusinessOut(id=m.business.id, name=m.business.name, gstin=m.business.gstin,
                          gst_type=m.business.gst_type, role=m.role)
            for m in memberships
        ],
    )


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: DB):
    email = data.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(name=data.name, email=email, phone=data.phone, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return TokenOut(token=create_token(user.id), **me_payload(db, user).model_dump())


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: DB):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(token=create_token(user.id), **me_payload(db, user).model_dump())


@router.get("/me", response_model=MeOut)
def me(db: DB, user: CurrentUser):
    return me_payload(db, user)
