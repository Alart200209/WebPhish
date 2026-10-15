from datetime import datetime, timedelta
from typing import Optional
import hashlib
import re
import secrets
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db
from .models import User, AuthToken
import os

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production-min-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# Адрес сайта для ссылок в письмах и возврата с оплаты
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(hours=1)

# Хеширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 схема
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# Самые частые пароли из утечек: их подбирают первыми
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "password1", "password123",
    "qwerty123", "qwertyuiop", "1q2w3e4r", "1q2w3e4r5t", "qwerty12", "11111111",
    "00000000", "88888888", "iloveyou", "abc12345", "admin123", "admin12345",
    "passw0rd", "123qwe123", "zaq12wsx", "1qaz2wsx", "qazwsx123", "phishdet1",
}

PASSWORD_RULES_TEXT = "Пароль: от 8 символов, хотя бы одна буква и одна цифра"


def validate_password(password: str, email: Optional[str] = None) -> str:
    """Проверяет требования к паролю. Возвращает пароль или бросает ValueError
    с понятным пользователю текстом (pydantic превращает его в ответ 422)."""
    if len(password) < 8:
        raise ValueError("Пароль должен быть не короче 8 символов")
    # bcrypt учитывает только первые 72 байта - длиннее молча обрезал бы
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Пароль слишком длинный: максимум 72 байта (около 36 символов кириллицей)")
    if password != password.strip():
        raise ValueError("Пароль не должен начинаться или заканчиваться пробелом")
    if not re.search(r"[A-Za-zА-Яа-яЁё]", password) or not re.search(r"\d", password):
        raise ValueError("Пароль должен содержать хотя бы одну букву и одну цифру")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Этот пароль слишком распространён - придумайте другой")
    if email:
        lowered = password.lower()
        local_part = email.split("@")[0].lower()
        if lowered == email.lower() or (len(local_part) >= 4 and local_part in lowered):
            raise ValueError("Пароль не должен повторять адрес почты")
    return password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_version = int(payload.get("ver", 0))
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    # После смены или сброса пароля токены, выданные раньше, больше не действуют
    if token_version != (user.token_version or 0):
        raise credentials_exception

    # Ленивый автооткат истёкшего триала/подписки — без фоновых задач и миграций.
    if apply_trial_expiry(user):
        await db.commit()
        await db.refresh(user)

    return user


def access_token_for(user: User) -> str:
    return create_access_token(data={"sub": user.email, "ver": user.token_version or 0})


async def get_verified_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """Проверки и оплата - только с подтверждённой почтой: иначе бесплатные
    проверки можно получать бесконечно, регистрируя несуществующие адреса."""
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Подтвердите почту: мы отправили ссылку в письме при регистрации",
            },
        )
    return current_user


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def create_one_time_token(db: AsyncSession, user: User, purpose: str, ttl: timedelta) -> str:
    """Создаёт одноразовый токен для письма. Прежние неиспользованные токены
    того же назначения гасятся - работает только последняя ссылка."""
    now = datetime.utcnow()
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
    )
    for old in result.scalars().all():
        old.used_at = now

    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        purpose=purpose,
        expires_at=now + ttl,
    ))
    await db.commit()
    return raw


async def find_one_time_token(db: AsyncSession, raw: str, purpose: str) -> Optional[AuthToken]:
    """Действующий токен (не истёк, не использован) или None. Не гасит его."""
    result = await db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == _hash_token(raw or ""),
            AuthToken.purpose == purpose,
        )
    )
    token = result.scalar_one_or_none()
    if token is None or token.used_at is not None:
        return None
    if token.expires_at.replace(tzinfo=None) < datetime.utcnow():
        return None
    return token


async def consume_one_time_token(db: AsyncSession, raw: str, purpose: str) -> Optional[User]:
    """Гасит токен и возвращает его владельца. None - токен неверный, истёк или уже использован."""
    token = await find_one_time_token(db, raw, purpose)
    if token is None:
        return None
    token.used_at = datetime.utcnow()
    return await db.get(User, token.user_id)


async def get_current_admin(
        current_user: User = Depends(get_current_user)
) -> User:
    """Пускает дальше только администратора (модерация отзывов)."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администратора",
        )
    return current_user


# Лимиты проверок по тарифам. None — без ограничений.
# Единственный источник правды: синхронизирован с лендингом и ценами.
# «free» — только стартовый пакет из 3 проверок на аккаунт (не подписка):
# лимит считается не по месяцам, а по общему счётчику monthly_checks_count.
# basic — базовая подписка для личных целей: 20 проверок в месяц.
# pro — расширенная персональная подписка: 200 проверок в месяц.
# corporate — корпоративная подписка: команды, API, SLA; проверки без лимита.
STARTER_CHECKS = 3
PLAN_LIMITS = {
    "free": STARTER_CHECKS,
    "basic": 20,
    "pro": 200,
    "corporate": None,
}


async def check_monthly_limit(user: User) -> bool:
    """Один честный источник лимита.

    free — стартовый пакет из 3 проверок на весь аккаунт: счётчик НЕ обнуляется
    каждый месяц, иначе «бесплатная подписка» вернулась бы бы по кругу.
    personal/corporate — месячный цикл: сброс раз в 30 дней.
    """
    plan = user.subscription_plan or "free"

    if plan != "free":
        now = datetime.utcnow()
        if user.last_check_reset:
            days_since_reset = (now - user.last_check_reset.replace(tzinfo=None)).days
            if days_since_reset >= 30:
                user.monthly_checks_count = 0
                user.last_check_reset = now

    limit = PLAN_LIMITS.get(plan, STARTER_CHECKS)
    if limit is not None and user.monthly_checks_count >= limit:
        return False

    return True


async def increment_check_count(user: User):
    user.monthly_checks_count += 1


def apply_trial_expiry(user: User) -> bool:
    """Ленивый автооткат истёкшей подписки/триала на стартовый пакет («free»).

    Миграции не требуются: колонка subscription_expires_at создаётся через
    Base.metadata.create_all для новых БД; для существующей SQLite-БД
    применяется лёгкий ALTER TABLE при старте (см. startup в main.py).
    Возвращает True, если подписка истекла и была откачена.
    """
    if user.subscription_plan in ("free", None):
        return False
    expires = user.subscription_expires_at
    if expires is None:
        # Платная подписка без срока (оформлена до введения поля) — считаем активной
        return False
    if expires.tzinfo is not None:
        expires = expires.replace(tzinfo=None)
    if datetime.utcnow() >= expires:
        user.subscription_plan = "free"
        user.subscription_expires_at = None
        # Откат на стартовый пакет: счётчик проверок НЕ обнуляем —
        # 3 бесплатные проверки даются один раз на аккаунт, а не каждый месяц.
        return True
    return False