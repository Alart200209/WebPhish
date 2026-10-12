"""
Тесты для модуля TinkoffPayment
"""
import pytest
from unittest.mock import patch, MagicMock
from api.payment import TinkoffPayment


@pytest.fixture
def payment_service():
    """Фикстура для создания экземпляра TinkoffPayment"""
    return TinkoffPayment(
        terminal_key="test_terminal_key",
        secret_key="test_secret_key"
    )


class TestTokenGeneration:
    """Тесты генерации токена"""

    def test_generate_token_returns_string(self, payment_service):
        """Токен должен быть строкой"""
        params = {
            "Amount": 10000,
            "OrderId": "test_order_123",
            "Description": "Test payment"
        }

        token = payment_service._generate_token(params)

        assert isinstance(token, str)
        assert len(token) == 64  # SHA256 = 64 символа

    def test_generate_token_is_deterministic(self, payment_service):
        """Одинаковые параметры должны давать одинаковый токен"""
        params = {
            "Amount": 10000,
            "OrderId": "test_order_123",
            "Description": "Test payment"
        }

        token1 = payment_service._generate_token(params)
        token2 = payment_service._generate_token(params)

        assert token1 == token2

    def test_generate_token_different_for_different_params(self, payment_service):
        """Разные параметры должны давать разные токены"""
        params1 = {"Amount": 10000, "OrderId": "order_1"}
        params2 = {"Amount": 20000, "OrderId": "order_2"}

        token1 = payment_service._generate_token(params1)
        token2 = payment_service._generate_token(params2)

        assert token1 != token2

    def test_generate_token_excludes_receipt(self, payment_service):
        """Receipt не должен участвовать в генерации токена"""
        params1 = {"Amount": 10000, "OrderId": "order_1"}
        params2 = {
            "Amount": 10000,
            "OrderId": "order_1",
            "Receipt": {"Items": []}
        }

        token1 = payment_service._generate_token(params1)
        token2 = payment_service._generate_token(params2)

        assert token1 == token2

    def test_generate_token_handles_boolean(self, payment_service):
        """Boolean значения должны конвертироваться в 'true'/'false'"""
        params = {
            "Amount": 10000,
            "OrderId": "order_1",
            "Recurrent": True
        }

        token = payment_service._generate_token(params)

        assert isinstance(token, str)
        assert len(token) == 64


class TestInitPayment:
    """Тесты инициализации платежа"""

    @patch('api.payment.requests.post')
    def test_init_payment_success(self, mock_post, payment_service):
        """Успешная инициализация платежа"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Success": True,
            "PaymentId": 123456789,
            "OrderId": "test_order_123",
            "PaymentURL": "https://securepay.tinkoff.ru/pay"
        }
        mock_post.return_value = mock_response

        result = payment_service.init_payment(
            amount=29900,
            order_id="test_order_123",
            description="Подписка Pro"
        )

        assert result["Success"] is True
        assert result["PaymentId"] == 123456789
        assert "PaymentURL" in result

        # Проверяем, что запрос был отправлен на правильный URL
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "Init" in call_args[0][0]

    @patch('api.payment.requests.post')
    def test_init_payment_with_receipt(self, mock_post, payment_service):
        """Инициализация платежа с чеком"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"Success": True}
        mock_post.return_value = mock_response

        receipt = {
            "Email": "test@example.com",
            "Taxation": "osn",
            "Items": [
                {
                    "Name": "Подписка",
                    "Price": 29900,
                    "Quantity": 1,
                    "Amount": 29900,
                    "Tax": "none"
                }
            ]
        }

        result = payment_service.init_payment(
            amount=29900,
            order_id="test_order_123",
            description="Подписка Pro",
            receipt=receipt
        )

        assert result["Success"] is True

        # Проверяем, что Receipt был передан
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]
        assert "Receipt" in request_data

    @patch('api.payment.requests.post')
    def test_init_payment_failure(self, mock_post, payment_service):
        """Обработка ошибки инициализации"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Success": False,
            "Message": "Invalid TerminalKey"
        }
        mock_post.return_value = mock_response

        result = payment_service.init_payment(
            amount=29900,
            order_id="test_order_123",
            description="Test"
        )

        assert result["Success"] is False
        assert "Invalid" in result["Message"]


class TestGetState:
    """Тесты получения статуса платежа"""

    @patch('api.payment.requests.post')
    def test_get_state_success(self, mock_post, payment_service):
        """Успешное получение статуса"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Success": True,
            "Status": "CONFIRMED",
            "Amount": 29900
        }
        mock_post.return_value = mock_response

        result = payment_service.get_state("123456789")

        assert result["Success"] is True
        assert result["Status"] == "CONFIRMED"
        assert result["Amount"] == 29900


class TestCancelPayment:
    """Тесты отмены платежа"""

    @patch('api.payment.requests.post')
    def test_cancel_payment_full(self, mock_post, payment_service):
        """Полная отмена платежа"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Success": True,
            "Status": "REVERSED"
        }
        mock_post.return_value = mock_response

        result = payment_service.cancel_payment("123456789")

        assert result["Success"] is True

    @patch('api.payment.requests.post')
    def test_cancel_payment_partial(self, mock_post, payment_service):
        """Частичная отмена платежа"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"Success": True}
        mock_post.return_value = mock_response

        result = payment_service.cancel_payment(
            payment_id="123456789",
            amount=10000
        )

        assert result["Success"] is True

        # Проверяем, что Amount был передан
        call_args = mock_post.call_args
        request_data = call_args[1]["json"]
        assert request_data["Amount"] == 10000


class TestWebhookSignature:
    """Тесты проверки подписи webhook"""

    def test_verify_valid_signature(self, payment_service):
        """Проверка валидной подписи"""
        data = {
            "Amount": 29900,
            "OrderId": "test_order_123",
            "Status": "CONFIRMED"
        }

        # Генерируем правильный токен
        data["Token"] = payment_service._generate_token(data)

        result = payment_service.verify_webhook_signature(data)

        assert result is True

    def test_verify_invalid_signature(self, payment_service):
        """Проверка невалидной подписи"""
        data = {
            "Amount": 29900,
            "OrderId": "test_order_123",
            "Status": "CONFIRMED",
            "Token": "invalid_token_123456"
        }

        result = payment_service.verify_webhook_signature(data)

        assert result is False

    def test_verify_missing_token(self, payment_service):
        """Проверка при отсутствии токена"""
        data = {
            "Amount": 29900,
            "OrderId": "test_order_123"
        }

        result = payment_service.verify_webhook_signature(data)

        assert result is False