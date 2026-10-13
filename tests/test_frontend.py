"""
E2E тесты фронтенда через Playwright
"""
from playwright.sync_api import sync_playwright, expect
from fastapi.testclient import TestClient
import re
import subprocess
import time
import os
import pytest
import urllib.request

from api.main import app

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def server():
    """Умный запуск сервера перед тестами"""
    # 1. Проверяем, не запущен ли сервер уже вручную в другом окне
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1)
        print("\n✅ [INFO] Сервер уже запущен на порту 8000. Используем его.")
        yield None
        return
    except Exception:
        pass

    # 2. Запускаем сервер принудительно
    print("\n⏳ [INFO] Запускаем тестовый сервер на порту 8000...")
    process = subprocess.Popen(
        ["uvicorn", "api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(__file__)),
        shell=True  # Критически важно для Windows!
    )

    # 3. Ждем, пока сервер ДЕЙСТВИТЕЛЬНО ответит (максимум 15 секунд)
    for _ in range(15):
        time.sleep(1)
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=1)
            print("✅ [INFO] Сервер успешно запущен и готов к тестам!")
            break
        except Exception:
            continue
    else:
        print("❌ [ERROR] Не удалось запустить сервер за 15 секунд.")
        process.terminate()
        raise RuntimeError("Не удалось запустить сервер для тестов. Проверьте, свободен ли порт 8000.")

    yield process

    # 4. Корректно останавливаем сервер после всех тестов
    print("\n🛑 [INFO] Останавливаем тестовый сервер...")
    process.terminate()
    process.wait()


@pytest.fixture
def browser():
    """Фикстура браузера"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    """Фикстура страницы"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="session")
def client():
    """HTTP-клиент для API-подготовки тестовых данных (регистрация и т.п.)"""
    return TestClient(app)


# ==========================================
# ВСЕ КЛАССЫ ТЕПЕРЬ НА ОДНОМ УРОВНЕ (БЕЗ ВЛОЖЕННОСТИ)
# ==========================================

class TestIndexPage:
    """Тесты главной страницы"""

    def test_page_loads(self, page, server):
        page.goto(BASE_URL)
        expect(page).to_have_title("PhishDet — проверка ссылок на фишинг перед открытием")

    def test_header_visible(self, page, server):
        page.goto(BASE_URL)
        header = page.locator(".header")
        expect(header).to_be_visible()

    def test_logo_clickable(self, page, server):
        page.goto(BASE_URL)
        logo = page.locator("header .logo").first
        expect(logo).to_be_visible()
        expect(logo).to_be_enabled()

    def test_hero_section_visible(self, page, server):
        page.goto(BASE_URL)
        hero = page.locator(".hero")
        expect(hero).to_be_visible()

    def test_checker_form_exists(self, page, server):
        page.goto(BASE_URL)
        form = page.locator("#checkerForm")
        expect(form).to_be_visible()

    def test_checker_input_placeholder(self, page, server):
        page.goto(BASE_URL)
        input_field = page.locator("#urlInput")
        expect(input_field).to_have_attribute("placeholder", "Вставьте ссылку для проверки...")

    def test_pricing_section_visible(self, page, server):
        page.goto(BASE_URL)
        pricing = page.locator("#pricing")
        expect(pricing).to_be_visible()

    def test_pricing_cards_count(self, page, server):
        page.goto(BASE_URL)
        cards = page.locator(".pricing-card")
        expect(cards).to_have_count(3)

    def test_pricing_buttons_link_to_pricing_page(self, page, server):
        page.goto(BASE_URL)
        pro_button = page.locator(".pricing-card.featured .pricing-btn")
        href = pro_button.get_attribute("href")
        assert "pricing.html" in href
        assert "plan=pro" in href

    def test_faq_accordion_works(self, page, server):
        page.goto(BASE_URL)
        first_question = page.locator(".faq-question").first
        first_question.click()
        faq_item = page.locator(".faq-item").first
        expect(faq_item).to_have_class(re.compile(r".*active.*"))

    def test_footer_visible(self, page, server):
        page.goto(BASE_URL)
        footer = page.locator(".footer")
        expect(footer).to_be_visible()


