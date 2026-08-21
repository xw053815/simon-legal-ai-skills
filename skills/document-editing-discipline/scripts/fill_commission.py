#!/usr/bin/env python3
"""
填写委托书（无律所盖章版）— 以修订模式填写律师信息
"""
import zipfile, os, shutil, sys, tempfile
from datetime import datetime, timezone
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def _now_iso():
    """当前 UTC 时间，ISO 8601 格式（v7.1 修复：禁止硬编码过期时间）。"""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def make_del_run(text, rPr_src, ins_id, author="律师"):
    d = etree.Element(f'{W}del')
    d.set(f'{W}id', str(ins_id))
    d.set(f'{W}author', author)
    d.set(f'{W}date', _now_iso())
    r = etree.SubElement(d, f'{W}r')
    if rPr_src is not None:
        r.append(rPr_src)
    t = etree.SubElement(r, f'{W}delText')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return d

def make_ins_run(text, rPr_src, ins_id, author="律师"):
    ins = etree.Element(f'{W}ins')
    ins.set(f'{W}id', str(ins_id))
    ins.set(f'{W}author', author)
    ins.set(f'{W}date', _now_iso())
    r = etree.SubElement(ins, f'{W}r')
    if rPr_src is not None:
        r.append(rPr_src)
    t = etree.SubElement(r, f'{W}t')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return ins

