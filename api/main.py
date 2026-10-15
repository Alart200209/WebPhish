from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
import logging
import os
import uuid
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from .database import get_db, engine, Base, async_session_maker
from .models import User, UrlCheck, Review, Payment
from .auth_routes import router as auth_router
from .auth import (
    get_current_user,
    get_current_admin,
    get_verified_user,
    get_password_hash,
    verify_password,
    check_monthly_limit,
    increment_check_count,
    PLAN_LIMITS,
    STARTER_CHECKS,
    apply_trial_expiry,
    PUBLIC_BASE_URL,
)
from .payment import YooKassaClient, YooKassaError, value_to_kopecks
from .rate_limit import hit, rate_limit

logger = logging.getLogger("phishdet")

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

# ЮKassa: shopId и секретный ключ из личного кабинета (Интеграция → Ключи API).
# Для тестового магазина ключ начинается с test_.
payment_service = YooKassaClient(
    shop_id=os.getenv("YOOKASSA_SHOP_ID", ""),
    secret_key=os.getenv("YOOKASSA_SECRET_KEY", ""),
    base_url=os.getenv("YOOKASSA_API_URL") or None,
    send_receipt=os.getenv("YOOKASSA_SEND_RECEIPT", "1").lower() in ("1", "true", "yes"),
    vat_code=int(os.getenv("YOOKASSA_VAT_CODE", "1")),
)

# Аккаунт модератора отзывов задаётся в admin.env (см. admin.env.example).
# Пароля по умолчанию нет: без файла администратор просто не создаётся.
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""


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
        current_user: User = Depends(get_verified_user),
        db: AsyncSession = Depends(get_db)
):
    # Защита от скриптов: даже безлимитный тариф не больше 30 проверок в минуту
    hit("check-url", str(current_user.id), limit=30, window=60)

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


@app.post(
    "/api/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("reviews", limit=5, window=3600))],
)
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
    description: Optional[str] = None
    customer: Optional[dict] = None  # {name, email, phone} — как отправляет js/checkout.js
    customer_email: Optional[str] = None
    plan: str = "pro"
    payment_method: Optional[str] = None  # card | sbp

    @property
    def email(self) -> Optional[str]:
        return self.customer_email or (self.customer or {}).get("email")


PLANS_RUB = {"basic": 9900, "pro": 29900, "corporate": 499000}  # копейки, должно совпадать с js/checkout.js
PLAN_TITLES = {"basic": "Базовая", "pro": "Про", "corporate": "Корпоративная"}
# Ключи URL-параметров из старых ссылок (personal/business) — маппим на новые тарифы
PLAN_ALIASES = {"personal": "basic", "business": "corporate"}
SUBSCRIPTION_DAYS = 30
# Платёж не прошёл - подписку по нему уже не выдадут
FAILED_PAYMENT_STATUSES = {"canceled", "INIT_ERROR", "AMOUNT_MISMATCH"}


@app.post("/api/payment/create")
async def create_payment(
        payload: PaymentCreateRequest,
        current_user: User = Depends(get_verified_user),
        db: AsyncSession = Depends(get_db),
):
    """Создаёт платёж в ЮKassa и возвращает ссылку для оплаты."""
    hit("payment-create", str(current_user.id), limit=10, window=600)

    plan = PLAN_ALIASES.get(payload.plan, payload.plan)
    if plan not in PLANS_RUB:
        raise HTTPException(status_code=400, detail="Неизвестный тариф")

    expected_price = PLANS_RUB[plan]
    if payload.amount != expected_price:
        raise HTTPException(status_code=400, detail="Несовпадение суммы с тарифом")

    # Номер заказа придумывает сервер, а не браузер: по нему находим платёж при возврате
    order_id = f"phishdet_{current_user.id}_{uuid.uuid4().hex[:16]}"
    payment = Payment(
        order_id=order_id,
        user_id=current_user.id,
        plan=plan,
        amount=expected_price,
        status="NEW",
    )
    db.add(payment)
    await db.commit()

    try:
        result = await run_in_threadpool(
            payment_service.create_payment,
            amount=expected_price,
            order_id=order_id,
            description=f"Подписка PhishDet «{PLAN_TITLES[plan]}» на {SUBSCRIPTION_DAYS} дней",
            return_url=f"{PUBLIC_BASE_URL}/payment-result.html?order={order_id}",
            # Чек уходит на почту аккаунта: её владелец подтвердил, что это его ящик
            customer_email=current_user.email,
            payment_method=payload.payment_method,
        )
    except YooKassaError as exc:
        logger.error("ЮKassa не создала платёж %s: %s", order_id, exc)
        payment.status = "INIT_ERROR"
        await db.commit()
        raise HTTPException(status_code=502, detail="Сервис оплаты временно недоступен. Попробуйте позже.")

    payment.payment_id = result.get("id")
    payment.status = result.get("status") or "pending"
    await db.commit()

    payment_url = (result.get("confirmation") or {}).get("confirmation_url")
    if not payment_url:
        raise HTTPException(status_code=502, detail="Не получена ссылка на оплату")

    return {
        "success": True,
        "payment_url": payment_url,
        "payment_id": payment.payment_id,
        "order_id": order_id,
    }


