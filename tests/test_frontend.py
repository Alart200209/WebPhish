"""
E2E тесты фронтенда через Playwright
"""
import pytest
from playwright.sync_api import sync_playwright, expect
import subprocess
import time
import signal
import os

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="session")
def server():
    """Запуск сервера перед тестами"""
    # Запускаем сервер в отдельном процессе
    process = subprocess.Popen(
        ["uvicorn", "api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.dirname(__file__))
    )

    # Ждем, пока сервер запустится
    time.sleep(3)

    yield process

    # Останавливаем сервер после тестов
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


class TestIndexPage:
    """Тесты главной страницы"""

    def test_page_loads(self, page, server):
        """Главная страница должна загружаться"""
        page.goto(BASE_URL)

        expect(page).to_have_title("PhishDet — Защита от фишинговых ссылок с помощью ИИ")

    def test_header_visible(self, page, server):
        """Header должен быть виден"""
        page.goto(BASE_URL)

        header = page.locator(".header")
        expect(header).to_be_visible()

    def test_logo_clickable(self, page, server):
        """Логотип должен быть кликабельным"""
        page.goto(BASE_URL)

        logo = page.locator(".logo")
        expect(logo).to_be_visible()
        expect(logo).to_be_enabled()

    def test_hero_section_visible(self, page, server):
        """Hero секция должна быть видна"""
        page.goto(BASE_URL)

        hero = page.locator(".hero")
        expect(hero).to_be_visible()

    def test_checker_form_exists(self, page, server):
        """Форма проверки должна существовать"""
        page.goto(BASE_URL)

        form = page.locator("#checkerForm")
        expect(form).to_be_visible()

    def test_checker_input_placeholder(self, page, server):
        """Input должен иметь placeholder"""
        page.goto(BASE_URL)

        input_field = page.locator("#urlInput")
        expect(input_field).to_have_attribute(
            "placeholder",
            "Вставьте ссылку для проверку..."
        )

    def test_pricing_section_visible(self, page, server):
        """Секция тарифов должна быть видна"""
        page.goto(BASE_URL)

        pricing = page.locator("#pricing")
        expect(pricing).to_be_visible()

    def test_pricing_cards_count(self, page, server):
        """Должно быть 3 карточки тарифов"""
        page.goto(BASE_URL)

        cards = page.locator(".pricing-card")
        expect(cards).to_have_count(3)

    def test_pricing_buttons_link_to_pricing_page(self, page, server):
        """Кнопки тарифов должны вести на страницу тарифов"""
        page.goto(BASE_URL)

        pro_button = page.locator(".pricing-card.featured .pricing-btn")
        href = pro_button.get_attribute("href")

        assert "pricing.html" in href
        assert "plan=pro" in href

    def test_faq_accordion_works(self, page, server):
        """FAQ аккордеон должен работать"""
        page.goto(BASE_URL)

        first_question = page.locator(".faq-question").first
        first_question.click()

        faq_item = page.locator(".faq-item").first
        expect(faq_item).to_have_class( / active /)

        def test_footer_visible(self, page, server):
            """Footer должен быть виден"""
            page.goto(BASE_URL)

            footer = page.locator(".footer")
            expect(footer).to_be_visible()

    class TestPricingPage:
        """Тесты страницы тарифов"""

        def test_pricing_page_loads(self, page, server):
            """Страница тарифов должна загружаться"""
            page.goto(f"{BASE_URL}/pricing.html")

            expect(page).to_have_title("Тарифы — PhishDet")

        def test_plan_cards_present(self, page, server):
            """Все карточки планов должны быть на странице"""
            page.goto(f"{BASE_URL}/pricing.html")

            free_plan = page.locator("#free")
            pro_plan = page.locator("#pro")
            business_plan = page.locator("#business")

            expect(free_plan).to_be_visible()
            expect(pro_plan).to_be_visible()
            expect(business_plan).to_be_visible()

        def test_plan_prices_correct(self, page, server):
            """Цены должны быть корректными"""
            page.goto(f"{BASE_URL}/pricing.html")

            free_price = page.locator("#free .plan-price")
            expect(free_price).to_contain_text("0 ₽")

            pro_price = page.locator("#pro .plan-price")
            expect(pro_price).to_contain_text("299 ₽")

            business_price = page.locator("#business .plan-price")
            expect(business_price).to_contain_text("1 990 ₽")

        def test_checkout_buttons_link(self, page, server):
            """Кнопки должны вести на checkout"""
            page.goto(f"{BASE_URL}/pricing.html")

            pro_button = page.locator("#pro .plan-cta .btn-primary")
            href = pro_button.get_attribute("href")

            assert "checkout.html" in href
            assert "plan=pro" in href

        def test_comparison_table_visible(self, page, server):
            """Таблица сравнения должна быть видна"""
            page.goto(f"{BASE_URL}/pricing.html")

            table = page.locator(".comparison-table")
            expect(table).to_be_visible()

        def test_scroll_to_plan_from_url(self, page, server):
            """Должна быть прокрутка к плану из URL параметра"""
            page.goto(f"{BASE_URL}/pricing.html?plan=pro")

            pro_plan = page.locator("#pro")
            expect(pro_plan).to_be_in_viewport()

    class TestCheckoutPage:
        """Тесты страницы оплаты"""

        def test_checkout_page_loads(self, page, server):
            """Страница оплаты должна загружаться"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            expect(page).to_have_title("Оплата — PhishDet")

        def test_plan_info_displayed(self, page, server):
            """Информация о плане должна отображаться"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            plan_name = page.locator("#planName")
            expect(plan_name).to_contain_text("Про")

            total_price = page.locator("#totalPrice")
            expect(total_price).to_contain_text("299 ₽")

        def test_form_fields_present(self, page, server):
            """Все поля формы должны быть на странице"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            expect(page.locator("#firstName")).to_be_visible()
            expect(page.locator("#lastName")).to_be_visible()
            expect(page.locator("#email")).to_be_visible()
            expect(page.locator("#phone")).to_be_visible()

        def test_payment_methods_present(self, page, server):
            """Способы оплаты должны быть на странице"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            card_method = page.locator('input[name="paymentMethod"][value="card"]')
            sbp_method = page.locator('input[name="paymentMethod"][value="sbp"]')

            expect(card_method).to_be_visible()
            expect(sbp_method).to_be_visible()

        def test_submit_button_disabled_without_terms(self, page, server):
            """Кнопка отправки должна быть неактивна без согласия с условиями"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            # Заполняем форму
            page.fill("#firstName", "Иван")
            page.fill("#lastName", "Иванов")
            page.fill("#email", "test@example.com")

            submit_btn = page.locator("#submitBtn")

            # Пытаемся отправить без чекбокса
            submit_btn.click()

            # Форма не должна отправиться (браузер покажет ошибку)
            # Проверяем, что модалка не появилась
            modal = page.locator("#successModal")
            expect(modal).not_to_be_visible()

        def test_free_plan_zero_price(self, page, server):
            """Бесплатный план должен показывать 0 рублей"""
            page.goto(f"{BASE_URL}/checkout.html?plan=free")

            total_price = page.locator("#totalPrice")
            expect(total_price).to_contain_text("0 ₽")

        def test_business_plan_price(self, page, server):
            """Бизнес план должен показывать 1990 рублей"""
            page.goto(f"{BASE_URL}/checkout.html?plan=business")

            total_price = page.locator("#totalPrice")
            expect(total_price).to_contain_text("1 990 ₽")

        def test_security_notice_visible(self, page, server):
            """Уведомление о безопасности должно быть видно"""
            page.goto(f"{BASE_URL}/checkout.html?plan=pro")

            notice = page.locator(".security-notice")
            expect(notice).to_be_visible()

    class TestURLChecker:
        """Тесты проверки URL"""

        def test_safe_url(self, page, server):
            """Проверка безопасной ссылки"""
            page.goto(BASE_URL)

            page.fill("#urlInput", "https://google.com")
            page.click('button[type="submit"]')

            # Ждем результата
            result = page.locator("#checkerResult")
            expect(result).to_be_visible(timeout=5000)

            # Должен показать безопасный результат
            result_title = page.locator(".result-title")
            expect(result_title).to_contain_text("безопасн", ignore_case=True)

        def test_suspicious_url(self, page, server):
            """Проверка подозрительной ссылки"""
            page.goto(BASE_URL)

            page.fill("#urlInput", "http://secure-login-bank-verify.ru")
            page.click('button[type="submit"]')

            result = page.locator("#checkerResult")
            expect(result).to_be_visible(timeout=5000)

            # Должен показать предупреждение
            result_title = page.locator(".result-title")
            expect(result_title).to_contain_text("подозрительн", ignore_case=True)

        def test_empty_url_validation(self, page, server):
            """Валидация пустого URL"""
            page.goto(BASE_URL)

            page.click('button[type="submit"]')

            # Форма не должна отправиться
            result = page.locator("#checkerResult")
            expect(result).not_to_be_visible()

    class TestResponsive:
        """Тесты адаптивности"""

        def test_mobile_view(self, page, server):
            """Проверка мобильной версии"""
            page.set_viewport_size({"width": 375, "height": 667})
            page.goto(BASE_URL)

            # Мобильное меню должно быть
            mobile_toggle = page.locator(".mobile-toggle")
            expect(mobile_toggle).to_be_visible()

        def test_tablet_view(self, page, server):
            """Проверка планшетной версии"""
            page.set_viewport_size({"width": 768, "height": 1024})
            page.goto(BASE_URL)

            # Все должно корректно отображаться
            hero = page.locator(".hero")
            expect(hero).to_be_visible()

        def test_desktop_view(self, page, server):
            """Проверка десктопной версии"""
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.goto(BASE_URL)

            # Навигация должна быть видна
            nav = page.locator(".nav")
            expect(nav).to_be_visible()