def main(src_path):
    bak_path = src_path.replace('.docx', '_bak.docx')
    shutil.copy2(src_path, bak_path)
    
    with zipfile.ZipFile(src_path, 'r') as z:
        xml = z.read('word/document.xml')
    
    root = etree.fromstring(xml)
    body = root.find(f'{W}body')
    paras = list(body.findall(f'{W}p'))
    
    ins_id = [1]
    def next_id():
        ins_id[0] += 1
        return ins_id[0]
    
    # ============ 1. 段落[3] — 律师姓名、当事人、案由 ============
    p3 = paras[3]
    
    # 找出所有 run 的文本
    def get_runs_text(p):
        runs = list(p)
        result = []
        for r in runs:
            t = r.find(f'{W}t') or r.find(f'{W}delText')
            txt = t.text if t is not None else ''
            u = 'Y' if r.find(f'{W}u') is not None or (r.find(f'{W}rPr') is not None and r.find(f'{W}rPr').find(f'{W}u') is not None) else ''
            result.append((txt, u))
        return result
    
    runs_p3 = list(p3)
    p3_texts = get_runs_text(p3)
    
    # 替换律师姓名空格 → "经办律师"
    # 第4个run（索引3）: "              " 有下划线
    for idx, (txt, u) in enumerate(p3_texts):
        if txt and txt.strip() == '' and u == 'Y' and len(txt) >= 12:
            old_r = runs_p3[idx]
            rPr = old_r.find(f'{W}rPr')
            if rPr is not None:
                # 检查长度：最短的空格（12个）是律师姓名
                if len(txt) >= 12 and len(txt) <= 15:
                    ins = make_ins_run("经办律师", rPr, next_id())
                    d = make_del_run(txt, rPr, next_id())
                    p3.replace(old_r, d)
                    d_idx = list(p3).index(d)
                    p3.insert(d_idx + 1, ins)
                    print(f"  律师姓名: 空格({len(txt)}个) → 经办律师")
                    break
    
    # 重新获取 runs
    runs_p3 = list(p3)
    
    # 替换原告空格 → "[委托人公司全称]"
    # 找"与"字前面的空格run
    for i, r in enumerate(runs_p3):
        t = r.find(f'{W}t')
        if t is not None and t.text and t.text == '与':
            prev_r = runs_p3[i-1]
            pt = prev_r.find(f'{W}t') or prev_r.find(f'{W}delText')
            if pt is not None and pt.text and pt.text.strip() == '':
                rPr = prev_r.find(f'{W}rPr')
                if rPr is not None:
                    ins = make_ins_run("[委托人公司全称]", rPr, next_id())
                    d = make_del_run(pt.text, rPr, next_id())
                    p3.replace(prev_r, d)
                    d_idx = list(p3).index(d)
                    p3.insert(d_idx + 1, ins)
                    print(f"  原告: 空格 → [委托人公司全称]")
                    break
    
    runs_p3 = list(p3)
    
    # 替换被告空格 → "[相对方公司全称]"
    # 找"与"字后面的空格run（最长的下划线空格）
    for i, r in enumerate(runs_p3):
        t = r.find(f'{W}t')
        if t is not None and t.text and t.text == '与':
            for j in range(i+1, len(runs_p3)):
                nr = runs_p3[j]
                nt = nr.find(f'{W}t') or nr.find(f'{W}delText')
                if nt is not None and nt.text and nt.text.strip() == '':
                    rPr = nr.find(f'{W}rPr')
                    if rPr is not None:
                        ins = make_ins_run("[相对方公司全称]", rPr, next_id())
                        d = make_del_run(nt.text, rPr, next_id())
                        p3.replace(nr, d)
                        d_idx = list(p3).index(d)
                        p3.insert(d_idx + 1, ins)
                        print(f"  被告: 空格 → [相对方公司全称]")
                        break
            break
    
    runs_p3 = list(p3)
    
    # 替换案由 "的______________" → "的[案由]"
    for r in runs_p3:
        t = r.find(f'{W}t')
        if t is not None and t.text and '______________' in t.text:
            rPr = r.find(f'{W}rPr')
            ins = make_ins_run("的[案由]", rPr, next_id())
            d = make_del_run(t.text, rPr, next_id())
            p3.replace(r, d)
            d_idx = list(p3).index(d)
            p3.insert(d_idx + 1, ins)
            print(f"  案由: 的______________ → 的[案由]")
            break
    
    # ============ 2. 段落[4] — 代理角色 ============
    p4 = paras[4]
    runs_p4 = list(p4)
    
    # 替换第一个下划线空格run → "被告"
    found_first = False
    for i, r in enumerate(runs_p4):
        t = r.find(f'{W}t') or r.find(f'{W}delText')
        if t is not None and t.text and t.text.strip() == '':
            rPr = r.find(f'{W}rPr')
            if rPr is not None and rPr.find(f'{W}u') is not None:
                if not found_first:
                    ins = make_ins_run("被告", rPr, next_id())
                    d = make_del_run(t.text, rPr, next_id())
                    p4.replace(r, d)
                    d_idx = list(p4).index(d)
                    p4.insert(d_idx + 1, ins)
                    print(f"  代理角色1: 空格 → 被告")
                    found_first = True
                    break
    
    runs_p4 = list(p4)
    
    # 替换第二个下划线空格run（最长的）→ "诉讼代理人"
    found_second = False
    for i, r in enumerate(runs_p4):
        t = r.find(f'{W}t') or r.find(f'{W}delText')
        if t is not None and t.text and t.text.strip() == '' and len(t.text) >= 17:
            rPr = r.find(f'{W}rPr')
            if rPr is not None:
                ins = make_ins_run("诉讼代理人", rPr, next_id())
                d = make_del_run(t.text, rPr, next_id())
                p4.replace(r, d)
                d_idx = list(p4).index(d)
                p4.insert(d_idx + 1, ins)
                print(f"  代理角色2: 空格 → 诉讼代理人")
                found_second = True
                break
    
    # ============ 3. 代理权限 — ☑特别代理 ============
    p8 = paras[8]
    for r in list(p8):
        t = r.find(f'{W}t')
        if t is not None and t.text and '□特别代理' in t.text:
            rPr = r.find(f'{W}rPr')
            ins = make_ins_run("☑特别代理", rPr, next_id())
            d = make_del_run("□特别代理", rPr, next_id())
            p8.replace(r, d)
            d_idx = list(p8).index(d)
            p8.insert(d_idx + 1, ins)
            print(f"  代理权限: □特别代理 → ☑特别代理")
            break
    
    # ============ 4. 段落[19] — 法院 ============
    p19 = paras[19]
    for r in list(p19):
        t = r.find(f'{W}t') or r.find(f'{W}delText')
        if t is not None and t.text and t.text.strip() == '':
            rPr = r.find(f'{W}rPr')
            if rPr is not None and rPr.find(f'{W}u') is not None:
                ins = make_ins_run("[管辖法院所在地]", rPr, next_id())
                d = make_del_run(t.text, rPr, next_id())
                p19.replace(r, d)
                d_idx = list(p19).index(d)
                p19.insert(d_idx + 1, ins)
                print(f"  法院: 空格 → [管辖法院所在地]")
                break
    
    # ============ 5. 段落[21] — 委托人 ============
    p21 = paras[21]
    for r in list(p21):
        t = r.find(f'{W}t')
        if t is not None and t.text and '委托人' in t.text:
            rPr = r.find(f'{W}rPr')
            ins = make_ins_run("[委托人公司全称]", rPr, next_id())
            d = make_del_run(t.text, rPr, next_id())
            p21.replace(r, d)
            d_idx = list(p21).index(d)
            p21.insert(d_idx + 1, ins)
            print(f"  委托人: 委托人： → [委托人公司全称]")
            break
    
    # ============ 6. 段落[24] — 日期 ============
    p24 = paras[24]
    for r in list(p24):
        t = r.find(f'{W}t')
        if t is not None and t.text and '年' in t.text:
            rPr = r.find(f'{W}rPr')
            ins = make_ins_run("2026 年 7 月 22 日", rPr, next_id())
            d = make_del_run(t.text, rPr, next_id())
            p24.replace(r, d)
            d_idx = list(p24).index(d)
            p24.insert(d_idx + 1, ins)
            print(f"  日期: 年  月  日 → 2026 年 7 月 22 日")
            break
    
    # 写入修改后的 XML
    new_xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    
    tmp = tempfile.mktemp('.docx')
    with zipfile.ZipFile(src_path, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == 'word/document.xml':
                    zout.writestr(item, new_xml)
                else:
                    zout.writestr(item, zin.read(item.filename))
    
    shutil.move(tmp, src_path)
    print(f"\n完成！共生成 {ins_id[0]} 个修订ID")
    print(f"备份文件: {bak_path}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: fill_commission.py <docx_path>")
        sys.exit(1)
    main(sys.argv[1])