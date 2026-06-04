from __future__ import annotations

"""
Stripe支付集成模块

封装Stripe API，提供客户管理、订阅管理、支付处理功能
"""

import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


class StripePriceProtocol(Protocol):
    id: str


class StripeItemProtocol(Protocol):
    price: StripePriceProtocol
    quantity: int


class StripeItemsProtocol(Protocol):
    data: Sequence[StripeItemProtocol]


class StripeSubscriptionProtocol(Protocol):
    id: str
    customer: str
    status: str
    current_period_start: int
    current_period_end: int
    items: StripeItemsProtocol
    cancel_at_period_end: bool


class StripeInvoiceProtocol(Protocol):
    id: str
    customer: str
    subscription: str | None
    amount_due: int
    amount_paid: int
    status: str
    created: int
    invoice_pdf: str | None


@dataclass
class StripeCustomer:
    """Stripe客户"""

    customer_id: str
    email: str
    name: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


@dataclass
class StripeSubscription:
    """Stripe订阅"""

    subscription_id: str
    customer_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    plan_id: str
    quantity: int = 1
    cancel_at_period_end: bool = False


@dataclass
class StripeInvoice:
    """Stripe发票"""

    invoice_id: str
    customer_id: str
    subscription_id: str | None
    amount_due: Decimal
    amount_paid: Decimal
    status: str
    created_at: datetime
    pdf_url: str | None = None


class StripeClient:
    """Stripe API客户端

    封装Stripe Python SDK，提供B-OS Cloud所需的支付功能
    """

    PRICE_IDS = {
        "free": None,
        "pro": "price_pro_monthly",
        "enterprise": "price_enterprise_monthly",
    }

    def __init__(self, api_key: str | None = None) -> None:
        """初始化Stripe客户端

        Args:
            api_key: Stripe API密钥，默认从环境变量STRIPE_API_KEY读取
        """
        self.api_key = api_key or os.getenv("STRIPE_API_KEY")
        if not self.api_key:
            raise ValueError("Stripe API key required. Set STRIPE_API_KEY env var.")

        try:
            import stripe  # type: ignore[import-not-found]

            stripe.api_key = self.api_key
            self.stripe = stripe
        except ImportError as e:
            raise ImportError("stripe package required. Install: pip install stripe") from e

    # ==================== 客户管理 ====================

    def create_customer(
        self, email: str, name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> StripeCustomer:
        """创建Stripe客户"""
        customer = self.stripe.Customer.create(email=email, name=name, metadata=metadata or {})

        return StripeCustomer(
            customer_id=customer.id,
            email=customer.email,
            name=customer.name,
            metadata=dict(customer.metadata) if customer.metadata else {},
            created_at=datetime.fromtimestamp(customer.created),
        )

    def get_customer(self, customer_id: str) -> StripeCustomer | None:
        """获取客户信息"""
        try:
            customer = self.stripe.Customer.retrieve(customer_id)
            return StripeCustomer(
                customer_id=customer.id,
                email=customer.email,
                name=customer.name,
                metadata=dict(customer.metadata) if customer.metadata else {},
                created_at=datetime.fromtimestamp(customer.created),
            )
        except self.stripe.error.InvalidRequestError:
            return None

    def update_customer(
        self,
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StripeCustomer:
        """更新客户信息"""
        update_params: dict[str, Any] = {}
        if email:
            update_params["email"] = email
        if name:
            update_params["name"] = name
        if metadata:
            update_params["metadata"] = metadata

        customer = self.stripe.Customer.modify(customer_id, **update_params)

        return StripeCustomer(
            customer_id=customer.id,
            email=customer.email,
            name=customer.name,
            metadata=dict(customer.metadata) if customer.metadata else {},
            created_at=datetime.fromtimestamp(customer.created),
        )

    # ==================== 订阅管理 ====================

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        quantity: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> StripeSubscription:
        """创建订阅"""
        subscription = self.stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id, "quantity": quantity}],
            metadata=metadata or {},
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
        )

        return self._parse_subscription(subscription)

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> StripeSubscription:
        """取消订阅"""
        if at_period_end:
            subscription = self.stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        else:
            subscription = self.stripe.Subscription.delete(subscription_id)

        return self._parse_subscription(subscription)

    def get_subscription(self, subscription_id: str) -> StripeSubscription | None:
        """获取订阅信息"""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return self._parse_subscription(subscription)
        except self.stripe.error.InvalidRequestError:
            return None

    def update_subscription_quantity(self, subscription_id: str, quantity: int) -> StripeSubscription:
        """更新订阅数量（升级/降级用户数）"""
        subscription = self.stripe.Subscription.retrieve(subscription_id)

        self.stripe.SubscriptionItem.modify(subscription.items.data[0].id, quantity=quantity)

        return self.get_subscription(subscription_id)  # type: ignore[return-value]

    # ==================== 发票与支付 ====================

    def get_invoice(self, invoice_id: str) -> StripeInvoice | None:
        """获取发票信息"""
        try:
            invoice = self.stripe.Invoice.retrieve(invoice_id)
            return self._parse_invoice(invoice)
        except self.stripe.error.InvalidRequestError:
            return None

    def list_invoices(self, customer_id: str, limit: int = 10) -> list[StripeInvoice]:
        """获取客户发票列表"""
        invoices = self.stripe.Invoice.list(customer=customer_id, limit=limit)

        return [self._parse_invoice(inv) for inv in invoices.data]

    def create_payment_intent(
        self,
        customer_id: str,
        amount: Decimal,
        currency: str = "usd",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建支付意图（用于一次性付款）"""
        intent = self.stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency=currency,
            customer=customer_id,
            metadata=metadata or {},
            automatic_payment_methods={"enabled": True},
        )

        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "status": intent.status,
        }

    # ==================== 工具方法 ====================

    def _parse_subscription(self, subscription: StripeSubscriptionProtocol) -> StripeSubscription:
        """解析Stripe订阅对象"""
        return StripeSubscription(
            subscription_id=subscription.id,
            customer_id=subscription.customer,
            status=subscription.status,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            plan_id=subscription.items.data[0].price.id if subscription.items.data else "",
            quantity=subscription.items.data[0].quantity if subscription.items.data else 1,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )

    def _parse_invoice(self, invoice: StripeInvoiceProtocol) -> StripeInvoice:
        """解析Stripe发票对象"""
        return StripeInvoice(
            invoice_id=invoice.id,
            customer_id=invoice.customer,
            subscription_id=invoice.subscription,
            amount_due=Decimal(invoice.amount_due) / 100,
            amount_paid=Decimal(invoice.amount_paid) / 100,
            status=invoice.status,
            created_at=datetime.fromtimestamp(invoice.created),
            pdf_url=invoice.invoice_pdf,
        )
