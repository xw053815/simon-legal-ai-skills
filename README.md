# Simon's Legal AI Skills

面向法律行业的 AI 技能集合（Skills），沉淀自一位律师的日常 AI 工作台实践。本仓库的五个可执行技能覆盖法律工作的实操链路：**材料全量转录流水线 → 对抗式审查 → 律师函 → 文书排版纪律 → 微信对话读取**。

每个技能均附带详细说明：**输入 / 处理过程 / 输出 / 运行环境**。

## 技能总览

| # | 技能 | 一句话定位 | 输入 → 输出 |
|---|------|-----------|------------|
| 1 | [raw-manuscript-pipeline](skills/raw-manuscript-pipeline/SKILL.md) | 批量材料全量转录流水线（双引擎 OCR 交叉核对） | 批量材料（PDF/图片/邮件/Word/音频）→ 结构化底稿 JSON+MD |
| 2 | [adversarial-review](skills/adversarial-review/SKILL.md) | 对抗式审查方法论（独立入口，多视角红队审查） | 成熟交付物 → 审查报告 + P0-P3 分级修改方案 |
| 3 | [lawyer-letter](skills/lawyer-letter/SKILL.md) | 律师函全流程（起草/核验/排版/发送/留证） | 委托事项 → 可发出的律师函 + 留证材料 |
| 4 | [document-editing-discipline](skills/document-editing-discipline/SKILL.md) | 法律文书排版与编辑纪律（三轨分类 + 修订模式留痕） | 任意 .docx → 符合交付标准的排版文书 |
| 5 | [wechat-chat-reader](skills/wechat-chat-reader/SKILL.md) | 微信对话读取（本机本人账号） | 联系人/群 + 时间段 → 聊天记录文本/文件 |


---




## 1. raw-manuscript-pipeline — 批量材料全量转录流水线（含可运行代码）

### 定位

把任意批量材料（PDF/图片/邮件/Word/音频）全量转写为**结构化、可核验、机器可消费**的底稿。核心能力：双引擎 OCR 交叉核对（PaddleOCR + MinerU）+ 四档裁决 + 多模态兜底 + 防偷懒合约。**本技能附带完整可运行代码（`scripts/`）。**

### 输入

| 输入项 | 说明 |
|--------|------|
| 触发场景 | 诉讼/尽调材料全量转录；批量 PDF/图片/截图转写为结构化底稿 |
| 数据格式 | 任意文件批量（PDF 扫描件/文字型 PDF/图片/邮件 .eml/Word/.docx/音频） |
| 前置条件 | Python 3.8+；OCR 引擎 token（PaddleOCR/MinerU，环境变量注入）；可选 PyMuPDF/python-docx |
| 可选输入 | 交叉核对报告（已有报告时可直接组装，跳过 OCR） |

### 处理过程

```
Phase 0  文件预标准化：路径编码规范化 + 压缩包跳过 + 文件头探测（不信任扩展名）
Phase 1  五路并行：文字型 PDF→PyMuPDF / 扫描件→双引擎批量 OCR / 图片→双引擎或多模态 / 邮件→email 模块 / 音频→转文字
Phase 2  交叉核对四档裁决：≥95% 自动定稿 → 80-95% 定稿+差异标记 → <80% AI 语义终裁 → 双引擎失败多模态兜底
Phase 3  一次性组装：JSON（主，机器消费）+ MD（辅，人眼核校）+ schema.json（契约）+ 防偷懒合约门禁
Phase 4  三方视角验证审查（我方/对方/裁判）+ 审修一体
```

**防偷懒合约（V0.5 确定性门禁）**：JSON 结构完整性 / schema 版本一致性 / 材料全量覆盖（输出条目=输入数量）/ 双引擎交叉核对不可省——四项硬合约，不达标 BLOCK。

### 输出

| 输出项 | 说明 |
|--------|------|
| 底稿 JSON（主） | `[案件简称]_原始底稿.json`——机器消费格式，含 m_id/source_file/pages[blocks{type,bbox,content}]/transcript_fulltext/confidence A-E/engine_source/diff_markup |
| 底稿 MD（辅） | `[案件简称]_原始底稿.md`——人眼核校版，从 JSON 渲染 |
| schema.json | JSON Schema 契约（下游消费字段规范） |
| 降级输出 | JSON 组装失败时自动降级为纯 MD 单输出（保底） |

### 运行环境

