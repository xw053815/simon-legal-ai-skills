#!/usr/bin/env python3
"""
自动环境检查
"""
import sys
import os
from pathlib import Path


def auto_env_check():
    """
    自动检测环境，返回推荐配置和工作模式

    Returns:
        dict: {'mode': 'full'|'single'|'local', 'speed': str, 'accuracy': str}
    """
    print("=== 原始底稿流水线 - 自动环境检查 ===\n")

    # 1. 检查 OCR API 配置（环境变量优先，其次配置文件）
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ocr_backend import CrossCheckerV6

    checker = CrossCheckerV6()
    paddle_ok = checker.paddleocr_token is not None
    mineru_ok = checker.mineru_token is not None

    # 2. 打印状态
    print(f"PaddleOCR API: {'✅ 已配置' if paddle_ok else '❌ 未配置'}")
    print(f"MinerU API:    {'✅ 已配置' if mineru_ok else '❌ 未配置'}")

    # 3. 推荐模式
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

    # 4. 给出配置建议
    if not paddle_ok or not mineru_ok:
        print(f"\n⚠️ 建议配置API以提升速度和准确度：")
        if not paddle_ok:
            print(f"  PaddleOCR: https://aistudio.baidu.com/paddleocr")
        if not mineru_ok:
            print(f"  MinerU: https://mineru.net")
        print(f"\n配置方式：设置环境变量 PADDLEOCR_TOKEN / MINERU_TOKEN")
        print(f"或写入配置文件（OCR_API_CONFIG 指定路径，默认 ~/.workbuddy/ocr_api_config.json）")

    return {'mode': mode, 'speed': speed, 'accuracy': accuracy}


if __name__ == '__main__':
    result = auto_env_check()
    print(f"\n检测结果：{result['mode']} 模式")
