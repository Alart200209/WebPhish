"""
Тесты для FastAPI endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Добавляем api в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app


@pytest.fixture
def client():
    """Фикстура тестового клиента"""
    return TestClient(app)


class TestHealthEndpoint:
    """Тесты health check"""

    def test_health_check(self, client):
        """Health endpoint должен возвращать OK"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "PhishDet API"


class TestPaymentCreateEndpoint:
    """Тесты создания платежа"""

    @patch('api.main.payment_service')
    def test_create_payment_success(self, mock_payment, client):
        """Успешное создание платежа"""
        mock_payment.init_payment.return_value = {
            "Success": True,
            "PaymentId": 123456789,
            "OrderId": "test_order_123",
            "PaymentURL": "https://securepay.tinkoff.ru/pay"
        }

        payload = {
            "amount": 29900,
            "order_id": "test_order_123",
            "description": "Подписка Pro",
            "customer": {
                "name": "Иван Иванов",
                "email": "test@example.com",
                "phone": "+79991234567"
            },
            "plan": "pro",
            "trial": False,
            "payment_method": "card"
        }

        response = client.post("/api/payment/create", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "payment_url" in data
        assert data["payment_id"] == "123456789"

    @patch('api.main.payment_service')
    def test_create_payment_failure(self, mock_payment, client):
        """Обработка ошибки создания платежа"""
        mock_payment.init_payment.return_value = {
            "Success": False,
            "Message": "Invalid amount"
        }

        payload = {
            "amount": 0,
            "order_id": "test_order_123",
            "description": "Test",
            "customer": {
                "email": "test@example.com"
            },
            "plan": "pro",
            "trial": False,
            "payment_method": "card"
        }

        response = client.post("/api/payment/create", json=payload)

        assert response.status_code >= 400

    def test_create_payment_invalid_payload(self, client):
        """Валидация payload"""
        # Отсутствует обязательное поле
        payload = {
            "description": "Test"
        }

        response = client.post("/api/payment/create", json=payload)

        assert response.status_code == 422  # Validation error

    @patch('api.main.payment_service')
    def test_create_payment_with_trial(self, mock_payment, client):
        """Создание платежа с триалом (0 рублей)"""
        mock_payment.init_payment.return_value = {
            "Success": True,
            "PaymentId": 123456789,
            "PaymentURL": "https://securepay.tinkoff.ru/pay"
        }

        payload = {
            "amount": 0,
            "order_id": "trial_order_123",
            "description": "Trial Pro",
            "customer": {
                "email": "test@example.com"
            },
            "plan": "pro",
            "trial": True,
            "payment_method": "card"
        }

        response = client.post("/api/payment/create", json=payload)

        assert response.status_code == 200


class TestPaymentWebhookEndpoint:
    """Тесты webhook endpoint"""

    def test_webhook_success(self, client):
        """Успешная обработка webhook"""
        payload = {
            "OrderId": "test_order_123",
            "Status": "CONFIRMED",
            "Amount": 29900,
            "PaymentId": 123456789
        }

        response = client.post("/api/payment/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_webhook_empty_payload(self, client):
        """Webhook с пустым payload"""
        response = client.post("/api/payment/webhook", json={})

        assert response.status_code == 200


class TestPaymentStatusEndpoint:
    """Тесты получения статуса платежа"""

    @patch('api.main.payment_service')
    def test_get_payment_status_success(self, mock_payment, client):
        """Успешное получение статуса"""
        mock_payment.get_state.return_value = {
            "Success": True,
            "Status": "CONFIRMED",
            "Amount": 29900
        }

        response = client.get("/api/payment/status/123456789")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "CONFIRMED"
        assert data["amount"] == 29900

    @patch('api.main.payment_service')
    def test_get_payment_status_not_found(self, mock_payment, client):
        """Платеж не найден"""
        mock_payment.get_state.return_value = {
            "Success": False,
            "Message": "Payment not found"
        }

        response = client.get("/api/payment/status/999999999")

        assert response.status_code >= 400