r"""Routing regression MATRIX for `classify_intent` — the net eval_harness is not.

WHY THIS FILE EXISTS
--------------------
`run_eval()` in `mos.eval_harness` is the package's nominal regression net, and it
reports 15/15 at score 1.0000. That number is real but it measures almost nothing
about routing precedence: all nine `intent` cases in `EVAL_CASES` are English
(`who calls function foo`, `open tasks and debt list`, ...) and none of them
contains a temporal token, so `_TEMPORAL_RE` cannot fire on any of them — not at
its current position (third), and not at the position it held before option B
(last). A change that moved the temporal check across six other checks therefore
scored a perfect 15/15 on both sides. This file is the missing baseline.

CALIBRATED AGAINST kairon origin/main (915fc76b) — READ THIS BEFORE TRUSTING A ROW
------------------------------------------------------------------------------
Every expectation here was measured, not assumed. The corpus was first written
against a WORKING TREE that carried three uncommitted edits; that worktree was
destroyed and none of it reached `origin/main`. Measured against the real module,
the corpus turned out to diverge from `origin/main` in THREE ways, not one:

  1. `_TEMPORAL_RE` is at position 3 (CODE, TASK, TEMPORAL, PREF, ENTITY, CARD,
     FILE) — so a time word outranks a document/card/preference noun.
  2. The six non-temporal patterns still wrap their CJK arms in `\b`, which is
     dead for CJK (see "THE CJK `\b` DEFECT" below).
  3. **AND — the one that dominates everything else — `_TEMPORAL_RE` does not
     contain a single year- or month-relative word.** Not 去年/今年/明年/前年/后年,
     not 上个月/本月/上月/下月/下个月, not 什么时候/期限/生效日/哪天/截止日期.
     `git log -S` over the whole of kairon history shows the regex has been
     byte-identical since it was introduced (`bf5c02db`) and has never held one.

Consequence, and it is the single most important line in this file:

    **0 of the 79 queries below match `_TEMPORAL_RE`.**

So cause (1) is currently INOBSERVABLE through this corpus. Moving `_TEMPORAL_RE`
to last — option B, the reorder the pending decision is about — changes no row in
this file. That is not a gap in the measurements; it is the measurement. Any claim
that this matrix guards the temporal/noun precedence boundary is false until
`_TEMPORAL_RE` gains the words the corpus actually uses, or the corpus is rebuilt
on words it already has. `test_temporal_token_gap_is_pinned` fails the moment
either happens, so the change cannot land silently.

WHY THE EXPECTATIONS LOOK THE WAY THEY DO
------------------------------------------
Each row carries a `cause` when its expectation was recalibrated off the original
intent. Two distinct defects are tracked and never collapsed into each other:

  * `temporal-token-gap` — the corpus's time word is absent from `_TEMPORAL_RE`
    (cause 3 above). A COVERAGE GAP, not a precedence decision.
  * `cjk-word-boundary-defect` — the route pattern's CJK arm is unreachable
    because of `\b` wrapping (cause 2). A BUG, tracked by
    BET-Y2Q4-T10-CJK-ROUTING; the fix is lost commit `2976f20`.

Collapsing these would hide a real, still-present routing bug behind a passing
test, so each is labelled per-row via `Probe.cause`, and `INTENDED` records what
the route SHOULD be once the corresponding defect is fixed. A row recalibrated
for cause 3 must never be read as endorsing the `general` it now pins.

THE CJK `\b` DEFECT
-------------------
`src/mos/routing.py` line 41 says, in a comment, "avoid \b for CJK tokens
(Python word-boundary is ASCII-oriented)" — and then does exactly that in the six
patterns below it. Python's `\b` is defined over `\w`, which for `str` patterns
IS Unicode-aware and therefore INCLUDES CJK. So `\b文档\b` only matches when
文档 is flanked by non-word characters. In `文档路径` the 路 is a word character,
there is no boundary after 文档, and the pattern does not fire. Line 41's own
rule is currently honoured by exactly one pattern — `_TEMPORAL_RE` — which is why
the year-relative rows below reach neither the temporal nor the noun route.

CATEGORIES
----------
See `CATEGORY_NOTES`. Category names describe the QUERY SHAPE, not the route it
lands on; where the two disagree the row says so in its own comment.

  * `pure-time`         — a time word, no carrier noun.
  * `time+<noun>`       — a time word attached to a carrier noun. These are the
                          rows the pending decision is actually about.
  * `noun-control`      — a noun with no time word. The control group.
  * `en-control`        — English controls mirroring the eval_harness corpus.
  * `temporal-negative` — near-miss tokens that must NOT become temporal.
  * `ambiguous`         — two or more patterns would match once the `\b` defect
                          is fixed. PINNED, NOT ENDORSED.

CITE
----
The precedence question these rows bear on is open and human-gated:
.omo/tasks/active/BET-Y2Q4-T10-TEMPORAL-PRECEDENCE.yaml (status: pending,
human_approval_required: true, circuit_breaker: 决策未落定前不得改动
classify_intent 的检查顺序). Nothing in this file endorses the current order.
"""

from __future__ import annotations

import inspect
import re
from typing import NamedTuple

from mos import routing
from mos.routing import classify_intent

# The three ways a row's expectation can diverge from its original intent. Kept as
# distinct constants because the first two are defects of different severity: a
# lost bug versus a vocabulary that was never written.
CAUSE_TEMPORAL_TOKEN_GAP = "temporal-token-gap"  # noqa: S105 -- defect label, not a credential
CAUSE_CJK_BOUNDARY = "cjk-word-boundary-defect"

