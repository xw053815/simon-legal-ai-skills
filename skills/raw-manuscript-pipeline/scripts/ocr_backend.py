#!/usr/bin/env python3
"""
OCR 引擎后端接口契约 + 参考实现
================================

本模块定义原始底稿流水线与 OCR 引擎之间的标准接口，并提供两种实现：

1. **参考实现（本文件）**：对接 PaddleOCR / MinerU 官方 HTTP API
2. **Mock 模式**：未配置 token 时返回模拟报告，用于流水线功能演示

接口契约（实现方必须满足）：

```python
class CrossCheckerV6:
    def check_file(self, fp: str, pymupdf_text: str = None) -> dict:
        \"\"\"单文件交叉核对。
        返回: {
            "status": "auto_resolved" | "auto_resolved_with_diff" | "single_engine"
                    | "need_multimodal" | "failed",
            "primary_text": str,          # 定稿文本
            "verification_text": str,     # 核对文本
            "confidence": "A".."E",
            "similarity": float,          # 0-1
            "source": "mineru" | "paddleocr" | "multimodal_vision" | ...,
            "language": "zh" | "en",
            "diff_markup": str | None,    # <ins>/<del> 差异标记
            "structured_mineru": {"content_list": ..., "middle_json": ...},
            "structured_paddle": {"layoutParsingResults": ...},
            "file": str,
        }

    def batch_check_v2(self, file_paths: list, max_workers: int = 4) -> list:
        \"\"\"批量交叉核对（引擎级批量）。
        返回: list[dict]，顺序与 file_paths 对齐。\"\"\"
"""
__version__ = "1.0.0"

import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional


# ============ 配置 ============

def _get_config() -> Dict[str, Any]:
    """
    从环境变量或配置文件读取 OCR 引擎 token。

    优先级：
    1. 环境变量 PADDLEOCR_TOKEN / MINERU_TOKEN
    2. 配置文件（路径由 OCR_API_CONFIG 指定，默认 ~/.workbuddy/ocr_api_config.json）
    """
    config = {"paddleocr": {"token": None}, "mineru": {"token": None}}

    env_map = {"paddleocr": "PADDLEOCR_TOKEN", "mineru": "MINERU_TOKEN"}
    for engine, env_name in env_map.items():
        val = os.environ.get(env_name)
        if val:
            config[engine]["token"] = val

    config_path = os.environ.get("OCR_API_CONFIG")
    if not config_path:
        config_path = str(os.path.expanduser("~/.workbuddy/ocr_api_config.json"))
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            for engine in ("paddleocr", "mineru"):
                if engine in file_cfg and file_cfg[engine].get("token"):
                    config[engine]["token"] = file_cfg[engine]["token"]
        except Exception:
            pass

    return config


# ============ 引擎客户端（参考实现） ============

class PaddleOCRClient:
    """PaddleOCR API 客户端（参考实现）"""

    BASE_URL = "https://aistudio.baidu.com/paddleocr"

    def __init__(self, token: Optional[str] = None):
        self.token = token or _get_config()["paddleocr"]["token"]

    def parse_file(self, fp: str) -> Dict[str, Any]:
        """单文件解析。返回 {full_text, layoutParsingResults}"""
        # 真实实现：multipart 上传文件 → 解析响应
        # 示例（伪代码）：
        #   import requests
        #   with open(fp, "rb") as f:
        #       resp = requests.post(f"{self.BASE_URL}/v3/ocr", files={"file": f},
        #                            headers={"Authorization": f"Bearer {self.token}"})
        #   data = resp.json()
        #   return {"full_text": data["prunedResult"]["markdown"]["text"],
        #           "layoutParsingResults": [data["prunedResult"]]}
        raise NotImplementedError(
            "PaddleOCR 真实调用未实现——请在此处对接你的 OCR 服务，或使用 Mock 模式"
        )

    def parse_files(self, file_paths: List[str], max_workers: int = 4) -> List[Dict[str, Any]]:
        """多文件并行提交 + 统一轮询"""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.parse_file, fp): fp for fp in file_paths}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"error": str(e), "file": futures[fut]})
        return results


class MinerUClient:
    """MinerU API 客户端（参考实现）"""

    BASE_URL = "https://mineru.net"

    def __init__(self, token: Optional[str] = None):
        self.token = token or _get_config()["mineru"]["token"]

    def parse_file(self, fp: str) -> Dict[str, Any]:
        """单文件解析。返回 {full_text, content_list, middle_json}"""
        # 真实实现：上传文件 → 轮询任务 → 下载 zip → 解压提取 content_list.json
        raise NotImplementedError(
            "MinerU 真实调用未实现——请在此处对接你的 OCR 服务，或使用 Mock 模式"
        )

    def parse_files(self, file_paths: List[str], max_workers: int = 4) -> List[Dict[str, Any]]:
        """多文件批量提交（一批 ≤50 文件）"""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.parse_file, fp): fp for fp in file_paths}
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as e:
                    results.append({"error": str(e), "file": futures[fut]})
        return results


