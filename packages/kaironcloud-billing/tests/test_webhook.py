"""Tests for the Stripe webhook handler."""

import hashlib
import hmac
import json

import pytest
from kaironcloud_billing.webhook_handler import (
    StripeEventType,
    WebhookEvent,
    WebhookHandler,
)


class TestStripeEventType:
    def test_payment_events(self):
        assert StripeEventType.PAYMENT_INTENT_SUCCEEDED == "payment_intent.succeeded"
        assert StripeEventType.PAYMENT_INTENT_PAYMENT_FAILED == "payment_intent.payment_failed"

    def test_subscription_events(self):
        assert StripeEventType.CUSTOMER_SUBSCRIPTION_CREATED == "customer.subscription.created"
        assert StripeEventType.CUSTOMER_SUBSCRIPTION_UPDATED == "customer.subscription.updated"
        assert StripeEventType.CUSTOMER_SUBSCRIPTION_DELETED == "customer.subscription.deleted"

    def test_invoice_events(self):
        assert StripeEventType.INVOICE_PAID == "invoice.paid"
        assert StripeEventType.INVOICE_PAYMENT_FAILED == "invoice.payment_failed"


class TestWebhookEvent:
    def test_create(self):
        from datetime import UTC, datetime

        event = WebhookEvent(
            event_id="evt_123",
            event_type=StripeEventType.INVOICE_PAID,
            timestamp=datetime(2025, 1, 15, tzinfo=UTC),
            data={"object": "invoice", "id": "in_123"},
            livemode=False,
        )
        assert event.event_id == "evt_123"
        assert event.event_type == StripeEventType.INVOICE_PAID
        assert event.data["id"] == "in_123"
        assert event.livemode is False


class TestSignatureVerification:
    def _compute_signature(self, secret, timestamp, payload):
        """Compute the expected Stripe webhook signature."""
        signed_payload = f"{timestamp}.{payload}"
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={expected}"

    def test_valid_signature(self):
        secret = "whsec_test_12345"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)
        payload = json.dumps({"type": "invoice.paid", "data": {"object": {}}})
        timestamp = "1234567890"
        signature = self._compute_signature(secret, timestamp, payload)

        assert handler.verify_signature(payload, signature) is True

    def test_invalid_signature(self):
        secret = "whsec_test_12345"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)
        payload = json.dumps({"type": "invoice.paid"})
        signature = "t=1234567890,v1=invalidhash12345"

        assert handler.verify_signature(payload, signature) is False

    def test_missing_secret_raises(self):
        handler = WebhookHandler(webhook_secret="")
        handler.webhook_secret = None  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Webhook secret not configured"):
            handler.verify_signature("payload", "t=123,v1=abc")

    def test_malformed_signature_header(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)
        # Missing v1 part
        assert handler.verify_signature("payload", "t=123") is False

    def test_no_timestamp(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)
        assert handler.verify_signature("payload", "v1=abc") is False


class TestHandleEvent:
    def _compute_signature(self, secret, timestamp, payload):
        signed_payload = f"{timestamp}.{payload}"
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={expected}"

    def test_valid_event_dispatches(self):
        secret = "whsec_test_12345"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)

        handled_events = []

        def my_handler(event):
            handled_events.append(event)

        handler.register_handler(StripeEventType.INVOICE_PAID, my_handler)

        payload = json.dumps(
            {
                "id": "evt_123",
                "type": "invoice.paid",
                "data": {"object": {"id": "in_123", "customer": "cus_123"}},
                "livemode": False,
            }
        )
        timestamp = "1234567890"
        signature = self._compute_signature(secret, timestamp, payload)

        result = handler.handle_event(payload, signature)
        assert result["event_id"] == "evt_123"
        assert result["handlers_executed"] == 1
        assert result["results"][0]["status"] == "success"
        assert len(handled_events) == 1
        assert handled_events[0].event_id == "evt_123"

    def test_invalid_signature_raises(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)
        payload = json.dumps({"type": "invoice.paid"})
        signature = "t=123,v1=badsignature"

        with pytest.raises(ValueError, match="Invalid webhook signature"):
            handler.handle_event(payload, signature)

    def test_no_matching_handler(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)

        payload = json.dumps(
            {
                "id": "evt_456",
                "type": "invoice.paid",
                "data": {"object": {}},
                "livemode": True,
            }
        )
        timestamp = "1234567890"
        signature = self._compute_signature(secret, timestamp, payload)

        result = handler.handle_event(payload, signature)
        assert result["handlers_executed"] == 0
        assert result["results"] == []

    def test_multiple_handlers(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)

        results = []

        def handler_a(event):
            results.append("a")

        def handler_b(event):
            results.append("b")

        handler.register_handler(StripeEventType.INVOICE_PAID, handler_a)
        handler.register_handler(StripeEventType.INVOICE_PAID, handler_b)

        payload = json.dumps(
            {
                "id": "evt_multi",
                "type": "invoice.paid",
                "data": {"object": {}},
            }
        )
        timestamp = "1234567890"
        signature = self._compute_signature(secret, timestamp, payload)

        result = handler.handle_event(payload, signature)
        assert result["handlers_executed"] == 2
        assert results == ["a", "b"]

    def test_handler_error_is_recorded(self):
        secret = "whsec_test"  # noqa: S105
        handler = WebhookHandler(webhook_secret=secret)

        def failing_handler(event):
            raise ValueError("Test error")

        handler.register_handler(StripeEventType.INVOICE_PAID, failing_handler)

        payload = json.dumps(
            {
                "id": "evt_err",
                "type": "invoice.paid",
                "data": {"object": {}},
            }
        )
        timestamp = "1234567890"
        signature = self._compute_signature(secret, timestamp, payload)

        result = handler.handle_event(payload, signature)
        assert result["handlers_executed"] == 1
        assert result["results"][0]["status"] == "error"
        assert "Test error" in result["results"][0]["error"]


class TestDefaultHandlers:
    def test_setup_default_handlers(self):
        handler = WebhookHandler(webhook_secret="whsec_test")  # noqa: S106
        handler.setup_default_handlers()

        assert StripeEventType.INVOICE_PAYMENT_FAILED in handler._handlers
        assert StripeEventType.CUSTOMER_SUBSCRIPTION_UPDATED in handler._handlers
        assert StripeEventType.CUSTOMER_SUBSCRIPTION_DELETED in handler._handlers
        assert len(handler._handlers[StripeEventType.INVOICE_PAYMENT_FAILED]) == 1


class TestParseSignatureHeader:
    def test_valid_header(self):
        handler = WebhookHandler(webhook_secret="whsec_test")  # noqa: S106
        timestamp, sig_hash = handler._parse_signature_header("t=1234567890,v1=abcdef123456")
        assert timestamp == "1234567890"
        assert sig_hash == "abcdef123456"

    def test_with_spaces(self):
        handler = WebhookHandler(webhook_secret="whsec_test")  # noqa: S106
        timestamp, sig_hash = handler._parse_signature_header("t=1234567890, v1=abcdef123456")
        assert timestamp == "1234567890"
        assert sig_hash == "abcdef123456"

    def test_missing_timestamp_raises(self):
        handler = WebhookHandler(webhook_secret="whsec_test")  # noqa: S106
        with pytest.raises(ValueError, match="Invalid signature header format"):
            handler._parse_signature_header("v1=abcdef123456")

    def test_missing_v1_raises(self):
        handler = WebhookHandler(webhook_secret="whsec_test")  # noqa: S106
        with pytest.raises(ValueError, match="Invalid signature header format"):
            handler._parse_signature_header("t=1234567890")
