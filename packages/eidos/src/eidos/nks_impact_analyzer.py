from __future__ import annotations

import logging
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from eidos.graph_store import Entity, GraphStore  # type: ignore[import-not-found]

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Constraint: "Must provide actionable impact analysis for Agents"
Summary: "ImpactAnalyzer - Analyze impact of code changes"
Tags:
- nks
- impact-analysis
- risk-assessment
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Impact Analyzer ≡ Module
# 内涵 ≝ {Impact, Analyzer}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, ImpactAnalyzer)}
# 功能 ⊢ {Impact_Analyzer, Init_Impact, Validate_Analyzer}
# =============================================================================

_log = logging.getLogger(__name__)


@dataclass
class ImpactReport:
    """
    Comprehensive impact analysis report for code changes.

    Attributes:
        changed_entities: List of entities that were changed
        direct_impacts: Entities directly impacted (callers/callees)
        transitive_impacts: Entities indirectly impacted through dependency chains
        risk_score: Calculated risk score (0.0 - 1.0)
        suggested_tests: Test files that should be run
        dependency_chains: Call chains showing impact propagation
    """

    changed_entities: list[Entity] = field(default_factory=list)
    direct_impacts: list[Entity] = field(default_factory=list)
    transitive_impacts: list[Entity] = field(default_factory=list)
    risk_score: float = 0.0
    suggested_tests: list[str] = field(default_factory=list)
    dependency_chains: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert report to dictionary format."""
        return {
            "changed_entities": [e.entity_id for e in self.changed_entities],
            "direct_impacts": [e.entity_id for e in self.direct_impacts],
            "transitive_impacts": [e.entity_id for e in self.transitive_impacts],
            "risk_score": round(self.risk_score, 4),
            "risk_level": self._get_risk_level(),
            "suggested_tests": self.suggested_tests,
            "dependency_chains": self.dependency_chains,
            "summary": self._generate_summary(),
        }

    def _get_risk_level(self) -> str:
        """Get human-readable risk level."""
        if self.risk_score >= 0.8:
            return "CRITICAL"
        elif self.risk_score >= 0.6:
            return "HIGH"
        elif self.risk_score >= 0.4:
            return "MEDIUM"
        elif self.risk_score >= 0.2:
            return "LOW"
        return "MINIMAL"

    def _generate_summary(self) -> str:
        """Generate human-readable summary."""
        return (
            f"Impact analysis: {len(self.changed_entities)} changed, "
            f"{len(self.direct_impacts)} direct, {len(self.transitive_impacts)} transitive impacts. "
            f"Risk: {self._get_risk_level()} ({self.risk_score:.2f}). "
            f"Suggested tests: {len(self.suggested_tests)} files."
        )


class ImpactAnalyzer:
    """
    ImpactAnalyzer - Layer A: Analysis Layer of NKS

    Analyzes the impact of code changes on the knowledge graph.
    Provides risk assessment and suggests test files to run.

    Features:
    - Direct impact analysis (callers/callees)
    - Transitive impact analysis (dependency chains)
    - Risk score calculation
    - Test file suggestion
    - Impact visualization via dependency chains
    """

    # Risk scoring weights
    CHANGE_TYPE_WEIGHTS = {
        "add": 0.1,
        "delete": 0.5,
        "modify": 0.3,
    }
    CHANGED_ENTITY_WEIGHT = 0.1
    DIRECT_IMPACT_WEIGHT = 0.05
    TRANSITIVE_IMPACT_WEIGHT = 0.02
    MAX_RISK_SCORE = 1.0

    # Default configuration
    DEFAULT_MAX_DEPTH = 5
    DEFAULT_TEST_PATTERNS = ["test_*.py", "*_test.py"]

    def __init__(self, graph_store: GraphStore | None = None, db_path: str | None = None) -> None:
        """
        Initialize ImpactAnalyzer.

        Args:
            graph_store: Existing GraphStore instance (optional)
            db_path: Path to GraphStore database (if graph_store not provided)
        """

        # Initialize or use provided GraphStore
        if graph_store:
            self.graph_store = graph_store
        elif db_path:
            self.graph_store = GraphStore(db_path)
        else:
            # Default database path using standard PathResolver
            try:
                from nucleus.Z_Microkernel.facades import get_path_resolver  # type: ignore[import-not-found]

                resolver = get_path_resolver()
                default_db = resolver.resolve_db("memory", "nks_graph.db")
            except ImportError:
                root_path = os.environ.get("BOS_ROOT", ".")
                default_db = str(Path(root_path) / "data" / "db" / "organs" / "memory" / "nks_graph.db")
            self.graph_store = GraphStore(str(default_db))

        # Cache for test file discovery
        self._test_file_cache: list[str] | None = None
        self._test_patterns = self.DEFAULT_TEST_PATTERNS

        # Metabolic tax for initialization
        self._deduct_metabolic_tax(amount=3.0)

    def _deduct_metabolic_tax(self, amount: float) -> None:
        _ = amount

    def _constraint_check(self, entity_id: str) -> bool:
        return True

    def analyze_impact(
        self,
        changed_entity_ids: list[str],
        change_type: str = "modify",
    ) -> ImpactReport:
        """
        Main entry point for impact analysis.

        Analyzes the impact of changes to specified entities.

        Args:
            changed_entity_ids: List of entity IDs that were changed
            change_type: Type of change - "add", "delete", or "modify"

        Returns:
            ImpactReport containing analysis results

        Raises:
            ValueError: If change_type is invalid
        """
        # Validate change type
        if change_type not in self.CHANGE_TYPE_WEIGHTS:
            raise ValueError(
                f"Invalid change_type: {change_type}. Must be one of: {list(self.CHANGE_TYPE_WEIGHTS.keys())}"
            )

        # Constraint check for operation
        self._constraint_check(f"analyze_impact:{change_type}")

        report = ImpactReport()

        # 1. Collect changed entities
        report.changed_entities = self._get_changed_entities(changed_entity_ids)

        # 2. Find direct impacts (callers and callees)
        report.direct_impacts = self._find_direct_impacts(report.changed_entities)

        # 3. Find transitive impacts (secondary dependencies)
        report.transitive_impacts = self._find_all_transitive_impacts(report.changed_entities, report.direct_impacts)

        # 4. Build dependency chains
        report.dependency_chains = self._build_dependency_chains(
            report.changed_entities, report.direct_impacts, report.transitive_impacts
        )

        # 5. Calculate risk score
        report.risk_score = self._calculate_risk_score(
            report.changed_entities, report.direct_impacts, report.transitive_impacts, change_type
        )

        # 6. Suggest test files
        all_impacted = report.changed_entities + report.direct_impacts + report.transitive_impacts
        report.suggested_tests = self._suggest_tests(report.changed_entities, all_impacted)

        # Metabolic tax for analysis
        self._deduct_metabolic_tax(amount=1.0 + len(changed_entity_ids) * 0.1)

        return report

    def _get_changed_entities(self, entity_ids: list[str]) -> list[Entity]:
        """Retrieve changed entities from graph store."""
        entities = []
        for entity_id in entity_ids:
            entity = self.graph_store.get_entity(entity_id)
            if entity:
                entities.append(entity)
        return entities

    def _find_direct_impacts(self, changed_entities: list[Entity]) -> list[Entity]:
        """
        Find entities directly impacted by changes.

        Direct impacts include:
        - Entities called by changed entities (outgoing)
        - Entities calling changed entities (incoming)
        """
        direct_impacts: dict[str, Entity] = {}
        changed_ids = {e.entity_id for e in changed_entities}

        for entity in changed_entities:
            # Get all relations for this entity
            relations = self.graph_store.get_relations_for_entity(entity.entity_id, direction="both")

            for relation in relations:
                # Add the other entity in the relation
                if relation.source_id == entity.entity_id:
                    other_id = relation.target_id
                else:
                    other_id = relation.source_id

                # Skip if it's one of the changed entities
                if other_id in changed_ids:
                    continue

                # Add to direct impacts
                other_entity = self.graph_store.get_entity(other_id)
                if other_entity and other_id not in direct_impacts:
                    direct_impacts[other_id] = other_entity

        return list(direct_impacts.values())

    def _find_all_transitive_impacts(
        self, changed_entities: list[Entity], direct_impacts: list[Entity]
    ) -> list[Entity]:
        """
        Find all transitive impacts for all changed entities.

        Combines results from BFS starting at each changed entity.
        """
        all_transitive: dict[str, Entity] = {}
        exclude_ids = {e.entity_id for e in changed_entities}
        exclude_ids.update(e.entity_id for e in direct_impacts)

        for entity in changed_entities:
            transitive = self._find_transitive_impacts(
                entity.entity_id, exclude_ids=exclude_ids, max_depth=self.DEFAULT_MAX_DEPTH
            )
            for impacted in transitive:
                if impacted.entity_id not in exclude_ids:
                    all_transitive[impacted.entity_id] = impacted

        return list(all_transitive.values())

    def _find_transitive_impacts(self, start_entity_id: str, exclude_ids: set[str], max_depth: int = 5) -> list[Entity]:
        """
        BFS to find transitive impacts starting from an entity.

        Args:
            start_entity_id: Entity ID to start from
            exclude_ids: Entity IDs to exclude (changed + direct)
            max_depth: Maximum depth to traverse

        Returns:
            List of transitively impacted entities
        """
        visited = set(exclude_ids)
        visited.add(start_entity_id)

        queue = deque([(start_entity_id, 0)])  # (entity_id, depth)
        transitive: list[Entity] = []

        while queue:
            current_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get outgoing relations (entities called by current)
            relations = self.graph_store.get_relations_for_entity(current_id, direction="outgoing")

            for relation in relations:
                target_id = relation.target_id

                if target_id not in visited:
                    visited.add(target_id)
                    entity = self.graph_store.get_entity(target_id)
                    if entity:
                        transitive.append(entity)
                        queue.append((target_id, depth + 1))

        return transitive

    def _calculate_risk_score(
        self,
        changed: list[Entity],
        direct: list[Entity],
        transitive: list[Entity],
        change_type: str,
    ) -> float:
        """
        Calculate overall risk score based on impact analysis.

        Risk factors:
        - Change type weight (delete > modify > add)
        - Number of changed entities
        - Number of direct impacts
        - Number of transitive impacts

        Args:
            changed: Changed entities
            direct: Directly impacted entities
            transitive: Transitively impacted entities
            change_type: Type of change

        Returns:
            Risk score between 0.0 and 1.0
        """
        # Base risk from change type
        risk = self.CHANGE_TYPE_WEIGHTS.get(change_type, 0.3)

        # Additional risk from impact scope
        risk += len(changed) * self.CHANGED_ENTITY_WEIGHT
        risk += len(direct) * self.DIRECT_IMPACT_WEIGHT
        risk += len(transitive) * self.TRANSITIVE_IMPACT_WEIGHT

        # Cap at maximum
        return min(risk, self.MAX_RISK_SCORE)

    def _suggest_tests(self, changed: list[Entity], impacted: list[Entity]) -> list[str]:
        """
        Suggest test files to run based on impact analysis.

        Strategy:
        1. Find test files in same directory as changed entities
        2. Find test files that reference impacted entities
        3. Include integration tests for high-impact changes

        Args:
            changed: Changed entities
            impacted: All impacted entities (direct + transitive)

        Returns:
            List of test file paths
        """
        suggested: set[str] = set()

        # Collect all source files from changed and impacted entities
        all_source_files: set[str] = set()
        for entity in changed + impacted:
            all_source_files.update(entity.source_files)

        # Discover available test files (cached)
        test_files = self._discover_test_files()

        # Strategy 1: Tests in same directory as source files
        for source_file in all_source_files:
            source_dir = Path(source_file).parent
            for test_file in test_files:
                test_path = Path(test_file)
                if test_path.parent == source_dir:
                    suggested.add(test_file)

        # Strategy 2: Tests with matching naming patterns
        for source_file in all_source_files:
            source_name = Path(source_file).stem
            for test_file in test_files:
                test_path = Path(test_file)
                test_name = test_path.stem
                # Match patterns like: module.py -> test_module.py
                if test_name.endswith(source_name) or test_name.startswith(f"test_{source_name}"):
                    suggested.add(test_file)

        # Strategy 3: Domain-specific tests
        domain_tests = self._find_domain_tests(changed + impacted)
        suggested.update(domain_tests)

        # Sort for consistent output
        return sorted(suggested)

    def _discover_test_files(self) -> list[str]:
        """Discover all test files in the project."""
        if self._test_file_cache is not None:
            return self._test_file_cache

        test_files: list[Path] = []
        root_path = Path(os.environ.get("BOS_ROOT", "."))
        tests_dir = root_path / "tests"

        if tests_dir.exists():
            for pattern in self._test_patterns:
                test_files.extend(tests_dir.rglob(pattern))

        self._test_file_cache = [str(f.relative_to(root_path)) for f in test_files]
        return self._test_file_cache

    def _find_domain_tests(self, entities: list[Entity]) -> list[str]:
        """Find tests specific to the domains of the entities."""
        domain_tests: set[str] = set()
        root_path = Path(os.environ.get("BOS_ROOT", "."))

        for entity in entities:
            # Extract domain from entity properties or source files
            domain = entity.properties.get("domain", "")

            if not domain:
                # Infer domain from source file path
                for source_file in entity.source_files:
                    if "organs/D-" in source_file:
                        parts = source_file.split("/")
                        if "organs" in parts:
                            idx = parts.index("organs")
                            if idx + 1 < len(parts) and parts[idx + 1].startswith("D-"):
                                domain = parts[idx + 1]
                                break

            if domain:
                # Look for domain-specific tests
                domain_test_dir = root_path / "tests" / "unit" / "organs" / domain
                if domain_test_dir.exists():
                    for test_file in domain_test_dir.rglob("test_*.py"):
                        domain_tests.add(str(test_file.relative_to(root_path)))

        return list(domain_tests)

    def _build_dependency_chains(
        self,
        changed: list[Entity],
        direct: list[Entity],
        transitive: list[Entity],
    ) -> list[list[str]]:
        """
        Build dependency chains showing impact propagation.

        Each chain shows a path from a changed entity to a transitively impacted entity.

        Returns:
            List of chains, where each chain is a list of entity IDs
        """
        chains: list[list[str]] = []
        direct_ids = {e.entity_id for e in direct}
        transitive_ids = {e.entity_id for e in transitive}

        for changed_entity in changed:
            # Build chains from this changed entity
            chains.extend(
                self._trace_dependency_chains(
                    changed_entity.entity_id,
                    direct_ids,
                    transitive_ids,
                    max_depth=self.DEFAULT_MAX_DEPTH,
                )
            )

        return chains

    def _trace_dependency_chains(
        self,
        start_id: str,
        target_ids: set[str],
        transitive_ids: set[str],
        max_depth: int = 5,
    ) -> list[list[str]]:
        """Trace all dependency chains from start_id to any target."""
        chains: list[list[str]] = []

        def dfs(current_id: str, path: list[str], depth: int) -> None:
            if depth > max_depth:
                return

            # Check if current is a target
            if current_id in target_ids and len(path) > 1:
                chains.append(path.copy())

            # Get outgoing relations
            relations = self.graph_store.get_relations_for_entity(current_id, direction="outgoing")

            for relation in relations:
                next_id = relation.target_id
                if next_id not in path:  # Avoid cycles
                    path.append(next_id)
                    dfs(next_id, path, depth + 1)
                    path.pop()

        dfs(start_id, [start_id], 0)
        return chains

    def analyze_file_change(self, file_path: str, change_type: str = "modify") -> ImpactReport:
        """
        Analyze impact of changes to a specific file.

        Convenience method that finds all entities associated with a file
        and analyzes their impact.

        Args:
            file_path: Path to the changed file
            change_type: Type of change

        Returns:
            ImpactReport
        """
        self._constraint_check(f"analyze_file_change:{file_path}")

        # Find all entities associated with this file
        # Search in graph store for entities with matching source_files
        entity_ids = self._find_entities_by_file(file_path)

        if not entity_ids:
            # Return empty report if no entities found
            return ImpactReport(
                risk_score=self.CHANGE_TYPE_WEIGHTS.get(change_type, 0.3),
                suggested_tests=self._suggest_tests_for_file(file_path),
            )

        return self.analyze_impact(entity_ids, change_type)

    def _find_entities_by_file(self, file_path: str) -> list[str]:
        """Find entity IDs associated with a source file."""
        # Query candidate entities by source file
        candidates = self.graph_store.get_candidate_entities(source_file=file_path)
        entity_ids = [c.entity_id for c in candidates]

        # Also search canonical entities by checking source_files JSON
        # This requires scanning, so we use a heuristic approach
        # In production, this could be optimized with a reverse index

        return entity_ids

    def _suggest_tests_for_file(self, file_path: str) -> list[str]:
        """Suggest tests for a specific file when no entities are found."""
        suggested: set[str] = set()
        root_path = Path(os.environ.get("BOS_ROOT", "."))

        # Look for test file in same directory
        file_dir = Path(file_path).parent
        file_name = Path(file_path).stem

        # Pattern: test_<file>.py or <file>_test.py
        test_patterns = [f"test_{file_name}.py", f"{file_name}_test.py"]
        for pattern in test_patterns:
            test_file = file_dir / pattern
            if test_file.exists():
                suggested.add(str(test_file.relative_to(root_path)))

        # Look in tests directory with matching structure
        tests_dir = root_path / "tests"
        if tests_dir.exists():
            for pattern in self._test_patterns:
                matching = list(tests_dir.rglob(f"*{file_name}*"))
                for match in matching:
                    if match.match(pattern):
                        suggested.add(str(match.relative_to(root_path)))

        return sorted(suggested)

    def get_impact_summary(self, report: ImpactReport) -> str:
        """Generate a human-readable impact summary."""
        lines = [
            "=" * 60,
            "IMPACT ANALYSIS REPORT",
            "=" * 60,
            f"Risk Score: {report.risk_score:.2f} ({report._get_risk_level()})",
            "",
            f"Changed Entities ({len(report.changed_entities)}):",
        ]

        for entity in report.changed_entities:
            lines.append(f"  - {entity.name} ({entity.entity_id})")

        lines.extend(
            [
                "",
                f"Direct Impacts ({len(report.direct_impacts)}):",
            ]
        )

        for entity in report.direct_impacts[:10]:  # Limit display
            lines.append(f"  - {entity.name} ({entity.entity_id})")

        if len(report.direct_impacts) > 10:
            lines.append(f"  ... and {len(report.direct_impacts) - 10} more")

        lines.extend(
            [
                "",
                f"Transitive Impacts ({len(report.transitive_impacts)}):",
            ]
        )

        for entity in report.transitive_impacts[:10]:
            lines.append(f"  - {entity.name} ({entity.entity_id})")

        if len(report.transitive_impacts) > 10:
            lines.append(f"  ... and {len(report.transitive_impacts) - 10} more")

        lines.extend(
            [
                "",
                f"Suggested Tests ({len(report.suggested_tests)}):",
            ]
        )

        for test in report.suggested_tests[:10]:
            lines.append(f"  - {test}")

        if len(report.suggested_tests) > 10:
            lines.append(f"  ... and {len(report.suggested_tests) - 10} more")

        if report.dependency_chains:
            lines.extend(
                [
                    "",
                    f"Dependency Chains ({len(report.dependency_chains)}):",
                ]
            )

            for chain in report.dependency_chains[:5]:
                lines.append(f"  {' -> '.join(chain)}")

            if len(report.dependency_chains) > 5:
                lines.append(f"  ... and {len(report.dependency_chains) - 5} more chains")

        lines.append("=" * 60)

        return "\n".join(lines)

    def ping(self) -> bool:
        """Health check for ImpactAnalyzer."""
        try:
            return self.graph_store.ping()
        except (TypeError, ValueError, AttributeError, RuntimeError):
            return False

    def _handle_analyze(self, params: dict) -> dict:
        """Handle 'analyze' action via BOS-URI protocol."""
        entity_ids = params.get("entity_ids", [])
        change_type = params.get("change_type", "modify")
        file_path = params.get("file_path")

        if file_path:
            report = self.analyze_file_change(file_path, change_type)
        else:
            report = self.analyze_impact(entity_ids, change_type)

        return {
            "status": "success",
            "report": report.to_dict(),
        }

    def _handle_summary(self, params: dict) -> dict:
        """Handle 'summary' action via BOS-URI protocol."""
        # Reuse analyze and format as summary
        result = self._handle_analyze(params)
        if result["status"] == "success":
            report_dict = result["report"]
            # Reconstruct minimal report for summary
            report = ImpactReport(
                risk_score=report_dict.get("risk_score", 0),
                suggested_tests=report_dict.get("suggested_tests", []),
            )
            return {
                "status": "success",
                "summary": report._generate_summary(),
                "risk_level": report._get_risk_level(),
            }
        return result
