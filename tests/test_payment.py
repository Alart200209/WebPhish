"""
Тесты для клиента ЮKassa
"""
import pytest
from unittest.mock import patch, MagicMock

import requests

from api.payment import YooKassaClient, YooKassaError, kopecks_to_value, value_to_kopecks


@pytest.fixture
def client():
    """Тестовый магазин ЮKassa"""
    return YooKassaClient(shop_id="123456", secret_key="test_secret")


def make_response(status_code=200, data=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data if data is not None else {}
    return response


class TestAmountConversion:
    """Копейки <-> строка в рублях"""

    @pytest.mark.parametrize("kopecks,value", [(9900, "99.00"), (29900, "299.00"), (499000, "4990.00"), (1, "0.01")])
    def test_kopecks_to_value(self, kopecks, value):
        assert kopecks_to_value(kopecks) == value

    @pytest.mark.parametrize("value,kopecks", [("99.00", 9900), ("4990.00", 499000), ("0.10", 10), (299, 29900)])
    def test_value_to_kopecks(self, value, kopecks):
        assert value_to_kopecks(value) == kopecks

    @pytest.mark.parametrize("value", [None, "abc", "99.001"])
    def test_value_to_kopecks_invalid(self, value):
        assert value_to_kopecks(value) is None


class TestCreatePayment:
    """Создание платежа"""

    @patch("api.payment.requests.request")
    def test_request_body(self, mock_request, client):
        mock_request.return_value = make_response(200, {
            "id": "2d3b-000f", "status": "pending",
            "confirmation": {"type": "redirect", "confirmation_url": "https://yoomoney.ru/checkout/x"},
        })

        result = client.create_payment(
            amount=29900,
            order_id="phishdet_1_abc",
            description="Подписка Про",
            return_url="http://127.0.0.1:8000/payment-result.html?order=phishdet_1_abc",
            customer_email="user@example.com",
            payment_method="sbp",
        )

        assert result["confirmation"]["confirmation_url"] == "https://yoomoney.ru/checkout/x"
        method, url = mock_request.call_args.args
        kwargs = mock_request.call_args.kwargs
        assert method == "POST"
        assert url == "https://api.yookassa.ru/v3/payments"
        assert kwargs["auth"] == ("123456", "test_secret")
        assert kwargs["headers"]["Idempotence-Key"] == "phishdet_1_abc"

        body = kwargs["json"]
        assert body["amount"] == {"value": "299.00", "currency": "RUB"}
        assert body["capture"] is True
        assert body["confirmation"]["return_url"].endswith("order=phishdet_1_abc")
        assert body["metadata"] == {"order_id": "phishdet_1_abc"}
        assert body["payment_method_data"] == {"type": "sbp"}
        assert body["receipt"]["customer"] == {"email": "user@example.com"}
        assert body["receipt"]["items"][0]["amount"]["value"] == "299.00"

    @patch("api.payment.requests.request")
    def test_card_and_unknown_method(self, mock_request, client):
        mock_request.return_value = make_response(200, {"id": "1"})

        client.create_payment(29900, "o1", "d", "http://x", payment_method="card")
        assert mock_request.call_args.kwargs["json"]["payment_method_data"] == {"type": "bank_card"}

        client.create_payment(29900, "o2", "d", "http://x", payment_method="crypto")
        assert "payment_method_data" not in mock_request.call_args.kwargs["json"]

    @patch("api.payment.requests.request")
    def test_without_receipt(self, mock_request):
        no_receipt = YooKassaClient("123456", "test_secret", send_receipt=False)
        mock_request.return_value = make_response(200, {"id": "1"})

        no_receipt.create_payment(9900, "o1", "d", "http://x", customer_email="user@example.com")
        assert "receipt" not in mock_request.call_args.kwargs["json"]

    @patch("api.payment.requests.request")
    def test_long_description_trimmed(self, mock_request, client):
        mock_request.return_value = make_response(200, {"id": "1"})
        client.create_payment(9900, "o1", "x" * 300, "http://x")
        assert len(mock_request.call_args.kwargs["json"]["description"]) == 128

    @patch("api.payment.requests.request")
    def test_api_error(self, mock_request, client):
        mock_request.return_value = make_response(401, {"type": "error", "description": "Authentication failed"})
        with pytest.raises(YooKassaError, match="Authentication failed"):
            client.create_payment(9900, "o1", "d", "http://x")

    @patch("api.payment.requests.request")
    def test_network_error(self, mock_request, client):
        mock_request.side_effect = requests.ConnectionError("down")
        with pytest.raises(YooKassaError):
            client.create_payment(9900, "o1", "d", "http://x")

    def test_not_configured(self):
        with pytest.raises(YooKassaError):
            YooKassaClient("", "").create_payment(9900, "o1", "d", "http://x")


class TestGetPayment:
    """Получение статуса платежа"""

    @patch("api.payment.requests.request")
    def test_get_payment(self, mock_request, client):
        mock_request.return_value = make_response(200, {"id": "2d3b", "status": "succeeded", "paid": True})

        result = client.get_payment("2d3b")

        assert result["status"] == "succeeded"
        method, url = mock_request.call_args.args
        assert method == "GET"
        assert url == "https://api.yookassa.ru/v3/payments/2d3b"