| 维度 | 说明 |
|------|------|
| **推荐** | 在支持技能/工具调用与多模态视觉的 AI 工作台（如 **WorkBuddy**）中运行——多模态兜底、AI 语义终裁依赖主模型视觉识别能力；`parallel_main.py` 的 `process_all_files_parallel()` 与 `assemble_manuscript_output()` 形成闭环入口 |
| 最小 | 标准 Python 3.8+ 环境：`assemble_json.py` 零外部依赖可直接运行（组装+Schema 校验+MD 渲染）；完整流水线需配置 OCR 引擎 token（环境变量 `PADDLEOCR_TOKEN`/`MINERU_TOKEN`）并可选安装 `pip install requests pymupdf python-docx` |
| OCR 引擎 | PaddleOCR（https://aistudio.baidu.com/paddleocr）+ MinerU（https://mineru.net）HTTP API；未配置 token 时 `ocr_backend.py` 自动进入 Mock 模式（可演示运行） |
| 接口扩展 | `scripts/ocr_backend.py` 定义 `CrossCheckerV6` 标准接口契约——对接任意 OCR 服务只需实现 `PaddleOCRClient.parse_file()` / `MinerUClient.parse_file()` |

### scripts/ 目录说明

| 文件 | 职责 | 依赖 |
|------|------|------|
| `assemble_json.py` | 底稿 JSON 组装 + Schema 校验 + MD 渲染 + 降级 | 零外部依赖，可直接运行 |
| `parallel_main.py` | 文件级并行调度 + 智能路由 + 双输出闭环入口 | ocr_backend + 可选 PyMuPDF/python-docx/PIL |
| `ocr_backend.py` | OCR 引擎接口契约 + 参考实现 + Mock 模式 | requests（真实调用时） |
| `auto_env_check.py` | 自动检测 OCR API 配置状态 | ocr_backend |
| `test_assemble_json.py` | 组装器功能测试（模拟真实交叉核对报告） | 无（可直接 `python test_assemble_json.py`） |

---

## 2. adversarial-review — 对抗式审查方法论

### 定位

对成熟交付物进行多视角、独立 Agent、高判断力模型的对抗式审查。输出审查报告 + P0-P3 分级修改方案（模式A），或审查+直接优化（模式B）。核心：审查 Agent 与执行者严格分离，每个视角扮演具体角色（对方律师/法官/平台审核员等）"试图推翻核心结论——推不翻才放行"。

### 输入

| 输入项 | 说明 |
|--------|------|
| 触发场景 | 用户提交结构完整、自认为可交付的成熟成果（法律文书/诉讼策略/报告/合同/公众号文章/方案文档），要求对抗式审查/红队审查/多视角审查/压力测试 |
| 前置条件 | 交付物为成熟成果（半成品退回让用户先补完）；复杂度自评 ≥2 分 |
| 触发词 | 对抗式审查、红队审查、多视角审查、三方审查、独立审查、压力测试、red-team |

### 处理过程

```
Step 0  复杂度自评 → 定档（Light 2-3分 / Standard ≥4分 / Brutal 法律定稿）
Step 1  识别交付物类型 + 判定输出模式（A 审查报告 / B 审查+直接优化）
Step 2  选定审查视角 + 定义角色身份（姓名+关注点+攻击方向）
Step 3  草拟审查要点（通用 8 维度 + 视角专属 + 主会话补充）
Step 3.5 构建分派简报（项目背景/审查目的/交付物上下文/角色要点/边界行）
Step 4  spawn 独立高判断力审查 Agent（每个带完整简报）
Step 4.5 验证者环节：独立 Agent 对每条 P0/P1 发现逐条反驳
Step 5  带背景审核 → 汇总去重 → P0-P3 分级 → 聚合判定
模式A: 硬停 → 用户确认 → 执行修改 → P0/P1 复审 → 成品
模式B: P0 熔断检查 → 直接修改 → 复审 → 成品 + 修改说明
```

### 输出

| 输出项 | 说明 |
|--------|------|
| 审查报告 | 交付物信息/审查依据/审查团队/发现汇总（P0-P3 分级）/总体判定 PASS-BLOCK/修改方案/被反驳发现附录/不确定性声明 |
| 修改方案 | 按 P0→P3 排序，每条含问题/修改内容/预期效果/修复成本 |
| 成品（模式B/确认后） | 修改后的交付物 + 修改说明（改了什么、为什么、原文） |

### 运行环境

| 维度 | 说明 |
|------|------|
| **推荐** | 在支持 Sub-Agent 分派与模型分级的 AI 工作台（如 WorkBuddy）中运行——需要独立 spawn 审查 Agent 并指定高判断力模型 |
| 最小 | 任意支持多 Agent 编排的 AI 环境 |
| 外部依赖 | 无硬性安装要求；需要可用的高判断力模型（reasoning 级） |

---

## 3. lawyer-letter — 律师函全流程

### 定位

律师函起草、核验、排版、发送与跟进的全流程技能。以始为终——先明确律师函的定义与法律性质，再按「授权核验→事实核验→正文结构→措辞分寸→排版规范→委托人确认→发送留证→归档跟进」执行。正文结构对齐上海律协 2026 指引三段式（相关事实/法律意见/律师建议）。

### 输入