# Categories whose rows carry a year-relative word. This is now a claim about the
# CORPUS, not about `_TEMPORAL_RE` — see the module docstring. It used to assert
# the latter, which made the whole matrix unsatisfiable on origin/main.
TEMPORAL_CATEGORIES = frozenset(
    {
        "pure-time",
        "time+doc",
        "time+card",
        "time+pref",
        "time+entity",
        "time+code",
        "time+task",
    }
)
CLEAN_CATEGORIES = frozenset({"noun-control", "en-control", "temporal-negative"})
# `live-precedence` carries temporal tokens that _TEMPORAL_RE ACTUALLY holds today
# (有效期/过期/effective/expired/until), so unlike the `time+*` blocks its rows
# genuinely contend with a noun pattern right now. It is the only part of this
# corpus that can observe the precedence boundary the pending decision is about.
LIVE_TEMPORAL_CATEGORIES = frozenset({"live-precedence"})
# `ambiguous` is in NEITHER set: the block is heterogeneous by construction.
EXEMPT_CATEGORIES = frozenset({"ambiguous"})

# Year-relative vocabulary this corpus is built on. Verified absent from
# `_TEMPORAL_RE` by `test_temporal_token_gap_is_pinned`.
CORPUS_YEAR_WORDS = (
    "去年",
    "今年",
    "明年",
    "前年",
    "后年",
    "上个月",
    "下个月",
    "本月",
    "上月",
    "下月",
    "什么时候",
    "截止日期",
    "期限",
    "生效日",
    "哪天",
    "失效",
)


CATEGORY_NOTES: dict[str, str] = {
    "pure-time": (
        "A time word and no carrier noun. On origin/main EVERY row here pins "
        "general, because no year-relative word is a `_TEMPORAL_RE` token "
        "(temporal-token-gap). So this block currently documents an UNREACHABLE "
        "route rather than a precedence baseline -- it is the corpus's loudest "
        "false promise and the reason `test_temporal_token_gap_is_pinned` exists."
    ),
    "time+doc": (
        "Time word + a document/file noun. CJK rows pin general via the `\\b` "
        "defect; `去年的 ADR 是什么` reaches file_note because ADR is an ASCII "
        "token and survives `\\b`. That contrast is the defect, in one block."
    ),
    "time+card": (
        "Time word + a card noun (卡片/知识卡片). All pin general: 卡片 is CJK and "
        "`\\b`-wrapped, so `_CARD_RE` cannot fire on any real Chinese query."
    ),
    "time+pref": (
        "Time word + a preference noun. SPLIT, and the split is the finding. "
        "喜欢/过敏 are `_PREF_RE` CJK tokens, dead under `\\b`; 偏好 ('preference') "
        "is in NEITHER arm -- the ASCII arm has prefer|preference and the CJK arm "
        "has no 偏好. Both halves therefore pin general, for different reasons; the "
        "second also carries the temporal-token gap."
    ),
    "time+entity": (
        "Time word + a relation noun (关系/谁投资). All pin general via the `\\b` "
        "defect. The English control `who invested in Acme` reaches "
        "entity_relation, so the ASCII arm of `_ENTITY_RE` is live."
    ),
    "time+code": (
        "Time word + a code noun. The three CJK rows pin general via the `\\b` "
        "defect. `去年的 call graph 有变化吗` reaches code_structure because "
        "`call graph` is ASCII and survives `\\b`. `去年的重构在哪个文件` is filed "
        "here against its intent on purpose: 重构 is not a `_CODE_RE` token, so "
        "even with the defect fixed it is 哪个文件 (FILE) that would claim it."
    ),
    "time+task": (
        "Time word + a task/debt noun (任务/债务/开放任务). All pin general via the "
        "`\\b` defect. Note `去年的任务` is the one row the pending decision's own "
        "table records as already changing hands (TASK precedes TEMPORAL) -- that "
        "only becomes observable once the temporal tokens exist."
    ),
    "noun-control": (
        "CONTROL GROUP -- a noun with NO time word, and the block that carries the "
        "`\\b` defect most visibly: 13 of 14 rows pin general purely because the "
        "route's CJK arm is dead. `哪个文件记录了 ADR` is the lone row that routes, "
        "via the ASCII `ADR` token. These are the rows mutation-testing the CJK fix "
        "is expected to move."
    ),
    "en-control": (
        "English controls, mirroring the eval_harness intent corpus so this matrix "
        "and run_eval() can be compared row-for-row. All 13 are GREEN and were "
        "never recalibrated: every ASCII arm of every pattern survives `\\b`, which "
        "localises the defect to CJK and nothing else."
    ),
    "temporal-negative": (
        "Near-miss tokens that must not become temporal: bare 日期/时间 are too "
        "broad. All pin general -- but note that on origin/main they would pin "
        "general even if they DID match a temporal token, so this block currently "
        "cannot fail. It guards token drift only once the gap above is closed. "
        "The ASCII near-misses `taskforce`/`recard` live in `en-control`."
    ),
    "live-precedence": (
        "THE ONLY BLOCK THAT OBSERVES TEMPORAL PRECEDENCE TODAY. Each row pairs a "
        "token `_TEMPORAL_RE` really holds (有效期/过期/effective/expired/until) with "
        "a noun token from another pattern, so at least two patterns match and the "
        "winner is decided purely by check order. These rows are what makes the "
        "reorder observable: moving `_TEMPORAL_RE` to last, or deleting it, moves "
        "this block and nothing else in the file. Everything in `pure-time` and "
        "`time+*` is inert with respect to precedence until the corpus time words "
        "enter the pattern -- see the module docstring."
    ),
    "ambiguous": (
        "PINNED, NOT ENDORSED. Each row matches two or more patterns ONCE THE `\\b` "
        "DEFECT IS FIXED, so today the winner is decided by nothing at all -- every "
        "row falls to general. Which pattern would win is still purely a function "
        "of check order, which is exactly what the pending decision has to settle. "
        "`test_ambiguous_rows_really_are_ambiguous` evaluates the corrected "
        "patterns so the label keeps meaning what it claims."
    ),
}


class Probe(NamedTuple):
    category: str
    query: str
    expected: str
    # One or more of the CAUSE_* constants; "" when the row was already correct on
    # origin/main. Machine-readable so the invariant tests below can require a
    # label rather than trusting a prose comment.
    cause: str = ""


# Route each recalibrated row SHOULD have, keyed by query. Only rows in
# INTENDED_CAUSES carry an entry: a row that was already green needs no intent.
INTENDED: dict[str, str] = {}
INTENDED_CAUSES: dict[str, str] = {}


