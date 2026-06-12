"""kairon-observability 基础测试"""

import kairon_observability


class TestObservability:
    """可观测性测试"""

    def test_import(self):
        """测试导入"""
        assert kairon_observability is not None
