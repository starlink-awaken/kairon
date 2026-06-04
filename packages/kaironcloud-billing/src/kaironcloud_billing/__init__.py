"""kaironcloud-billing — Billing subsystem extracted from SharedBrain D_Cloud.

Provides:
- Core data models (ResourceType, UsageRecord, Bill, PricingTier, etc.)
- Tiered pricing engine with Decimal precision
- SQLite-backed async usage tracker
- Monthly bill generation
- Stripe SDK integration (optional)
- Subscription lifecycle management
- Stripe webhook HMAC verification
- EU (Energy Unit) virtual resource accounting (merged from eu-pricing)
"""

from kaironcloud_billing.models import (
    Bill,
    BillDetails,
    BillLineItem,
    BillStatus,
    PricingTier,
    ResourceType,
    TenantSubscription,
    TierType,
    UsageBreakdown,
    UsageRecord,
    UsageReport,
)
from kaironcloud_billing.pricing import PricingModel
from kaironcloud_billing.pricing.eu_energy_model import (
    DEFAULT_EU_PRICING,
    EnergyBudget,
    EnergyEntry,
)
from kaironcloud_billing.pricing.eu_energy_model import (
    ResourceType as EUResourceType,
)
from kaironcloud_billing.pricing.eu_ledger import EUBalance, EULedger, EUTransaction
from kaironcloud_billing.pricing.eu_market import MarketAnalyzer, get_market_analyzer
from kaironcloud_billing.pricing.eu_optimizer import Budget, CostEstimate, EnergyOptimizer, Strategy
from kaironcloud_billing.pricing.eu_reputation import ReputationLedger
from kaironcloud_billing.pricing.eu_rewards import Reward, RewardConfig, RewardEngine, RewardType
from kaironcloud_billing.usage_tracker import UsageTracker
from kaironcloud_billing.webhook_handler import StripeEventType, WebhookEvent, WebhookHandler

__all__ = (
    # Cloud billing
    "Bill",
    "BillDetails",
    "BillLineItem",
    "BillStatus",
    "PricingModel",
    "PricingTier",
    "ResourceType",
    "StripeEventType",
    "TenantSubscription",
    "TierType",
    "UsageBreakdown",
    "UsageRecord",
    "UsageReport",
    "UsageTracker",
    "WebhookEvent",
    "WebhookHandler",
    # EU virtual resource accounting (merged from eu-pricing)
    "Budget",
    "CostEstimate",
    "DEFAULT_EU_PRICING",
    "EnergyBudget",
    "EnergyEntry",
    "EnergyOptimizer",
    "EUBalance",
    "EULedger",
    "EUResourceType",
    "EUTransaction",
    "get_market_analyzer",
    "MarketAnalyzer",
    "ReputationLedger",
    "Reward",
    "RewardConfig",
    "RewardEngine",
    "RewardType",
    "Strategy",
)