# ---------------------------------------------------------------------------------------
# PURE TIME — 15 rows, all temporal-token-gap.
#
# Original intent: every one of these reaches temporal_fact on a `_TEMPORAL_RE` that
# recognises year-relative words. On origin/main it does not, and never has
# (`git log -S"去年" -- packages/mos/src/mos/routing.py` is empty). These pin general.
# `什么时候生效` is the sharpest one: 生效 is adjacent to the live 何时生效 token, but
# 生效 alone is not a token, so the near-miss does not save it.
# ---------------------------------------------------------------------------------------
PURE_TIME: tuple[Probe, ...] = tuple(
    Probe("pure-time", q, "general", CAUSE_TEMPORAL_TOKEN_GAP)
    for q in (
        "去年做过什么",
        "明年的计划",
        "上个月发生了什么",
        "什么时候生效",
        "截止日期是什么时候",
        "今年的计划是什么",
        "前年做过什么",
        "后年的安排",
        "下个月的计划",
        "本月的工作",
        "上月的事",
        "下月的安排",
        "期限是什么时候",
        "生效日在哪天",
        "什么时候失效",
    )
)
INTENDED.update({p.query: "temporal_fact" for p in PURE_TIME})
INTENDED_CAUSES.update({p.query: CAUSE_TEMPORAL_TOKEN_GAP for p in PURE_TIME})

# ---------------------------------------------------------------------------------------
# TIME + DOC — 7 rows of token-gap + CJK-`\b`, 1 row green.
#
# `去年的 ADR 是什么` was NEVER recalibrated: ADR is an ASCII token in `_FILE_RE`
# and `\bADR\b` matches between two spaces. It is the control that proves the
# divergence is CJK-specific rather than a broken `_FILE_RE`.
# ---------------------------------------------------------------------------------------
TIME_DOC_GREEN = Probe("time+doc", "去年的 ADR 是什么", "file_note")

# Fixed 2026-10-06 (BET-Y2Q4-T3-04): the CJK arms no longer carry `\b`, so these
# rows now reach file_note — their INTENDED route. Green; no cause label remains.
TIME_DOC_CJK: tuple[Probe, ...] = tuple(
    Probe("time+doc", q, "file_note")
    for q in (
        "去年写的文档在哪",  # 文档 — `_FILE_RE` CJK arm
        "去年笔记里写了什么",  # 笔记 — same
        "去年的文档",  # 文档
        "明年的文档计划",  # 文档
        "去年哪个文件记录了这个决定",  # 哪个文件
        "去年做的文档",  # 文档
        "去年的文档路径是什么",  # 文档 + 路径
    )
)
TIME_DOC = (TIME_DOC_GREEN,) + TIME_DOC_CJK

# ---------------------------------------------------------------------------------------
# TIME + CARD — 4 rows, all token-gap + CJK-`\b`.
# `知识卡片`/`卡片` are `_CARD_RE` CJK tokens; no ASCII arm exists to carry the route.
# ---------------------------------------------------------------------------------------
# Fixed 2026-10-06 (BET-Y2Q4-T3-04): 知识卡片/卡片 are `_CARD_RE` CJK tokens and now
# reachable. Green; no cause label.
TIME_CARD: tuple[Probe, ...] = tuple(
    Probe("time+card", q, "card_ops")
    for q in (
        "去年做的知识卡片",
        "去年的卡片",
        "今年新建的卡片",
        "去年的知识卡片",
    )
)

# ---------------------------------------------------------------------------------------
# TIME + PREF — the split block, and the two halves are NOT the same defect.
#
# HALF 1 (rows 1-3): the noun IS a `_PREF_RE` CJK token (喜欢/过敏), dead under `\b`.
#   These SHOULD reach preference_self once the `\b` defect is fixed.
# HALF 2 (rows 4-6): 偏好 ('preference') is in NEITHER arm of `_PREF_RE` -- a lexical
#   gap independent of `\b` -- AND the year word is not a `_TEMPORAL_RE` token. The
#   original file expected temporal_fact for these, reasoning that with no
#   recognized noun they are pure-time. That reasoning still holds; it just cannot
#   fire on origin/main. Labelled token-gap alone, because fixing `\b` will NOT
#   move them -- they need 偏好 in the CJK arm AND the temporal tokens.
# ---------------------------------------------------------------------------------------
TIME_PREF_CJK: tuple[Probe, ...] = (
    # Fixed 2026-10-06 (BET-Y2Q4-T3-04): 喜欢/过敏 are `_PREF_RE` CJK tokens and now
    # reachable. Green.
    Probe("time+pref", "去年的过敏信息", "preference_self"),
    Probe("time+pref", "去年我喜欢什么", "preference_self"),
    Probe("time+pref", "去年喜欢吃什么", "preference_self"),
)
TIME_PREF_LEXICAL: tuple[Probe, ...] = (
    Probe("time+pref", "我去年的偏好", "general", CAUSE_TEMPORAL_TOKEN_GAP),
    Probe("time+pref", "去年记住了什么偏好", "general", CAUSE_TEMPORAL_TOKEN_GAP),
    Probe("time+pref", "去年的偏好是什么", "general", CAUSE_TEMPORAL_TOKEN_GAP),
)
TIME_PREF = TIME_PREF_CJK + TIME_PREF_LEXICAL
INTENDED.update({p.query: "temporal_fact" for p in TIME_PREF_LEXICAL})
INTENDED_CAUSES.update({p.query: CAUSE_TEMPORAL_TOKEN_GAP for p in TIME_PREF_LEXICAL})

# ---------------------------------------------------------------------------------------
# TIME + ENTITY — 3 rows, all token-gap + CJK-`\b` (关系 / 谁投资).
# ---------------------------------------------------------------------------------------
TIME_ENTITY: tuple[Probe, ...] = tuple(
    # Fixed 2026-10-06 (BET-Y2Q4-T3-04): 关系 / 谁投资 now reachable. Green.
    Probe("time+entity", q, "entity_relation")
    for q in (
        "谁投资了去年的公司",
        "去年的关系是什么",
        "去年谁投资了这家公司",
    )
)

