"""认证服务：邮箱 + 密码 -> JWT。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.roles import ROLE_LABELS
from src.models.user import User
from src.utils.security import create_access_token, hash_password, verify_password


class AuthError(Exception):
    def __init__(self, code: str, status_code: int = 401):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower().strip()))


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "org": user.org,
    }


def login(db: Session, email: str, password: str) -> dict:
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("AUTH_INVALID", 401)
    token, expires_in = create_access_token(user.email, user.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": serialize_user(user)}


def ensure_user(db: Session, email: str, password: str, display_name: str, role: str, org: str) -> User:
    user = get_user_by_email(db, email)
    if user is None:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            org=org,
        )
        db.add(user)
        db.flush()
    return user
