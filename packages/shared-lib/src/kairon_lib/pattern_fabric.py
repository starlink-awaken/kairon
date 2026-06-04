"""Fabric curated pattern library -- migrated from agentmesh toolkit/patterns/fabric.ts."""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

type PatternCategory = str  # 'analyze' | 'extract' | 'summarize' | 'transform'


class PatternDefinition:
    def __init__(
        self,
        pattern_id: str,
        name: str,
        description: str,
        category: str,
        template: str,
        variables: list[str] | None = None,
        examples: list[str] | None = None,
    ) -> None:
        self.id = pattern_id
        self.name = name
        self.description = description
        self.category = category
        self.template = template
        self.variables = variables or []
        self.examples = examples or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "template": self.template,
            "variables": self.variables,
            "examples": self.examples,
        }


# ---------------------------------------------------------------------------
# Pattern data
# ---------------------------------------------------------------------------

def _make(id_: str, name: str, desc: str, cat: str, template: str,
          variables: list[str] | None = None, examples: list[str] | None = None) -> PatternDefinition:
    return PatternDefinition(id_, name, desc, cat, template, variables, examples)


ANALYZE_PATTERNS: list[PatternDefinition] = [
    _make("analyze/trend", "Trend Analysis", "分析数据趋势和变化方向", "analyze",
          "分析以下内容的趋势：\n{{content}}\n\n请识别：\n1. 主要趋势方向\n2. 关键转折点\n3. 异常变化\n4. 预测建议",
          ["content"], ["销售数据趋势分析", "用户增长趋势"]),
    _make("analyze/compare", "Compare Analysis", "对比多个对象的异同", "analyze",
          "对比分析以下内容：\n{{content}}\n\n请提供：\n1. 相同点\n2. 不同点\n3. 优劣势对比\n4. 适用场景建议",
          ["content"], ["方案对比", "产品对比"]),
    _make("analyze/risk", "Risk Analysis", "识别和评估潜在风险", "analyze",
          "对以下内容进行风险分析：\n{{content}}\n\n请识别：\n1. 主要风险点\n2. 风险等级评估\n3. 风险原因\n4. 缓解建议",
          ["content"], ["项目风险", "投资风险"]),
    _make("analyze/cause", "Cause Analysis", "深入分析问题的根本原因", "analyze",
          "分析以下问题的根本原因：\n{{problem}}\n\n请使用根本原因分析方法：\n1. 直接原因\n2. 间接原因\n3. 根本原因\n4. 解决方案建议",
          ["problem"], ["问题诊断", "故障分析"]),
    _make("analyze/sentiment", "Sentiment Analysis", "分析文本的情感倾向", "analyze",
          "分析以下文本的情感：\n{{content}}\n\n请识别：\n1. 情感倾向（正面/负面/中性）\n2. 情感强度\n3. 关键情感词\n4. 情感原因",
          ["content"], ["评论分析", "反馈分析"]),
    _make("analyze/impact", "Impact Analysis", "分析决策或变化的影响", "analyze",
          "分析以下决策的影响：\n{{decision}}\n\n请评估：\n1. 正面影响\n2. 负面影响\n3. 长期影响\n4. 利益相关者影响",
          ["decision"], ["决策影响", "变更影响"]),
    _make("analyze/strength", "Strength Analysis", "分析竞争优势和优势", "analyze",
          "分析以下内容的优势：\n{{content}}\n\n请识别：\n1. 核心优势\n2. 差异化特点\n3. 竞争壁垒\n4. 潜在弱点",
          ["content"], ["竞争优势分析", "SWOT分析"]),
    _make("analyze/gap", "Gap Analysis", "分析现状与目标的差距", "analyze",
          "分析当前状态与目标的差距：\n当前状态：{{current}}\n目标状态：{{target}}\n\n请提供：\n1. 差距描述\n2. 差距原因\n3. 缩小差距的建议\n4. 优先级建议",
          ["current", "target"], ["绩效差距", "能力差距"]),
]

