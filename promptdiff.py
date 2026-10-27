"""promptdiff —— 逐行比对两次提示词的改动。

设计原则：
1. **看语义块，不看行号**。普通 diff 会告诉你第 40 行换了个词，
   不会告诉你「这一句把允许范围收窄了」。
2. **约束增删要单独拎出来**。改措辞和改规则不是一回事。
3. **不自动合并**。这是给人看的审阅工具。

仅依赖 Python 标准库。

用法:
    python promptdiff.py --help
    python promptdiff.py --old v1.txt --new v2.txt
    python promptdiff.py --old v1.txt --new v2.txt --json
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys

# ---------------------------------------------------------------------------
# 语义块切分
# ---------------------------------------------------------------------------

# 提示词里的「块」：标题行、列表项、编号项、代码块围栏、其它整段。
BLOCK_PATTERNS = [
    ("heading", re.compile(r"^\s*#{1,6}\s+\S")),
    ("list", re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")),
    ("fence", re.compile(r"^\s*(?:```|~~~)")),
]


def split_blocks(text: str) -> list[dict]:
    """把提示词切成语义块。每块带类型与文本。"""
    blocks: list[dict] = []
    lines = text.splitlines()
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 代码块整体作为一个块
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if in_fence:
                blocks.append({"type": "fence", "text": line})
                in_fence = False
                i += 1
                continue
            chunk = [line]
            in_fence = True
            i += 1
            while i < len(lines):
                chunk.append(lines[i])
                if lines[i].strip().startswith(("```", "~~~")):
                    in_fence = False
                    i += 1
                    break
                i += 1
            blocks.append({"type": "fence", "text": "\n".join(chunk)})
            continue

        if not stripped:
            i += 1
            continue

        btype = "para"
        for name, pat in BLOCK_PATTERNS:
            if pat.match(line):
                btype = name
                break

        # 段落：连续非空行合并
        chunk = [line]
        j = i + 1
        if btype == "para":
            while j < len(lines) and lines[j].strip():
                chunk.append(lines[j])
                j += 1
            i = j
        else:
            i += 1

        blocks.append({"type": btype, "text": "\n".join(chunk)})

    return blocks


# ---------------------------------------------------------------------------
# 改动分类
# ---------------------------------------------------------------------------

# 约束类关键词：这些块里出现的话，改动属于「改规则」
CONSTRAINT_RE = re.compile(
    r"(不要|不得|禁止|必须|只能|至多|至少|不超过|限制|要求|务必|一律|"
    r"只能使用|仅限|最多|最少|必须包含|必须不)", re.I)

FORMAT_RE = re.compile(
    r"(JSON|XML|YAML|CSV|Markdown|表格|列表|纯文本|格式|结构|字数|"
    r"语言|英文|中文|语气|风格)", re.I)


def constraint_markers(text: str) -> set[str]:
    """抽出这段话里出现的约束词集合（用来比较「约束有没有变」）。"""
    return set(CONSTRAINT_RE.findall(text or ""))


def classify_change(old: str, new: str) -> dict:
    """把一次改动归类。"""
    old_marks = constraint_markers(old)
    new_marks = constraint_markers(new)
    old_c = bool(old_marks)
    new_c = bool(new_marks)
    old_f = bool(FORMAT_RE.search(old))
    new_f = bool(FORMAT_RE.search(new))

    ratio = difflib.SequenceMatcher(None, old, new).ratio()

    if old_c and not new_c:
        kind = "constraint_removed"
    elif not old_c and new_c:
        kind = "constraint_added"
    elif old_c and new_c and old_marks != new_marks:
        kind = "constraint_changed"
    elif old_f != new_f:
        kind = "format_changed"
    elif ratio > 0.8:
        kind = "wording"
    else:
        kind = "rewrite"

    return {
        "kind": kind,
        "similarity": round(ratio, 4),
        "constraint_change": old_marks != new_marks,
        "format_change": old_f != new_f,
    }


KIND_LABEL = {
    "constraint_added": "新增约束",
    "constraint_removed": "移除约束",
    "format_changed": "格式要求变化",
    "wording": "措辞调整",
    "rewrite": "整段重写",
}


def diff_prompts(old_text: str, new_text: str) -> dict:
    """比对两版提示词。"""
    old_blocks = split_blocks(old_text)
    new_blocks = split_blocks(new_text)

    sm = difflib.SequenceMatcher(
        None, [b["text"] for b in old_blocks], [b["text"] for b in new_blocks])

    changes: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        olds = [b["text"] for b in old_blocks[i1:i2]]
        news = [b["text"] for b in new_blocks[j1:j2]]

        # replaced：逐对比较；delete/insert：整块
        pairs = min(len(olds), len(news))
        for k in range(pairs):
            info = classify_change(olds[k], news[k])
            changes.append({
                "type": "replaced",
                "old": olds[k],
                "new": news[k],
                **info,
            })
        for extra in olds[pairs:]:
            changes.append({
                "type": "deleted", "old": extra, "new": "",
                "kind": "constraint_removed"
                if CONSTRAINT_RE.search(extra) else "removed",
                "similarity": 0.0,
                "constraint_change": bool(CONSTRAINT_RE.search(extra)),
                "format_change": False,
            })
        for extra in news[pairs:]:
            changes.append({
                "type": "added", "old": "", "new": extra,
                "kind": "constraint_added"
                if CONSTRAINT_RE.search(extra) else "added",
                "similarity": 0.0,
                "constraint_change": bool(CONSTRAINT_RE.search(extra)),
                "format_change": False,
            })

    constraint_changes = [c for c in changes if c["constraint_change"]]
    format_changes = [c for c in changes if c["format_change"]]

    return {
        "old_block_count": len(old_blocks),
        "new_block_count": len(new_blocks),
        "changes": changes,
        "constraint_changes": constraint_changes,
        "format_changes": format_changes,
        "summary": {
            "total": len(changes),
            "constraint": len(constraint_changes),
            "format": len(format_changes),
            "wording": sum(1 for c in changes if c["kind"] == "wording"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(result: dict) -> str:
    out: list[str] = []
    s = result["summary"]
    out.append("提示词改动审阅")
    out.append("=" * 56)
    out.append(f"块数 {result['old_block_count']} → {result['new_block_count']}"
               f" ｜ 改动 {s['total']} 处"
               f"（约束 {s['constraint']} / 格式 {s['format']} / 措辞 {s['wording']}）")
    out.append("")

    if not result["changes"]:
        out.append("两版没有差异。")
        return "\n".join(out)

    # 约束与格式变化排前面
    changes = sorted(
        result["changes"],
        key=lambda c: (not c["constraint_change"], not c["format_change"], c["kind"]))

    for c in changes:
        label = KIND_LABEL.get(c["kind"], c["kind"])
        flag = ""
        if c["constraint_change"]:
            flag += "  ★约束"
        if c["format_change"]:
            flag += "  ★格式"
        out.append(f"[{label}]{flag}  相似度 {c['similarity']:.2f}")
        if c["old"]:
            out.append(f"  - {c['old']}")
        if c["new"]:
            out.append(f"  + {c['new']}")
        out.append("")

    if result["constraint_changes"]:
        out.append("★ 约束类改动需要人确认：这类改动会直接改变行为边界。")
    return "\n".join(out).rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="promptdiff",
        description="逐行比对两次提示词的改动（仅依赖标准库）",
        epilog=(
            "示例:\n"
            "  python promptdiff.py --old v1.txt --new v2.txt\n"
            "  python promptdiff.py --old v1.txt --new v2.txt --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--old", required=True, help="旧版提示词")
    ap.add_argument("--new", required=True, help="新版提示词")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    try:
        old_text = open(args.old, "r", encoding="utf-8").read()
        new_text = open(args.new, "r", encoding="utf-8").read()
    except OSError as e:
        print(f"读不了文件：{e}", file=sys.stderr)
        return 2

    result = diff_prompts(old_text, new_text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