# ============ Mock 模式（无 token 时可运行演示） ============

class MockOCREngine:
    """Mock 引擎：未配置 token 时返回模拟报告，供流水线功能演示"""

    def parse_file(self, fp: str) -> Dict[str, Any]:
        return {
            "full_text": f"[Mock OCR] {os.path.basename(fp)} 的模拟识别文本。",
            "content_list": [
                {"type": "text", "bbox": [0, 0, 100, 50], "text": "模拟文本"},
            ],
            "layoutParsingResults": [
                {"prunedResult": {"res": [
                    {"block_label": "text", "block_box": [0, 0, 100, 50],
                     "text": "模拟文本"},
                ]}},
            ],
        }


# ============ 交叉核对器 ============

class CrossCheckerV6:
    """
    双引擎交叉核对器

    行为：
    - 配置了双引擎 token → 真实交叉核对（需实现引擎客户端）
    - 未配置 token → Mock 模式（返回模拟报告，可演示）
    - 单文件：check_file()；批量：batch_check_v2()
    """

    def __init__(self):
        config = _get_config()
        self.paddleocr_token = config["paddleocr"]["token"]
        self.mineru_token = config["mineru"]["token"]

        if self.paddleocr_token and self.mineru_token:
            self.pc = PaddleOCRClient(self.paddleocr_token)
            self.mu = MinerUClient(self.mineru_token)
            self.mock = False
        else:
            self.pc = MockOCREngine()
            self.mu = MockOCREngine()
            self.mock = True

    def _detect_language(self, text: str) -> str:
        """检测文本语言（CJK vs Latin 字符比例）——引擎选择铁则"""
        if not text:
            return "zh"
        cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        latin = sum(1 for c in text if c.isascii() and c.isalpha())
        return "zh" if cjk >= latin else "en"

    def _similarity(self, a: str, b: str) -> float:
        """文本相似度（轻量：字符 n-gram 重叠）"""
        if not a or not b:
            return 0.0
        sa, sb = set(a), set(b)
        return round(len(sa & sb) / max(len(sa | sb), 1), 4)

    def check_file(self, fp: str, pymupdf_text: str = None) -> Dict[str, Any]:
        """单文件交叉核对"""
        if self.mock:
            return self._mock_report(fp)
        raise NotImplementedError(
            "真实交叉核对未实现——请实现 PaddleOCRClient.parse_file 与 MinerUClient.parse_file"
        )

    def batch_check_v2(self, file_paths: List[str], max_workers: int = 4) -> List[Dict[str, Any]]:
        """批量交叉核对（引擎级批量），顺序与 file_paths 对齐"""
        reports = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.check_file, fp): fp for fp in file_paths}
            for fut in as_completed(futures):
                try:
                    reports.append(fut.result())
                except Exception as e:
                    reports.append({
                        "status": "failed", "error": str(e), "confidence": "E",
                        "file": futures[fut], "primary_text": "",
                    })
        # 按 file_paths 顺序对齐
        order = {fp: i for i, fp in enumerate(file_paths)}
        reports.sort(key=lambda r: order.get(r.get("file", ""), 0))
        return reports

    def _mock_report(self, fp: str) -> Dict[str, Any]:
        """Mock 报告（模拟 auto_resolved）"""
        text = f"[Mock OCR] {os.path.basename(fp)} 的模拟识别文本。"
        return {
            "status": "auto_resolved",
            "primary_text": text,
            "verification_text": text,
            "confidence": "A",
            "similarity": 0.99,
            "source": "mineru",
            "language": "zh",
            "diff_markup": None,
            "structured_mineru": {"content_list": [
                {"type": "text", "bbox": [0, 0, 100, 50],
                 "content": {"paragraph_content": [{"type": "text", "content": text}]}},
            ], "middle_json": None},
            "structured_paddle": None,
            "file": fp,
        }


# ============ CLI ============
if __name__ == "__main__":
    cc = CrossCheckerV6()
    mode = "Mock" if cc.mock else "Real"
    print(f"OCR 后端：{mode} 模式")
    print(f"  PaddleOCR: {'✅' if cc.paddleocr_token else '❌'} | MinerU: {'✅' if cc.mineru_token else '❌'}")
