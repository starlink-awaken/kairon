from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: Context migration protocol with integrity validation
Authority: organs/D-Continuity/AGENTS.md
---
"""


import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# ContextMigration ≡ Context_Transfer
# 内涵 ≝ {Migrate, Validate, Transfer}
# 外延 ≝ {m | m ∈ D-Continuity ∧ migrates(m, Context)}
# 功能 ⊢ {Migrate_Memory, Migrate_Preferences, Migrate_Emotion, Validate_Integrity}
# =============================================================================


@dataclass
class MigrationManifest:
    """Manifest describing what is included in a context migration."""

    migration_id: str
    source_session_id: str
    target_session_id: str
    created_at: str
    version: int = 1
    includes_memory: bool = True
    includes_preferences: bool = True
    includes_emotion: bool = True
    field_counts: dict[str, int] = field(default_factory=dict)
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("checksum", None)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any], checksum: str = "") -> MigrationManifest:
        fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        fields["checksum"] = checksum
        return cls(**fields)


@dataclass
class MigrationBundle:
    """Complete migration package containing all transferable context."""

    manifest: MigrationManifest
    memory: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    emotion_state: dict[str, Any] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "memory": self.memory,
            "preferences": self.preferences,
            "emotion_state": self.emotion_state,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MigrationBundle:
        manifest = MigrationManifest.from_dict(
            data.get("manifest", {}),
            checksum=data.get("manifest", {}).get("checksum", ""),
        )
        return cls(
            manifest=manifest,
            memory=data.get("memory", {}),
            preferences=data.get("preferences", {}),
            emotion_state=data.get("emotion_state", {}),
            raw_data=data.get("raw_data", {}),
        )


@dataclass
class IntegrityReport:
    """Result of migration integrity validation."""

    valid: bool
    migration_id: str
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class MigrationIntegrityError(Exception):
    """Raised when migration integrity validation fails."""

    pass


class ContextMigration:
    """
    Context migration protocol for transferring digital twin state across sessions.

    Features:
    1. Memory, preference, and emotion state migration
    2. Migration manifest with field counts
    3. SHA256-based integrity checksum
    4. Validation before and after migration
    """

    def __init__(self) -> None:
        self.metadata_path = "eidos/context_migration.py"
        self.organ_name = "context_migration"
        self.organ_id = f"eidos-{id(self):x}"
        self._status = "active"
        self._metabolic_budget = 1000.0
    # --------------------------------------------------------------------------
    # Build migration bundle
    # --------------------------------------------------------------------------

    def create_bundle(
        self,
        source_session_id: str,
        target_session_id: str,
        memory: dict[str, Any],
        preferences: dict[str, Any],
        emotion_state: dict[str, Any],
        migration_id: str | None = None,
    ) -> MigrationBundle:
        """
        Create a migration bundle from source session data.

        Args:
            source_session_id: Session the data is migrating from
            target_session_id: Session the data is migrating to
            memory: Memory state dict
            preferences: Preferences dict
            emotion_state: Emotion state dict
            migration_id: Optional migration ID (auto-generated if None)

        Returns:
            MigrationBundle with manifest and all data
        """
        import uuid

        mid = migration_id or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        manifest = MigrationManifest(
            migration_id=mid,
            source_session_id=source_session_id,
            target_session_id=target_session_id,
            created_at=now,
            version=1,
            includes_memory=bool(memory),
            includes_preferences=bool(preferences),
            includes_emotion=bool(emotion_state),
            field_counts={
                "memory_keys": len(memory) if isinstance(memory, dict) else 0,
                "preference_keys": len(preferences) if isinstance(preferences, dict) else 0,
                "emotion_keys": len(emotion_state) if isinstance(emotion_state, dict) else 0,
            },
        )

        bundle = MigrationBundle(
            manifest=manifest,
            memory=memory,
            preferences=preferences,
            emotion_state=emotion_state,
        )

        # Compute checksum from all data
        bundle.manifest.checksum = self._compute_checksum(bundle)
        manifest.checksum = bundle.manifest.checksum

        _log.info(
            "Migration bundle %s created: %s -> %s (checksum=%s)",
            mid,
            source_session_id,
            target_session_id,
            manifest.checksum[:16],
        )

        return bundle

    def bundle_to_dict(self, bundle: MigrationBundle) -> dict[str, Any]:
        """Serialize a migration bundle to a plain dict."""
        return bundle.to_dict()

    def bundle_from_dict(self, data: dict[str, Any]) -> MigrationBundle:
        """Deserialize a migration bundle from a plain dict."""
        return MigrationBundle.from_dict(data)

    # --------------------------------------------------------------------------
    # Integrity validation
    # --------------------------------------------------------------------------

    def validate(
        self,
        bundle: MigrationBundle,
        strict: bool = True,
    ) -> IntegrityReport:
        """
        Validate the integrity of a migration bundle.

        Args:
            bundle: The MigrationBundle to validate
            strict: If True, fail on any warning. If False, allow warnings.

        Returns:
            IntegrityReport describing what passed/failed
        """
        checks_passed: list[str] = []
        checks_failed: list[str] = []
        warnings: list[str] = []
        details: dict[str, Any] = {}

        manifest = bundle.manifest
        mid = manifest.migration_id

        # Check 1: Manifest exists
        if manifest.migration_id:
            checks_passed.append("manifest_id_present")
        else:
            checks_failed.append("manifest_id_present")

        # Check 2: Source and target session IDs differ
        if manifest.source_session_id != manifest.target_session_id:
            checks_passed.append("source_target_differ")
        else:
            checks_failed.append("source_target_differ")
            warnings.append("Source and target session IDs are identical")

        # Check 3: Manifest has expected fields
        expected_fields = {"migration_id", "source_session_id", "target_session_id", "created_at"}
        missing = expected_fields - set(manifest.to_dict().keys())
        if not missing:
            checks_passed.append("manifest_fields_complete")
        else:
            checks_failed.append("manifest_fields_complete")
            details["missing_manifest_fields"] = list(missing)

        # Check 4: Memory is a dict
        if isinstance(bundle.memory, dict):
            checks_passed.append("memory_is_dict")
        else:
            checks_failed.append("memory_is_dict")
            warnings.append("Memory is not a dict — type coercion may occur")

        # Check 5: Preferences is a dict
        if isinstance(bundle.preferences, dict):
            checks_passed.append("preferences_is_dict")
        else:
            checks_failed.append("preferences_is_dict")

        # Check 6: Emotion state is a dict
        if isinstance(bundle.emotion_state, dict):
            checks_passed.append("emotion_state_is_dict")
        else:
            checks_failed.append("emotion_state_is_dict")

        # Check 7: Field count match
        actual_counts = {
            "memory_keys": len(bundle.memory) if isinstance(bundle.memory, dict) else 0,
            "preference_keys": len(bundle.preferences) if isinstance(bundle.preferences, dict) else 0,
            "emotion_keys": len(bundle.emotion_state) if isinstance(bundle.emotion_state, dict) else 0,
        }
        details["field_counts"] = actual_counts

        if manifest.field_counts == actual_counts:
            checks_passed.append("field_counts_match")
        else:
            checks_failed.append("field_counts_match")
            details["expected_field_counts"] = manifest.field_counts
            warnings.append("Field counts mismatch between manifest and actual data")

        # Check 8: Checksum integrity
        recomputed = self._compute_checksum(bundle)
        if manifest.checksum and manifest.checksum == recomputed:
            checks_passed.append("checksum_valid")
        elif manifest.checksum:
            checks_failed.append("checksum_valid")
            details["stored_checksum"] = manifest.checksum[:16]
            details["computed_checksum"] = recomputed[:16]
        else:
            warnings.append("No checksum present in manifest")

        # Check 9: Created timestamp is valid ISO
        try:
            datetime.fromisoformat(manifest.created_at)
            checks_passed.append("created_at_valid")
        except (ValueError, TypeError):
            checks_failed.append("created_at_valid")

        # Check 10: No empty migration
        has_content = bool(bundle.memory or bundle.preferences or bundle.emotion_state)
        if has_content:
            checks_passed.append("migration_has_content")
        else:
            checks_failed.append("migration_has_content")
            warnings.append("Migration bundle contains no data")

        is_valid = len(checks_failed) == 0 and (not strict or len(warnings) == 0)

        return IntegrityReport(
            valid=is_valid,
            migration_id=mid,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            warnings=warnings,
            details=details,
        )

    def migrate(
        self,
        bundle: MigrationBundle,
        target_memory: dict[str, Any] | None = None,
        target_preferences: dict[str, Any] | None = None,
        target_emotion: dict[str, Any] | None = None,
        strategy: str = "replace",
    ) -> dict[str, Any]:
        """
        Apply a migration bundle to a target context.

        Args:
            bundle: MigrationBundle to apply
            target_memory: Existing memory dict to merge into (mutated if None)
            target_preferences: Existing preferences dict to merge into (mutated if None)
            target_emotion: Existing emotion dict to merge into (mutated if None)
            strategy: "replace" (overwrite) or "merge" (shallow merge)

        Returns:
            dict with migration results and field counts
        """
        if strategy not in ("replace", "merge"):
            raise ValueError(f"Unknown strategy: {strategy!r}. Use 'replace' or 'merge'.")

        result_memory = target_memory or {}
        result_preferences = target_preferences or {}
        result_emotion = target_emotion or {}

        if strategy == "replace":
            if bundle.manifest.includes_memory:
                result_memory = dict(bundle.memory)
            if bundle.manifest.includes_preferences:
                result_preferences = dict(bundle.preferences)
            if bundle.manifest.includes_emotion:
                result_emotion = dict(bundle.emotion_state)
        else:  # merge
            if bundle.manifest.includes_memory:
                result_memory = {**result_memory, **bundle.memory}
            if bundle.manifest.includes_preferences:
                result_preferences = {**result_preferences, **bundle.preferences}
            if bundle.manifest.includes_emotion:
                result_emotion = {**result_emotion, **bundle.emotion_state}

        result = {
            "migration_id": bundle.manifest.migration_id,
            "strategy": strategy,
            "memory_keys": len(result_memory),
            "preference_keys": len(result_preferences),
            "emotion_keys": len(result_emotion),
            "memory": result_memory,
            "preferences": result_preferences,
            "emotion_state": result_emotion,
        }

        _log.info(
            "Migration %s applied (strategy=%s, mem=%d, pref=%d, emotion=%d)",
            bundle.manifest.migration_id,
            strategy,
            result["memory_keys"],
            result["preference_keys"],
            result["emotion_keys"],
        )

        return result

    # --------------------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------------------

    def _compute_checksum(self, bundle: MigrationBundle) -> str:
        """Compute SHA256 checksum over the entire bundle data."""
        payload = json.dumps(
            {
                "memory": bundle.memory,
                "preferences": bundle.preferences,
                "emotion_state": bundle.emotion_state,
                "migration_id": bundle.manifest.migration_id,
                "source_session_id": bundle.manifest.source_session_id,
                "target_session_id": bundle.manifest.target_session_id,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