class TestPricingPage:
    """Тесты страницы тарифов"""

    def test_pricing_page_loads(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html")
        expect(page).to_have_title("Тарифы — PhishDet")

    def test_plan_cards_present(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html")
        expect(page.locator("#free")).to_be_visible()
        expect(page.locator("#pro")).to_be_visible()
        expect(page.locator("#business")).to_be_visible()

    def test_plan_prices_correct(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html")
        expect(page.locator("#free .plan-price")).to_contain_text("0 ₽")
        expect(page.locator("#pro .plan-price")).to_contain_text("299 ₽")
        expect(page.locator("#business .plan-price")).to_contain_text("1 990 ₽")

    def test_checkout_buttons_link(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html")
        pro_button = page.locator("#pro .plan-cta .btn-primary")
        href = pro_button.get_attribute("href")
        assert "checkout.html" in href
        assert "plan=pro" in href

    def test_free_plan_cta_goes_to_register_not_checkout(self, page, server):
        """Бесплатный тариф не должен вести на оплату — только регистрация."""
        page.goto(f"{BASE_URL}/pricing.html")
        free_button = page.locator("#free .plan-cta a")
        href = free_button.get_attribute("href")
        assert "auth.html" in href
        assert "checkout" not in href

    def test_comparison_table_visible(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html")
        table = page.locator(".comparison-table")
        expect(table).to_be_visible()

    def test_scroll_to_plan_from_url(self, page, server):
        page.goto(f"{BASE_URL}/pricing.html?plan=pro")
        pro_plan = page.locator("#pro")
        expect(pro_plan).to_be_in_viewport()


class TestCheckoutPage:
    """Тесты страницы оплаты"""

    def test_checkout_page_loads(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")
        expect(page).to_have_title("Оплата — PhishDet")

    def test_plan_info_displayed(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")
        expect(page.locator("#planName")).to_contain_text("Про")
        expect(page.locator("#totalPrice")).to_contain_text("299 ₽")

    def test_form_fields_present(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")
        expect(page.locator("#firstName")).to_be_visible()
        expect(page.locator("#lastName")).to_be_visible()
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#phone")).to_be_visible()

    def test_payment_methods_present(self, page, server):
        """Способы оплаты должны быть на странице"""
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")

        # Проверяем видимые label, так как сами input скрыты через CSS (display: none)
        expect(page.locator('label:has-text("Банковская карта")')).to_be_visible()
        expect(page.locator('label:has-text("СБП")')).to_be_visible()

    def test_submit_button_disabled_without_terms(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")
        page.fill("#firstName", "Иван")
        page.fill("#lastName", "Иванов")
        page.fill("#email", "test@example.com")

        submit_btn = page.locator("#submitBtn")
        submit_btn.click()

        modal = page.locator("#successModal")
        expect(modal).not_to_be_visible()

    def test_free_plan_zero_price(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=free")
        expect(page.locator("#totalPrice")).to_contain_text("0 ₽")

    def test_business_plan_price(self, page, server):
        """Бизнес план должен показывать 1990 рублей"""
        page.goto(f"{BASE_URL}/checkout.html?plan=business")

        # JS выводит "1990 ₽" без пробела между цифрами
        expect(page.locator("#totalPrice")).to_contain_text("1990 ₽")

    def test_security_notice_visible(self, page, server):
        page.goto(f"{BASE_URL}/checkout.html?plan=pro")
        expect(page.locator(".security-notice")).to_be_visible()


# ==========================================
# Тесты проверки URL.
# Проверка требует авторизации (лимиты привязаны к аккаунту),
# поэтому регистрируем тестового пользователя через API и подставляем
# токен в localStorage браузера.
# ==========================================

import json


def _register_test_user(client):
    """Регистрирует нового пользователя и возвращает access_token."""
    import time
    email = f"e2e_{int(time.time() * 1000)}@example.com"
    response = client.post("/api/auth/register", json={
        "email": email,
        "password": "TestPass123!",
    })
    assert response.status_code in (200, 201), response.text
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture
def authed_page(page, server, client):
    """Страница с авторизованным пользователем."""
    token = _register_test_user(client)
    page.goto(BASE_URL)
    page.evaluate(f"localStorage.setItem('access_token', '{token}')")
    page.goto(BASE_URL)
    return page


class TestURLChecker:
    """Тесты проверки URL"""

    def test_safe_url(self, authed_page):
        page = authed_page
        page.fill("#urlInput", "https://google.com")
        page.click('button[type="submit"]')

        result = page.locator("#checker-result")
        expect(result).to_be_visible(timeout=5000)

        result_title = page.locator(".result-title").first
        expect(result_title).to_contain_text("безопасн", ignore_case=True)

    def test_suspicious_url(self, authed_page):
        page = authed_page
        page.fill("#urlInput", "http://secure-login-bank-verify.ru")
        page.click('button[type="submit"]')

        result = page.locator("#checker-result")
        expect(result).to_be_visible(timeout=5000)

        result_title = page.locator(".result-title").first
        expect(result_title).to_contain_text("риск", ignore_case=True)

    def test_empty_url_validation(self, authed_page):
        page = authed_page
        page.click('button[type="submit"]')

        result = page.locator("#checker-result")
        expect(result).not_to_be_visible()


class TestResponsive:
    """Тесты адаптивности"""

    def test_mobile_view(self, page, server):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(BASE_URL)
        mobile_toggle = page.locator(".mobile-toggle")
        expect(mobile_toggle).to_be_visible()

    def test_tablet_view(self, page, server):
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(BASE_URL)
        hero = page.locator(".hero")
        expect(hero).to_be_visible()

    def test_desktop_view(self, page, server):
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(BASE_URL)
        nav = page.locator(".nav")
        expect(nav).to_be_visible()