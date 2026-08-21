# 修订模式（Track Changes）操作指南 v7.1

> 本文档包含修订模式的完整操作指南、实测语法、代码示例和禁止事项。SKILL.md §4.1 是唯一权威定义，本文档为执行细则。
> **v7.1（2026-08-20）**：主链切换为 OfficeCLI 原生修订（实测 v1.0.143）；author 统一"律师"；新增格式修订（rPrChange）与拟人化修订纪律。

## 一、工具路径选型（v7.1：OfficeCLI 首选）

| 路径 | 工具 | 适用场景 | 支持能力 | 优先级 |
|------|------|---------|---------|--------|
| **OfficeCLI** | officecli v1.0.143 `set` 修订语法 | 一切修订任务（默认） | **已实测**：ins/del/format（rPrChange）+ revision.author + query 核验 + accept/reject；**官方支持未实测**：moveTo/moveFrom（需用时先最小实测） | **首选** |
| python-docx 原生 | `preserve_format_revisions.py` / `apply_revisions.py` | 无 OfficeCLI 环境；复杂跨 run 修订 | ins/del + run 级格式继承 | 降级备选 |
| docx-editor / docs-comment-mcp | — | **废弃**（v7.1 起不使用） | 格式漂移风险高 | 不推荐 |

**选型决策树**：
```
需要修订（添加/删除/替换/格式调整）？
  │
  ├─ 有 OfficeCLI → OfficeCLI set --find/--replace + revision.author=律师（首选）
  ├─ 无 OfficeCLI 环境 → python-docx apply_revisions.py（降级）
  └─ 其他 MCP 工具 → 一律不用（已废弃）
```

## 二、OfficeCLI 修订操作（首选 · 2026-08-20 实测通过）

**二进制**：`[用户目录]\AppData\Local\OfficeCLI\officecli.exe`（v1.0.143）

### 2.1 文本替换留痕（自动生成 del 旧 + ins 新 一对修订）

```bash
officecli set 文件.docx /body --prop find=旧词 --prop replace=新词 --prop revision.author=律师
```

实测输出：`find=旧词, replace=新词, revision.author=律师 (1 matched)` → query 可见 `revision.type=del`（旧词）+ `revision.type=ins`（新词）两条，author 均为"律师"。

### 2.2 删除留痕（纯删除）

```bash
officecli set 文件.docx /body --prop find=删除词 --prop replace= --prop revision.author=律师
```

`replace=` 空值 → 仅生成 `revision.type=del`。

### 2.3 格式调整留痕（format 修订 → rPrChange）

```bash
# 加粗
officecli set 文件.docx /body --prop find=目标词 --prop bold=true --prop revision.author=律师
# 改颜色
officecli set 文件.docx /body --prop find=目标词 --prop color=FF0000 --prop revision.author=律师
# 段落级（对齐/行距等 → 生成 pPrChange）
officecli set 文件.docx /body/p[N] --prop align=both --prop revision.author=律师
```

实测输出：`revision.type=format`。**run 级格式（字体/加粗/颜色）→ `w:rPrChange`；段落级格式（对齐/行距/缩进）→ `w:pPrChange`**（§三）。

### 2.4 author 核验（V 阶段强制）

```bash
# 查非"律师"author 的修订（有命中 = 失败）
officecli query 文件.docx "revision[@author!='律师']"
# 列出全部修订
officecli query 文件.docx "revision"
```

### 2.5 接受/拒绝修订（须先逐条审查）

```bash
# 接受全部（仅审查通过后）
officecli set 文件.docx /revision --prop revision.action=accept
# 拒绝全部
officecli set 文件.docx /revision --prop revision.action=reject
# 按 author/type 筛选
officecli set 文件.docx "/revision[@author='律师']" --prop revision.action=accept
```

> ⚠️ 接受/拒绝前必须逐条审查（§4.1.6 拟人化纪律 5），禁止无脑 Accept All。

### 2.6 强制留痕锁定（可选，敏感文件）

