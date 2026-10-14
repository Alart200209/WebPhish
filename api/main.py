from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from .database import get_db, engine, Base, async_session_maker
from .models import User, UrlCheck, Review
from .auth_routes import router as auth_router
from .auth import (
    get_current_user,
    get_current_admin,
    get_password_hash,
    verify_password,
    check_monthly_limit,
    increment_check_count,
    PLAN_LIMITS,
    STARTER_CHECKS,
    apply_trial_expiry,
)
from .payment import TinkoffPayment

# Логин и пароль администратора живут в отдельном файле admin.env в корне
# проекта. Он перекрывает общие переменные окружения (override=True),
# чтобы правка файла всегда применялась при следующем запуске.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "admin.env", override=True)

app = FastAPI(
    title="PhishDet API",
    description="API для проверки фишинговых ссылок и оплаты подписок",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TINKOFF_TERMINAL_KEY = os.getenv("TINKOFF_TERMINAL_KEY", "test_key")
TINKOFF_SECRET_KEY = os.getenv("TINKOFF_SECRET_KEY", "test_secret")

payment_service = TinkoffPayment(
    terminal_key=TINKOFF_TERMINAL_KEY,
    secret_key=TINKOFF_SECRET_KEY
)

# Аккаунт модератора отзывов. Пароль по умолчанию - только для локальной
# разработки, в продакшене задаётся через переменные окружения.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@phishdet.ru")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")


class CheckUrlRequest(BaseModel):
    url: str


class CheckUrlResponse(BaseModel):
    url: str
    is_phishing: bool
    risk_score: float
    verdict: str
    details: list[str]
    checks_remaining: Optional[int] = None


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "PhishDet API"}


@app.post("/api/check-url", response_model=CheckUrlResponse)
async def check_url(
        payload: CheckUrlRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    can_check = await check_monthly_limit(current_user)

    if not can_check:
        plan = current_user.subscription_plan or "free"
        limit = PLAN_LIMITS.get(plan, STARTER_CHECKS)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": (
                    "Стартовые бесплатные проверки исчерпаны"
                    if plan == "free" else "Месячный лимит проверок исчерпан"
                ),
                "checks_used": current_user.monthly_checks_count,
                "checks_limit": limit,
                "upgrade_url": "/pricing.html"
            }
        )

    # Импортируем предсказание (если файла ml_model.py нет, сработает безопасная заглушка)
    try:
        from .ml_model import predict_url
        result = predict_url(payload.url)
    except ImportError:
        result = {
            "is_phishing": False,
            "risk_score": 0.15,
            "verdict": "Безопасно",
            "details": ["Заглушка - ML-модель еще не подключена"]
        }

    new_check = UrlCheck(
        user_id=current_user.id,
        url=payload.url,
        is_phishing=result["is_phishing"],
        risk_score=result["risk_score"],
        verdict=result["verdict"]
    )
    db.add(new_check)

    await increment_check_count(current_user)
    await db.commit()

    plan = current_user.subscription_plan or "free"
    plan_limit = PLAN_LIMITS.get(plan, STARTER_CHECKS)
    checks_remaining = None if plan_limit is None else max(plan_limit - current_user.monthly_checks_count, 0)

    return {
        "url": payload.url,
        "is_phishing": result["is_phishing"],
        "risk_score": result["risk_score"],
        "verdict": result["verdict"],
        "details": result.get("details", []),
        "checks_remaining": checks_remaining
    }


@app.get("/api/checks/history")
async def get_checks_history(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        limit: int = 50
):
    result = await db.execute(
        select(UrlCheck)
        .where(UrlCheck.user_id == current_user.id)
        .order_by(desc(UrlCheck.created_at))
        .limit(limit)
    )

    checks = result.scalars().all()

    return [
        {
            "id": check.id,
            "url": check.url,
            "is_phishing": check.is_phishing,
            "risk_score": check.risk_score,
            "verdict": check.verdict,
            "created_at": check.created_at.isoformat() if check.created_at else None
        }
        for check in checks
    ]


class ReviewCreate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    text: str


class ReviewOut(BaseModel):
    id: int
    name: Optional[str] = None
    role: Optional[str] = None
    text: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminReviewOut(ReviewOut):
    is_published: bool = False


