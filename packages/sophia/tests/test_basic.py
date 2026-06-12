"""sophia 基础测试"""

from sophia import cli
from sophia.compiler import Compiler


class TestCompiler:
    """编译器测试"""

    def test_import(self):
        """测试导入"""
        assert Compiler is not None

    def test_compiler_init(self):
        """测试编译器初始化"""
        compiler = Compiler()
        assert compiler is not None


class TestCLI:
    """CLI 测试"""

    def test_import(self):
        """测试 CLI 导入"""
        assert cli is not None
