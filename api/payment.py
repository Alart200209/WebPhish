import hashlib
import json
import requests
from typing import Optional, Dict, Any


class TinkoffPayment:
    """
    Интеграция с Tinkoff Касса API
    Документация: https://www.tinkoff.ru/kassa/dev/api/
    """

    BASE_URL = "https://securepay.tinkoff.ru/v2/"

    def __init__(self, terminal_key: str, secret_key: str):
        self.terminal_key = terminal_key
        self.secret_key = secret_key

    def _generate_token(self, params: Dict[str, Any]) -> str:
        """
        Генерация токена для подписи запроса
        """
        # Добавляем TerminalKey
        params_copy = params.copy()
        params_copy["TerminalKey"] = self.terminal_key

        # Сортируем по ключам
        sorted_params = sorted(params_copy.items())

        # Конкатенируем значения в строку
        values_string = ""
        for key, value in sorted_params:
            if key != "Token" and key != "Receipt":
                if isinstance(value, bool):
                    values_string += "true" if value else "false"
                elif isinstance(value, (int, float)):
                    values_string += str(value)
                elif isinstance(value, str):
                    values_string += value

        # Добавляем секретный ключ
        values_string += self.secret_key

        # SHA256 хеш
        token = hashlib.sha256(values_string.encode("utf-8")).hexdigest()

        return token

    def init_payment(
            self,
            amount: int,
            order_id: str,
            description: str,
            customer_email: Optional[str] = None,
            customer_phone: Optional[str] = None,
            receipt: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Инициализация платежа

        Args:
            amount: Сумма в копейках
            order_id: Уникальный идентификатор заказа
            description: Описание платежа
            customer_email: Email клиента
            customer_phone: Телефон клиента
            receipt: Чек (для 54-ФЗ)

        Returns:
            Ответ от Tinkoff API
        """
        params = {
            "Amount": amount,
            "OrderId": order_id,
            "Description": description,
            "TerminalKey": self.terminal_key,
        }

        if customer_email:
            params["CustomerKey"] = customer_email

        if receipt:
            params["Receipt"] = receipt

        # Генерируем токен
        params["Token"] = self._generate_token(params)

        # Отправляем запрос
        response = requests.post(
            f"{self.BASE_URL}Init",
            json=params,
            headers={"Content-Type": "application/json"}
        )

        return response.json()

    def confirm_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Подтверждение платежа
        """
        params = {
            "PaymentId": payment_id,
            "TerminalKey": self.terminal_key
        }

        params["Token"] = self._generate_token(params)

        response = requests.post(
            f"{self.BASE_URL}Confirm",
            json=params,
            headers={"Content-Type": "application/json"}
        )

        return response.json()

    def cancel_payment(self, payment_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """
        Отмена платежа
        """
        params = {
            "PaymentId": payment_id,
            "TerminalKey": self.terminal_key
        }

        if amount:
            params["Amount"] = amount

        params["Token"] = self._generate_token(params)

        response = requests.post(
            f"{self.BASE_URL}Cancel",
            json=params,
            headers={"Content-Type": "application/json"}
        )

        return response.json()

    def get_state(self, payment_id: str) -> Dict[str, Any]:
        """
        Получение статуса платежа
        """
        params = {
            "PaymentId": payment_id,
            "TerminalKey": self.terminal_key
        }

        params["Token"] = self._generate_token(params)

        response = requests.post(
            f"{self.BASE_URL}GetState",
            json=params,
            headers={"Content-Type": "application/json"}
        )

        return response.json()

    def verify_webhook_signature(self, data: Dict[str, Any]) -> bool:
        """
        Проверка подписи webhook от Tinkoff
        """
        # Получаем токен из данных
        received_token = data.get("Token")

        if not received_token:
            return False

        # Генерируем ожидаемый токен
        params = data.copy()
        expected_token = self._generate_token(params)

        return received_token == expected_token