| 输入项 | 说明 |
|--------|------|
| 触发场景 | 出具律师函（催款催收/侵权警告/解除合同/违约催告/声明澄清等全类型） |
| 前置条件 | 委托事项；法律服务合同/授权委托书（G0 授权核验）；事实材料（G1 事实核验） |
| 触发词 | 律师函、出函、催款函、侵权警告函、解除通知函、催告函、声明函 |

### 处理过程

```
§0 定义与性质（七要素拆解）→ §1 P0 红线（4 条无例外）
§2 发函前双门禁：G0 授权核验 + G1 事实核验（10 项）
§3 类型矩阵（催款/侵权/解除/声明 → 专属结构+措辞+风险点）
§4 措辞分寸十三条（限定语/降险体系/权利保留三件套/禁语清单）
§5 败笔修正表（13 条实战规则）→ §6 正文结构（三段式+委托声明+函件尾部四要素）
§7 排版规范 → §8 定稿确认与出函门禁 → §9 发送与留证 → §10 跟进 → §11 归档
```

### 输出

| 输出项 | 说明 |
|--------|------|
| 律师函成品 | `[日期]_律师函_致[相对方简称].docx`，三段式正文 + 权利保留条款 + 落款 |
| 事实底稿 | 已核对/待核验二分 + 文书同步口径 + 裁判视角核验 |
| 留证材料 | EMS 面单+存根+送达截图+OA 审批截图（时效中断证据链） |

### 运行环境

| 维度 | 说明 |
|------|------|
| **推荐** | 在 AI 工作台（如 WorkBuddy）中运行——流程编排 + 检索核验 + 文档构建一体 |
| 最小 | 任意具备法律检索与文档生成能力的 AI 环境 |
| 外部依赖 | 法律数据库（法条现行有效性核验）；企业信息数据库（相对方存续核验）；Office 文档命令行工具（排版构建） |

---

## 4. document-editing-discipline — 法律文书排版与编辑纪律

### 定位

统一法律文书排版与编辑纪律技能。三轨分类（A 诉讼黑白 / B 非诉严肃 / C 非诉商务藏蓝强调色）+ 修订模式（Track Changes）全类型留痕。凡涉及生成、输出、修订、交付 Word 文档（.docx）触发。

### 输入

| 输入项 | 说明 |
|--------|------|
| 触发场景 | 生成/修改/修订/排版/交付 .docx/.xlsx/.pptx 法律文书 |
| 前置条件 | 文档内容（草稿或待排版文本）；文书类型（决定轨道 A/B/C 与参数包） |
| 触发词 | 排版、字体字号、页边距、修订模式、track changes、交付文档、定稿 |

### 处理过程

```
E 识别文书类型（三轨分类 → 确定参数包）→ P 确定排版方案（字体/页边距/标题层级/编号/页码）
I 执行排版与模板套用（OfficeCLI 批量命令）→ V 独立审校 + 字体验收（5 项交付门禁）
修订模式：只标实际变化的词 / 逐处留痕 / 禁止覆盖式改格式 / 接受拒绝双向验证
```

### 输出

| 输出项 | 说明 |
|--------|------|
| 排版文书 | 符合轨道参数包的 .docx（字体/页边距/编号/页码/页眉/落款全达标） |
| 修订版 | 开启修订留痕的版本（w:ins/del/format 逐处记录，author 统一"律师"） |
| 验收记录 | OOXML 字体验收结果 + 交付门禁核验 |

### 运行环境

| 维度 | 说明 |
|------|------|
| **推荐** | 在接入 Office 文档命令行工具（OfficeCLI）的 AI 工作台（如 WorkBuddy）中运行 |
| 最小 | 任意具备 Office 文档生成能力的 AI 环境 + OfficeCLI 或等价工具 |
| 外部依赖 | OfficeCLI（docx/xlsx/pptx 构建与校验）；参考 `references/排版规格书.md` |

---

## 5. wechat-chat-reader — 微信对话读取

### 定位

按联系人/群名 + 时间段读取**本人微信账号、本机**的聊天记录，供起草邮件、案件证据梳理、内部复盘等下游任务使用。⚠️ 仅限本人账号本机数据；导出内容不得上传第三方；涉密案件内容仅本地分析（合规边界与涉密红线见技能正文）。

### 输入

| 输入项 | 说明 |
|--------|------|
| 触发场景 | 读取/查看/整理微信聊天记录；"读一下我和 XX 的聊天记录""看看 XX 群昨天聊了什么" |
| 前置条件 | 微信 PC 版登录运行中；本机安装技能脚本（wcdb 解密工具 + 查询脚本，参考开源项目 TANGandXue/wcdb-key-tool） |
| 参数 | 联系人/群（昵称/备注/wxid）、时间范围（昨天/最近N天/X月X日）、关键词过滤 |

### 处理过程

