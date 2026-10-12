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
    subscription_plan = Column(String, default="free")  # free, pro, business

    # Лимит проверок
    monthly_checks_count = Column(Integer, default=0)  # Сколько проверок в этом месяце
    last_check_reset = Column(DateTime(timezone=True),
                              server_default=func.now())  # Когда последний раз сбрасывали счетчик

    # Связь с проверками
    url_checks = relationship("UrlCheck", back_populates="user", cascade="all, delete-orphan")


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