class ReviewModerate(BaseModel):
    is_published: bool


def _clean_optional(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


@app.get("/api/reviews", response_model=list[ReviewOut])
async def list_reviews(
        db: AsyncSession = Depends(get_db),
        limit: int = 20
):
    """Публичная лента отзывов: последние опубликованные сверху."""
    limit = max(1, min(limit, 50))
    result = await db.execute(
        select(Review)
        .where(Review.is_published.is_(True))
        .order_by(desc(Review.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@app.post("/api/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
        payload: ReviewCreate,
        db: AsyncSession = Depends(get_db)
):
    """Принимает отзыв с формы. Публикуется только после проверки администратором."""
    text = " ".join((payload.text or "").split())
    if len(text) < 5:
        raise HTTPException(status_code=400, detail="Отзыв слишком короткий")
    if len(text) > 1000:
        raise HTTPException(status_code=400, detail="Отзыв слишком длинный")

    review = Review(
        name=_clean_optional(payload.name, 60),
        role=_clean_optional(payload.role, 60),
        text=text,
        is_published=False,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@app.get("/api/admin/reviews", response_model=list[AdminReviewOut])
async def admin_list_reviews(
        status_filter: str = "all",
        _admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_db),
):
    """Модерация отзывов: pending - на проверке, published - в журнале, all - всё."""
    query = select(Review).order_by(desc(Review.created_at))
    if status_filter == "pending":
        query = query.where(Review.is_published.is_(False))
    elif status_filter == "published":
        query = query.where(Review.is_published.is_(True))

    result = await db.execute(query)
    return result.scalars().all()


@app.patch("/api/admin/reviews/{review_id}", response_model=AdminReviewOut)
async def admin_moderate_review(
        review_id: int,
        payload: ReviewModerate,
        _admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_db),
):
    """Одобрить отзыв (is_published=true) или снять с публикации (false)."""
    review = await db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    review.is_published = payload.is_published
    await db.commit()
    await db.refresh(review)
    return review


@app.delete("/api/admin/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_review(
        review_id: int,
        _admin: User = Depends(get_current_admin),
        db: AsyncSession = Depends(get_db),
):
    """Удаляет отзыв безвозвратно."""
    review = await db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    await db.delete(review)
    await db.commit()
    return None


class PaymentCreateRequest(BaseModel):
    amount: int
    order_id: str
    description: str
    customer: Optional[dict] = None  # {name, email, phone} — как отправляет js/checkout.js
    customer_email: Optional[str] = None
    plan: str = "pro"
    trial: bool = False

    @property
    def email(self) -> Optional[str]:
        return self.customer_email or (self.customer or {}).get("email")


PLANS_RUB = {"basic": 9900, "pro": 29900, "corporate": 499000}  # копейки, должно совпадать с js/checkout.js
# Ключи URL-параметров из старых ссылок (personal/business) — маппим на новые тарифы
PLAN_ALIASES = {"personal": "basic", "business": "corporate"}
TRIAL_DAYS = 7


@app.post("/api/payment/create")
async def create_payment(
        payload: PaymentCreateRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Создаёт платёж в Tinkoff и возвращает ссылку для оплаты."""
    plan = PLAN_ALIASES.get(payload.plan, payload.plan)
    if plan not in PLANS_RUB:
        raise HTTPException(status_code=400, detail="Неизвестный тариф")

    expected_price = PLANS_RUB[plan]
    is_trial = False  # триалов нет: бесплатно — только стартовые 3 проверки при регистрации

    if payload.amount != expected_price:
        raise HTTPException(status_code=400, detail="Несовпадение суммы с тарифом")

    order_id = f"{payload.order_id}_{plan}"

    try:
        result = payment_service.init_payment(
            amount=payload.amount,
            order_id=order_id,
            description=payload.description or f"Подписка {payload.plan}",
            customer_email=payload.email or current_user.email,
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Сервис оплаты временно недоступен")

    if not result.get("Success"):
        raise HTTPException(status_code=502, detail=result.get("Message", "Не удалось создать платёж"))

    payment_url = result.get("FormUrl") or result.get("PaymentURL")

    return {
        "success": True,
        "payment_url": payment_url,
        "payment_id": str(result.get("PaymentId")),
        "order_id": order_id,
    }


@app.post("/api/payment/webhook")
async def payment_webhook(
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """Уведомление от Tinkoff: при успешной оплате активируем подписку."""
    data = await request.json()

    if not payment_service.verify_webhook_signature(data):
        raise HTTPException(status_code=403, detail="Неверная подпись уведомления")

    order_id = str(data.get("OrderId", ""))
    status_value = data.get("Status")

    if status_value in ("CONFIRMED", "PAID"):
        is_trial = order_id.endswith("_trial")
        result = await db.execute(
            select(User).where(User.email == data.get("CustomerKey"))
        )
        user = result.scalar_one_or_none()

        if user:
            now = datetime.utcnow()
            order_lower = order_id.lower()
            if "corporate" in order_lower:
                plan = "corporate"
            elif "_pro" in order_lower:
                plan = "pro"
            else:
                plan = "basic"
            user.subscription_plan = plan
            # Сброс месячного цикла: при входе на платный тариф счётчик обнуляется
            user.monthly_checks_count = 0
            user.last_check_reset = now

            if is_trial:
                user.trial_used = True
                # После триала — сразу переход на платную базу: через TRIAL_DAYS дней откатим
                # на стартовый пакет, если оплата не пришла. Это честная модель «попробуй, потом реши».
                user.subscription_expires_at = now + timedelta(days=TRIAL_DAYS)
            else:
                # Продление: прибавляем месяц к оставшемуся сроку, а не перезаписываем
                base = (
                    user.subscription_expires_at.replace(tzinfo=None)
                    if user.subscription_expires_at and user.subscription_expires_at > now
                    else now
                )
                user.subscription_expires_at = base + timedelta(days=30)

            await db.commit()

    return {"success": True}


# Подключаем роутеры авторизации
app.include_router(auth_router)


# Инициализация БД при старте
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Лёгкая миграция для существующих SQLite-БД: create_all не добавляет
        # новые колонки в уже созданные таблицы.
        if engine.dialect.name == "sqlite":
            from sqlalchemy import text
            res = await conn.execute(text("PRAGMA table_info(users)"))
            columns = {row[1] for row in res.fetchall()}
            if "subscription_expires_at" not in columns:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN subscription_expires_at DATETIME"
                ))
            if "trial_used" not in columns:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN trial_used BOOLEAN DEFAULT 0"
                ))
            if "is_admin" not in columns:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"
                ))

    # Администратор задаётся файлом admin.env. При старте приводим учётную
    # запись в соответствие: создаём, если её ещё нет, обновляем пароль,
    # если он поменялся в файле, и держим ровно одного администратора.
    if ADMIN_EMAIL:
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
            admin = result.scalar_one_or_none()

            if admin is None:
                session.add(User(
                    email=ADMIN_EMAIL,
                    hashed_password=get_password_hash(ADMIN_PASSWORD or "admin12345"),
                    is_admin=True,
                    monthly_checks_count=0,
                    last_check_reset=datetime.utcnow(),
                ))
                await session.commit()
                print(f"👤 Создан администратор {ADMIN_EMAIL}")
            else:
                changed = False
                if not admin.is_admin:
                    admin.is_admin = True
                    changed = True
                if ADMIN_PASSWORD and not verify_password(ADMIN_PASSWORD, admin.hashed_password):
                    admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
                    changed = True
                if changed:
                    await session.commit()
                    print(f"🔑 Обновлён доступ администратора {ADMIN_EMAIL}")

            # Администратор ровно один - тот, что указан в admin.env.
            await session.execute(
                update(User)
                .where(User.email != ADMIN_EMAIL, User.is_admin.is_(True))
                .values(is_admin=False)
            )
            await session.commit()

    print("✅ База данных инициализирована")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


# Раздача статики (фронтенда)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR

# Неизвестные /api/* отдают JSON (оформленную 404-страницу раздаёт StaticFiles).
# Регистрируется до mount("/"), поэтому реальные API-ручки имеют приоритет.
@app.api_route("/api/{_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
async def api_not_found(_path: str):
    return JSONResponse({"detail": "Not Found"}, status_code=404)


# StaticFiles с html=True сам отдаёт 404.html для несуществующих страниц.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")