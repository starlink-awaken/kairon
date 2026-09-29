"""KOS 全文检索的唯一分词入口(写入与查询必须同一套切法)。

documents_fts 用 FTS5 默认 unicode61 分词器: 它不切中文, 一整段连续汉字会被当成一个
token。所以写入时要先用 jieba 切成空格分隔的词, 查询时同样切词再 OR 连接。

历史(2026-05 FAIL-20260513-005 → 2026-09-29 全链路实测): 5 月只在查询侧加了 jieba,
索引器会切词但线上 13588 篇全经 `kos ingest` 写入且不切词, 中文关键词召回 14–42%。
任何写 documents_fts 的地方都用 fts_text(), 任何 MATCH 的参数都用 fts_query()。
"""

from __future__ import annotations

import re
from pathlib import Path

_CJK = re.compile(r"[一-鿿]")
_WORD = re.compile(r"[\w一-鿿]")  # 至少含一个字母/数字/汉字才算词, 标点丢弃
_FTS_OPERATORS = re.compile(r"\s(OR|AND|NOT|NEAR)\s|NEAR\(")
_jieba = None


def _get_jieba():
    """惰性加载 jieba 与 KOS 自带用户词典; 未安装时返回 None(退化为原文)。"""
    global _jieba
    if _jieba is None:
        try:
            import jieba

            userdict = Path(__file__).parent / "indexer" / "data" / "jieba_userdict.txt"
            if userdict.exists():
                jieba.load_userdict(str(userdict))
            _jieba = jieba
        except ImportError:
            return None
    return _jieba


def tokenize_cn(text: str) -> str:
    """把文本切成空格分隔的词(英文与数字原样保留)。"""
    if not text:
        return text or ""
    jb = _get_jieba()
    if jb is None or not _CJK.search(text):
        return text
    return " ".join(t for t in jb.cut(text) if t.strip())


def fts_text(text: str) -> str:
    """写入 documents_fts 的标题/正文前调用。"""
    return tokenize_cn(text or "")


def _tokens(text: str) -> list[str]:
    return [t for t in tokenize_cn(text).split() if _WORD.search(t)]


def _quote(tok: str) -> str:
    return '"' + tok.replace('"', "") + '"'


def fts_query(query: str) -> str:
    """把用户输入转成 FTS5 MATCH 检索式。

    - 已含 OR/AND/NOT/NEAR 的原样保留(调用方自己写了检索式)
    - 引号内是短语: 切词后作为一个短语 "A B"
    - 其余含中文的部分: 切词, 每词加引号(防止 - + 等字符触发语法错误), OR 连接
    - 纯英文/数字: 原样保留
    """
    query = (query or "").strip()
    if not query or _FTS_OPERATORS.search(query):
        return query
    parts: list[str] = []
    for seg in re.split(r"""(["'][^"']*["'])""", query):
        seg = seg.strip()
        if not seg:
            continue
        if len(seg) > 1 and seg[0] == seg[-1] and seg[0] in "\"'":
            toks = _tokens(seg[1:-1])
            if toks:
                parts.append('"' + " ".join(t.replace('"', "") for t in toks) + '"')
            continue
        if not _CJK.search(seg):
            # 纯英文: 普通单词原样(保持 AND 语义); 带 - * : ^ ( ) 等的词加引号, 否则 FTS5 当语法解析
            words = [w if re.fullmatch(r"\w+", w) else _quote(w) for w in seg.split() if _WORD.search(w)]
            if words:
                parts.append(" ".join(words))
            continue
        toks = _tokens(seg)
        if toks:
            parts.append(" OR ".join(_quote(t) for t in toks))
    return " ".join(parts)