# ---------------------------------------------------------------------------------------
# TIME + CODE — 2 recalibrated + 2 green.
#
# `去年的 call graph 有变化吗` is green: `call graph` is ASCII and survives `\b`, which
# is the control proving `_CODE_RE` itself is intact and only its CJK arm is dead.
# `去年的重构在哪个文件` pins general here because 哪个文件 is CJK and `\b`-wrapped, but
# its INTENT stays file_note: 重构 is not a `_CODE_RE` token, so even with the defect
# fixed, 哪个文件 (FILE) is what claims this row — not CODE. That divergence is the
# interesting fact and filing it under time+code against its intent keeps it visible.
# ---------------------------------------------------------------------------------------
TIME_CODE_GREEN = Probe("time+code", "去年的 call graph 有变化吗", "code_structure")

TIME_CODE_CJK: tuple[Probe, ...] = (
    # Fixed 2026-10-06 (BET-Y2Q4-T3-04): 谁调用/调用了/函数 now reachable. Green.
    Probe("time+code", "谁调用了去年的那个函数", "code_structure"),
    Probe("time+code", "去年改了哪个函数", "code_structure"),
)
# Filed in time+code against its intent ON PURPOSE: the user asking this is asking a
# code question, but 哪个文件 is a `_FILE_RE` token and 重构 is not a `_CODE_RE` token,
# so file_note is where it belongs now that `\b` is fixed. Moving it to time+doc would
# hide that divergence.
TIME_CODE_FILE = Probe(
    "time+code",
    "去年的重构在哪个文件",
    "file_note",
)
TIME_CODE = (TIME_CODE_GREEN,) + TIME_CODE_CJK + (TIME_CODE_FILE,)

# ---------------------------------------------------------------------------------------
# TIME + TASK — 5 rows, all token-gap + CJK-`\b` (任务 / 债务 / 开放任务).
# `去年的任务` is the row the pending decision's table flags as TASK-vs-TEMPORAL.
# ---------------------------------------------------------------------------------------
TIME_TASK: tuple[Probe, ...] = tuple(
    # Fixed 2026-10-06 (BET-Y2Q4-T3-04): 任务 / 债务 / 开放任务 now reachable. Green.
    Probe("time+task", q, "task_debt")
    for q in (
        "去年的任务",
        "去年完成的任务清单",
        "去年的债务",
        "去年开放任务",
        "去年有哪些任务",
    )
)

# ---------------------------------------------------------------------------------------
# CONTROL GROUP — noun, no time word. 13 CJK-`\b` rows, 1 green (the ASCII `ADR`).
# ---------------------------------------------------------------------------------------
NOUN_CONTROL_GREEN = Probe("noun-control", "哪个文件记录了 ADR", "file_note")

# Fixed 2026-10-06 (BET-Y2Q4-T3-04): every CJK noun control now reaches its route
# (the ASCII `ADR` row was already green). No cause labels remain.
_INTENDED_NOUN_CONTROL = {
    "文档路径": "file_note",
    "知识卡片在哪里": "card_ops",
    "过敏信息": "preference_self",
    "谁投资了这家公司": "entity_relation",
    "任务列表": "task_debt",
    "谁调用了这个函数": "code_structure",
    "具体的调用关系是什么": "entity_relation",
    "我的偏好是素食": "preference_self",
    "打开任务和债务": "task_debt",
    "我对花生过敏": "preference_self",
    "这张卡片的内容是什么": "card_ops",
    "帮我新建一张卡片": "card_ops",
    "哪个笔记记了这件事": "file_note",
}
NOUN_CONTROL: tuple[Probe, ...] = tuple(
    Probe("noun-control", q, route) for q, route in _INTENDED_NOUN_CONTROL.items()
)
NOUN_CONTROL_ALL = (NOUN_CONTROL_GREEN,) + NOUN_CONTROL

# ---------------------------------------------------------------------------------------
# ENGLISH CONTROLS — all 13 green, never recalibrated. Every ASCII arm survives `\b`,
# which is what localises the whole defect to CJK.
# `taskforce` / `recard` live here, not in temporal-negative: they exercise the ASCII
# `\b` on `_TASK_RE`/`_CARD_RE`, not a temporal decision.
# ---------------------------------------------------------------------------------------
EN_CONTROL: tuple[Probe, ...] = (
    Probe("en-control", "who calls function foo", "code_structure"),
    Probe("en-control", "open tasks and debt", "task_debt"),
    Probe("en-control", "my preference is vegetarian", "preference_self"),
    Probe("en-control", "which ADR documents Memory OS", "file_note"),
    Probe("en-control", "hello world", "general"),
    Probe("en-control", "caller of bar method", "code_structure"),
    Probe("en-control", "find vault notes about governance", "file_note"),
    Probe("en-control", "knowledge card slug", "card_ops"),
    Probe("en-control", "who invested in Acme", "entity_relation"),
    Probe("en-control", "show the call graph", "code_structure"),
    Probe("en-control", "which file has the schema", "file_note"),
    Probe("en-control", "taskforce regroup", "general"),
    Probe("en-control", "recard the deck", "general"),
)

TEMPORAL_NEGATIVE: tuple[Probe, ...] = (
    Probe("temporal-negative", "这个日期怎么填", "general"),
    Probe("temporal-negative", "现在几点", "general"),
    Probe("temporal-negative", "会议时间改到几点", "general"),
)

# ---------------------------------------------------------------------------------------
# AMBIGUOUS — PINNED, NOT ENDORSED. Fixed 2026-10-06 (BET-Y2Q4-T3-04): with the CJK
# arms reachable, every row below matches two or more patterns, so the winner is a
# pure function of check order — which is exactly the open decision.
#
#   函数在哪个文件          CODE(函数) vs FILE(哪个文件)      -> code_structure
#   去年写的文档在哪个文件   FILE(文档, 哪个文件) + year word  -> file_note
#   谁调用了去年的任务       CODE(谁调用, 调用了) vs TASK(任务) -> code_structure
#   谁投资了去年的卡片       ENTITY(谁投资) vs CARD(卡片)       -> entity_relation
#
# Note 谁投资了去年的卡片: ENTITY is checked before CARD, so it lands on
# entity_relation purely by check order. The previous round judged that strictly
# WORSE than the temporal route claiming it -- asking about a card and being handed
# an entity-relation query is the wrong backend set. That judgment is preserved here
# rather than quietly re-baselined; resolving it is the point of the open decision.
# ---------------------------------------------------------------------------------------
AMBIGUOUS: tuple[Probe, ...] = (
    Probe("ambiguous", "函数在哪个文件", "code_structure"),
    Probe("ambiguous", "去年写的文档在哪个文件", "file_note"),
    Probe("ambiguous", "谁调用了去年的任务", "code_structure"),
    Probe("ambiguous", "谁投资了去年的卡片", "entity_relation"),
)

