"""Tests for KEMS Runtime — methodology operationalization."""

from sophia.kems_runtime import Chains, KemsRuntime, Planes, Protocols


class TestPlanes:
    """四平面验证 — 常量 + MAP 映射."""

    def test_has_four_constants(self):
        assert hasattr(Planes, "KNOWLEDGE")
        assert hasattr(Planes, "EXPERIENCE")
        assert hasattr(Planes, "METHODOLOGY")
        assert hasattr(Planes, "SYSTEM")

    def test_constant_values(self):
        assert Planes.KNOWLEDGE == "knowledge"
        assert Planes.EXPERIENCE == "experience"
        assert Planes.METHODOLOGY == "methodology"
        assert Planes.SYSTEM == "system"

    def test_map_has_four_entries(self):
        assert len(Planes.MAP) == 4

    def test_map_contains_all_planes(self):
        assert Planes.KNOWLEDGE in Planes.MAP
        assert Planes.EXPERIENCE in Planes.MAP
        assert Planes.METHODOLOGY in Planes.MAP
        assert Planes.SYSTEM in Planes.MAP

    def test_map_values_are_strings(self):
        for v in Planes.MAP.values():
            assert isinstance(v, str)
            assert len(v) > 0

    def test_knowledge_plane_mentions_kos(self):
        assert "KOS" in Planes.MAP[Planes.KNOWLEDGE]

    def test_experience_plane_mentions_gbrain(self):
        assert "gbrain" in Planes.MAP[Planes.EXPERIENCE]

    def test_methodology_plane_mentions_ontoderive(self):
        assert "ontoderive" in Planes.MAP[Planes.METHODOLOGY]

    def test_system_plane_mentions_ecos(self):
        assert "ecos" in Planes.MAP[Planes.SYSTEM]


class TestChains:
    """三链验证 — 常量 + MAP 映射."""

    def test_has_three_constants(self):
        assert hasattr(Chains, "DATA")
        assert hasattr(Chains, "METHOD")
        assert hasattr(Chains, "EVOLUTION")

    def test_constant_values(self):
        assert Chains.DATA == "data"
        assert Chains.METHOD == "method"
        assert Chains.EVOLUTION == "evolution"

    def test_map_has_three_entries(self):
        assert len(Chains.MAP) == 3

    def test_map_contains_all_chains(self):
        assert Chains.DATA in Chains.MAP
        assert Chains.METHOD in Chains.MAP
        assert Chains.EVOLUTION in Chains.MAP

    def test_map_values_are_strings(self):
        for v in Chains.MAP.values():
            assert isinstance(v, str)
            assert len(v) > 0

    def test_data_chain_mentions_kronos(self):
        assert "kronos" in Chains.MAP[Chains.DATA]

    def test_data_chain_mentions_eidos(self):
        assert "eidos" in Chains.MAP[Chains.DATA]

    def test_data_chain_mentions_kos(self):
        assert "KOS" in Chains.MAP[Chains.DATA]

    def test_method_chain_mentions_minerva(self):
        assert "minerva" in Chains.MAP[Chains.METHOD]

    def test_method_chain_mentions_ontoderive(self):
        assert "ontoderive" in Chains.MAP[Chains.METHOD]

    def test_method_chain_mentions_kos(self):
        assert "KOS" in Chains.MAP[Chains.METHOD]

    def test_evolution_chain_mentions_observe(self):
        assert "observe" in Chains.MAP[Chains.EVOLUTION]

    def test_evolution_chain_mentions_hypothesize(self):
        assert "hypothesize" in Chains.MAP[Chains.EVOLUTION]

    def test_evolution_chain_mentions_experiment(self):
        assert "experiment" in Chains.MAP[Chains.EVOLUTION]

    def test_evolution_chain_mentions_learn(self):
        assert "learn" in Chains.MAP[Chains.EVOLUTION]


