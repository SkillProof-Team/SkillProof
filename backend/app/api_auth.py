"""T04 registration, login, current user and session logout only."""

import sqlite3
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .db import now_iso, transaction
from .models import LoginInput, RegisterInput
from .security import (
    PASSWORD_HASHER,
    Principal,
    check_rate_limit,
    clear_cookie,
    dummy_verify,
    get_db,
    issue_session,
    password_matches,
    public_user,
    require_user,
    token_hash,
)

router = APIRouter(prefix="/api/auth", tags=["accounts"])


@router.post("/register", status_code=201)
def register(payload: RegisterInput, request: Request, response: Response, con=Depends(get_db)):
    check_rate_limit(con, request, "register", payload.email)
    hashed_password = PASSWORD_HASHER.hash(payload.password)
    user_id = str(uuid4())
    try:
        with transaction(con):
            con.execute(
                "INSERT INTO users(id,email,name,role,password_hash,created_at) VALUES(?,?,?,'student',?,?)",
                (user_id, payload.email, payload.name, hashed_password, now_iso()),
            )
            old_cookie = request.cookies.get(request.app.state.settings.cookie_name)
            if old_cookie:
                con.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(old_cookie),))
            _, csrf = issue_session(con, user_id, response, request.app.state.settings)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "该邮箱已经注册") from exc
    user = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return {"user": public_user(user), "csrfToken": csrf}


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response, con=Depends(get_db)):
    check_rate_limit(con, request, "login", payload.email)
    user = con.execute("SELECT * FROM users WHERE email=?", (payload.email,)).fetchone()
    if not user:
        dummy_verify(payload.password)
        raise HTTPException(401, "邮箱或密码不正确")
    if not password_matches(user["password_hash"], payload.password):
        raise HTTPException(401, "邮箱或密码不正确")
    with transaction(con):
        # Check the password hash again under the write lock to avoid login/delete or
        # login/password-change races granting a stale session.
        latest = con.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not latest or latest["password_hash"] != user["password_hash"]:
            raise HTTPException(409, "账户状态已变化，请重新登录")
        if PASSWORD_HASHER.check_needs_rehash(latest["password_hash"]):
            con.execute("UPDATE users SET password_hash=? WHERE id=?", (PASSWORD_HASHER.hash(payload.password), user["id"]))
        old_cookie = request.cookies.get(request.app.state.settings.cookie_name)
        if old_cookie:
            con.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(old_cookie),))
        _, csrf = issue_session(con, user["id"], response, request.app.state.settings)
    return {"user": public_user(latest), "csrfToken": csrf}


@router.post("/logout")
def logout(request: Request, response: Response, principal: Principal = Depends(require_user), con=Depends(get_db)):
    con.execute("DELETE FROM sessions WHERE token_hash=?", (principal.session_hash,))
    clear_cookie(response, request.app.state.settings)
    return {"ok": True}


@router.get("/me")
def me(principal: Principal = Depends(require_user)):
    return {"user": public_user(principal.user), "csrfToken": principal.csrf_token}
