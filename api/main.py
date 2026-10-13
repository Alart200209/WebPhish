from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from .database import get_db, engine, Base
from .models import User, UrlCheck
from .auth_routes import router as auth_router
from .auth import (
    get_current_user,
    check_monthly_limit,
    increment_check_count,
    PLAN_LIMITS,
    STARTER_CHECKS,
    apply_trial_expiry,
)
from .payment import TinkoffPayment

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
            "details": ["Заглушка: ML-модель еще не подключена"]
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
    print("✅ База данных инициализирована")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


# Раздача статики (фронтенда)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")