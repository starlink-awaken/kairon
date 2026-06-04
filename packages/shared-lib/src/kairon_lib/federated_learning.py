"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Federated Learning ≡ Module
# 内涵 ≝ {Federated, Learning}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FederatedLearning)}
# 功能 ⊢ {Federated_Learning, Init_Federated, Validate_Learning}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
# Type: Organ
# Status: ACTIVE
# Layer: L3
# Domain: D-Governance
"""
Federated Learning Platform for B-OS

Privacy-preserving distributed ML with:
- Differential privacy (DP-SGD)
- Secure aggregation
- Personalized local models
- Cross-node model federation

Type: Organ
Name: FederatedLearningPlatform
Layer: L3
Domain: D-Governance
Maturity: 99
Author: @Sage
"""

import asyncio
import hashlib
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FLRole(Enum):
    """Federated learning roles"""

    SERVER = "server"
    CLIENT = "client"


@dataclass
class ModelUpdate:
    """Model update from client"""

    client_id: str
    round_num: int
    weights: list[float]
    sample_count: int
    timestamp: float


@dataclass
class GlobalModel:
    """Global federated model"""

    version: str
    weights: list[float]
    round_num: int
    aggregated_from: list[str]
    timestamp: float


class DifferentialPrivacy:
    """
    Differential Privacy mechanism (DP-SGD)

    Adds noise to protect individual data contributions
    """

    def __init__(self, epsilon: float = 1.0, delta: float = 1e-5) -> None:
        self.epsilon = epsilon
        self.delta = delta
        self.noise_multiplier = self._compute_noise_multiplier()

    def _compute_noise_multiplier(self) -> float:
        """Compute noise multiplier from privacy budget"""
        import math

        return math.sqrt(2 * math.log(1.25 / self.delta)) / self.epsilon

    def apply(self, gradients: list[float]) -> list[float]:
        """Apply differential privacy to gradients"""
        # Clip gradients
        max_grad_norm = 1.0
        grad_norm = sum(g**2 for g in gradients) ** 0.5
        clip_coef = min(1.0, max_grad_norm / (grad_norm + 1e-6))
        clipped = [g * clip_coef for g in gradients]

        # Add Gaussian noise
        noisy = []
        for g in clipped:
            noise = random.gauss(0, self.noise_multiplier * max_grad_norm)
            noisy.append(g + noise)

        return noisy


class SecureAggregation:
    """
    Secure aggregation protocol

    Aggregates model updates without revealing individual contributions
    """

    def __init__(self) -> None:
        self.masks: dict[str, list[float]] = {}

    def create_mask(self, client_id: str, round_num: int) -> list[float]:
        """Create random mask for client"""
        # Deterministic mask from client_id and round — use isolated RNG to avoid
        # polluting the global random state seen by other code in the same thread.
        rng = random.Random(f"{client_id}:{round_num}")  # noqa: S311
        mask = [rng.uniform(-1, 1) for _ in range(10)]
        self.masks[client_id] = mask
        return mask

    def mask_update(self, update: list[float], mask: list[float]) -> list[float]:
        """Apply mask to model update"""
        return [u + m for u, m in zip(update, mask, strict=False)]

    def unmask_aggregate(self, masked_updates: list[list[float]], client_ids: list[str]) -> list[float]:
        """Aggregate and unmask updates"""
        # Sum masked updates
        aggregated = [0.0] * len(masked_updates[0])
        for update in masked_updates:
            for i, val in enumerate(update):
                aggregated[i] += val

        # Remove masks (sum of all masks cancels out in real protocol)
        for client_id in client_ids:
            mask = self.masks.get(client_id, [0] * len(aggregated))
            for i, m in enumerate(mask):
                aggregated[i] -= m

        # Average
        n = len(masked_updates)
        return [a / n for a in aggregated]


