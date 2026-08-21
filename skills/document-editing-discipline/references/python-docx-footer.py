# -*- coding: utf-8 -*-
"""python-docx 页脚页码域构建：PAGE / NUMPAGES 域字段

用户确认规则（2026-06-30）：页码格式永远是 `1 / X` 阿拉伯数字格式，
不要用「第 X 页 / 共 Y 页」中文版。所有 Word 文档生成默认采用此格式。

OfficeCLI 域字段注意事项：
- `add --type field` 的 `font.ea` / `font.latin` 会被忽略（报 UNSUPPORTED props）
- 必须在 add 后用 `set` 单独给字段结果 run 设字体
- 字段结构：fieldChar(begin) → instrText(PAGE/NUMPAGES) → fieldChar(separate) → run(结果) → fieldChar(end)
"""

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_field_run(para, field_code, font_name='Times New Roman', ea_font='宋体', size=9):
    """在指定段落中追加一个域字段 run"""
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    rf = OxmlElement('w:rFonts')
    rf.set(qn('w:ascii'), font_name)
    rf.set(qn('w:hAnsi'), font_name)
    rPr.append(rf)
    ea = OxmlElement('w:eastAsia')
    ea.text = ea_font
    rPr.append(ea)
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), str(size * 2))
    rPr.append(sz)
    r.append(rPr)

    # fieldChar(begin)
    r_begin = OxmlElement('w:r')
    fc_begin = OxmlElement('w:fldChar')
    fc_begin.set(qn('w:fldCharType'), 'begin')
    r_begin.append(fc_begin)
    para.append(r_begin)

    # instrText
    r_instr = OxmlElement('w:r')
    it = OxmlElement('w:instrText')
    it.set(qn('xml:space'), 'preserve')
    it.text = field_code
    r_instr.append(it)
    para.append(r_instr)

    # fieldChar(separate)
    r_sep = OxmlElement('w:r')
    fc_sep = OxmlElement('w:fldChar')
    fc_sep.set(qn('w:fldCharType'), 'separate')
    r_sep.append(fc_sep)
    para.append(r_sep)

    # 结果 run（占位，Word 打开后自动计算）
    r_result = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.set(qn('xml:space'), 'preserve')
    t.text = '1'
    r_result.append(t)
    para.append(r_result)

    # fieldChar(end)
    r_end = OxmlElement('w:r')
    fc_end = OxmlElement('w:fldChar')
    fc_end.set(qn('w:fldCharType'), 'end')
    r_end.append(fc_end)
    para.append(r_end)


def build_footer(doc):
    """构建页脚：PAGE / NUMPAGES 域"""
    sec = doc.sections[0]
    footer = sec.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.text = ''
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

    r_para = fp._p
    add_field_run(r_para, ' PAGE ')   # 当前页
    # 中间加 " / "
    r_sep = OxmlElement('w:r')
    t_sep = OxmlElement('w:t')
    t_sep.set(qn('xml:space'), 'preserve')
    t_sep.text = ' / '
    r_sep.append(t_sep)
    r_para.append(r_sep)
    add_field_run(r_para, ' NUMPAGES ')  # 总页数

    # Word 打开后自动渲染为 "1 / 3"
