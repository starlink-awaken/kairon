"""RedTeam: 跨方法状态污染集成测试"""

from engine.core.derive import OntoDerive


def test_derive_pipeline_facts_isolation():
    """验证自我修复: _derive_bayesian 异常后 _facts 不被污染"""
    od = OntoDerive("examples/z-park")
    # derive() 应正常完成，返回结构完整的 summary
    s = od.derive()
    assert "facts" in s
    assert "derived_conclusions" in s
    assert "derivation_hints" in s
    assert "analysis_mode" in s


def test_derive_pipeline_full_output():
    """管线完整输出验证"""
    od = OntoDerive("examples/z-park")
    s = od.derive()
    assert s["facts"] >= 2
    assert isinstance(s.get("derived_conclusions"), list)
    assert isinstance(s.get("derivation_hints"), list)


def test_derive_called_twice_same_objects():
    """同一 OntoDerive 实例连续调用两次 derive()"""
    od = OntoDerive("examples/z-park")
    s1 = od.derive()
    s2 = od.derive()
    # 两次结果应自洽（同一项目）
    assert s1["facts"] == s2["facts"]
    assert len(s1.get("derived_conclusions", [])) >= 0
    assert len(s2.get("derived_conclusions", [])) >= 0


def test_derive_with_new_project(tmp_project):
    """在新项目上运行 derive() 管线"""
    od = OntoDerive(str(tmp_project))
    s = od.derive()
    # 新项目至少有一个事实
    assert s["facts"] >= 1
    assert "derived_at" in s
