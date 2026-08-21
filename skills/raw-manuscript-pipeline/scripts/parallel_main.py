#!/usr/bin/env python3
"""
原始底稿流水线 - 并行处理主脚本
核心优化：文件级并行 + 智能路由 + 自动环境检查
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any

# OCR 引擎后端（同目录，接口见 ocr_backend.py）
from ocr_backend import CrossCheckerV6


def auto_env_check():
    """
    自动环境检查

    Returns:
        dict: {'mode': 'full'|'single'|'local', 'speed': str, 'accuracy': str}
    """
    print("=== 原始底稿流水线 - 自动环境检查 ===\n")

    # 检查 OCR API
    checker = CrossCheckerV6()
    paddle_ok = checker.paddleocr_token is not None
    mineru_ok = checker.mineru_token is not None

    # 打印状态
    print(f"PaddleOCR API: {'✅ 已配置' if paddle_ok else '❌ 未配置'}")
    print(f"MinerU API:    {'✅ 已配置' if mineru_ok else '❌ 未配置'}")

    # 推荐模式
    if paddle_ok and mineru_ok:
        mode = 'full'
        speed = '~8分钟/120文件'
        accuracy = '★★★★★'
    elif paddle_ok or mineru_ok:
        mode = 'single'
        speed = '~15分钟/120文件'
        accuracy = '★★★★'
    else:
        mode = 'local'
        speed = '~25分钟/120文件'
        accuracy = '★★★'

    print(f"\n推荐工作模式：{mode}")
    print(f"预计速度：{speed}")
    print(f"预计准确度：{accuracy}")

    if not paddle_ok or not mineru_ok:
        print(f"\n⚠️ 建议配置API以提升速度和准确度：")
        if not paddle_ok:
            print(f"  PaddleOCR: https://aistudio.baidu.com/paddleocr")
        if not mineru_ok:
            print(f"  MinerU: https://mineru.net")
        print(f"\n配置方式：设置环境变量 PADDLEOCR_TOKEN / MINERU_TOKEN")
        print(f"（详见 SKILL.md「环境配置」章节）")

    return {'mode': mode, 'speed': speed, 'accuracy': accuracy}


def detect_file_type(filepath: str) -> str:
    """
    通过文件头检测实际文件类型

    Returns:
        'pdf' | 'docx' | 'png' | 'jpg' | 'audio' | 'unknown'
    """
    with open(filepath, 'rb') as f:
        header = f.read(16)

    # PDF: %PDF-
    if header[:5] == b'%PDF-':
        return 'pdf'

    # ZIP (含 .docx): PK..
    if header[:4] == b'PK\x03\x04':
        return 'docx'

    # PNG: .PNG
    if header[:4] == b'\x89PNG':
        return 'png'

    # JPEG: .jpg
    if header[:2] == b'\xff\xd8':
        return 'jpg'

    return 'unknown'


def build_smart_routing(file_paths: List[str]) -> Dict[str, List[str]]:
    """
    智能路由：自动判断文件类型，分配到最佳处理工具

    Returns:
        dict: {
            'text_pdf': [文件列表],
            'scanned_pdf': [文件列表],
            'img_ocr': [文件列表],
            'img_multimodal': [文件列表],
            'docx': [文件列表],
            'audio': [文件列表],
        }
    """
    routing = {
        'text_pdf': [],
        'scanned_pdf': [],
        'img_ocr': [],
        'img_multimodal': [],
        'docx': [],
        'audio': [],
        'skip': []
    }

    for fp in file_paths:
        file_type = detect_file_type(fp)

        if file_type == 'pdf':
            # 判断是否为文字型PDF
            if is_text_pdf(fp):
                routing['text_pdf'].append(fp)
            else:
                routing['scanned_pdf'].append(fp)

        elif file_type in ['jpg', 'png']:
            # 判断是否为长截图（启发式：竖长图）
            if is_long_screenshot(fp):
                routing['img_multimodal'].append(fp)
            else:
                routing['img_ocr'].append(fp)

        elif file_type == 'docx':
            routing['docx'].append(fp)

        elif file_type == 'audio':
            routing['audio'].append(fp)

        else:
            routing['skip'].append(fp)

    return routing


def is_text_pdf(fp: str) -> bool:
    """判断是否为文字型PDF"""
    try:
        import fitz
        doc = fitz.open(fp)
        text = doc[0].get_text().strip()
        doc.close()
        return len(text) > 50
    except Exception:
        return False


def is_long_screenshot(fp: str) -> bool:
    """判断是否为竖长图（截图类，走多模态）"""
    try:
        from PIL import Image
        img = Image.open(fp)
        w, h = img.size
        return h > w * 2  # 竖长图
    except Exception:
        return False


def process_all_files_parallel(file_paths: List[str], max_workers: int = 3):
    """
    并行处理所有文件

    Returns:
        dict: {'pdf_results': {...}, 'img_results': {...}, ...}
    """
    # 1. 智能路由
    routing = build_smart_routing(file_paths)

    print(f"\n智能路由结果：")
    print(f"  文字型PDF: {len(routing['text_pdf'])} 个")
    print(f"  扫描件PDF: {len(routing['scanned_pdf'])} 个")
    print(f"  图片(OCR): {len(routing['img_ocr'])} 个")
    print(f"  图片(多模态): {len(routing['img_multimodal'])} 个")
    print(f"  Word文档: {len(routing['docx'])} 个")
    print(f"  音频: {len(routing['audio'])} 个")
    print(f"  跳过: {len(routing['skip'])} 个\n")

    results = {
        'pdf_results': {},
        'img_results': {},
        'docx_results': {},
        'audio_results': {},
    }

    start_time = time.time()

    # 2. 批量处理扫描件PDF（OCR双引擎批量）
    scanned_pdf_results = {}
    if routing['scanned_pdf']:
        print(f"\n批量处理 {len(routing['scanned_pdf'])} 个扫描件PDF...")
        scanned_pdf_results = process_scanned_pdfs_batch(routing['scanned_pdf'])
        for fp, res in scanned_pdf_results.items():
            results['pdf_results'][fp] = res

    # 3. 并行处理其他类型文件
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        # 3a. 文字型PDF（PyMuPDF）
        for fp in routing['text_pdf']:
            future = executor.submit(process_text_pdf, fp)
            futures[future] = ('pdf', fp)

        # 3b. 图片（OCR）- 单文件兼容
        for fp in routing['img_ocr']:
            future = executor.submit(process_img_ocr, fp)
            futures[future] = ('img', fp)

        # 3c. 图片（多模态）
        for fp in routing['img_multimodal']:
            future = executor.submit(process_img_multimodal, fp)
            futures[future] = ('img', fp)

        # 3d. Word文档
        for fp in routing['docx']:
            future = executor.submit(process_docx, fp)
            futures[future] = ('docx', fp)

        # 4. 收集结果
        completed = 0
        total = len(futures) + len(routing['scanned_pdf'])

        for future in as_completed(futures):
            item_type, fp = futures[future]
            completed += 1

            try:
                result = future.result(timeout=300)

                if item_type == 'pdf':
                    results['pdf_results'][fp] = result
                elif item_type == 'img':
                    results['img_results'][fp] = result
                elif item_type == 'docx':
                    results['docx_results'][fp] = result

                # 进度显示
                elapsed = time.time() - start_time
                avg_time = elapsed / max(completed + len(routing['scanned_pdf']), 1)
                remaining = (total - completed - len(routing['scanned_pdf'])) * avg_time

                print(f"[{completed + len(routing['scanned_pdf'])}/{total}] {Path(fp).name} - "
                      f"预计剩余: {remaining/60:.1f}分钟")

            except Exception as e:
                print(f"[{completed + len(routing['scanned_pdf'])}/{total}] {Path(fp).name} - 失败: {e}")

    # 4. 统计
    elapsed_total = time.time() - start_time
    results['stats'] = {
        'total': total,
        'elapsed_seconds': elapsed_total,
        'elapsed_minutes': elapsed_total / 60,
        'max_workers': max_workers,
    }

    print(f"\n✅ 处理完成：{total} 个文件，耗时 {elapsed_total/60:.1f} 分钟")

    return results


def process_text_pdf(fp: str) -> Dict[str, Any]:
    """处理文字型PDF（PyMuPDF）"""
    import fitz

    doc = fitz.open(fp)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    return {
        'status': 'resolved',
        'primary_text': text,
        'confidence': 'A',  # PyMuPDF极可靠
        'source': 'PyMuPDF',
        'file': fp,
    }


def process_scanned_pdfs_batch(file_paths: List[str]) -> Dict[str, Any]:
    """批量处理扫描件PDF（OCR双引擎批量）"""
    try:
        checker = CrossCheckerV6()
        reports = checker.batch_check_v2(file_paths, max_workers=4)

        # 按文件路径映射结果
        return {fp: report for fp, report in zip(file_paths, reports)}
    except Exception as e:
        return {fp: {'status': 'failed', 'error': str(e), 'confidence': 'E'} for fp in file_paths}


def process_pdf_ocr(fp: str) -> Dict[str, Any]:
    """处理扫描件PDF（兼容单文件调用）"""
    return process_scanned_pdfs_batch([fp]).get(fp, {
        'status': 'failed', 'error': '未知错误', 'confidence': 'E'
    })


def process_img_ocr(fp: str) -> Dict[str, Any]:
    """
    处理普通图片（单文件双引擎 OCR 交叉核对）
    """
    try:
        checker = CrossCheckerV6()
        report = checker.check_file(fp)

        # 双引擎均失败时标记多模态兜底（由 Agent 后续处理）
        if report.get('status') == 'need_multimodal':
            return {
                'status': 'need_multimodal',
                'file': fp,
                'primary_text': '',
                'confidence': 'Pending',
                'source': 'pending_multimodal',
                'note': 'OCR双引擎均失败，需要调用多模态模型进行完整转录'
            }
        return report
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'file': fp,
            'confidence': 'E'
        }


def process_img_multimodal(fp: str) -> Dict[str, Any]:
    """
    处理图片（多模态）

    注意：实际多模态调用由 Agent 完成（通过视觉模型读取图片）
    本函数返回特殊状态，让 Agent 知道需要处理
    """
    return {
        'status': 'need_multimodal',
        'file': fp,
        'primary_text': '',
        'confidence': 'Pending',
        'source': 'pending_multimodal',
        'note': '需要调用多模态模型进行完整转录'
    }


def process_docx(fp: str) -> Dict[str, Any]:
    """处理Word文档（python-docx）"""
    try:
        from docx import Document

        doc = Document(fp)
        text = "\n".join(para.text for para in doc.paragraphs)

        return {
            'status': 'resolved',
            'primary_text': text,
            'confidence': 'A',
            'source': 'python-docx',
            'file': fp,
        }
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e),
            'confidence': 'E',
            'file': fp,
        }


def assemble_manuscript_output(project_name: str, results: Dict[str, Any], output_dir: str) -> Dict[str, Any]:
    """
    将 parallel_main 处理结果组装为底稿 JSON + MD（双输出入口）

    Args:
        project_name: 案件简称
        results: process_all_files_parallel 的返回（pdf_results / img_results / docx_results / audio_results）
        output_dir: 输出目录（如 02_scratch/[项目名]/01_原始底稿/）

    Returns:
        assemble_json.ManuscriptAssembler.assemble() 的返回
    """
    from assemble_json import ManuscriptAssembler

    # 拍平分组结果 → reports 列表（保持 M 编号顺序：PDF → 图片 → Word → 音频）
    reports = []
    for group in ("pdf_results", "img_results", "docx_results", "audio_results"):
        group_data = results.get(group, {})
        if isinstance(group_data, dict):
            for fp, res in group_data.items():
                r = dict(res)
                r.setdefault("file", fp)
                r.setdefault("status", res.get("status", "unknown"))
                r.setdefault("confidence", res.get("confidence", "?"))
                r.setdefault("primary_text", res.get("primary_text", ""))
                # need_multimodal 文件已由 Agent 多模态转录并回填 primary_text 后，此处直接组装
                reports.append(r)
        elif isinstance(group_data, list):
            for res in group_data:
                if isinstance(res, dict):
                    r = dict(res)
                    r.setdefault("file", res.get("file", "unknown"))
                    r.setdefault("status", res.get("status", "unknown"))
                    r.setdefault("confidence", res.get("confidence", "?"))
                    r.setdefault("primary_text", res.get("primary_text", ""))
                    reports.append(r)

    asm = ManuscriptAssembler()
    return asm.assemble(project_name, reports, output_dir)


if __name__ == '__main__':
    # 自动环境检查
    env = auto_env_check()
    print(f"\n检测结果：{env['mode']} 模式")
