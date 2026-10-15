"""
Тесты для FastAPI endpoints
"""
import pytest
from fastapi.testclient import TestClient
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


class TestPaymentEndpointsRequireAuth:
    """Оплата и статус платежа - только для вошедших пользователей"""

    def test_create_payment_requires_auth(self, client):
        response = client.post("/api/payment/create", json={"amount": 29900, "plan": "pro"})
        assert response.status_code == 401

    def test_payment_status_requires_auth(self, client):
        response = client.get("/api/payment/status/phishdet_1_abc")
        assert response.status_code == 401


class TestPaymentWebhookEndpoint:
    """HTTP-уведомления ЮKassa"""

    def test_webhook_ignores_non_payment_events(self, client):
        """Возвраты и прочие события пока не обрабатываются, но ЮKassa получает 200"""
        payload = {"type": "notification", "event": "refund.succeeded", "object": {"id": "r-1"}}
        response = client.post("/api/payment/webhook", json=payload)
        assert response.status_code == 200

    def test_webhook_empty_payload(self, client):
        response = client.post("/api/payment/webhook", json={})
        assert response.status_code == 200

    def test_webhook_unknown_payment(self, client):
        """Платёж не наш - отвечаем 200, чтобы ЮKassa не повторяла уведомление"""
        payload = {"type": "notification", "event": "payment.succeeded", "object": {"id": "unknown-id"}}
        response = client.post("/api/payment/webhook", json=payload)
        assert response.status_code == 200

    def test_webhook_not_json(self, client):
        response = client.post("/api/payment/webhook", content=b"not json")
        assert response.status_code == 400
