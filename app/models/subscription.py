import uuid
from sqlalchemy import Column, String, Integer, DateTime, Numeric, Boolean, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.base import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    plan_type = Column(String, nullable=False)          # free | basic | pro | enterprise
    billing_interval = Column(String)                   # monthly | annual
    price_monthly = Column(Numeric(10, 2))
    price_annual_monthly = Column(Numeric(10, 2))
    price_annual_total = Column(Numeric(10, 2))
    annual_discount_percentage = Column(Numeric(5, 2))
    annual_savings_amount = Column(Numeric(10, 2))
    currency = Column(String, default="USD")
    image_allowance = Column(Integer, default=0)
    video_allowance = Column(Integer, default=0)
    total_credits = Column(Integer, default=0)
    description = Column(Text)
    features = Column(JSON, default=[])
    ai_model_key = Column(String)
    ai_model_identifier = Column(String)
    ai_provider = Column(String)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("UserSubscription", back_populates="plan")
    orders = relationship("Order", back_populates="plan")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False)
    previous_subscription_id = Column(UUID(as_uuid=True), nullable=True)
    pending_downgrade_id = Column(UUID(as_uuid=True), nullable=True)
    change_type = Column(String)
    status = Column(String, default="active")           # active | cancelled | expired | paused
    billing_interval = Column(String)
    billing_cycle_start = Column(DateTime)
    billing_cycle_end = Column(DateTime)
    cancelled_at = Column(DateTime)
    downgrade_scheduled_at = Column(DateTime)
    lxt_id = Column(UUID(as_uuid=True))
    upgrade_count = Column(Integer, default=0)
    downgrade_count = Column(Integer, default=0)
    upgrade_reset_used = Column(Boolean, default=False)
    auto_renew = Column(Boolean, default=True)
    images_balance = Column(Integer, default=0)
    videos_balance = Column(Integer, default=0)
    credits_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String, unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("subscription_plans.id"))
    user_subscription_id = Column(UUID(as_uuid=True))
    order_type = Column(String)                         # new | renewal | upgrade | downgrade
    status = Column(String, default="pending")          # pending | completed | failed | refunded
    billing_interval = Column(String)
    amount = Column(Numeric(10, 2))
    discount_amount = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2))
    currency = Column(String, default="USD")
    stripe_customer_id = Column(String)
    stripe_subscription_id = Column(String)
    stripe_invoice_id = Column(String)
    stripe_payment_intent_id = Column(String)
    failure_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    plan = relationship("SubscriptionPlan", back_populates="orders")
    transactions = relationship("PaymentTransaction", back_populates="order")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    transaction_type = Column(String)                   # charge | refund | dispute
    status = Column(String)                             # success | failed | pending
    amount = Column(Numeric(10, 2))
    currency = Column(String, default="USD")
    stripe_payment_intent_id = Column(String)
    stripe_charge_id = Column(String)
    stripe_invoice_id = Column(String)
    stripe_refund_id = Column(String)
    payment_method_type = Column(String)
    card_brand = Column(String)
    card_last4 = Column(String)
    card_exp_month = Column(Integer)
    card_exp_year = Column(Integer)
    failure_code = Column(String)
    failure_message = Column(Text)
    stripe_raw_payload = Column(JSON)
    stripe_event_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="transactions")