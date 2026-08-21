# OfficeCLI 律师函构建命令模板

> **P0 铁律**：新建 .docx 一律走 OfficeCLI MCP（`mcp__officecli-mcp__officecli`），禁止默认 python-docx，禁止同一文件混用两种引擎。
> MCP 调用方式：单参数 `command`，CLI 命令原文透传；路径用 Windows 绝对形式 `C:/Users/...`（盘符+冒号+前向斜杠）。
> 若 MCP 断开，回退 Bash 直调二进制：`[用户目录]/AppData/Local/OfficeCLI/officecli.exe`。

## 一、构建主链（按顺序执行）

```json
{"command":"create C:/.../[日期]_律师函_致[相对方简称].docx"}
```

```json
{"command":"set C:/.../律师函.docx /section[1] --prop marginTop=2.2cm --prop marginBottom=2.2cm --prop marginLeft=2.4cm --prop marginRight=2.4cm"}
```

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"律 师 函\" --prop font.ea=黑体 --prop font.latin=\"Times New Roman\" --prop size=18pt --prop bold=true --prop align=center"}
```

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"（2026）XX律函字第XX号\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=12pt --prop align=center"}
```

正文段落（一级标题与正文逐段 add；标题黑体加粗、不缩进，正文宋体、首行缩进 2 字符）。**一级标题按上海律协 2026 指引第 12 条三段式**（一、相关事实；二、法律意见；三、律师建议），不要用某科技公司变体标题：

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"一、相关事实\" --prop font.ea=黑体 --prop font.latin=\"Times New Roman\" --prop size=12pt --prop bold=true --prop align=both"}
```

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"[正文段落]\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=12pt --prop align=both --prop firstLineChars=2"}
```

落款块（右对齐）与联络人信息（小一号，左对齐）：

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"XX律师事务所\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=12pt --prop align=right"}
```

```json
{"command":"add C:/.../律师函.docx /body --type paragraph --prop text=\"经办律师：[经办律师]\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=10.5pt --prop align=left"}
```

> **字体写法说明**：`font.latin` 值写 `Times New Roman`（含空格，与门禁 OOXML 核验标准 `w:ascii/hAnsi="Times New Roman"` 一致）；如 CLI 对含空格参数报错，改用 `TimesNewRoman` 并在交付门禁第 4 条 `raw` 核验中确认实际写入值，不一致则用 `set ... --find/--replace` 修正。
> **首行缩进说明**：`firstLineChars=2` 仅用于正文段落；标题、落款、联络人信息、材料清单项不缩进。

全文行距 1.5 倍、刷盘：

```json
{"command":"set C:/.../律师函.docx /body --prop lineSpacing=1.5x"}
{"command":"save C:/.../律师函.docx"}
```

## 二、页眉页脚

| 项 | 内容 | 说明 |
|----|------|------|
| 页眉 | 律所信头 + 日期 + 档案编号，宋体小五 9pt | logo 图片由经办律师在 Word 中手动粘贴（6.5cm×1.4cm 浮动）；文字排版和边框控制由 OfficeCLI 负责 |
| 页码 | ≤2 页不加；>2 页用 `1 / X` 阿拉伯数字格式，底部居中，宋体小五 | 客户确认规则：永远 `1 / X`，不用「第 X 页 共 Y 页」 |

页眉文字构建命令（logo 图片部分仍由经办律师手动粘贴）：

```json
{"command":"add C:/.../律师函.docx /section[1]/header --type paragraph --prop text=\"XX律师事务所\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=9pt --prop align=left"}
{"command":"add C:/.../律师函.docx /section[1]/header --type paragraph --prop text=\"[YYYY]年[M]月[D]日　档案编号：[XX]\" --prop font.ea=宋体 --prop font.latin=\"Times New Roman\" --prop size=9pt --prop align=right"}
```

> 如 CLI 版本不支持 header 路径，降级方案：页眉文字在 Word/WPS 中手动补录，并在交付记录中注明。

## 三、付款节点表格（催款类适用）

```json
{"command":"add C:/.../律师函.docx /body --type table --prop rows=[表头1行+实际期数] --prop cols=3"}
```

> rows 按「1 行表头 + 实际付款期数」计算，禁止照抄示例数字。

表头「付款节点 / 约定金额 / 履行状态」，表头宋体加粗 10.5pt 居中浅灰底；表体宋体 10.5pt；数字右对齐。**表格只放结论性事实，分析性文字移出表格。**

## 四、交付门禁（任一失败 = 不交付）

```json
{"command":"validate C:/.../律师函.docx"}
{"command":"view C:/.../律师函.docx issues --json"}
{"command":"view C:/.../律师函.docx text"}
{"command":"raw C:/.../律师函.docx /document"}
{"command":"save C:/.../律师函.docx"}
```

| # | 检查 | 通过标准 |
|---|------|---------|
| 1 | `validate` | 无错误 |
| 2 | `view issues` | 无 overflow / format / structure 问题 |
| 3 | `view text` | 无残留占位符（`xxxx`、`[方括号]` 未替换项、`{{...}}`、空 `()` / `[]`） |
| 4 | `raw /document` | `w:rFonts`：eastAsia=宋体/黑体；ascii/hAnsi=Times New Roman（逐 run 抽检） |
| 5 | 人工终检 | `save` 刷盘后 WPS/Word 打开，无截断、无乱码、页眉落款正常 |

## 五、定稿限制编辑（客户版零内部痕迹）

定稿才限制编辑（仅黄色高亮可改）：

```json
{"command":"set C:/.../律师函_定稿.docx / --prop protection.type=allowOnlyFormFields --prop protection.enforce=true"}
```

定稿前清除：修订痕迹（`revision.action=accept`）、批注、文档属性中的作者/公司元数据。
