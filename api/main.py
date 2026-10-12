from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from pathlib import Path
import os

from api.payment import TinkoffPayment

app = FastAPI(
    title="PhishDet API",
    description="API для проверки фишинговых ссылок и оплаты подписок",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация Tinkoff Payment
# ВАЖНО: Замените на свои реальные ключи из .env файла
TINKOFF_TERMINAL_KEY = os.getenv("TINKOFF_TERMINAL_KEY", "ваш_terminal_key")
TINKOFF_SECRET_KEY = os.getenv("TINKOFF_SECRET_KEY", "ваш_secret_key")

payment_service = TinkoffPayment(
    terminal_key=TINKOFF_TERMINAL_KEY,
    secret_key=TINKOFF_SECRET_KEY
)


# ===================================
# MODELS
# ===================================

class PaymentRequest(BaseModel):
    amount: int  # в копейках
    order_id: str
    description: str
    customer: dict
    plan: str
    trial: bool = False
    payment_method: str = "card"


class PaymentResponse(BaseModel):
    success: bool
    payment_url: Optional[str] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None


# ===================================
# API ENDPOINTS
# ===================================

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "PhishDet API"}


@app.post("/api/payment/create", response_model=PaymentResponse)
async def create_payment(request: PaymentRequest):
    """
    Создание платежа через Tinkoff Касса
    """
    try:
        # Создаем платеж
        result = payment_service.init_payment(
            amount=request.amount,
            order_id=request.order_id,
            description=request.description,
            customer_email=request.customer.get("email"),
            customer_phone=request.customer.get("phone"),
            receipt={
                "Email": request.customer.get("email"),
                "Phone": request.customer.get("phone"),
                "Taxation": "osn",
                "Items": [
                    {
                        "Name": f"Подписка {request.plan}",
                        "Price": request.amount,
                        "Quantity": 1,
                        "Amount": request.amount,
                        "Tax": "none"
                    }
                ]
            }
        )

        if result.get("Success"):
            return PaymentResponse(
                success=True,
                payment_url=result.get("PaymentURL"),
                payment_id=str(result.get("PaymentId")),
                order_id=result.get("OrderId")
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("Message", "Ошибка создания платежа")
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сервера: {str(e)}"
        )


@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    """
    Webhook от Tinkoff о статусе платежа
    """
    try:
        data = await request.json()

        # Проверяем подпись (опционально, но рекомендуется)
        # payment_service.verify_webhook_signature(data)

        order_id = data.get("OrderId")
        status = data.get("Status")

        # Здесь сохраняем статус платежа в базу данных
        # Например: db.update_payment_status(order_id, status)

        print(f"Payment webhook: order={order_id}, status={status}")

        return {"success": True}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка обработки webhook: {str(e)}"
        )


@app.get("/api/payment/status/{payment_id}")
async def get_payment_status(payment_id: str):
    """
    Проверка статуса платежа
    """
    try:
        result = payment_service.get_state(payment_id)

        if result.get("Success"):
            return {
                "success": True,
                "status": result.get("Status"),
                "amount": result.get("Amount")
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("Message", "Ошибка получения статуса")
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сервера: {str(e)}"
        )


# ===================================
# STATIC FILES (FRONTEND)
# ===================================

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR

if STATIC_DIR.exists():
    # API роуты должны быть зарегистрированы ДО mount
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)