def _activate_subscription(user: User, plan: str, now: datetime) -> None:
    """Выдаёт или продлевает подписку на месяц после подтверждённой оплаты."""
    if user.subscription_plan != plan:
        # Новый тариф - новый месячный цикл и чистый счётчик проверок
        user.monthly_checks_count = 0
        user.last_check_reset = now
    user.subscription_plan = plan

    # Продление: прибавляем месяц к оставшемуся сроку, а не перезаписываем
    current = user.subscription_expires_at.replace(tzinfo=None) if user.subscription_expires_at else None
    base = current if current and current > now else now
    user.subscription_expires_at = base + timedelta(days=SUBSCRIPTION_DAYS)


async def _sync_payment(db: AsyncSession, payment: Payment, remote: dict) -> None:
    """Переносит состояние платежа из ЮKassa к нам. Идемпотентно: подписка
    по одному платежу выдаётся один раз, сколько бы раз ни пришло уведомление."""
    remote_status = remote.get("status") or payment.status

    if payment.applied:
        # Подписка уже выдана - статус больше не трогаем
        return

    if remote_status == "succeeded" and remote.get("paid"):
        paid_amount = value_to_kopecks((remote.get("amount") or {}).get("value"))
        currency = (remote.get("amount") or {}).get("currency")
        if paid_amount != payment.amount or currency != "RUB":
            # Сумма не та, что мы выставляли - подписку не выдаём, разбираемся руками
            logger.error("Заказ %s: оплачено %s %s, ожидалось %s", payment.order_id,
                         paid_amount, currency, payment.amount)
            payment.status = "AMOUNT_MISMATCH"
        else:
            now = datetime.utcnow()
            user = await db.get(User, payment.user_id)
            if user:
                _activate_subscription(user, payment.plan, now)
            payment.status = "succeeded"
            payment.applied = True
            payment.paid_at = now
    elif payment.status != "AMOUNT_MISMATCH":
        payment.status = remote_status

    await db.commit()


async def _fetch_remote_payment(payment: Payment) -> Optional[dict]:
    """Спрашивает у ЮKassa актуальный платёж. None - если не получилось."""
    if not payment.payment_id:
        return None
    try:
        remote = await run_in_threadpool(payment_service.get_payment, payment.payment_id)
    except YooKassaError as exc:
        logger.warning("Не удалось получить платёж %s из ЮKassa: %s", payment.payment_id, exc)
        return None
    # Платёж должен относиться именно к этому заказу
    if (remote.get("metadata") or {}).get("order_id") != payment.order_id:
        logger.error("Платёж %s не относится к заказу %s", payment.payment_id, payment.order_id)
        return None
    return remote