class TestProtocols:
    """三协议验证 — 常量 + MAP 映射."""

    def test_has_three_constants(self):
        assert hasattr(Protocols, "KNOWLEDGE")
        assert hasattr(Protocols, "PROCESS")
        assert hasattr(Protocols, "EVOLUTION")

    def test_constant_values(self):
        assert Protocols.KNOWLEDGE == "knowledge"
        assert Protocols.PROCESS == "process"
        assert Protocols.EVOLUTION == "evolution"

    def test_map_has_three_entries(self):
        assert len(Protocols.MAP) == 3

    def test_map_contains_all_protocols(self):
        assert Protocols.KNOWLEDGE in Protocols.MAP
        assert Protocols.PROCESS in Protocols.MAP
        assert Protocols.EVOLUTION in Protocols.MAP

    def test_map_values_are_strings(self):
        for v in Protocols.MAP.values():
            assert isinstance(v, str)
            assert len(v) > 0

    def test_knowledge_protocol_mentions_eidos(self):
        assert "eidos" in Protocols.MAP[Protocols.KNOWLEDGE]

    def test_process_protocol_mentions_pipeline(self):
        assert "pipeline" in Protocols.MAP[Protocols.PROCESS]

    def test_evolution_protocol_mentions_hitl(self):
        assert "HITL" in Protocols.MAP[Protocols.EVOLUTION]

    def test_evolution_protocol_mentions_adaptation(self):
        assert "adaptation" in Protocols.MAP[Protocols.EVOLUTION]


class TestKemsRuntime:
    """KemsRuntime 综合验证."""

    def test_init_creates_planes(self):
        rt = KemsRuntime()
        assert hasattr(rt, "planes")
        assert isinstance(rt.planes, Planes)

    def test_init_creates_chains(self):
        rt = KemsRuntime()
        assert hasattr(rt, "chains")
        assert isinstance(rt.chains, Chains)

    def test_init_creates_protocols(self):
        rt = KemsRuntime()
        assert hasattr(rt, "protocols")
        assert isinstance(rt.protocols, Protocols)

    def test_describe_returns_dict(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert isinstance(result, dict)

    def test_describe_has_planes_key(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert "planes" in result

    def test_describe_has_chains_key(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert "chains" in result

    def test_describe_has_protocols_key(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert "protocols" in result

    def test_describe_planes_matches_planes_map(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["planes"] == dict(Planes.MAP)

    def test_describe_chains_matches_chains_map(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["chains"] == dict(Chains.MAP)

    def test_describe_protocols_matches_protocols_map(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["protocols"] == dict(Protocols.MAP)

    def test_describe_plane_knowledge_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["planes"]["knowledge"] == Planes.MAP["knowledge"]

    def test_describe_plane_experience_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["planes"]["experience"] == Planes.MAP["experience"]

    def test_describe_plane_system_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["planes"]["system"] == Planes.MAP["system"]

    def test_describe_plane_methodology_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["planes"]["methodology"] == Planes.MAP["methodology"]

    def test_describe_chain_data_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["chains"]["data"] == Chains.MAP["data"]

    def test_describe_chain_method_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["chains"]["method"] == Chains.MAP["method"]

    def test_describe_chain_evolution_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["chains"]["evolution"] == Chains.MAP["evolution"]

    def test_describe_protocol_knowledge_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["protocols"]["knowledge"] == Protocols.MAP["knowledge"]

    def test_describe_protocol_process_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["protocols"]["process"] == Protocols.MAP["process"]

    def test_describe_protocol_evolution_is_correct(self):
        rt = KemsRuntime()
        result = rt.describe()
        assert result["protocols"]["evolution"] == Protocols.MAP["evolution"]

    def test_multiple_instances_are_independent(self):
        rt1 = KemsRuntime()
        rt2 = KemsRuntime()
        assert rt1.describe() == rt2.describe()

    def test_describe_does_not_mutate_maps(self):
        rt = KemsRuntime()
        before = dict(Planes.MAP)
        rt.describe()
        assert Planes.MAP == before
