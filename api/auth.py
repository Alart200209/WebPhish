from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .database import get_db
from .models import User
import os

# Конфигурация
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-this-in-production-min-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# Хеширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 схема
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


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
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    # Ленивый автооткат истёкшего триала/подписки — без фоновых задач и миграций.
    if apply_trial_expiry(user):
        await db.commit()
        await db.refresh(user)

    return user


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