# ---------------------------------------------------------------------------------------
# LIVE PRECEDENCE — 7 rows, every one MEASURED, none recalibrated, no `cause`.
#
# Unlike `pure-time` and `time+*`, these use temporal tokens `_TEMPORAL_RE` actually
# holds on origin/main, so two patterns really do match each row and the winner is
# decided purely by the order of the `if` statements. That makes them the matrix's
# only working instrument on the precedence boundary:
#
#   CODE and TASK precede TEMPORAL -> those rows route to the noun, proving the
#                                     temporal check is NOT first.
#   TEMPORAL precedes PREF/ENTITY/CARD/FILE -> those rows route temporal_fact,
#                                     proving the temporal check is NOT last.
#
# Read together the six rows pin the exact order origin/main implements:
# CODE < TASK < TEMPORAL < PREF < ENTITY < CARD < FILE.
#
# Deliberately ASCII-only in the noun arm (`ADR`, `card`, `task`, `preference`,
# `relation`, `call graph`). A CJK noun here would be dead under the `\b` defect and
# the row would collapse into the `general` pins above -- i.e. it would stop testing
# precedence and start testing the bug. Mixed forms (过期 ADR / 有效期 ADR) are
# included to show the CJK temporal tokens are live, which is the whole reason
# `_TEMPORAL_RE` is the one pattern that obeys the line-41 rule.
#
# These expectations WILL change if option B is adopted, and that is the point: they
# are the rows a reorder is supposed to show up in.
# ---------------------------------------------------------------------------------------
LIVE_PRECEDENCE: tuple[Probe, ...] = (
    # CODE precedes TEMPORAL -> temporal loses.
    Probe("live-precedence", "effective call graph", "code_structure"),
    # TASK precedes TEMPORAL -> temporal loses.
    Probe("live-precedence", "expired task", "task_debt"),
    # TEMPORAL precedes FILE.
    Probe("live-precedence", "effective ADR", "temporal_fact"),
    Probe("live-precedence", "过期 ADR", "temporal_fact"),
    Probe("live-precedence", "有效期 ADR", "temporal_fact"),
    # TEMPORAL precedes CARD / PREF / ENTITY.
    Probe("live-precedence", "effective card", "temporal_fact"),
    Probe("live-precedence", "effective preference", "temporal_fact"),
    Probe("live-precedence", "effective relation", "temporal_fact"),
)

PROBE_SET: tuple[Probe, ...] = (
    PURE_TIME
    + TIME_DOC
    + TIME_CARD
    + TIME_PREF
    + TIME_ENTITY
    + TIME_CODE
    + TIME_TASK
    + LIVE_PRECEDENCE
    + NOUN_CONTROL_ALL
    + EN_CONTROL
    + TEMPORAL_NEGATIVE
    + AMBIGUOUS
)

BY_CATEGORY: dict[str, tuple[Probe, ...]] = {}
for _probe in PROBE_SET:
    BY_CATEGORY[_probe.category] = BY_CATEGORY.get(_probe.category, ()) + (_probe,)

# The route patterns in the order classify_intent checks them on origin/main.
ROUTE_PATTERNS = (
    routing._CODE_RE,
    routing._TASK_RE,
    routing._TEMPORAL_RE,
    routing._PREF_RE,
    routing._ENTITY_RE,
    routing._CARD_RE,
    routing._FILE_RE,
)


def _corrected(pattern: re.Pattern[str]) -> re.Pattern[str]:
    """`pattern` with every `\\b` removed — models the lost CJK fix `2976f20`.

    Stripping `\b` wholesale (rather than splitting the arms) is deliberate: these
    patterns are alternations of ASCII and CJK literals, and the diagnostic question
    this file needs answered is "would this row route anywhere if the CJK arms were
    reachable", not "would the ASCII arms over-match". The ASCII arms are protected
    by the `en-control` block, which is green today and must stay green.
    """
    return re.compile(pattern.pattern.replace(r"\b", ""), pattern.flags)


CORRECTED_PATTERNS = tuple(_corrected(rx) for rx in ROUTE_PATTERNS)

# ROUTE_NAMES is the order `classify_intent` checks the patterns in, on origin/main.
ROUTE_NAMES = (
    "code_structure",
    "task_debt",
    "temporal_fact",
    "preference_self",
    "entity_relation",
    "card_ops",
    "file_note",
)


def _route(patterns: tuple[re.Pattern[str], ...], query: str) -> str:
    """Classify `query` against `patterns` without touching routing.py.

    Takes the pattern list as an argument precisely so this file can ask
    "what WOULD happen if both defects were closed" without mutating the module it
    is pinning.
    """
    for i, rx in enumerate(patterns):
        if rx.search(query):
            return ROUTE_NAMES[i]
    return "general"


def _hypothetical_patterns() -> tuple[re.Pattern[str], ...]:
    """Both defects closed: CJK arms reachable AND the corpus time vocabulary live.

    This is the standard the corpus is measured against wherever the question is
    "what would the route be", as opposed to "what is the route". Using one function
    for both keeps the ambiguity invariant and the coverage invariant from quietly
    disagreeing about what the matrix is supposed to prove.
    """
    return CORRECTED_PATTERNS[:2] + (re.compile("|".join(CORPUS_YEAR_WORDS)),) + CORRECTED_PATTERNS[3:]


HYPOTHETICAL_PATTERNS = _hypothetical_patterns()


