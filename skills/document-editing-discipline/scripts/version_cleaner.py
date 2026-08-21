r"""
版本清理脚本 - 保留最新3个版本，删除更早版本

用法：
  python version_cleaner.py [目录路径] [保留版本数]

示例：
  python version_cleaner.py "[用户目录]\WorkBuddy\某案件\02_scratch" 3
  python version_cleaner.py . 3
"""

import os
import re
import sys
import shutil


def clean_old_versions(directory, keep=3):
    """
    保留最新keep个版本，删除更早版本，更新无后缀版本
    
    Args:
        directory: 要清理的目录路径
        keep: 保留的版本数量（默认3）
    """
    # 扫描所有文件
    files = []
    for f in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, f)):
            files.append(f)
    
    # 按[类型]_[案件简称]分组
    groups = {}
    for f in files:
        # 匹配格式：[日期]_[类型]_[案件简称]_v[版本号].[扩展名]
        match = re.match(r'^(.+)_v(\d+)(\..+)$', f)
        if match:
            base = match.group(1)  # [日期]_[类型]_[案件简称]
            ver = int(match.group(2))  # 版本号
            ext = match.group(3)  # .docx / .md 等
            if base not in groups:
                groups[base] = []
            groups[base].append((ver, f, ext))
    
    # 每组保留最新keep个
    deleted = []
    for base, versions in groups.items():
        versions.sort(reverse=True)  # 按版本号降序排序
        
        # 删除早期版本
        for i, (ver, fname, ext) in enumerate(versions):
            if i >= keep:
                file_path = os.path.join(directory, fname)
                os.remove(file_path)
                deleted.append(fname)
        
        # 更新无后缀版本
        if versions:
            latest_ver = versions[0][1]  # vN的文件名
            latest_ext = versions[0][2]  # 扩展名
            no_suffix = base + latest_ext  # 无后缀版本的文件名
            no_suffix_path = os.path.join(directory, no_suffix)
            
            if os.path.exists(no_suffix_path):
                # 更新为副本（Windows下软链接需要管理员权限）
                shutil.copy2(os.path.join(directory, latest_ver), no_suffix_path)
                print(f"  已更新无后缀版本：{no_suffix}")
    
    if deleted:
        print(f"已删除早期版本（保留最新{keep}个）：")
        for f in deleted:
            print(f"  - {f}")
    else:
        print(f"无需清理（每个文件最多{keep}个版本）")
    
    return deleted


def main():
    if len(sys.argv) < 2:
        print("用法：python version_cleaner.py [目录路径] [保留版本数]")
        print("\n示例：")
        print(r'  python version_cleaner.py "[用户目录]\WorkBuddy\某案件\02_scratch" 3')
        print('  python version_cleaner.py . 3')
        sys.exit(1)
    
    directory = sys.argv[1]
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    if not os.path.isdir(directory):
        print(f"错误：目录不存在 - {directory}")
        sys.exit(1)
    
    print(f"清理目录：{directory}")
    print(f"保留版本数：{keep}")
    print("-" * 50)
    
    deleted = clean_old_versions(directory, keep)
    
    print("-" * 50)
    print(f"清理完成：删除 {len(deleted)} 个早期版本")


if __name__ == '__main__':
    main()
