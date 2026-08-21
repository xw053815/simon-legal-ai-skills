# OfficeCLI 新建文档 batch 实战配方

> 来源：2026-08-04 合并论证报告任务（118 条 batch 指令一次成型，56 段落+1 表格，双引擎核验全通过）。以下语法全部经过实测验证，可直接复用。

## batch JSON 核心语法

batch 指令的字段名与 CLI 单条命令不同——**`command` 而非 `action`，`props` 而非 `prop`，`parent` 而非 `path`**（`path` 仅用于 `set`/`remove`/`get` 的目标）。

| 字段 | 用法 | 说明 |
|------|------|------|
| `command` | `"add"` / `"set"` / `"remove"` / `"get"` / `"query"` / `"move"` / `"swap"` | 必选，动词 |
| `parent` | `"/body"` / `"/body/p[N]"` / `"/body/tbl[N]/tr[R]/tc[C]/p[1]"` | `add` 的目标父节点 |
| `path` | `"/body/p[N]"` / `"/section[1]"` / `"/footer[1]/p[1]/r[N]"` | `set`/`remove`/`get` 的目标路径 |
| `type` | `"paragraph"` / `"run"` / `"table"` / `"field"` / `"footer"` / `"header"` | `add` 时的元素类型 |
| `props` | `{...}` | 属性键值对，见下方语法规则 |

**props 语法铁律（batch 内）**：

1. **字体必须点分**：`"font.ea":"宋体"` + `"font.latin":"Times New Roman"`。**禁止** `"font":{"ea":"宋体","latin":"TNR"}`（报 `Unexpected token StartObject`）。
2. **字号带单位**：`"size":"12pt"`，不是 `"size":12`（CLI 单条可裸值，batch JSON 须带 `pt`）。
3. **布尔值用字符串**：`"bold":"true"`，不是 `"bold":true`。
4. **段落级格式**：`"align":"both"`（两端对齐）、`"lineSpacing":1.5`、`"firstLineChars":200`、`"spaceBefore":0`、`"spaceAfter":0`。
5. **`set` 不支持 `firstLine`**——正确属性名是 **`firstLineIndent`**（如 `"firstLineIndent":"0.85cm"`）。

## 段内混合加粗（核心结论/引导句场景）

正文段中部分加粗（如"**维持三层架构不变**：香港公司承担……"），须拆分为多个 run：

```json
[
  {"command":"add","parent":"/body","type":"paragraph","props":{"text":"1. ","font.ea":"宋体","font.latin":"Times New Roman","size":"12pt","align":"both","firstLineChars":200,"lineSpacing":1.5}},
  {"command":"add","parent":"/body/p[N]","type":"run","props":{"text":"维持三层架构不变","font.ea":"宋体","font.latin":"Times New Roman","size":"12pt","bold":"true"}},
  {"command":"add","parent":"/body/p[N]","type":"run","props":{"text":"：香港公司承担……","font.ea":"宋体","font.latin":"Times New Roman","size":"12pt"}}
]
```

**规则**：第一个 run 随 `add paragraph` 创建（含段落格式）；后续 run 用 `add run` 追加到 `/body/p[N]`，只设字体/加粗，不设段落级属性（`align`/`firstLineChars`/`lineSpacing` 在 run 层被忽略）。

## 表格生成（单元格 run 嵌套）

```json
[
  {"command":"add","parent":"/body","type":"table","props":{"rows":3,"cols":6,"style":"Table Grid"}},
  {"command":"add","parent":"/body/tbl[1]/tr[1]/tc[1]/p[1]","type":"run","props":{"text":"层级","font.ea":"宋体","font.latin":"Times New Roman","size":"10.5pt","bold":"true"}},
  {"command":"set","path":"/body/tbl[1]/tr[1]/tc[1]","props":{"align":"center"}},
  {"command":"add","parent":"/body/tbl[1]/tr[2]/tc[1]/p[1]","type":"run","props":{"text":"香港公司","font.ea":"宋体","font.latin":"Times New Roman","size":"10.5pt"}},
  {"command":"set","path":"/body/tbl[1]/tr[2]/tc[1]","props":{"align":"center"}}
]
```