def _assert_block(category: str) -> None:
    """Assert every row of one category, reporting ALL moved rows at once.

    Stopping at the first mismatch would hide the shape of a regression: "one row
    moved" and "this whole category moved" call for different responses. Each moved
    row is reported with the route it SHOULD reach if its labelled defect is fixed,
    so a genuine regression is never mistaken for a known-defect row.
    """
    rows = BY_CATEGORY[category]
    moved = []
    for p in rows:
        actual = classify_intent(p.query)
        if actual == p.expected:
            continue
        intended = INTENDED.get(p.query)
        detail = f"expected {p.expected!r}, got {actual!r}"
        if intended:
            detail += (
                f"\n        KNOWN {p.cause}: should be {intended!r} once "
                f"{p.cause} is fixed — do NOT read this pin as endorsement"
            )
        moved.append(f"      {p.query!r}\n        {detail}")
    assert not moved, (
        f"routing matrix regression in [{category}] — {len(moved)} of {len(rows)} rows moved.\n"
        f"  {CATEGORY_NOTES[category]}\n"
        f"  If this is a routing change, update the expectations in "
        f"tests/test_routing_matrix.py deliberately and adjust the row's `cause`. "
        f"If it is not, the token set or the check order in src/mos/routing.py "
        f"regressed.\n" + "\n".join(moved)
    )


def test_pure_time_routes_to_temporal_fact():
    """NAME IS THE ORIGINAL INTENT; the pin is general. See the module docstring.

    The test name is kept so the diff against the pre-loss revision stays legible,
    but it must not be read as claiming these rows reach temporal_fact. They do not,
    and `test_temporal_token_gap_is_pinned` is the test that says so out loud.
    """
    _assert_block("pure-time")


def test_time_plus_document_routes_to_file_note():
    _assert_block("time+doc")


def test_time_plus_card_routes_to_card_ops():
    _assert_block("time+card")


def test_time_plus_preference_matrix():
    _assert_block("time+pref")


def test_time_plus_entity_routes_to_entity_relation():
    _assert_block("time+entity")


def test_time_plus_code_matrix():
    _assert_block("time+code")


def test_time_plus_task_routes_to_task_debt():
    _assert_block("time+task")


def test_noun_only_controls_are_unchanged():
    _assert_block("noun-control")


def test_english_controls_are_unchanged():
    _assert_block("en-control")


def test_near_miss_tokens_do_not_route_to_temporal():
    _assert_block("temporal-negative")


def test_live_precedence_pins_the_implemented_check_order():
    _assert_block("live-precedence")


def test_ambiguous_rows_are_pinned_not_endorsed():
    _assert_block("ambiguous")


# ---------------------------------------------------------------------------------------
# Semantic claims -- stated as properties, not as a snapshot of the table above.
# ---------------------------------------------------------------------------------------


def test_temporal_token_gap_is_pinned():
    """The corpus's time vocabulary is absent from `_TEMPORAL_RE`. THIS IS THE FINDING.

    On origin/main not one of the corpus's 79 original rows matches
    `_TEMPORAL_RE`, so the whole temporal/noun precedence boundary as this corpus
    states it -- the subject of the pending decision -- is unobservable through it.
    (The `live-precedence` block is deliberately excluded: it uses tokens the regex
    really holds, and existing is its entire purpose.) Asserting the gap makes it a
    tripwire in BOTH directions: it goes red the moment someone adds 去年/今年/… to
    the pattern, forcing the precedence matrix to be rebuilt and the decision
    re-baselined, instead of the corpus quietly going stale.
    """
    corpus_rows = [p for category in TEMPORAL_CATEGORIES for p in BY_CATEGORY[category]]
    hits = [p.query for p in corpus_rows if routing._TEMPORAL_RE.search(p.query)]
    assert not hits, (
        f"{len(hits)} corpus row(s) now match `_TEMPORAL_RE`, e.g. {hits[:3]}. The "
        "temporal-token-gap pins in this file are now WRONG: recalibrate the "
        "temporal categories against measured behavior and re-open the precedence "
        "matrix. The pending decision "
        "(.omo/tasks/active/BET-Y2Q4-T10-TEMPORAL-PRECEDENCE.yaml) cannot be "
        "answered from a corpus where the temporal route is unreachable."
    )


def test_cjk_word_boundary_defect_is_fixed():
    """The six CJK arms are reachable. This is the failing-then-passing guard.

    Pre-fix (origin/main 915fc76) every CJK arm below returned no match: the whole
    alternation was wrapped in `\\b`, which cannot delimit a CJK token sitting inside
    a CJK run. Post-fix (BET-Y2Q4-T3-04) the CJK arms carry no `\\b` and match.
    Run against the pre-fix routing.py this test FAILS; against the fixed routing.py
    it PASSES. ASCII arms keep `\\b`, so taskforce / recard / vaulted still do not
    match — the fix must not widen the ASCII arms.
    """
    cjk_tokens = {
        routing._CODE_RE: ("谁调用", "调用了", "函数"),
        routing._TASK_RE: ("任务", "债务", "开放任务"),
        routing._PREF_RE: ("过敏", "素食", "喜欢"),
        routing._ENTITY_RE: ("关系", "谁投资"),
        routing._CARD_RE: ("卡片",),
        routing._FILE_RE: ("文档", "笔记", "哪个文件"),
    }
    checked = 0
    for pattern, tokens in cjk_tokens.items():
        for token in tokens:
            query = f"前缀{token}后缀"  # CJK on both sides => no word boundary
            assert routing._TEMPORAL_RE.search(query) is None, (
                f"probe scaffolding query {query!r} accidentally matches a temporal "
                "token; it cannot isolate the CJK arms"
            )
            assert pattern.search(query) is not None, (
                f"{token!r} does not match {pattern.pattern!r} inside {query!r}. The "
                "CJK arm is still unreachable — the `\\b` defect has regressed or the "
                "token set changed; recalibrate against measured behavior."
            )
            checked += 1
    assert checked >= 12, f"only {checked} CJK tokens checked; the sweep shrank"

    # The ASCII half of each alternation must still be word-bounded: a longer ASCII
    # word containing the token must NOT match.
    for query, pattern in (
        ("taskforce", routing._TASK_RE),
        ("recard", routing._CARD_RE),
        ("vaulted", routing._FILE_RE),
    ):
        assert pattern.search(query) is None, (
            f"ASCII arm of {pattern.pattern!r} over-matched {query!r}; the CJK fix "
            "must not drop the ASCII word boundary"
        )