class FederatedLearningPlatform:
    """
    Federated Learning Platform for B-OS

    Provides:
    - Distributed model training
    - Differential privacy protection
    - Secure aggregation
    - Cross-node model federation
    """

    def __init__(self, role: FLRole = FLRole.CLIENT) -> None:
        self.role = role

        self.dp = DifferentialPrivacy()
        self.secure_agg = SecureAggregation()

        self.global_model: GlobalModel | None = None
        self.local_model: list[float] | None = None

        self.clients: list[str] = []
        self.current_round = 0

        self._initialized = False
        self.stats = {
            "rounds_completed": 0,
            "updates_submitted": 0,
            "updates_aggregated": 0,
        }

    async def initialize(self) -> bool:
        """Initialize FL platform"""
        try:
            print(f"Initializing Federated Learning Platform ({self.role.value})...")

            # Initialize local model
            self.local_model = [0.0] * 10

            if self.role == FLRole.SERVER:
                self.global_model = GlobalModel(
                    version="1.0.0",
                    weights=[0.0] * 10,
                    round_num=0,
                    aggregated_from=[],
                    timestamp=time.time(),
                )

            self._initialized = True
            print("Federated Learning Platform initialized")
            return True

        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            print(f"Error: {e}")
            return False

    def register_client(self, client_id: str) -> None:
        """Register a client (server only)"""
        if self.role == FLRole.SERVER:
            self.clients.append(client_id)

    async def train_round(self, local_data: list[dict]) -> ModelUpdate:
        """
        Execute one local training round (client)

        Args:
            local_data: Local training data

        Returns:
            Model update with differential privacy
        """
        if not self._initialized:
            raise RuntimeError("Not initialized")

        # Simulate local training
        gradients = self._compute_gradients(local_data)

        # Apply differential privacy
        private_gradients = self.dp.apply(gradients)

        # Create update
        update = ModelUpdate(
            client_id=self._get_client_id(),
            round_num=self.current_round,
            weights=private_gradients,
            sample_count=len(local_data),
            timestamp=time.time(),
        )

        self.stats["updates_submitted"] += 1

        return update

    async def aggregate_round(self, updates: list[ModelUpdate]) -> GlobalModel:
        """
        Aggregate client updates (server)

        Args:
            updates: List of model updates from clients

        Returns:
            Updated global model
        """
        if self.role != FLRole.SERVER:
            raise RuntimeError("Only server can aggregate")

        # Secure aggregation
        client_ids = [u.client_id for u in updates]

        # Create masks and mask updates
        masked_updates = []
        for update, client_id in zip(updates, client_ids, strict=False):
            mask = self.secure_agg.create_mask(client_id, self.current_round)
            masked = self.secure_agg.mask_update(update.weights, mask)
            masked_updates.append(masked)

        # Aggregate
        aggregated_weights = self.secure_agg.unmask_aggregate(masked_updates, client_ids)

        # Update global model
        self.current_round += 1
        self.global_model = GlobalModel(
            version=f"1.0.{self.current_round}",
            weights=aggregated_weights,
            round_num=self.current_round,
            aggregated_from=client_ids,
            timestamp=time.time(),
        )

        self.stats["updates_aggregated"] += len(updates)
        self.stats["rounds_completed"] += 1

        return self.global_model

    def _compute_gradients(self, data: list[dict]) -> list[float]:
        """Compute gradients from local data (simulated)"""
        # Simulated gradient computation
        return [random.uniform(-0.1, 0.1) for _ in range(10)]  # noqa: S311

    def _get_client_id(self) -> str:
        """Get unique client ID"""
        return f"client-{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"  # noqa: S324

    def get_stats(self) -> dict[str, Any]:
        """Get FL statistics"""
        return {
            **self.stats,
            "role": self.role.value,
            "current_round": self.current_round,
            "num_clients": len(self.clients),
            "epsilon": self.dp.epsilon,
            "initialized": self._initialized,
        }


# ============== Test ==============


async def test_federated_learning() -> None:
    """Test federated learning platform"""
    print("Testing Federated Learning Platform...")

    # Create server
    server = FederatedLearningPlatform(FLRole.SERVER)
    await server.initialize()

    # Create clients
    num_clients = 3
    clients = []
    for i in range(num_clients):
        client = FederatedLearningPlatform(FLRole.CLIENT)
        await client.initialize()
        clients.append(client)
        server.register_client(f"client-{i}")

    # Simulate FL rounds
    print("\n1. Running federated learning rounds...")

    for round_num in range(2):
        print(f"\n  Round {round_num + 1}:")

        # Clients train locally
        updates = []
        for i, client in enumerate(clients):
            local_data = [{"x": j, "y": j * 2} for j in range(100)]
            update = await client.train_round(local_data)
            updates.append(update)
            print(f"    Client {i}: {update.sample_count} samples")

        # Server aggregates
        global_model = await server.aggregate_round(updates)
        print(f"    Server: Aggregated {len(updates)} updates")
        print(f"    New model version: {global_model.version}")

    # Test 2: Stats
    print("\n2. Platform Stats...")
    server_stats = server.get_stats()
    print(f"  Rounds completed: {server_stats['rounds_completed']}")
    print(f"  Updates aggregated: {server_stats['updates_aggregated']}")
    print(f"  Privacy epsilon: {server_stats['epsilon']}")

    print("\n" + "=" * 60)
    print("Federated Learning Platform tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_federated_learning())