**关键约束**：
- run 必须挂在 `tc[C]/p[1]` 下，不可直接挂 `tc`（`p[1]` 是 cell 的默认段落）。
- `align` 设在 **cell**（`tc`）而非 run（run 层 align 被忽略）。
- 表头 `bold:"true"` + 居中；数据行按内容定（短标签居中、文字左对齐、数字右对齐）。
- 表格索引独立于段落索引（`/body/tbl[1]` 不影响 `/body/p[N]` 编号）。

## 页脚域字段三步法（PAGE / NUMPAGES）

页脚页码 `1 / X` 的正确构建顺序（先 PAGE 域 → " / " 分隔 → NUMPAGES 域）：

```json
[
  {"command":"add","parent":"/","type":"footer","props":{"align":"center"}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"field","props":{"fieldType":"page"}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"run","props":{"text":" / ","font.ea":"宋体","font.latin":"Times New Roman","size":"9pt"}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"field","props":{"fieldType":"numpages"}}
]
```

**规则**：
- `add --type field` 的 `font.ea` / `font.latin` 会被忽略（报 `UNSUPPORTED props`），必须在 add 后用 `set` 单独给字段结果 run 设字体。
- 字段结构：`fieldChar(begin)` → `instrText(PAGE/NUMPAGES)` → `fieldChar(separate)` → `run(结果)` → `fieldChar(end)`。结果 run 的字体决定页码显示样式。
- 页脚段落本身的 `align` 在 `add footer` 时设置。

## 跨段补丁定位法（双条件防错位）

当需要批量修正某类格式（如补充 `firstLineIndent` 到所有正文段）时，**禁止用正则跨段模糊匹配**（会导致标题段被误改）。正确做法：

```python
import zipfile, re, json

def find_target_paragraphs(docx_path, condition):
    """逐段独立判断，用双条件精确定位"""
    z = zipfile.ZipFile(docx_path)
    xml = z.read("word/document.xml").decode("utf-8")
    blocks = re.split(r'(?=<w:p[ >])', xml)  # 按段落开始标签切分
    targets = []
    for b in blocks:
        m = re.search(r'w14:paraId="([0-9A-F]+)"', b)
        if not m or "<w:pPr>" not in b:
            continue
        pid = m.group(1)
        if condition(b):  # 在段落块内独立判断
            targets.append(pid)
    return targets

# 示例：找"有 firstLineChars 但缺 firstLine"的正文段（需补 firstLineIndent）
need_add = find_target_paragraphs(path, lambda b: 'firstLineChars="200"' in b and 'w:firstLine="482"' not in b)
# 示例：找"有 firstLine 但无 firstLineChars"的标题段（需移除误加的 firstLineIndent）
need_remove = find_target_paragraphs(path, lambda b: 'w:firstLine="482"' in b and 'firstLineChars="200"' not in b)
```

**核心原则**：用"有 A 且无 B"或"有 B 且无 A"的双条件组合，确保每类段落只被一种操作命中，不会交叉污染。

## 新建文档完整流程（执行阶段顺序）

```
① 先用最小测试文档验证 props 语法（1 标题 + 1 正文 + 1 混合加粗段 + 1 表格）
   → officecli create test.docx → batch 3-5 条指令 → view text 确认 → 删除
② 确认语法通过后，Python 脚本生成完整 batch JSON
③ officecli create 目标文件.docx
④ officecli batch 目标文件.docx --input batch.json
⑤ officecli set 页边距 → add footer → 修正域字段字体 → save
⑥ 双引擎交叉核验（见 references/audit_docx.py）→ 交付
```