@app.post("/api/payment/webhook")
async def payment_webhook(
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """HTTP-уведомление ЮKassa (payment.succeeded, payment.canceled, ...).

    Адрес задаётся в личном кабинете ЮKassa: Интеграция → HTTP-уведомления.
    Уведомления не подписаны, поэтому содержимому не верим: берём из него
    только id платежа и запрашиваем настоящий статус у ЮKassa.
    На любой разобранный запрос отвечаем 200 - иначе ЮKassa будет повторять его сутки.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Ожидается JSON")

    obj = data.get("object") if isinstance(data, dict) else None
    payment_id = obj.get("id") if isinstance(obj, dict) else None
    event = data.get("event") if isinstance(data, dict) else None

    if not payment_id or not str(event or "").startswith("payment."):
        # Возвраты (refund.*) и прочее пока не обрабатываем
        return {"success": True}

    result = await db.execute(select(Payment).where(Payment.payment_id == str(payment_id)))
    payment = result.scalar_one_or_none()
    if payment is None:
        logger.warning("Уведомление %s по неизвестному платежу %s", event, payment_id)
        return {"success": True}

    remote = await _fetch_remote_payment(payment)
    if remote is None:
        # ЮKassa сейчас не ответила - просим повторить уведомление позже
        raise HTTPException(status_code=503, detail="Не удалось проверить платёж")

    await _sync_payment(db, payment, remote)
    return {"success": True}


@app.get("/api/payment/status/{order_id}")
async def payment_status(
        order_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Статус платежа для страницы возврата с оплаты (payment-result.html).

    Если уведомление ещё не пришло (или не может прийти - например, при
    локальном запуске), сами спрашиваем статус у ЮKassa.
    """
    result = await db.execute(
        select(Payment).where(Payment.order_id == order_id, Payment.user_id == current_user.id)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if not payment.applied and payment.status not in FAILED_PAYMENT_STATUSES:
        remote = await _fetch_remote_payment(payment)
        if remote is not None:
            await _sync_payment(db, payment, remote)
            await db.refresh(current_user)

    if payment.applied:
        state = "paid"
    elif payment.status in FAILED_PAYMENT_STATUSES:
        state = "failed"
    else:
        state = "pending"

    return {
        "order_id": payment.order_id,
        "plan": payment.plan,
        "plan_title": PLAN_TITLES.get(payment.plan, payment.plan),
        "amount": payment.amount,
        "status": payment.status,
        "state": state,
        "subscription_plan": current_user.subscription_plan,
        "subscription_expires_at": (
            current_user.subscription_expires_at.isoformat()
            if current_user.subscription_expires_at else None
        ),
    }


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
            if "email_verified" not in columns:
                # Аккаунты, созданные до подтверждения почты, считаем подтверждёнными,
                # чтобы не отрезать им доступ. Новые получают False из модели.
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 1"
                ))
            if "token_version" not in columns:
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0"
                ))

    # Администратор задаётся файлом admin.env. При старте приводим учётную
    # запись в соответствие: создаём, если её ещё нет, обновляем пароль,
    # если он поменялся в файле, и держим ровно одного администратора.
    if ADMIN_EMAIL and not ADMIN_PASSWORD:
        print("ADMIN_EMAIL задан, а ADMIN_PASSWORD нет - администратор не создан")
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        async with async_session_maker() as session:
            result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
            admin = result.scalar_one_or_none()

            if admin is None:
                session.add(User(
                    email=ADMIN_EMAIL,
                    hashed_password=get_password_hash(ADMIN_PASSWORD),
                    is_admin=True,
                    email_verified=True,
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
                if not admin.email_verified:
                    admin.email_verified = True
                    changed = True
                if not verify_password(ADMIN_PASSWORD, admin.hashed_password):
                    admin.hashed_password = get_password_hash(ADMIN_PASSWORD)
                    admin.token_version = (admin.token_version or 0) + 1
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


# Раздача статики (фронтенда). Только папка static/: корень проекта наружу
# не отдаём - там лежат .env, admin.env, база и исходники.
STATIC_DIR = PROJECT_ROOT / "static"

# Неизвестные /api/* отдают JSON (оформленную 404-страницу раздаёт StaticFiles).
# Регистрируется до mount("/"), поэтому реальные API-ручки имеют приоритет.
@app.api_route("/api/{_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
async def api_not_found(_path: str):
    return JSONResponse({"detail": "Not Found"}, status_code=404)


# StaticFiles с html=True сам отдаёт 404.html для несуществующих страниц.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")