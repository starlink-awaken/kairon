"""写入与查询统一中文分词(kos.tokenize)的回归测试。

2026-09-29 全链路实测: 线上文档经 `kos ingest` 写入时不切中文, unicode61 把整段汉字当一个
token, 中文关键词召回 14–42%, `kos context` 中文问题召回为空。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from kos.tokenize import fts_query, fts_text


def test_fts_query_contract():
    q = fts_query("双轨运行 多少天")
    assert " OR " in q and '"双轨运行"' in q  # 领域词典让「双轨运行」整体成词
    assert fts_query("xiamingxing") == "xiamingxing"
    assert fts_query("信息化 OR 平台") == "信息化 OR 平台"
    assert fts_query('"数据安全专项"').startswith('"') and " OR " not in fts_query('"数据安全专项"')


def test_fts_query_never_raises_syntax_error():
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(body)")
    conn.execute("INSERT INTO t VALUES (?)", (fts_text("C++ 与 HIS-迁移，等保三级（复测）"),))
    for q in ("C++ 与 HIS-迁移", "等保三级（复测）", "“双轨运行”", "a-b*c", "信创：替代？", "NEAR 附近"):
        conn.execute("SELECT count(*) FROM t WHERE t MATCH ?", (fts_query(q),)).fetchone()


def test_fts_text_segments_chinese_but_keeps_ascii():
    assert fts_text("核心业务系统替代实行双轨运行").count(" ") >= 2
    assert fts_text("plain english") == "plain english"


def _kos(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "KOS_HOME": str(home), "HOME": str(home)}
    return subprocess.run(
        [sys.executable, "-m", "kos.cli", *args], capture_output=True, text=True, env=env, timeout=300
    )


def test_ingest_then_chinese_search_and_context(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "rules.md").write_text(
        "# 区卫健委信创替代工作细则\n核心业务系统替代实行“双轨运行不少于 90 天”，双轨期间原系统只读保留。\n",
        encoding="utf-8",
    )
    (docs / "meeting.md").write_text(
        "# 信息化专题会纪要\n会议确定：朝阳分院作为第一批信创试点，张磊为试点项目负责人。\n", encoding="utf-8"
    )
    home = tmp_path / "kos"
    home.mkdir()
    assert _kos(home, "ingest", str(docs)).returncode == 0
    out = _kos(home, "search", "双轨运行").stdout
    assert "results" in out and " 0 results" not in out, out
    ctx = _kos(home, "context", "朝阳分院 信创试点 负责人")
    data = json.loads(ctx.stdout[ctx.stdout.index("{") :])
    knowledge = "\n".join(s["content"] for s in data["sections"] if s["type"] == "knowledge")
    assert "张磊" in knowledge, data