```bash
officecli set 文件.docx /settings --prop trackRevisions=true
officecli set 文件.docx /settings --prop protection=trackedChanges
```

### 2.7 已知语法要点（实测）

- **本规范统一用 `--prop find=... --prop replace=...` 写法**（实测稳定）；`--find`/`--replace` 顶层参数亦可用（hint 提示，但混用易乱，二选一全程一致）；`revision.author` 必须放 `--prop`
- 禁止在 find 场景加 `revision.type=ins/del`（歧义错误）——替换/删除类型由 `replace` 值自动推断
- `query` 路径语法：`query 文件.docx "revision[@author='律师']"`
- **匹配语义**：`--prop find=` 全局/首个语义以实测为准；多处同名仅需改一处时，先 `query`/`view` 定位段落，再用 `/body/p[N]` 限定路径操作

## 三、格式修订留痕规范（w:rPrChange，v7.1 新增）

**原理**：格式调整同样是"修改"，必须以原生修订呈现。Word 用 `<w:rPrChange>`（run 属性修订）/ `<w:pPrChange>`（段落属性修订），修订前格式快照内嵌。

**OOXML 结构示例**（"斜体改加粗"）：

```xml
<w:rPr>
  <w:b/>                                            <!-- 新格式 -->
  <w:rPrChange w:id="42" w:author="律师" w:date="2026-08-20T08:00:00Z">
    <w:rPr><w:i/></w:rPr>                           <!-- 修订前格式快照 -->
  </w:rPrChange>
</w:rPr>
```

**实现方式**：
1. 首选 OfficeCLI（见 §2.3）——`--prop bold=true` 等格式 props + `revision.author` 自动生成 rPrChange
2. 降级 python-docx：手工构造 `<w:rPrChange>`，四要素齐备（w:id 文档内唯一 / w:author="律师" / w:date ISO 8601 / 修订前完整 rPr 快照）

**禁止**：直接 set 格式不留修订（覆盖式改格式 = 改了不留痕 = 违规，SKILL §7 #26）。

## 四、拟人化修订纪律（v7.1 新增）

1. **最小精确编辑**：只标记实际变化的文本——改 "30 日"→"60 日"，只标记 `30`→`60`，禁止整句/整段塞进修订标记
2. **逐处留痕**：多处修改每处独立标记，不合并，保持每处可单独接受/拒绝
3. **嵌套修订统一口径（v7.1）**：禁止生成嵌套修订（在他人 `<w:ins>` 内再生成新修订会导致 WPS/Word 显示异常、接受/拒绝不可控，且降级脚本不支持）。目标在他人插入内容内时：修订放置于外层 `<w:ins>` 之外（紧邻前后），author 保持"律师"，交付说明标注"修订他人插入内容，请人工复核"
4. **双向验证**：接受全部后内容符合预期 + 拒绝全部后还原原文，任一项失败 = 修订不完整
5. **禁止无脑 Accept All**：接受/拒绝逐条审查后执行

## 五、python-docx 降级路径（无 OfficeCLI 时）

核心模块：`scripts/preserve_format_revisions.py` / `scripts/apply_revisions.py`

**核心原则**：
1. 格式继承精确到 run：删除/插入文本的格式继承其所在位置原 run 的 `<w:rPr>`
2. surrounding runs 保持不动：未修改的文本不会重建，不引入格式漂移
3. 支持跨 run 替换：目标文本跨多个 run 时，按 run 边界分别删除，新文本继承第一个命中 run 的格式
4. 支持表格单元格：遍历文档中所有段落，包括表格单元格内的段落
5. 不嵌套 `<w:ins>`：如果目标已在 `<w:ins>` 内，将新修订放在外层 ins 之前/之后

**标准操作流程**：

