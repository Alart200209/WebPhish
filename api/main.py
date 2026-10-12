from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from .database import get_db, engine, Base
from .models import User, UrlCheck
from .auth_routes import router as auth_router
from .auth import get_current_user, check_monthly_limit, increment_check_count
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
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Месячный лимит проверок исчерпан",
                "checks_used": current_user.monthly_checks_count,
                "checks_limit": 5,
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

    checks_remaining = 5 - current_user.monthly_checks_count if current_user.subscription_plan == "free" else 9999

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


@app.post("/api/payment/create")
async def create_payment(request: Request):
    # Заглушка для создания платежа (полная логика в payment.py)
    return {"success": True, "payment_url": "https://securepay.tinkoff.ru/pay", "payment_id": "123"}


@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    data = await request.json()
    print(f"Payment webhook: order={data.get('OrderId')}, status={data.get('Status')}")
    return {"success": True}


# Подключаем роутеры авторизации
app.include_router(auth_router)


# Инициализация БД при старте
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База данных инициализирована")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


# Раздача статики (фронтенда)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")