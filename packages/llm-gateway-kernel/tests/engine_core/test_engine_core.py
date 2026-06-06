"""Tests for engine-core modules."""
import pytest

try:
    from llm_gateway_kernel.engine_core.capability import Capability, CapabilityCatalog
    from llm_gateway_kernel.engine_core.dag import TaskDAG, TaskNode
    from llm_gateway_kernel.engine_core.event_bus import EventBus, make_event
    from llm_gateway_kernel.engine_core.retry_policy import RetryPolicy, RetryState
    from llm_gateway_kernel.engine_core.task_store import TaskRecord, TaskState
except ImportError:
    pytest.skip("engine_core imports require kairon_lib (not in PYTHONPATH)", allow_module_level=True)


class TestRetryPolicy:
    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_attempts == 3
        assert p.backoff_base == 2.0

    def test_delay_increases(self):
        p = RetryPolicy(backoff_base=3.0)
        d1 = p.delay_for_attempt(1)
        d2 = p.delay_for_attempt(2)
        assert d2 > d1


class TestRetryState:
    def test_not_exhausted_initially(self):
        s = RetryState(attempt_count=0)
        assert hasattr(s, "exhausted")

    def test_exhausted_after_max(self):
        s = RetryState(attempt_count=5, next_retry_at=0.0)
        assert hasattr(s, "exhausted")


class TestCapability:
    def test_capability_exists(self):
        c = Capability(id="code", name="code", source="test")
        assert c.id == "code"

    def test_catalog_register(self):
        cat = CapabilityCatalog()
        cat.register(Capability(id="c1", name="c1", source="test"))
        assert len(cat._capabilities) == 1


class TestEventBus:
    def test_make_event(self):
        e = make_event("test_type", "src", {"k": "v"})
        assert e.event_type == "test_type"

    def test_listener_lifecycle(self):
        bus = EventBus()
        lid = bus.add_listener()
        bus.remove_listener(lid)


class TestDAG:
    def test_topological_sort(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(task_id="c", depends_on=["a", "b"]))
        dag.add_node(TaskNode(task_id="b", depends_on=["a"]))
        dag.add_node(TaskNode(task_id="a"))
        order = dag.topological_sort()
        assert order is not None
        assert order.index("a") < order.index("b") < order.index("c")

    def test_no_cycle(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(task_id="x"))
        assert not dag.has_cycle()

    def test_has_cycle(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(task_id="a", depends_on=["b"]))
        dag.add_node(TaskNode(task_id="b", depends_on=["a"]))
        assert dag.has_cycle()

    def test_critical_path(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(task_id="a", estimated_duration=1.0))
        dag.add_node(TaskNode(task_id="b", estimated_duration=3.0, depends_on=["a"]))
        path_len, _ = dag.critical_path()
        assert path_len == 4.0

    def test_node_count(self):
        dag = TaskDAG()
        dag.add_node(TaskNode(task_id="a"))
        assert dag.node_count == 1


class TestTaskStore:
    def test_task_state_enum(self):
        assert TaskState.pending.value == "pending"

    def test_task_record_defaults(self):
        r = TaskRecord(task_id="t1", intent="test")
        assert r.state == TaskState.pending

    def test_task_record_priority_validation(self):
        with pytest.raises(ValueError):
            TaskRecord(task_id="t1", intent="x", priority=0)
        with pytest.raises(ValueError):
            TaskRecord(task_id="t1", intent="x", priority=11)

    def test_task_record_roundtrip(self):
        r = TaskRecord(task_id="t1", intent="test", state=TaskState.running)
        row = r.to_row()
        r2 = TaskRecord.from_row(row)
        assert r2.task_id == "t1"
        assert r2.state == TaskState.running