def test_intended_routes_are_unreachable_today():
    """Every recalibrated row pins general, and should route somewhere better.

    Recalibration must never quietly become endorsement. Each row that carries a
    cause asserts (a) it currently lands on general, and (b) its intended route is
    NOT what it currently does — so if a future fix makes the pin agree with the
    intent, this test fails and forces the cause label to be removed deliberately.
    """
    for p in PROBE_SET:
        if not p.cause:
            continue
        assert p.expected == "general", (
            f"[{p.category}] {p.query!r} is labelled {p.cause!r} but pins "
            f"{p.expected!r}; the origin/main measurement said every such row falls "
            "to general. Re-measure before changing this."
        )
        assert INTENDED[p.query] != p.expected, (
            f"[{p.category}] {p.query!r} is labelled {p.cause!r} yet its intended "
            f"route {INTENDED[p.query]!r} equals the pinned {p.expected!r}; the "
            "label is now stale"
        )


def test_noun_controls_match_no_temporal_token():
    """The control group is only a control if it is genuinely temporal-free.

    Checked against the pattern, not against the expectations, so it is independent
    of the block above and stays true even while the temporal-token gap is open.
    """
    for category in CLEAN_CATEGORIES:
        for p in BY_CATEGORY[category]:
            assert routing._TEMPORAL_RE.search(p.query) is None, (
                f"[{category}] {p.query!r} matches `_TEMPORAL_RE`; a control row "
                "carrying a temporal token is not a control"
            )


def test_category_temporal_partition_is_honest():
    """Every temporal-bearing row really carries a corpus time word, and vice versa.

    Re-scoped on calibration: this used to assert the rows match `_TEMPORAL_RE`,
    which made it unsatisfiable — the corpus vocabulary has never been in that
    regex (see `test_temporal_token_gap_is_pinned`). It now asserts the property
    that IS true and worth keeping: the temporal categories are exactly the rows
    containing a corpus year word, so option B still has a well-defined row set to
    be measured against the moment the tokens exist.
    """
    assert TEMPORAL_CATEGORIES.isdisjoint(CLEAN_CATEGORIES)
    assert LIVE_TEMPORAL_CATEGORIES.isdisjoint(CLEAN_CATEGORIES)
    assert not (TEMPORAL_CATEGORIES | CLEAN_CATEGORIES | LIVE_TEMPORAL_CATEGORIES) & EXEMPT_CATEGORIES
    assert TEMPORAL_CATEGORIES | CLEAN_CATEGORIES | LIVE_TEMPORAL_CATEGORIES | EXEMPT_CATEGORIES == set(BY_CATEGORY), (
        "every category must be declared temporal-bearing, live-temporal, clean, or exempt"
    )
    for category, rows in BY_CATEGORY.items():
        if category in EXEMPT_CATEGORIES:
            continue
        for p in rows:
            if category in LIVE_TEMPORAL_CATEGORIES:
                # The one category whose rows MUST match `_TEMPORAL_RE` -- that is
                # what makes it an instrument rather than a pin.
                assert routing._TEMPORAL_RE.search(p.query), (
                    f"[{category}] {p.query!r} does not match `_TEMPORAL_RE`; the "
                    "block has stopped observing precedence and would silently "
                    "become another set of inert pins"
                )
                continue
            has_word = any(w in p.query for w in CORPUS_YEAR_WORDS)
            if category in TEMPORAL_CATEGORIES:
                assert has_word, (
                    f"[{category}] {p.query!r} has no corpus time word, so it is "
                    "really a noun-control and does not belong in this block"
                )
            else:
                assert not has_word, (
                    f"[{category}] {p.query!r} unexpectedly carries a corpus time word, so it is not a control"
                )


def _implemented_check_order() -> tuple[str, ...]:
    """Read the real `if` order out of `classify_intent`'s source.

    Derived from the live function rather than from `ROUTE_PATTERNS`, because the
    pattern tuple is a fixed snapshot of pattern IDENTITY and its indices do not
    move when the checks are reordered. Asserting against indices would let a
    reorder pass silently — which is precisely the regression this file exists to
    catch, and precisely how it passed vacuously during the first round of
    mutation testing.
    """
    source = inspect.getsource(routing.classify_intent)
    found = re.findall(r"if (_[A-Z]+_RE)\.search", source)
    names = {
        "_CODE_RE": "code_structure",
        "_TASK_RE": "task_debt",
        "_TEMPORAL_RE": "temporal_fact",
        "_PREF_RE": "preference_self",
        "_ENTITY_RE": "entity_relation",
        "_CARD_RE": "card_ops",
        "_FILE_RE": "file_note",
    }
    order = [names[n] for n in found if n in names]
    assert len(order) == 7, f"parsed {len(order)} checks from classify_intent, expected 7: {order}"
    return tuple(order)