```
Step 1 解析用户意图（联系人/时间/关键词参数）
Step 2 数据新鲜度检查（原始库 vs 解密库时间戳比对）
Step 3 刷新解密（微信运行中 → 密钥提取 → 解密 message_0.db）
Step 4 查询对话（--contact + --since/--until + --limit）
Step 5 输出处理（时间戳+发送者+内容 → 下游任务；--format json 供程序化消费）
富媒体：文件保存 / 图片解密导出 / 语音提取（SILK 转码待实现）/ 合并转发递归展开
```

### 输出

| 输出项 | 说明 |
|--------|------|
| 聊天记录文本 | 时间戳+发送者+内容（--format text 供上下文分析 / json 供程序消费） |
| 导出文件 | --save-files 按关键词过滤复制会话文件本体 |
| 解密图片 | --decrypt-images 导出可读 jpg/png |

### 运行环境

| 维度 | 说明 |
|------|------|
| **推荐** | 在 AI 工作台（如 WorkBuddy）中运行——读取结果直接进入模型上下文用于起草邮件/文书/证据梳理 |
| 最小 | 本机 Python 环境 + 微信 PC 版 4.x + 解密工具（脚本随 WorkBuddy 私有仓库分发，本仓库提供方法论与调用约定） |
| 外部依赖 | wcdb-key-tool（开源，MIT）；zstandard 库 |
| ⚠️ 数据安全 | 解密库与密钥缓存为敏感数据，需 ACL 收紧 + 阅后即焚；电脑外借/送修前清空 |

---


---

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/<your-username>/simon-legal-ai-skills.git
cd simon-legal-ai-skills

# 2. 体验原始底稿流水线（零依赖，Mock 模式）
cd skills/raw-manuscript-pipeline/scripts
python test_assemble_json.py        # 组装器功能测试，全部通过
python ocr_backend.py               # 检查 OCR 后端模式（Mock/Real）
python auto_env_check.py            # 环境检查

# 3. 配置真实 OCR 引擎（可选；需自行实现 parse_file() 对接，仓库提供接口契约与 Mock 演示）
export PADDLEOCR_TOKEN="your_token"
export MINERU_TOKEN="your_token"

# 4. 在 AI 工作台中使用
# 将 skills/*/SKILL.md 放入你的技能目录（如 WorkBuddy 的 ~/.workbuddy/skills/），
# AI 助手会在对应场景自动加载。
```

## 在 WorkBuddy 中使用

本仓库技能专为 **WorkBuddy**（AI 法律工作台）设计，安装方式：

1. 将 `skills/` 下各技能目录复制到 `~/.workbuddy/skills/`（用户级）或项目 `.workbuddy/skills/`（项目级）
2. 重启 WorkBuddy 或重载技能列表
3. 在对话中触发对应场景（如"做原始底稿""出一份律师函"），AI 自动加载对应 SKILL.md
4. 原始底稿流水线的 `scripts/` 可独立运行（Python 环境），亦可在 WorkBuddy 中由 AI 编排调用

## 设计理念

五个技能回答同一个问题：**如何让 AI 在法律工作中既快又可靠？**

- **raw-manuscript-pipeline**：怎么转录材料——双引擎交叉核对 + 防偷懒合约，产出结构化机器可消费底稿
- **adversarial-review**：怎么审查交付物——多视角角色化红队审查，推不翻才放行
- **lawyer-letter**：怎么出律师函——全流程铁律 + 双门禁 + 措辞分寸，避免自认/要约/侵权风险
- **document-editing-discipline**：怎么排版——三轨参数包消除判断，修订模式全类型留痕
- **wechat-chat-reader**：怎么读取对话——本机本人数据，合规边界内置

## 目录结构

```
simon-legal-ai-skills/
├── README.md
├── LICENSE              (MIT)
├── CHANGELOG.md
└── skills/
    ├── raw-manuscript-pipeline/
    │   ├── SKILL.md
    │   └── scripts/（assemble_json / parallel_main / ocr_backend / auto_env_check / test）
    ├── adversarial-review/SKILL.md
    ├── lawyer-letter/
    │   ├── SKILL.md
    │   └── references/（措辞库 / 事实底稿模板 / 律协指引要点 / 败笔修正表 / officecli 命令 / templates×5）
    ├── document-editing-discipline/
    │   ├── SKILL.md
    │   ├── references/（排版规格书 / 修订模式指南 / 批量模板 / audit_docx / 字体页脚修复脚本）
    │   └── scripts/（apply_revisions / fill_commission / preserve_format / version_cleaner / test）
    └── wechat-chat-reader/SKILL.md
```

## 许可证

[MIT](LICENSE)

## 免责声明

本仓库内容仅供**学习与参考**，不构成法律意见。使用前请结合具体案件事实核验；涉及诉讼/商业决策请咨询执业律师。
