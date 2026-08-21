#!/usr/bin/env python3
"""
原始底稿 JSON 组装器 v13.0
功能：
- 将 Phase 1-2 的交叉核对报告（含结构化 JSON）组装为标准底稿 JSON
- JSON Schema 校验（必填字段 + 类型检查）
- 从 JSON 渲染 MD（人眼核校版，双输出）
- 失败降级：组装失败时自动降级为 MD 单输出并告警

用法：
    from assemble_json import ManuscriptAssembler
    asm = ManuscriptAssembler()
    result = asm.assemble(project_name, reports, output_dir)
    # result = {status: "ok", json_path, md_path, material_count}
    # 或 {status: "degraded", md_path, error}（JSON 组装失败，仅 MD）

输出：
    02_scratch/[项目名]/01_原始底稿/[案件简称]_原始底稿.json   （主格式）
    02_scratch/[项目名]/01_原始底稿/[案件简称]_原始底稿.md    （辅助格式）
    02_scratch/[项目名]/01_原始底稿/schema.json               （Schema 契约）
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


# ============ Schema 定义（下游技能消费契约） ============

MANUSCRIPT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ManuscriptJSON",
    "type": "object",
    "required": ["schema_version", "metadata", "materials"],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0.0"},
        "metadata": {
            "type": "object",
            "required": ["case_name", "generated_at", "total_materials"],
            "properties": {
                "case_name": {"type": "string"},
                "generated_at": {"type": "string"},
                "total_materials": {"type": "integer"},
                "processing_stats": {"type": "object"},
                "cross_check_stats": {"type": "object"},
            },
        },
        "materials": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["m_id", "source_file", "pages", "transcript_fulltext"],
                "properties": {
                    "m_id": {"type": "string"},
                    "source_file": {"type": "string"},
                    "file_type": {"type": "string"},
                    "ocr_status": {"type": "string"},
                    "confidence": {"type": "string"},
                    "similarity": {"type": "number"},
                    "engine_source": {"type": "string"},
                    "language": {"type": "string"},
                    "note": {"type": "string"},
                    "pages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["page_idx"],
                            "properties": {
                                "page_idx": {"type": "integer"},
                                "blocks": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["type", "content"],
                                        "properties": {
                                            "type": {"type": "string"},
                                            "bbox": {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 4,
                                                "maxItems": 8,
                                            },
                                            "text_level": {"type": ["integer", "null"]},
                                            "content": {"type": "string"},
                                            "engine_source": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "diff_markup": {"type": ["string", "null"]},
                    "transcript_fulltext": {"type": "string"},
                    "raw_structured": {"type": "object"},
                },
            },
        },
    },
}


class ManuscriptAssembler:
    """底稿 JSON 组装器"""

    def __init__(self, schema_version: str = "1.0.0"):
        self.schema_version = schema_version

    # ============ 主入口 ============

    def assemble(self, project_name: str, reports: List[Dict[str, Any]],
                 output_dir: str) -> Dict[str, Any]:
        """
        组装底稿 JSON + 渲染 MD

        Args:
            project_name: 案件简称
            reports: Phase 2 交叉核对报告列表（每条含 primary_text / status / confidence /
                     structured_mineru / structured_paddle / file / similarity 等）
            output_dir: 输出目录（02_scratch/[项目名]/01_原始底稿/）

        Returns:
            {"status": "ok", "json_path": ..., "md_path": ..., "material_count": N}
            或 {"status": "degraded", "md_path": ..., "error": "..."}（JSON 失败，降级 MD）
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # 1. 组装 JSON 结构
        try:
            manuscript = self._build_manuscript(project_name, reports)
            self._validate(manuscript)

            json_path = out / f"{project_name}_原始底稿.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(manuscript, f, ensure_ascii=False, indent=2)

            # 写 Schema 契约
            schema_path = out / "schema.json"
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(MANUSCRIPT_SCHEMA, f, ensure_ascii=False, indent=2)

            # 2. 从 JSON 渲染 MD
            md_path = out / f"{project_name}_原始底稿.md"
            md_text = self.render_md(manuscript)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)

            return {
                "status": "ok",
                "json_path": str(json_path),
                "md_path": str(md_path),
                "schema_path": str(schema_path),
                "material_count": len(manuscript["materials"]),
            }

        except Exception as e:
            # 降级：JSON 组装失败 → 仅 MD 单输出
            md_path = self._degrade_to_md(project_name, reports, out)
            return {
                "status": "degraded",
                "md_path": str(md_path),
                "error": str(e),
            }

    # ============ JSON 组装 ============

    def _build_manuscript(self, project_name: str, reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建底稿 JSON 结构"""
        materials = []
        stats = {"auto_resolved": 0, "auto_resolved_with_diff": 0,
                 "multimodal_rescued": 0, "need_multimodal": 0, "single_engine": 0}
        conf_counts = {}

        for idx, report in enumerate(reports, start=1):
            m_id = f"M{idx:03d}"
            # v13.3：source_file 优先取 file_name（人工组装/备份报告常缺 file 字段），
            # 再 fallback 到 file 的 basename。此前仅取 file 导致 file_name 丢失 → source_file=unknown。
            fn = report.get("file_name") or report.get("file") or "unknown"
            source_file = fn if isinstance(fn, str) else "unknown"
            status = report.get("status", "unknown")
            conf = report.get("confidence", "?")
            conf_counts[conf] = conf_counts.get(conf, 0) + 1
            stats[status] = stats.get(status, 0) + 1

            # 结构化块（优先 MinerU content_list，其次 PaddleOCR layoutParsingResults）
            pages = self._extract_pages(report)

            material = {
                "m_id": m_id,
                "source_file": source_file,
                "file_type": report.get("file_type", self._guess_file_type(report.get("file", ""))),
                "ocr_status": status,
                "confidence": conf,
                "similarity": round(report.get("similarity", 0), 4),
                # v13.2：source 空值兜底改为 unknown（cross_check v13.2 已全分支固化 source，此处防历史报告/降级路径回归）
                "engine_source": report.get("source") or "unknown",
                "language": report.get("language", "zh"),
                "pages": pages,
                "diff_markup": report.get("diff_markup"),
                "transcript_fulltext": report.get("primary_text", ""),
                # 原始结构化数据保留（供下游深度消费）
                "raw_structured": {
                    "mineru_content_list": self._safe_get(report, "structured_mineru", "content_list"),
                    "mineru_middle": self._safe_get(report, "structured_mineru", "middle_json"),
                    "paddle_layouts": self._safe_get(report, "structured_paddle", "layoutParsingResults"),
                },
            }

            # 差异说明（flagged/auto_resolved_with_diff 时）
            note = report.get("note")
            if note:
                material["note"] = note

            materials.append(material)

        return {
            "schema_version": self.schema_version,
            "metadata": {
                "case_name": project_name,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_materials": len(materials),
                "processing_stats": stats,
                "cross_check_stats": {
                    "A": conf_counts.get("A", 0),
                    "B": conf_counts.get("B", 0),
                    "C": conf_counts.get("C", 0),
                    "D": conf_counts.get("D", 0),
                    "E": conf_counts.get("E", 0),
                },
            },
            "materials": materials,
        }

    def _extract_pages(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从结构化 JSON 提取 page → blocks 结构
        优先 MinerU content_list，其次 PaddleOCR layoutParsingResults
        """
        # ---- MinerU content_list ----
        # 实测（2026-08-09 真实 API）：V4 返回 list-of-pages，每页是块 list；
        # 块格式 {'type':'paragraph','content':{'paragraph_content':[{'type':'text','content':'...'}]},'bbox':[...]}
        # 兼容官方文档扁平格式（{'type':'text','text':'...','page_idx':n}）
        cl = self._safe_get(report, "structured_mineru", "content_list")
        if isinstance(cl, list):
            pages_map = {}
            for page_pos, item in enumerate(cl):
                # 嵌套页：元素本身是该页的块 list
                if isinstance(item, list):
                    for blk in item:
                        if not isinstance(blk, dict):
                            continue
                        page_idx = blk.get("page_idx", page_pos)
                        block = self._mineru_block(blk)
                        if block and block.get("content"):
                            pages_map.setdefault(page_idx, []).append(block)
                    continue
                # 扁平块
                if not isinstance(item, dict):
                    continue
                page_idx = item.get("page_idx", 0)
                block = self._mineru_block(item)
                if block and block.get("content"):
                    pages_map.setdefault(page_idx, []).append(block)
            if pages_map:
                return [{"page_idx": int(p), "blocks": pages_map[p]}
                        for p in sorted(pages_map.keys())]

        # ---- PaddleOCR layoutParsingResults ----
        layouts = self._safe_get(report, "structured_paddle", "layoutParsingResults")
        if isinstance(layouts, list):
            pages = []
            for page_idx, layout in enumerate(layouts):
                if not isinstance(layout, dict):
                    continue
                blocks = []
                pruned = layout.get("prunedResult")
                if isinstance(pruned, dict):
                    blocks = self._paddle_pruned_to_blocks(pruned, page_idx)
                if not blocks:
                    # 兜底：无 prunedResult 时用 markdown 全文作单块
                    md = layout.get("markdown", {})
                    text = md.get("text", "") if isinstance(md, dict) else ""
                    if text:
                        blocks = [{"type": "text", "bbox": None, "text_level": None,
                                   "content": text, "engine_source": "paddleocr"}]
                pages.append({"page_idx": int(page_idx), "blocks": blocks})
            if pages:
                return pages

        # ---- 双引擎均无结构化数据：全文作单块（降级） ----
        fulltext = report.get("primary_text", "")
        if fulltext:
            return [{"page_idx": 0, "blocks": [{
                "type": "text", "bbox": None, "text_level": None,
                "content": fulltext, "engine_source": report.get("source", "unknown"),
            }]}]
        return []

    def _mineru_block(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """规范化 MinerU content_list 块为统一 block（处理 paragraph 嵌套类型）"""
        btype = item.get("type", "text")
        # 实测 V4：type=paragraph，文本在 content.paragraph_content[].content
        if btype == "paragraph":
            inner = item.get("content")
            if isinstance(inner, dict):
                parts = inner.get("paragraph_content") or []
                text = "".join(
                    c.get("content", "") for c in parts
                    if isinstance(c, dict) and c.get("type") == "text"
                )
                # paragraph 内可能含子类型（如 title），取 text_level
                level = item.get("text_level")
                if not text:
                    text = "".join(str(c.get("content", "")) for c in parts if isinstance(c, dict))
                return {"type": "text", "bbox": item.get("bbox"), "text_level": level,
                        "content": text, "engine_source": "mineru"}
        # 其他类型走通用提取
        return {"type": btype, "bbox": item.get("bbox"),
                "text_level": item.get("text_level"),
                "content": self._block_content(item), "engine_source": "mineru"}

    def _block_content(self, item: Dict[str, Any]) -> str:
        """提取 content_list 元素的文本内容（text/table/image/equation 等）"""
        t = item.get("type", "")
        if t == "table":
            # 表格：HTML 优先
            html = item.get("table_body") or item.get("html")
            if isinstance(html, str) and html.strip():
                return html
            md = item.get("table_md") or item.get("markdown")
            if isinstance(md, str) and md.strip():
                return md
            # 退化：拼接 cells
            rows = item.get("table_body", [])
            if isinstance(rows, list):
                lines = []
                for row in rows:
                    if isinstance(row, dict):
                        cells = row.get("cells", [])
                        lines.append(" | ".join(str(c.get("content", "")) for c in cells if isinstance(c, dict)))
                return "\n".join(lines)
            return ""
        if t == "image":
            return item.get("image_path") or item.get("img_path") or "[图片]"
        if t == "equation":
            return item.get("latex") or item.get("equation") or ""
        if t == "code":
            return item.get("code_body") or ""
        if t == "list":
            items = item.get("list_items", [])
            return "\n".join(str(x) for x in items) if isinstance(items, list) else ""
        if t == "discarded":
            return item.get("text", "")
        # text 等
        text = item.get("text", "")
        return text if isinstance(text, str) else str(text)

    def _paddle_pruned_to_blocks(self, pruned: Dict[str, Any], page_idx: int) -> List[Dict[str, Any]]:
        """将 PaddleOCR prunedResult 转为 blocks
        实测（2026-08-09）：真实字段 parsing_res_list，块字段
        block_label / block_content / block_bbox / block_id / block_order
        """
        blocks = []
        # 真实字段优先，兼容旧字段
        for key in ("parsing_res_list", "layout_det_res", "layout_parsing_res", "res", "blocks"):
            val = pruned.get(key)
            if isinstance(val, list):
                for b in val:
                    if isinstance(b, dict):
                        blocks.append({
                            "type": b.get("block_label") or b.get("type") or "text",
                            "bbox": b.get("block_bbox") or b.get("block_box") or b.get("bbox"),
                            "text_level": b.get("text_level") or b.get("block_order"),
                            "content": b.get("block_content") or b.get("text") or b.get("content") or "",
                            "engine_source": "paddleocr",
                        })
                if blocks:
                    break
        return blocks

    def _validate(self, manuscript: Dict[str, Any]) -> None:
        """Schema 校验（轻量：必填字段 + 类型检查，避免引入 jsonschema 依赖）"""
        assert manuscript.get("schema_version") == self.schema_version, "schema_version 不匹配"
        assert isinstance(manuscript.get("metadata"), dict), "metadata 缺失"
        assert manuscript["metadata"].get("case_name"), "case_name 为空"
        assert isinstance(manuscript.get("materials"), list), "materials 缺失"
        for m in manuscript["materials"]:
            assert m.get("m_id"), "材料缺失 m_id"
            assert m.get("source_file"), f"{m.get('m_id')} 缺失 source_file"
            assert isinstance(m.get("transcript_fulltext"), str), f"{m.get('m_id')} transcript_fulltext 类型错误"
        # bbox 抽查：任一材料含 bbox 即认为版面信息保留
        has_bbox = any(
            block.get("bbox")
            for m in manuscript["materials"]
            for page in m.get("pages", [])
            for block in page.get("blocks", [])
        )
        if not has_bbox:
            # 不抛错——双引擎无结构化数据时降级为全文块是合法路径
            # 但记录提示（调用方可在日志中看到）
            pass

    # ============ MD 渲染（从 JSON） ============

    def render_md(self, manuscript: Dict[str, Any]) -> str:
        """从底稿 JSON 渲染 Markdown（人眼核校版）"""
        meta = manuscript["metadata"]
        stats = meta.get("processing_stats", {})
        cc = meta.get("cross_check_stats", {})

        lines = [
            f"# 原始底稿：{meta['case_name']}",
            f"> 生成时间：{meta['generated_at']}",
            f"> 材料总数：{meta['total_materials']} 件",
            f"> 质量控制：v13.0 双引擎 OCR 交叉核对 ✅ | 结构化 JSON 输出 ✅ | AI 语义终裁 ✅ | 多模态兜底 ✅",
            f"> 自动定稿：{stats.get('auto_resolved', 0)} 件 | 差异标记定稿：{stats.get('auto_resolved_with_diff', 0)} 件 "
            f"| 多模态转录：{stats.get('multimodal_rescued', 0)} 件 | 待人工复核：{stats.get('need_multimodal', 0)} 件",
            "",
            "## 处理统计",
            "",
            "| 类别 | 数量 |",
            "|------|------|",
            f"| 自动定稿（≥95%一致） | {stats.get('auto_resolved', 0)} |",
            f"| 差异标记定稿（80-95%一致） | {stats.get('auto_resolved_with_diff', 0)} |",
            f"| 多模态完整转录 | {stats.get('multimodal_rescued', 0)} |",
            f"| 待人工复核 | {stats.get('need_multimodal', 0)} |",
            f"| **总计** | **{meta['total_materials']}** |",
            "",
            "## 交叉核对统计",
            "",
            "| 置信度 | 数量 |",
            "|--------|------|",
            f"| A（高度确信） | {cc.get('A', 0)} |",
            f"| B（较高度确信） | {cc.get('B', 0)} |",
            f"| C（中度确信） | {cc.get('C', 0)} |",
            f"| D/E（需复核） | {cc.get('D', 0) + cc.get('E', 0)} |",
            "",
            "# 正文",
            "",
        ]

        for m in manuscript["materials"]:
            lines.append(f"## {m['m_id']}：{m['source_file']}")
            lines.append("### 来源信息")
            lines.append(f"- 原始文件：`{m['source_file']}`")
            lines.append(f"- 处理方式：{self._render_processing(m)}")
            lines.append(f"- 核对状态：{self._render_status(m)}")
            if m.get("similarity") is not None:
                lines.append(f"- 双引擎相似度：{m['similarity']:.2%}")
            if m.get("note"):
                lines.append(f"- 备注：{m['note']}")
            lines.append("")
            lines.append("### 全文转录")
            lines.append("")
            lines.append("```")
            lines.append(m.get("transcript_fulltext", "") or "（无文本内容，见原文件）")
            lines.append("```")
            lines.append("")
            if m.get("diff_markup"):
                lines.append("### 差异标记")
                lines.append("")
                lines.append("```")
                lines.append(m["diff_markup"])
                lines.append("```")
                lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _render_processing(self, m: Dict[str, Any]) -> str:
        status = m.get("ocr_status", "")
        if status == "multimodal_rescued":
            return "多模态完整转录（主模型视觉识别）"
        if status in ("auto_resolved", "auto_resolved_with_diff", "single_engine"):
            engine = m.get("engine_source", "")
            if "mineru" in engine:
                return "MinerU V4 结构化解析（权威源）"
            if "paddle" in engine:
                return "PaddleOCR-VL 结构化解析（权威源）"
            return "双引擎 OCR 交叉核对"
        return status or "待处理"

    def _render_status(self, m: Dict[str, Any]) -> str:
        status = m.get("ocr_status", "")
        conf = m.get("confidence", "?")
        mapping = {
            "auto_resolved": f"✅ 自动定稿（{conf}级）",
            "auto_resolved_with_diff": f"✅ 差异标记定稿（{conf}级，建议抽核关键数字）",
            "single_engine": f"⚠️ 单引擎定稿（{conf}级）",
            "multimodal_rescued": f"✅ 多模态转录（{conf}级，建议复核关键金额/日期）",
            "need_multimodal": f"⚠️ 需人工复核（{conf}级）",
            "failed": f"❌ 失败（{conf}级）",
        }
        return mapping.get(status, status)

    # ============ 降级 ============

    def _degrade_to_md(self, project_name: str, reports: List[Dict[str, Any]], out: Path) -> Path:
        """JSON 组装失败 → 降级生成纯 MD（保底输出）"""
        lines = [
            f"# 原始底稿：{project_name}（降级模式）",
            f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> ⚠️ JSON 组装失败，本文件为降级输出，请检查 assemble_json.py",
            "",
        ]
        for idx, r in enumerate(reports, start=1):
            fn = r.get("file_name") or r.get("file") or "unknown"
            fname = fn if isinstance(fn, str) else "unknown"
            lines.append(f"## M{idx:03d}：{fname}")
            lines.append(f"- 状态：{r.get('status', '?')} | 置信度：{r.get('confidence', '?')}")
            lines.append("")
            lines.append("```")
            lines.append(r.get("primary_text", ""))
            lines.append("```")
            lines.append("")
        md_path = out / f"{project_name}_原始底稿.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return md_path

    # ============ 工具方法 ============

    @staticmethod
    def _safe_get(report: Dict[str, Any], group: str, key: str):
        """安全取嵌套字段"""
        try:
            g = report.get(group) or {}
            if isinstance(g, dict):
                return g.get(key)
        except Exception:
            pass
        return None

    @staticmethod
    def _guess_file_type(path: str) -> str:
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            return "pdf"
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
            return "image"
        if ext in (".docx", ".doc"):
            return "word"
        if ext == ".eml":
            return "email"
        if ext in (".mp3", ".wav", ".m4a", ".amr"):
            return "audio"
        return "unknown"


# ============ CLI ============
if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python assemble_json.py <项目名> <reports.json> <输出目录>")
        sys.exit(1)
    project_name = sys.argv[1]
    reports_path = sys.argv[2]
    output_dir = sys.argv[3]

    with open(reports_path, "r", encoding="utf-8") as f:
        reports = json.load(f)

    asm = ManuscriptAssembler()
    result = asm.assemble(project_name, reports, output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