def test_temporal_outranks_nouns_exactly_where_check_order_says():
    """origin/main's actual precedence claim, stated as a testable property.

    The pre-loss revision of this file asserted option B's claim instead -- "a noun
    is the primary intent and a time word is a modifier on it" -- which is FALSE on
    origin/main and, with the corpus as it stands, unfalsifiable. This states what
    the module actually implements and what the pending decision would change:
    TEMPORAL beats PREF/ENTITY/CARD/FILE, but loses to CODE and TASK.

    Read from the function's own source, so adopting option B fails this test --
    the decision then lands where it is visible instead of drifting.
    """
    order = _implemented_check_order()
    assert order == (
        "code_structure",
        "task_debt",
        "temporal_fact",
        "preference_self",
        "entity_relation",
        "card_ops",
        "file_note",
    ), f"classify_intent now checks {order}; the pinned precedence order has changed"

    pos = {route: i for i, route in enumerate(order)}
    # Every live-precedence row must be a genuine contention, and the row's winner
    # must be the earliest-checked matcher. Stated that way it covers a temporal win
    # and a noun win alike, instead of needing a special case that quietly drops the
    # temporal pattern from its own comparison.
    for p in LIVE_PRECEDENCE:
        matching = [ROUTE_NAMES[i] for i, rx in enumerate(ROUTE_PATTERNS) if rx.search(p.query)]
        assert "temporal_fact" in matching, (
            f"[live-precedence] {p.query!r} does not match `_TEMPORAL_RE`; it is not "
            "a temporal-precedence probe and belongs in another block"
        )
        assert len(matching) >= 2, (
            f"[live-precedence] {p.query!r} matches only {matching}; the row is not a "
            "contention and cannot observe precedence"
        )
        earliest = min(matching, key=pos.__getitem__)
        assert p.expected == earliest, (
            f"[live-precedence] {p.query!r} pins {p.expected!r}, but the implemented "
            f"order {order} makes {earliest!r} win among {matching}"
        )


def test_ambiguous_rows_really_are_ambiguous():
    """The `ambiguous` label must keep meaning "two or more patterns would match".

    Evaluated against HYPOTHETICAL_PATTERNS (both defects closed), because on
    origin/main every one of these rows matches ZERO patterns -- the label would be
    vacuous otherwise. Note that closing the CJK defect ALONE is not enough:
    `去年写的文档在哪个文件` matches only `_FILE_RE` under corrected patterns, since
    文档 and 哪个文件 are both FILE tokens. Its ambiguity needs the temporal
    vocabulary too -- i.e. it is ambiguous about exactly the boundary the pending
    decision has to settle. This is the assertion that keeps the block meaningful
    across the fixes: if a token-set change stops two patterns competing, this
    goes red.
    """
    for p in BY_CATEGORY["ambiguous"]:
        matched = [i for i, rx in enumerate(HYPOTHETICAL_PATTERNS) if rx.search(p.query)]
        assert len(matched) >= 2, (
            f"[ambiguous] {p.query!r} matches {len(matched)} pattern(s) even with both "
            "defects closed; it is not ambiguous and does not belong here"
        )
        # And it must no longer be inert in the LIVE module: with the CJK arms
        # reachable (BET-Y2Q4-T3-04) at least one competing pattern now matches.
        # Rows carrying a corpus year word reach only one live matcher (the CJK noun)
        # because `_TEMPORAL_RE` still lacks that vocabulary — their second arm is
        # the pending temporal decision, not this fix. Year-free rows must already be
        # live-ambiguous.
        live = [i for i, rx in enumerate(ROUTE_PATTERNS) if rx.search(p.query)]
        assert live, (
            f"[ambiguous] {p.query!r} matches nothing in the live module; the CJK "
            "fix should have made at least its CJK arms reachable"
        )
        if not any(w in p.query for w in CORPUS_YEAR_WORDS):
            assert len(live) >= 2, (
                f"[ambiguous] {p.query!r} matches only {live} live; a year-free row's "
                "competition is CJK-only and must be live-ambiguous after the fix"
            )

    # Heterogeneity is exactly why the block is exempt from the partition above.
    with_time = [p for p in BY_CATEGORY["ambiguous"] if any(w in p.query for w in CORPUS_YEAR_WORDS)]
    without_time = [p for p in BY_CATEGORY["ambiguous"] if not any(w in p.query for w in CORPUS_YEAR_WORDS)]
    assert with_time and without_time, (
        "the ambiguous block is exempt from the temporal partition precisely because "
        "it contains both kinds of row; losing either kind means the exemption needs "
        "revisiting"
    )


def test_probe_set_shape_is_maintainable():
    """Structural invariants, so the matrix cannot rot into something weaker."""
    assert len(PROBE_SET) == len({p.query for p in PROBE_SET}), "duplicate query in PROBE_SET"
    assert set(BY_CATEGORY) == set(CATEGORY_NOTES), "a category is missing its note"
    for category in TEMPORAL_CATEGORIES:
        assert len(BY_CATEGORY[category]) >= 2, f"[{category}] needs more than one row to be evidence"
    assert len(PURE_TIME) >= 5 and len(NOUN_CONTROL_ALL) >= 10
    assert set(INTENDED) == {p.query for p in PROBE_SET if p.cause}, (
        "INTENDED and the cause labels disagree; every labelled row needs an intended "
        "route and every unlabelled row must have none"
    )
    assert set(INTENDED_CAUSES) == set(INTENDED)


def test_matrix_covers_every_route_once_the_defects_are_fixed():
    """Under the corrected patterns the corpus reaches all seven named intents.

    The original `test_matrix_actually_covers_every_route` asserted this over the
    EXPECTED column, which was true only under the reconstructed module. Measured
    against origin/main the corpus sends 66 of the original 79 rows to `general` and
    reaches temporal_fact ONLY via the `live-precedence` block -- never through a
    year-relative word. So the coverage claim is stated the only way it can honestly
    be: over what the corpus WOULD exercise once both defects are closed. That is the
    standard the matrix holds itself to, and it is checkable today.
    """
    corpus_rows = [p for category in TEMPORAL_CATEGORIES for p in BY_CATEGORY[category]]
    reachable = {_route(ROUTE_PATTERNS, p.query) for p in corpus_rows}
    assert "temporal_fact" not in reachable, (
        "temporal_fact is now reachable from a corpus year-word row — "
        "`_TEMPORAL_RE` matches at least one. The temporal-token-gap pins are "
        "stale; recalibrate them and re-open the precedence matrix."
    )

    # Under corrected patterns AND the corpus time vocabulary, the corpus is broad
    # enough to cover every route. Checked with the same hypothetical set the
    # ambiguity invariant uses, so the two cannot disagree about what the matrix
    # proves.
    covered = {_route(HYPOTHETICAL_PATTERNS, p.query) for p in PROBE_SET}
    expected_routes = set(routing.INTENT_ROUTES) | {"general"}
    assert covered == expected_routes, f"unprobed routes: {expected_routes - covered}"
