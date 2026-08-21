#!/usr/bin/env python3
"""assemble_json.py 功能测试（模拟真实 OCR 交叉核对报告）"""
import json
import sys
import os
import tempfile

# 同目录导入（不依赖任何私有路径）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble_json import ManuscriptAssembler

# ---- 模拟 3 份报告（含 MinerU content_list + PaddleOCR layouts） ----
reports = [
    {
        "file": "C:/temp/test/合同扫描件.pdf",
        "status": "auto_resolved",
        "confidence": "A",
        "similarity": 0.97,
        "source": "mineru",
        "language": "zh",
        "primary_text": "第一条 本合同自签署之日起生效。\n第二条 付款方式：银行转账。",
        "structured_mineru": {
            "content_list": [
                {"type": "title", "bbox": [100, 50, 500, 80], "text_level": 1,
                 "text": "股权转让合同"},
                {"type": "text", "bbox": [100, 100, 500, 150], "text_level": 0,
                 "text": "第一条 本合同自签署之日起生效。"},
                {"type": "table", "bbox": [100, 200, 600, 400], "text_level": None,
                 "table_body": [{"cells": [{"content": "付款方式"}, {"content": "金额"}]},
                                 {"cells": [{"content": "银行转账"}, {"content": "¥1,234,567"}]}]},
            ]
        },
        "structured_mineru_middle": None,
    },
    {
        "file": "C:/temp/test/银行流水.png",
        "status": "auto_resolved_with_diff",
        "confidence": "B",
        "similarity": 0.88,
        "source": "paddleocr_with_diff",
        "language": "zh",
        "primary_text": "交易日期 交易金额\n20XX-XX-XX ¥X,XXX\n20XX-XX-XX ¥X,XXX",
        "diff_markup": "交易金额：<del>¥9,500</del><ins>¥X,XXX</ins>",
        "structured_paddle": {
            "layoutParsingResults": [
                {"prunedResult": {
                    "res": [
                        {"block_label": "text", "block_box": [10, 20, 400, 50], "text": "交易日期 交易金额"},
                        {"block_label": "text", "block_box": [10, 60, 400, 90], "text": "20XX-XX-XX ¥X,XXX"},
                    ]
                }},
            ]
        },
        "structured_mineru": {"content_list": None, "middle_json": None},
    },
    {
        "file": "C:/temp/test/聊天记录.jpg",
        "status": "multimodal_rescued",
        "confidence": "C",
        "similarity": 0.0,
        "source": "multimodal_vision",
        "language": "zh",
        "primary_text": "甲：这笔钱什么时候还？\n乙：下个月吧。\n甲：好，那就下个月。",
        "structured_mineru": {"content_list": None, "middle_json": None},
        "structured_paddle": {"layoutParsingResults": None},
    },
]

asm = ManuscriptAssembler()

with tempfile.TemporaryDirectory() as tmp:
    result = asm.assemble("测试案件", reports, tmp)
    assert result["status"] == "ok", f"组装失败: {result}"
    print("✅ 组装成功:", json.dumps(result, ensure_ascii=False))

    # 验证 JSON 输出
    with open(result["json_path"], "r", encoding="utf-8") as f:
        ms = json.load(f)
    assert ms["metadata"]["total_materials"] == 3
    assert ms["materials"][0]["m_id"] == "M001"
    assert ms["materials"][0]["pages"][0]["page_idx"] == 0
    # 表格内容提取
    blocks0 = ms["materials"][0]["pages"][0]["blocks"]
    table_block = [b for b in blocks0 if b["type"] == "table"]
    assert table_block and "付款方式" in table_block[0]["content"], "表格内容未提取"
    # bbox 保留
    assert any(b.get("bbox") for b in blocks0), "bbox 丢失"
    print("✅ JSON 结构校验通过（m_id / pages / blocks / bbox / table）")

    # 验证 PaddleOCR 块
    blocks1 = ms["materials"][1]["pages"][0]["blocks"]
    assert len(blocks1) == 2 and blocks1[0]["engine_source"] == "paddleocr"
    print("✅ PaddleOCR prunedResult → blocks 提取通过")

    # 验证降级（无结构化数据 → 全文单块）
    blocks2 = ms["materials"][2]["pages"][0]["blocks"]
    assert blocks2[0]["type"] == "text" and "这笔钱" in blocks2[0]["content"]
    print("✅ 多模态材料降级为全文单块通过")

    # 验证 MD 渲染
    with open(result["md_path"], "r", encoding="utf-8") as f:
        md = f.read()
    # source_file 为报告中的完整路径（含目录），此处匹配文件名部分
    assert "M001" in md and "合同扫描件.pdf" in md
    assert "✅ 自动定稿（A级）" in md
    assert "差异标记" in md and "<ins>" in md
    print("✅ MD 渲染通过（标题/状态/差异标记）")

    # 验证 schema.json
    with open(result["schema_path"], "r", encoding="utf-8") as f:
        schema = json.load(f)
    assert schema["properties"]["materials"]["type"] == "array"
    print("✅ Schema 契约文件通过")

# ---- 降级路径测试：损坏的报告触发 degraded ----
bad_reports = [{"file": None}]  # 缺少 primary_text 等
with tempfile.TemporaryDirectory() as tmp:
    r2 = asm.assemble("坏数据案件", bad_reports, tmp)
    assert r2["status"] == "degraded", f"应降级: {r2}"
    assert os.path.exists(r2["md_path"])
    print("✅ 降级路径通过（JSON 失败 → MD 单输出）")

print("\n🎉 全部测试通过")
