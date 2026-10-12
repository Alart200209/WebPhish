"""
Конфигурация pytest
"""
import pytest
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_configure(config):
    """Настройка pytest"""
    config.addinivalue_line(
        "markers", "slow: помечает тесты как медленные"
    )
    config.addinivalue_line(
        "markers", "integration: интеграционные тесты"
    )


@pytest.fixture(scope="session")
def test_data():
    """Тестовые данные"""
    return {
        "valid_email": "test@example.com",
        "valid_phone": "+79991234567",
        "valid_amount": 29900,
        "plans": {
            "free": {"price": 0, "name": "Бесплатный"},
            "pro": {"price": 299, "name": "Про"},
            "business": {"price": 1990, "name": "Бизнес"}
        }
    }