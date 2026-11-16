"""Email + password login with server-side sessions in an httpOnly cookie."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import models
from app.db import config, get_db

COOKIE = "plenty_session"
hasher = PasswordHasher()
# Verifying against a dummy hash keeps unknown-email logins as slow as wrong passwords.
_DUMMY_HASH = hasher.hash("not-a-real-password")

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class LoginBody(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class Me(BaseModel):
    id: int
    email: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(
    db: Session = Depends(get_db), plenty_session: str | None = Cookie(None)
) -> models.User:
    if plenty_session:
        row = db.get(models.Session, _hash_token(plenty_session))
        if row and row.expires_at > _now():
            user = db.get(models.User, row.user_id)
            if user:
                return user
    raise HTTPException(401, "Not signed in")


# --- Brute-force protection: per email and per IP, in memory (fine for one instance) ---
_MAX_FAILS, _WINDOW = 5, 15 * 60
_fails: dict[str, deque[float]] = defaultdict(deque)


def _recent_fails(key: str) -> deque[float]:
    q, cutoff = _fails[key], time.monotonic() - _WINDOW
    while q and q[0] < cutoff:
        q.popleft()
    return q


def _client_ip(request: Request) -> str:
    # The left of X-Forwarded-For is whatever the client sent; the right-most entry is the
    # one our host's proxy appended, so it's the only one an attacker can't choose.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "?"


def _start_session(db: Session, response: Response, user: models.User) -> None:
    token = secrets.token_urlsafe(32)
    db.execute(delete(models.Session).where(models.Session.expires_at < _now()))
    db.add(
        models.Session(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=_now() + timedelta(days=config.session_days),
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=config.session_days * 86_400,
        httponly=True,
        secure=config.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/signup", response_model=Me, status_code=201)
def signup(body: Credentials, response: Response, db: Session = Depends(get_db)):
    has_users = db.scalar(select(func.count()).select_from(models.User))
    if has_users and not config.allow_signup:
        raise HTTPException(403, "Sign-ups are closed")
    email = body.email.lower()
    if not has_users and config.owner_email and email != config.owner_email.lower():
        raise HTTPException(403, "Sign-ups are closed")
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(409, "That email already has an account")
    user = models.User(email=email, password_hash=hasher.hash(body.password))
    db.add(user)
    db.flush()
    _start_session(db, response, user)
    return Me(id=user.id, email=user.email)


@router.post("/login", response_model=Me)
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    keys = (f"email:{email}", f"ip:{_client_ip(request)}")
    if any(len(_recent_fails(k)) >= _MAX_FAILS for k in keys):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")

    user = db.scalar(select(models.User).where(models.User.email == email))
    try:
        hasher.verify(user.password_hash if user else _DUMMY_HASH, body.password)
        if user is None:
            raise VerificationError
    except VerificationError:
        for k in keys:
            _fails[k].append(time.monotonic())
        raise HTTPException(401, "Wrong email or password") from None

    for k in keys:
        _fails.pop(k, None)
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(body.password)
    _start_session(db, response, user)
    return Me(id=user.id, email=user.email)


@router.post("/logout", status_code=204)
def logout(
    response: Response, db: Session = Depends(get_db), plenty_session: str | None = Cookie(None)
):
    if plenty_session:
        db.execute(
            delete(models.Session).where(models.Session.token_hash == _hash_token(plenty_session))
        )
        db.commit()
    response.delete_cookie(COOKIE, path="/")


class CredentialsChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_email: EmailStr | None = None
    new_password: str | None = Field(None, min_length=10, max_length=200)

    @model_validator(mode="after")
    def _changes_something(self):
        if self.new_email is None and self.new_password is None:
            raise ValueError("Give a new email, a new password, or both")
        return self


@router.put("/credentials", response_model=Me)
def change_credentials(
    body: CredentialsChange,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    """Change email and/or password. Needs the current password, and signs out other devices."""
    keys = (f"user:{user.id}", f"ip:{_client_ip(request)}")
    if any(len(_recent_fails(k)) >= _MAX_FAILS for k in keys):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    try:
        hasher.verify(user.password_hash, body.current_password)
    except VerificationError:
        for k in keys:
            _fails[k].append(time.monotonic())
        raise HTTPException(401, "Current password is wrong") from None
    for k in keys:
        _fails.pop(k, None)

    if body.new_email is not None:
        email = body.new_email.lower()
        taken = db.scalar(
            select(models.User).where(models.User.email == email, models.User.id != user.id)
        )
        if taken:
            raise HTTPException(409, "That email already has an account")
        user.email = email
    if body.new_password is not None:
        if body.new_password == body.current_password:
            raise HTTPException(422, "New password must be different")
        user.password_hash = hasher.hash(body.new_password)

    # Rotate: anyone holding an old session (another device, a stolen cookie) is signed out.
    db.execute(delete(models.Session).where(models.Session.user_id == user.id))
    _start_session(db, response, user)
    return Me(id=user.id, email=user.email)


class AuthStatus(BaseModel):
    user: Me | None
    signup_open: bool


@router.get("/status", response_model=AuthStatus)
def status(db: Session = Depends(get_db), plenty_session: str | None = Cookie(None)):
    """Who's signed in (if anyone), and whether the sign-up form should be offered."""
    try:
        user = current_user(db, plenty_session)
        me = Me(id=user.id, email=user.email)
    except HTTPException:
        me = None
    has_users = db.scalar(select(func.count()).select_from(models.User))
    return AuthStatus(user=me, signup_open=config.allow_signup or not has_users)
