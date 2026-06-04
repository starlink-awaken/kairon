from __future__ import annotations

"""
Stripe Webhook处理器

处理Stripe发送的事件通知，包括：
- 支付成功/失败
- 订阅状态变更
- 发票生成
- 退款处理
"""

import hashlib
import hmac
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class StripeEventType(StrEnum):
    """Stripe事件类型"""

    # 支付相关
    PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_INTENT_PAYMENT_FAILED = "payment_intent.payment_failed"

    # 订阅相关
    CUSTOMER_SUBSCRIPTION_CREATED = "customer.subscription.created"
    CUSTOMER_SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    CUSTOMER_SUBSCRIPTION_DELETED = "customer.subscription.deleted"

    # 发票相关
    INVOICE_CREATED = "invoice.created"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"

    # 客户相关
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    CUSTOMER_DELETED = "customer.deleted"


@dataclass
class WebhookEvent:
    """Webhook事件"""

    event_id: str
    event_type: StripeEventType
    timestamp: datetime
    data: dict[str, Any]
    livemode: bool


class WebhookHandler:
    """Stripe Webhook处理器

    验证webhook签名，分发事件到对应的处理函数
    """

    def __init__(self, webhook_secret: str | None = None) -> None:
        """初始化Webhook处理器

        Args:
            webhook_secret: Stripe webhook签名密钥
        """
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")
        self._handlers: dict[StripeEventType, list[Callable[[WebhookEvent], None]]] = {}

    def register_handler(self, event_type: StripeEventType, handler: Callable[[WebhookEvent], None]) -> None:
        """注册事件处理器

        Args:
            event_type: 要监听的事件类型
            handler: 处理函数，接收WebhookEvent参数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def verify_signature(self, payload: str, signature: str) -> bool:
        """验证Stripe webhook签名

        Args:
            payload: 请求body（原始字符串）
            signature: Stripe-Signature header值

        Returns:
            签名是否有效
        """
        if not self.webhook_secret:
            raise ValueError("Webhook secret not configured")

        try:
            timestamp, signature_hash = self._parse_signature_header(signature)

            signed_payload = f"{timestamp}.{payload}"

            expected_signature = hmac.new(
                self.webhook_secret.encode(), signed_payload.encode(), hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature_hash, expected_signature)
        except (ValueError, TypeError):
            return False

    def handle_event(self, payload: str, signature: str) -> dict[str, Any]:
        """处理webhook事件

        Args:
            payload: 请求body
            signature: Stripe-Signature header

        Returns:
            处理结果

        Raises:
            ValueError: 签名验证失败
        """
        if not self.verify_signature(payload, signature):
            raise ValueError("Invalid webhook signature")

        event_data = json.loads(payload)
        event = WebhookEvent(
            event_id=event_data["id"],
            event_type=StripeEventType(event_data["type"]),
            timestamp=datetime.now(UTC),
            data=event_data["data"]["object"],
            livemode=event_data.get("livemode", False),
        )

        handlers = self._handlers.get(event.event_type, [])
        results = []

        for handler in handlers:
            try:
                handler(event)
                results.append({"handler": handler.__name__, "status": "success"})
            except (OSError, ValueError, RuntimeError, KeyError) as e:
                results.append({"handler": handler.__name__, "status": "error", "error": str(e)})

        return {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "handlers_executed": len(handlers),
            "results": results,
        }

    def setup_default_handlers(self) -> None:
        """设置默认的事件处理器"""
        self.register_handler(StripeEventType.INVOICE_PAYMENT_FAILED, self._handle_payment_failed)
        self.register_handler(StripeEventType.CUSTOMER_SUBSCRIPTION_UPDATED, self._handle_subscription_updated)
        self.register_handler(StripeEventType.CUSTOMER_SUBSCRIPTION_DELETED, self._handle_subscription_deleted)

    def _handle_payment_failed(self, event: WebhookEvent) -> None:
        """处理支付失败"""
        invoice = event.data
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        print(f"Payment failed for customer {customer_id}, subscription {subscription_id}")

    def _handle_subscription_updated(self, event: WebhookEvent) -> None:
        """处理订阅更新"""
        subscription = event.data
        status = subscription.get("status")
        print(f"Subscription {subscription['id']} updated to status: {status}")

    def _handle_subscription_deleted(self, event: WebhookEvent) -> None:
        """处理订阅删除"""
        subscription = event.data
        customer_id = subscription.get("customer")
        print(f"Subscription {subscription['id']} deleted for customer {customer_id}")

    def _parse_signature_header(self, signature: str) -> tuple[str, str]:
        """解析Stripe签名头

        Returns:
            (timestamp, signature_hash)
        """
        parts: dict[str, str] = {}
        for part in signature.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                parts[key.strip()] = value.strip()

        timestamp = parts.get("t")
        signature_hash = parts.get("v1")

        if not timestamp or not signature_hash:
            raise ValueError("Invalid signature header format")

        return timestamp, signature_hash
