from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # free - не тариф, а стартовый пакет из 3 проверок; тарифы: basic, pro, corporate
    subscription_plan = Column(String, default="free")
    # До этого момента действует платная/триальная подписка; после — автооткат на free
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    trial_used = Column(Boolean, default=False)  # триал даём один раз на аккаунт

    # Доступ к модерации отзывов (см. /api/admin/reviews)
    is_admin = Column(Boolean, default=False)

    # Почта подтверждена по ссылке из письма. Без этого проверки и оплата недоступны.
    email_verified = Column(Boolean, default=False)
    # Версия токенов: растёт при смене/сбросе пароля, старые JWT перестают работать
    token_version = Column(Integer, default=0)

    # Лимит проверок
    monthly_checks_count = Column(Integer, default=0)  # Сколько проверок в этом месяце
    last_check_reset = Column(DateTime(timezone=True),
                              server_default=func.now())  # Когда последний раз сбрасывали счетчик

    # Связь с проверками
    url_checks = relationship("UrlCheck", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")


class UrlCheck(Base):
    __tablename__ = "url_checks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Теперь обязательно
    url = Column(String, nullable=False)
    is_phishing = Column(Boolean, nullable=False)
    risk_score = Column(Float, nullable=False)
    verdict = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="url_checks")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)   # как подписать автора (необязательно)
    role = Column(String, nullable=True)   # кто он (необязательно)
    text = Column(String, nullable=False)
    # Отзывы публикуются только после проверки администратором
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Payment(Base):
    """Платёж в ЮKassa. Нужен, чтобы не активировать подписку дважды
    на повторное уведомление и сверять сумму с тем, что выставили."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    payment_id = Column(String, index=True, nullable=True)  # id платежа в ЮKassa
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)  # копейки
    # NEW - создан у нас; дальше статусы ЮKassa: pending, succeeded, canceled;
    # наши: INIT_ERROR - не создался, AMOUNT_MISMATCH - оплачена не та сумма
    status = Column(String, nullable=False, default="NEW")
    # Подписка по этому платежу уже выдана - повторные CONFIRMED игнорируем
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payments")


class AuthToken(Base):
    """Одноразовые токены из писем: подтверждение почты и сброс пароля.
    В базе лежит только SHA-256 от токена, сам токен есть только в письме."""
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    purpose = Column(String, nullable=False)  # verify_email | reset_password
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