EXTRACT_PATTERNS: list[PatternDefinition] = [
    _make("extract/keywords", "Keyword Extraction", "从文本中提取关键信息", "extract",
          "从以下内容中提取关键词：\n{{content}}\n\n请提取：\n1. 核心关键词（5-10个）\n2. 辅助关键词\n3. 主题标签\n4. 重要术语",
          ["content"], ["关键词提取", "标签提取"]),
    _make("extract/entities", "Entity Recognition", "识别文本中的实体信息", "extract",
          "从以下内容中识别实体：\n{{content}}\n\n请识别：\n1. 人物\n2. 机构/组织\n3. 地点\n4. 时间\n5. 事件\n6. 产品/服务",
          ["content"], ["NER", "信息抽取"]),
    _make("extract/structure", "Structure Extraction", "提取文本的结构化信息", "extract",
          "从以下内容中提取结构化信息：\n{{content}}\n\n请按以下格式提取：\n1. 标题\n2. 主要观点\n3. 支持证据\n4. 结论",
          ["content"], ["文章结构", "大纲提取"]),
    _make("extract/action-items", "Action Items", "从会议或文档中提取行动项", "extract",
          "从以下内容中提取行动项：\n{{content}}\n\n请提取：\n1. 任务描述\n2. 负责人\n3. 截止时间\n4. 优先级\n5. 依赖关系",
          ["content"], ["会议纪要", "任务提取"]),
    _make("extract/questions", "Question Extraction", "从文本中提取需要回答的问题", "extract",
          "从以下内容中提取问题：\n{{content}}\n\n请识别：\n1. 明确问题\n2. 隐含问题\n3. 待决问题\n4. 问题优先级",
          ["content"], ["FAQ提取", "问题梳理"]),
    _make("extract/criteria", "Criteria Extraction", "提取判断或评估的标准", "extract",
          "从以下内容中提取评估标准：\n{{content}}\n\n请提取：\n1. 评估维度\n2. 评分标准\n3. 权重分配\n4. 合格线",
          ["content"], ["标准提取", "要求提取"]),
    _make("extract/metrics", "Metrics Extraction", "提取性能指标和度量", "extract",
          "从以下内容中提取关键指标：\n{{content}}\n\n请提取：\n1. KPI指标\n2. 基准值\n3. 目标值\n4. 测量方法",
          ["content"], ["指标提取", "度量提取"]),
    _make("extract/requirements", "Requirement Extraction", "从描述中提取需求", "extract",
          "从以下内容中提取需求：\n{{content}}\n\n请分类提取：\n1. 功能需求\n2. 非功能需求\n3. 约束条件\n4. 优先级",
          ["content"], ["需求分析", "需求提取"]),
]

SUMMARIZE_PATTERNS: list[PatternDefinition] = [
    _make("summarize/executive", "Executive Summary", "生成简洁的执行摘要", "summarize",
          "为以下内容生成执行摘要：\n{{content}}\n\n要求：\n1. 不超过3句话\n2. 包含核心信息\n3. 面向决策者\n4. 关键结论先行",
          ["content"], ["会议摘要", "报告摘要"]),
    _make("summarize/meeting", "Meeting Minutes", "生成结构化会议纪要", "summarize",
          "为以下会议内容生成纪要：\n{{content}}\n\n请包含：\n1. 会议主题\n2. 参与者\n3. 讨论要点\n4. 决策事项\n5. 行动项\n6. 下次会议安排",
          ["content"], ["会议记录", "会议总结"]),
    _make("summarize/document", "Document Summary", "生成文档的主要内容摘要", "summarize",
          "为以下文档生成摘要：\n{{content}}\n\n请提供：\n1. 文档目的\n2. 主要内容\n3. 关键结论\n4. 建议行动",
          ["content"], ["文档总结", "文章摘要"]),
    _make("summarize/code", "Code Summary", "生成代码的功能摘要", "summarize",
          "为以下代码生成功能摘要：\n{{code}}\n\n请说明：\n1. 代码功能\n2. 输入输出\n3. 依赖关系\n4. 使用示例",
          ["code"], ["代码注释", "函数说明"]),
    _make("summarize/changes", "Change Summary", "总结变更内容和影响", "summarize",
          "总结以下变更：\n{{content}}\n\n请包含：\n1. 变更内容\n2. 变更原因\n3. 影响范围\n4. 回滚方案（如需要）",
          ["content"], ["变更记录", "版本说明"]),
    _make("summarize/comparison", "Comparison Summary", "生成多选项的对比摘要", "summarize",
          "为以下选项生成对比摘要：\n{{options}}\n\n请提供：\n1. 各选项概述\n2. 主要差异\n3. 适用场景\n4. 推荐选择",
          ["options"], ["方案对比", "产品对比"]),
    _make("summarize/progress", "Progress Summary", "总结项目或任务进度", "summarize",
          "总结以下进度：\n{{content}}\n\n请包含：\n1. 总体进度\n2. 已完成\n3. 进行中\n4. 风险与问题\n5. 下一步计划",
          ["content"], ["周报", "进度报告"]),
    _make("summarize/decision", "Decision Summary", "总结决策内容和理由", "summarize",
          "总结以下决策：\n{{content}}\n\n请说明：\n1. 决策内容\n2. 决策依据\n3. 备选方案\n4. 预期结果\n5. 风险与对策",
          ["content"], ["决策记录", "结论总结"]),
]

