"""Интеграция с ЮKassa (API v3).

Документация: https://yookassa.ru/developers/api

Как устроена оплата:
1. create_payment - создаём платёж, получаем confirmation_url и ведём туда покупателя.
2. Покупатель платит на странице ЮKassa и возвращается на return_url.
3. ЮKassa присылает HTTP-уведомление (payment.succeeded / payment.canceled).
   Уведомления не подписаны, поэтому им не верим: по id из уведомления
   запрашиваем платёж через get_payment и смотрим его настоящий статус.
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

import requests


class YooKassaError(Exception):
    """ЮKassa ответила ошибкой или недоступна."""


def kopecks_to_value(amount: int) -> str:
    """9900 -> "99.00": ЮKassa принимает сумму строкой в рублях."""
    return f"{amount // 100}.{amount % 100:02d}"


def value_to_kopecks(value: Any) -> Optional[int]:
    """"99.00" -> 9900. None, если сумма не разбирается."""
    try:
        kopecks = Decimal(str(value)) * 100
    except (InvalidOperation, TypeError, ValueError):
        return None
    # Доли копейки - это не та сумма, которую мы выставляли, не округляем
    if not kopecks.is_finite() or kopecks != kopecks.to_integral_value():
        return None
    return int(kopecks)


# Способ оплаты из формы checkout -> тип в ЮKassa. Без него покупатель выберет сам.
PAYMENT_METHOD_TYPES = {"card": "bank_card", "sbp": "sbp"}


class YooKassaClient:
    BASE_URL = "https://api.yookassa.ru/v3"
    TIMEOUT = 15

    def __init__(
            self,
            shop_id: str,
            secret_key: str,
            base_url: Optional[str] = None,
            send_receipt: bool = True,
            vat_code: int = 1,
    ):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        # Чек по 54-ФЗ. Нужен, если в ЮKassa подключены «Чеки от ЮKassa»
        # или своя онлайн-касса. Без подключённых чеков ЮKassa отклонит платёж с receipt.
        self.send_receipt = send_receipt
        # Ставка НДС в чеке: 1 - без НДС. Точный код уточните у бухгалтера.
        self.vat_code = vat_code

    @property
    def configured(self) -> bool:
        return bool(self.shop_id and self.secret_key)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        if not self.configured:
            raise YooKassaError("Не заданы YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                auth=(self.shop_id, self.secret_key),
                timeout=self.TIMEOUT,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise YooKassaError(f"ЮKassa недоступна: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code >= 400:
            raise YooKassaError(data.get("description") or f"ЮKassa вернула {response.status_code}")
        return data

    def create_payment(
            self,
            amount: int,
            order_id: str,
            description: str,
            return_url: str,
            customer_email: Optional[str] = None,
            payment_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создаёт платёж с автосписанием (capture=true).

        amount - в копейках. order_id - наш номер заказа: уходит в metadata
        и служит ключом идемпотентности, так что повтор запроса не создаст второй платёж.
        """
        value = kopecks_to_value(amount)
        # ЮKassa ограничивает описание 128 символами
        description = description[:128]
        body: Dict[str, Any] = {
            "amount": {"value": value, "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description,
            "metadata": {"order_id": order_id},
        }

        method_type = PAYMENT_METHOD_TYPES.get(payment_method or "")
        if method_type:
            body["payment_method_data"] = {"type": method_type}

        if self.send_receipt and customer_email:
            body["receipt"] = {
                "customer": {"email": customer_email},
                "items": [{
                    "description": description,
                    "quantity": "1.00",
                    "amount": {"value": value, "currency": "RUB"},
                    "vat_code": self.vat_code,
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }],
            }

        return self._request(
            "POST",
            "/payments",
            json=body,
            headers={"Idempotence-Key": order_id},
        )

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """Актуальное состояние платежа - единственный источник правды о статусе."""
        return self._request("GET", f"/payments/{payment_id}")