**首次最小验证门禁（V 阶段第 16 项）**：任何新建文档任务，必须先跑①步最小测试（≤5 条指令），确认 `font.ea`/`size`/`bold`/`firstLineChars`/`lineSpacing` 等核心 props 语法正确后，再生成完整 batch。**禁止跳过最小验证直接生成 100+ 条指令的 batch**——一旦语法错误，原子回滚导致全部失败。

---

## C 轨藏蓝强调色配方（v7.0 新增 · 非诉商务文件强制）

色板：主色藏蓝 `#1A3A5C` / 表头底 `#E8ECF2` / 斑马纹 `#F5F7FA`。面积 ≤20%，正文纯黑，页码/表格边框黑色。

### 藏蓝一级标题（文字色）

```json
[
  {"command":"add","parent":"/body","type":"paragraph","props":{"text":"1. 执行摘要","font.ea":"黑体","font.latin":"Times New Roman","size":"16pt","bold":"true","color":"1A3A5C","align":"both","spaceBefore":14,"spaceAfter":8}}
]
```

### 表格表头底纹 + 藏蓝字（表头唯一默认；斑马纹默认不使用）

```json
[
  {"command":"add","parent":"/body","type":"table","props":{"rows":4,"cols":4,"style":"Table Grid"}},
  {"command":"set","path":"/body/tbl[1]/tr[1]","props":{"shading":"E8ECF2"}},
  {"command":"add","parent":"/body/tbl[1]/tr[1]/tc[1]/p[1]","type":"run","props":{"text":"项目","font.ea":"宋体","font.latin":"Times New Roman","size":"10.5pt","bold":"true","color":"1A3A5C"}}
]
```

> 斑马纹 `#F5F7FA` **默认不使用**，仅客户明确要求时对交替行加 `"shading":"F5F7FA"`。

> ⚠️ `color`/`shading` props 名须最小验证确认（v1.0.143）。

## 书刊式页码（单右双左 + 一字线，v7.0 红圈所标准）

替代旧"底部居中"。核心：启用奇偶页不同页脚（`evenAndOddHeaders`），奇数页页脚右对齐、偶数页页脚左对齐，页码两侧一字线：

```json
[
  {"command":"add","parent":"/","type":"footer","props":{"align":"right","type":"default"}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"run","props":{"text":"— "}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"field","props":{"fieldType":"page"}},
  {"command":"add","parent":"/footer[1]/p[1]","type":"run","props":{"text":" —"}},
  {"command":"add","parent":"/","type":"footer","props":{"align":"left","type":"even"}},
  {"command":"add","parent":"/footer[2]/p[1]","type":"run","props":{"text":"— "}},
  {"command":"add","parent":"/footer[2]/p[1]","type":"field","props":{"fieldType":"page"}},
  {"command":"add","parent":"/footer[2]/p[1]","type":"run","props":{"text":" —"}}
]
```

**规则**：
- 域字段字体须在 add 后用 `set` 单独设置（TNR 10.5pt），`add --type field` 不支持 font props
- 一字线"—"用中文全角一字线（U+2014），与页码间距各一个空格
- 若工具不支持奇偶页脚（even footer），降级方案：全部居中书刊式"— N —"（保持一字线格式，位置退化为居中，可接受但不理想）

## 页边距（v7.0 红圈所标准修正）

```bash
# A 轨法院版：上 3.7 / 下 3.5 / 左 2.8 / 右 2.6cm（右改为 2.6，切口）
officecli set out.docx /section[1] --prop marginTop=3.7cm --prop marginBottom=3.5cm --prop marginLeft=2.8cm --prop marginRight=2.6cm

# B/C 轨及 A 轨客户版：2.2 / 2.2 / 2.4 / 2.4cm
officecli set out.docx /section[1] --prop marginTop=2.2cm --prop marginBottom=2.2cm --prop marginLeft=2.4cm --prop marginRight=2.4cm
```