```python
from docx import Document
from pathlib import Path
from preserve_format_revisions import apply_revisions_to_doc

src = Path("input.docx")
dst = Path("output_revised.docx")
author = "律师"  # v7.1 统一，禁止个人名

doc = Document(src)
apply_revisions_to_doc(
    doc,
    replacements=[("30 日", "60 日")],
    insertions_after=[("60 日", "（宽限期）")],
    deletions=[("冗余文本",)],
    author=author,
)
doc.save(dst)
```

```bash
python apply_revisions.py input.docx output.docx --author 律师 \
  --replace "旧条款:新条款" \
  --insert-after "新条款:（已修订）" \
  --delete "冗余文本"
```

**限制**：
- `--replace` / `--insert-after` / `--insert-before` 用 `:` 分隔旧/锚点文本和新文本
- 不支持嵌套 `<w:ins>`（已在修订内的目标会跳过，需人工处理）
- 仅支持 `.docx`
- 默认自动备份为 `.backup.docx`；`--no-backup` 违反备份纪律（§七），正式文书禁止使用
- 禁止同一文件 OfficeCLI 与 python-docx 混用

## 六、作者与时间戳（v7.1 收紧）

| 项目 | 规范 |
|------|------|
| 作者名 | **统一 `"律师"`**，不要显示为 `"WorkBuddy"`/`"AI Assistant"`/个人姓名 |
| 时间戳 | 默认当前时间；如需特定时间，用 ISO 8601 格式；禁止硬编码过期时间 |
| initials | 批注场景用 `"WB"` |

## 七、操作前必须备份

**任何修订操作前，必须备份原始文档。** 禁止在原文件上直接生成修订（除非用户明确说"覆盖原文件"）。

备份命名：`原文件_原始备份.docx` 或 `原文件_YYYYMMDD_原始备份.docx`

## 八、修订后验收清单（v7.1 更新）

```
□ 文档能在 Word/WPS 正常打开
□ 修订痕迹在右侧/批注栏可见
□ 插入内容显示为下划线/彩色标记
□ 删除内容显示为删除线/红色
□ 作者名全部为"律师"（officecli query revision[@author!='律师'] 零命中）
□ 修订处字体、字号、加粗、颜色与原文完全一致
□ 未改动的 surrounding 文本格式未发生变化
□ 修订可逐条接受/拒绝
□ 格式调整（如有）以 format 修订呈现（rPrChange），非覆盖式
□ 接受所有修订后，文档内容符合预期
□ 拒绝所有修订后，与修订前备份文件 diff 一致（覆盖式修改的唯一检出手段——存在未留痕修改时，拒绝全部后 diff 即暴露）
□ 无遗漏的未标记修改
□ 无整段标红（最小精确编辑，未改内容不在修订内）
□ 版本清理完成（保留最新3版）
```

## 九、禁止事项（v7.1 更新）

1. **禁止直接修改后加颜色伪装**：颜色高亮不是修订痕迹，不能替代 track changes。
2. **禁止在旧式 `.doc` 或 `.wps` 格式上操作**：先另存为 `.docx`。
3. **禁止无备份就覆盖原文件**。
4. **禁止跨段落连续编辑时不重新定位索引**：段落引用和 MCP 的 paragraph_index 在编辑后可能变化。
5. **禁止把"批注"当"修订"**：批注是评论，修订是修改痕迹，两者功能不同。
6. **禁止在已有 `<w:ins>` 内再次生成新修订**：会导致嵌套修订，WPS/Word 可能显示异常。
7. **禁止使用 WorkBuddy/AI 或个人姓名作为修订作者名**：统一"律师"。
8. **禁止在 OfficeCLI 产物与 python-docx 之间混用同一文件**：格式引擎不同，会导致段落结构/关系项错乱。
9. **禁止格式调整不留修订痕迹**（v7.1）：改字体/加粗/颜色/对齐等必须用 format 修订（rPrChange）。
10. **禁止把未修改的整句/整段塞进修订标记**（v7.1）：最小精确编辑。
11. **禁止未经审查的 Accept All**（v7.1）：接受/拒绝逐条审查后执行。
