"""kairon-lib-events 基础测试"""

import kairon_events


class TestKaironEvents:
    """事件库测试"""

    def test_import(self):
        """测试导入"""
        assert kairon_events is not None
