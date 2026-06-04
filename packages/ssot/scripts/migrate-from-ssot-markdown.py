#!/usr/bin/env python3
"""
SSOT 迁移脚本 — 从 Markdown SSOT 导出 YAML 领域配置
=========================================================
用法:
    python3 migrate-from-ssot-markdown.py <ssot_dir> <output_dir>

从现有 Markdown 格式的 SSOT（01-实体本体/ 02-事实基座/ 等）
导出为 ssot-kernel 兼容的 YAML 领域配置。
"""

import re
import sys
from pathlib import Path

import yaml


def extract_frontmatter(text: str) -> dict:
    """提取 Markdown frontmatter"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if m:
        try:
            return yaml.safe_load(m.group(1)) or {}
        except:
            return {}
    return {}


def migrate_entities(ssot_dir: Path) -> list:
    """从 01-实体本体/ 迁移实体"""
    entities = []
    ent_dir = ssot_dir / "01-实体本体"
    if not ent_dir.exists():
        return entities

    for f in sorted(ent_dir.glob("*.md")):
        text = f.read_text("utf-8")
        fm = extract_frontmatter(text)
        fm.get("type", "ontology")

        # 提取表格中的实体
        tables = re.findall(r"^\|.*\|$", text, re.MULTILINE)
        for table in tables:
            cols = [c.strip() for c in table.split("|")[1:-1]]
            if len(cols) < 2:
                continue
            # 跳过表头行
            if cols[0].startswith("---"):
                continue
            # 如果第一列看起来像实体ID
            eid_match = re.match(r"\*{0,2}(ORG-[\w一-鿿-]+|ROL-[\w一-鿿-]+|PRJ-[\w一-鿿-]+)\*{0,2}", cols[0])
            if eid_match:
                eid = eid_match.group(1)
                prefix = eid.split("-")[0]
                type_map = {"ORG": "Organization", "ROL": "Role", "PRJ": "Project"}
                entities.append(
                    {
                        "id": eid,
                        "type": type_map.get(prefix, "Entity"),
                        "meta_type": "MET-DOMAIN",
                        "name": cols[1] if len(cols) > 1 else eid,
                        "status": "active",
                        "source": f.name,
                    }
                )
        # 也提取## 标题中的实体
        headings = re.findall(r"^##\s+[✅📋]\s+(.+)$", text, re.MULTILINE)
        for h in headings:
            eid_match = re.match(r"(ORG-[\w一-鿿-]+|ROL-[\w一-鿿-]+|PRJ-[\w一-鿿-]+)\b", h)
            if eid_match:
                eid = eid_match.group(1)
                if not any(e.get("id") == eid for e in entities):
                    prefix = eid.split("-")[0]
                    type_map = {"ORG": "Organization", "ROL": "Role", "PRJ": "Project"}
                    entities.append(
                        {
                            "id": eid,
                            "type": type_map.get(prefix, "Entity"),
                            "meta_type": "MET-DOMAIN",
                            "name": h,
                            "status": "active",
                            "source": f.name,
                        }
                    )

    print(f"  📦 实体: {len(entities)}")
    return entities


def migrate_facts(ssot_dir: Path) -> dict:
    """从 02-事实基座/ 迁移事实"""
    policy = []
    data = []
    fact_dir = ssot_dir / "02-事实基座"
    if not fact_dir.exists():
        return {"policy": policy, "data": data}

    for f in sorted(fact_dir.glob("*.md")):
        text = f.read_text("utf-8")
        extract_frontmatter(text)

        # 提取表格行
        tables = re.findall(r"^\|.*\|$", text, re.MULTILINE)
        for table in tables:
            cols = [c.strip() for c in table.split("|")[1:-1]]
            if not cols:
                continue
            # 跳过表头隔断行
            if cols[0].startswith("---"):
                continue
            # 检测表头
            if any(k in cols[0].lower() for k in ["编号", "id", "数据"]):
                continue
            if len(cols) >= 4:
                # 简单启发式：如果编号以P-F开头是政策，D-F开头是数据
                id_val = cols[0].strip("*")
                if id_val.startswith("P-F"):
                    policy.append(
                        {
                            "id": f"POL-{id_val}",
                            "title": cols[1] if len(cols) > 1 else "",
                            "level": 3,
                            "authority": cols[2] if len(cols) > 2 else "未知",
                            "date": cols[3] if len(cols) > 3 else "",
                            "summary": cols[4] if len(cols) > 4 else "",
                            "source": cols[-1] if len(cols) > 1 else "",
                        }
                    )
                elif id_val.startswith("D-F"):
                    data.append(
                        {
                            "id": f"DAT-{id_val}",
                            "title": cols[1] if len(cols) > 1 else "",
                            "value": cols[2] if len(cols) > 2 else "",
                            "source": cols[3] if len(cols) > 3 else "",
                            "date": cols[4] if len(cols) > 4 else "",
                        }
                    )

    print(f"  📦 政策事实: {len(policy)}, 数据事实: {len(data)}")
    return {"policy": policy, "data": data}


def migrate_inferences(ssot_dir: Path) -> list:
    """从 03-推论体系/ 迁移推论"""
    inferences = []
    inf_dir = ssot_dir / "03-推论体系"
    if not inf_dir.exists():
        return inferences

    for f in sorted(inf_dir.glob("*.md")):
        text = f.read_text("utf-8")
        # 提取L1-L4等矛盾诊断标题
        sections = re.split(r"\n(?=##\s+)", text)
        for sec in sections:
            title_m = re.match(r"##\s+(.+)$", sec, re.MULTILINE)
            if not title_m:
                continue
            title = title_m.group(1)
            # 提取INF编号
            id_m = re.search(r"(INF-[\w一-鿿-]+)", sec)
            inf_id = id_m.group(1) if id_m else ""

            # 提取结论
            conc_m = re.search(r"(推论结论|结论)[：:]\s*(.+?)(?:\n\n|\n---|\Z)", sec, re.DOTALL)
            conclusion = conc_m.group(2).strip()[:200] if conc_m else ""

            # 提取derives_from
            deps = re.findall(r"(DAT-[\w-]+|POL-[\w-]+)", sec)

            # 提取理论支撑
            theory_m = re.search(r"理论支撑[：:]\s*(.+?)$", sec, re.MULTILINE)
            theory = theory_m.group(1).strip() if theory_m else ""

            if inf_id:
                inferences.append(
                    {
                        "id": inf_id,
                        "title": title,
                        "derives_from": deps,
                        "conclusion": conclusion,
                        "theory": theory,
                        "status": "active",
                        "confidence": "inference",
                    }
                )

    print(f"  📦 推论: {len(inferences)}")
    return inferences


def main():
    if len(sys.argv) < 3:
        print("用法: python3 migrate-from-ssot-markdown.py <ssot_dir> <output_dir>")
        sys.exit(1)

    ssot_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    print("SSOT 迁移工具")
    print(f"  源: {ssot_dir}")
    print(f"  目标: {output_dir}")
    print()

    # 迁移实体
    entities = migrate_entities(ssot_dir)
    if entities:
        (output_dir / "entities.yaml").write_text(
            yaml.dump({"entities": entities}, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    # 迁移事实
    facts = migrate_facts(ssot_dir)
    if facts["policy"] or facts["data"]:
        (output_dir / "facts.yaml").write_text(
            yaml.dump(facts, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8"
        )

    # 迁移推论
    inferences = migrate_inferences(ssot_dir)
    if inferences:
        (output_dir / "inferences.yaml").write_text(
            yaml.dump({"inferences": inferences}, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    print(f"\n迁移完成 → {output_dir}")


if __name__ == "__main__":
    main()
