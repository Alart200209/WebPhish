from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from .database import get_db
from .models import User
from .auth import (
    get_password_hash,
    verify_password,
    access_token_for,
    get_current_user,
    check_monthly_limit,
    validate_password,
    create_one_time_token,
    consume_one_time_token,
    find_one_time_token,
    PLAN_LIMITS,
    PUBLIC_BASE_URL,
    VERIFY_EMAIL_TTL,
    RESET_PASSWORD_TTL,
)
from .mailer import send_verification_email, send_password_reset_email
from .rate_limit import client_ip, hit, rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def _find_user(db: AsyncSession, email: str) -> Optional[User]:
    # Старые аккаунты могли сохраниться с заглавными буквами - ищем без учёта регистра
    result = await db.execute(select(User).where(func.lower(User.email) == _normalize_email(email)))
    return result.scalars().first()


def _check_password_rules(password: str, email: Optional[str]) -> None:
    try:
        validate_password(password, email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    subscription_plan: str
    monthly_checks_count: int
    is_admin: bool = False
    email_verified: bool = False
    subscription_expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


async def _queue_verification_email(db: AsyncSession, user: User, background: BackgroundTasks) -> None:
    raw = await create_one_time_token(db, user, "verify_email", VERIFY_EMAIL_TTL)
    link = f"{PUBLIC_BASE_URL}/verify-email.html?token={raw}"
    background.add_task(send_verification_email, user.email, link)


@router.post(
    "/register",
    response_model=UserResponse,
    dependencies=[Depends(rate_limit("register", limit=5, window=3600))],
)
async def register(user: UserCreate, background: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    email = _normalize_email(user.email)
    _check_password_rules(user.password, email)

    if await _find_user(db, email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    hashed_password = get_password_hash(user.password)
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        monthly_checks_count=0,
        last_check_reset=datetime.utcnow(),
        email_verified=False,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    await _queue_verification_email(db, new_user, background)

    return new_user


@router.post("/login", response_model=Token)
async def login(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db)
):
    email = _normalize_email(form_data.username)
    # Подбор пароля: ограничиваем и по IP, и по атакуемому аккаунту
    hit("login-ip", client_ip(request), limit=10, window=60)
    hit("login-email", email, limit=10, window=15 * 60)

    user = await _find_user(db, email)

    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": access_token_for(user), "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/check-limit")
async def check_limit(current_user: User = Depends(get_current_user)):
    can_check = await check_monthly_limit(current_user)
    limit = PLAN_LIMITS.get(current_user.subscription_plan, PLAN_LIMITS["free"])

    return {
        "can_check": can_check,
        "checks_used": current_user.monthly_checks_count,
        "checks_limit": limit if limit is not None else "unlimited",
        "subscription_plan": current_user.subscription_plan
    }


@router.post("/verify-email", dependencies=[Depends(rate_limit("verify-email", limit=20, window=600))])
async def verify_email(payload: TokenPayload, db: AsyncSession = Depends(get_db)):
    user = await consume_one_time_token(db, payload.token, "verify_email")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ссылка недействительна или устарела. Запросите новое письмо в личном кабинете.",
        )

    user.email_verified = True
    await db.commit()
    return {"success": True, "message": "Почта подтверждена"}


@router.post("/resend-verification")
async def resend_verification(
        background: BackgroundTasks,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    if current_user.email_verified:
        return {"success": True, "message": "Почта уже подтверждена"}

    hit("resend-verification", str(current_user.id), limit=3, window=15 * 60)
    await _queue_verification_email(db, current_user, background)
    return {"success": True, "message": f"Письмо отправлено на {current_user.email}"}


@router.post("/forgot-password")
async def forgot_password(
        payload: ForgotPasswordRequest,
        request: Request,
        background: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
):
    email = _normalize_email(payload.email)
    hit("forgot-ip", client_ip(request), limit=5, window=15 * 60)
    hit("forgot-email", email, limit=3, window=15 * 60)

    user = await _find_user(db, email)

    if user and user.is_active:
        raw = await create_one_time_token(db, user, "reset_password", RESET_PASSWORD_TTL)
        link = f"{PUBLIC_BASE_URL}/reset-password.html?token={raw}"
        background.add_task(send_password_reset_email, user.email, link)

    # Ответ одинаковый, есть аккаунт или нет: по нему нельзя проверить, кто зарегистрирован
    return {
        "success": True,
        "message": "Если аккаунт с такой почтой есть, мы отправили на неё ссылку для сброса пароля.",
    }


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset-password", limit=10, window=15 * 60))])
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token = await find_one_time_token(db, payload.token, "reset_password")
    user = await db.get(User, token.user_id) if token else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ссылка недействительна или устарела. Запросите сброс пароля ещё раз.",
        )

    # Сначала проверяем пароль: неудачная попытка не должна сжигать ссылку из письма
    _check_password_rules(payload.new_password, user.email)

    token.used_at = datetime.utcnow()
    user.hashed_password = get_password_hash(payload.new_password)
    user.token_version = (user.token_version or 0) + 1
    # Письмо дошло до владельца ящика - значит, почта заодно подтверждена
    user.email_verified = True
    await db.commit()
    return {"success": True, "message": "Пароль изменён. Войдите с новым паролем."}


@router.post("/change-password", response_model=Token)
async def change_password(
        payload: ChangePasswordRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    hit("change-password", str(current_user.id), limit=5, window=15 * 60)

    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Текущий пароль указан неверно")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Новый пароль совпадает с текущим")
    _check_password_rules(payload.new_password, current_user.email)

    current_user.hashed_password = get_password_hash(payload.new_password)
    # Остальные сессии (другие браузеры, украденный токен) разлогиниваются,
    # а текущей возвращаем свежий токен
    current_user.token_version = (current_user.token_version or 0) + 1
    await db.commit()
    return {"access_token": access_token_for(current_user), "token_type": "bearer"}
