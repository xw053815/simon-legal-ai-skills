#!/usr/bin/env python3
"""apply_revisions.py — 对 docx 生成 Word/WPS 原生修订痕迹，并保留原格式。

用法示例：
    python apply_revisions.py input.docx output.docx --author 律师 \
        --replace "旧条款:新条款" \
        --replace "甲方:乙方" \
        --insert-after "新条款:（已修订）" \
        --delete "冗余文本"

支持：替换、锚点后插入、锚点前插入、删除。
所有修改以 Word/WPS track changes 形式保留，可在 Word/WPS 中逐条接受/拒绝。

关键特性：
- 保留修订处原 run 的格式（字体、字号、加粗、斜体、颜色、下划线等）。
- 支持跨 run 替换，按 run 边界分别保留格式。
- 支持表格单元格内的段落。
- 默认作者名为 "律师"（v7.1 统一，禁止个人姓名）。

限制：
- 操作参数用 ":" 分隔旧/锚点文本和新文本；若文本含 ":"，建议拆成多次操作。
- 暂不支持在已有 <w:ins> 内再生成新的修订（避免嵌套 ins）。
- 仅支持 .docx 格式。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Callable

from docx import Document

# 确保无论从哪个目录运行，都能找到同目录下的 preserve_format_revisions 模块
_scripts_dir = Path(__file__).parent.resolve()
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:
    from preserve_format_revisions import (
        apply_revisions_to_doc,
        TextNotFoundError,
    )
except ImportError as exc:  # pragma: no cover
    print(f"错误：无法导入 preserve_format_revisions ({exc})")
    sys.exit(1)


AuthorResolver = Callable[[], str]


def _default_author() -> str:
    """修订作者名（v7.1：统一"律师"）。

    当前规则：默认返回 "律师"；脚本不自动识别落款人，
    --author 参数保留以备扩展，但纪律上修订 author 统一为"律师"。
    """
    return "律师"


def _split_pair(value: str, sep: str = ":") -> tuple[str, str]:
    """按分隔符拆成 (old, new)，只拆第一处。"""
    if sep not in value:
        raise argparse.ArgumentTypeError(
            f"参数必须包含分隔符 '{sep}'，例如：旧条款{sep}新条款"
        )
    old, new = value.split(sep, 1)
    if not old:
        raise argparse.ArgumentTypeError("分隔符左侧不能为空")
    return old, new


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="对 docx 文件执行批量替换/插入/删除，并生成 Word/WPS 修订痕迹，保留原格式。"
    )
    parser.add_argument("input", type=Path, help="输入 docx 文件路径")
    parser.add_argument("output", type=Path, help="输出 docx 文件路径")
    parser.add_argument(
        "--author",
        default=_default_author(),
        help='修订作者名（v7.1 统一为 "律师"，禁止个人姓名/工具名）',
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="操作前备份原文件为 .backup.docx",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="强制不备份（不推荐）",
    )
    parser.add_argument(
        "--replace",
        action="append",
        type=_split_pair,
        default=[],
        help='替换操作，格式 "旧文本:新文本"，可多次使用',
    )
    parser.add_argument(
        "--insert-after",
        action="append",
        type=_split_pair,
        default=[],
        help='在锚点后插入，格式 "锚点文本:插入文本"，可多次使用',
    )
    parser.add_argument(
        "--insert-before",
        action="append",
        type=_split_pair,
        default=[],
        help='在锚点前插入，格式 "锚点文本:插入文本"，可多次使用',
    )
    parser.add_argument(
        "--delete",
        action="append",
        default=[],
        help='删除指定文本，可多次使用',
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="找不到目标时继续处理后续操作（默认会终止并报错）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # v7.1 纪律：修订 author 统一"律师"，拒绝个人名/工具名
    if args.author != "律师":
        print(f'错误：修订 author 必须为 "律师"（v7.1 纪律），收到 "{args.author}"')
        return 1

    if not args.input.exists():
        print(f"错误：输入文件不存在：{args.input}")
        return 1

    if args.input.suffix.lower() != ".docx":
        print("错误：仅支持 .docx 格式")
        return 1

    # 默认自动备份，除非用户明确 --no-backup
    if args.backup or (not args.no_backup):
        backup_path = args.input.with_suffix(".backup.docx")
        shutil.copy2(args.input, backup_path)
        print(f"已备份原文件：{backup_path}")

    doc = Document(args.input)

    try:
        log = apply_revisions_to_doc(
            doc,
            replacements=args.replace,
            insertions_after=args.insert_after,
            insertions_before=args.insert_before,
            deletions=args.delete,
            author=args.author,
            stop_on_error=not args.continue_on_error,
        )
    except TextNotFoundError as e:
        print(f"错误：{e}")
        return 1

    print("操作日志：")
    for line in log:
        print(f"  {line}")

    doc.save(args.output)
    print(f"\n已保存修订稿：{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