TRANSFORM_PATTERNS: list[PatternDefinition] = [
    _make("transform/format", "Format Conversion", "将内容转换为不同格式", "transform",
          "将以下内容转换为{{targetFormat}}格式：\n{{content}}\n\n要求：\n1. 保持语义完整\n2. 符合{{targetFormat}}规范\n3. 结构清晰",
          ["content", "targetFormat"], ["格式转换", "格式规范化"]),
    _make("transform/simplify", "Simplify", "将复杂内容简化", "transform",
          "简化以下内容：\n{{content}}\n\n要求：\n1. 保留核心信息\n2. 使用简单语言\n3. 不超过原长度的30%",
          ["content"], ["内容简化", "通俗化"]),
    _make("transform/elaborate", "Elaborate", "将简略内容详细化", "transform",
          "详细阐述以下内容：\n{{content}}\n\n请：\n1. 添加详细解释\n2. 提供例子\n3. 补充背景\n4. 说明细节",
          ["content"], ["详细说明", "扩展内容"]),
    _make("transform/translate", "Translate", "将内容翻译为目标语言", "transform",
          "将以下内容翻译成{{targetLanguage}}：\n{{content}}\n\n要求：\n1. 准确传达原意\n2. 符合目标语言习惯\n3. 保持风格一致",
          ["content", "targetLanguage"], ["中译英", "语言转换"]),
    _make("transform/structure", "Restructure", "重新组织内容结构", "transform",
          "重新组织以下内容的结构：\n{{content}}\n\n请：\n1. 重新分类\n2. 调整顺序\n3. 添加标题\n4. 优化层级",
          ["content"], ["结构重组", "大纲重构"]),
    _make("transform/tone", "Tone Adjustment", "调整内容的语气风格", "transform",
          "将以下内容调整为{{tone}}语气：\n{{content}}\n\n要求：\n1. 保持原意\n2. 符合{{tone}}风格\n3. 自然流畅",
          ["content", "tone"], ["正式/口语", "友好/严肃"]),
    _make("transform/audience", "Audience Adaptation", "根据目标受众调整内容", "transform",
          "将以下内容调整为面向{{audience}}的版本：\n{{content}}\n\n请：\n1. 调整专业程度\n2. 使用适当例子\n3. 符合受众习惯",
          ["content", "audience"], ["面向技术人员", "面向管理层"]),
    _make("transform/refactor", "Code Refactor", "重构优化代码", "transform",
          "重构以下代码：\n{{code}}\n\n请：\n1. 提高可读性\n2. 优化性能\n3. 遵循最佳实践\n4. 添加必要注释",
          ["code"], ["代码优化", "代码重构"]),
]

ALL_PATTERNS: list[PatternDefinition] = (
    ANALYZE_PATTERNS + EXTRACT_PATTERNS + SUMMARIZE_PATTERNS + TRANSFORM_PATTERNS
)

_PATTERN_BY_ID: dict[str, PatternDefinition] = {p.id: p for p in ALL_PATTERNS}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def get_pattern_by_id(pattern_id: str) -> PatternDefinition | None:
    return _PATTERN_BY_ID.get(pattern_id)


def get_patterns_by_category(category: str) -> list[PatternDefinition]:
    return [p for p in ALL_PATTERNS if p.category == category]


def search_patterns(keyword: str) -> list[PatternDefinition]:
    low = keyword.lower()
    return [
        p for p in ALL_PATTERNS
        if low in p.name.lower() or low in p.description.lower() or low in p.id.lower()
    ]
