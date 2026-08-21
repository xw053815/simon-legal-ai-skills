# Changelog

## [1.3.1] - 2026-08-21

### Fixed
- 第三方对抗式审查（隐私+可用性双视角）发现的脱敏遗漏与文档问题全部修复
- README：删除总览表重复块、首段链路描述与 5 技能对齐、触发示例对齐现有技能
- lawyer-letter：附件索引断链修复（2 处文件名同步）
- raw-manuscript-pipeline：README/SKILL.md 中 OCR 引擎配置的措辞与实际实现能力对齐（接口契约+Mock，真实调用需自行实现）
- document-editing-discipline：内部术语泛化、内网路径清理
- wechat-chat-reader：故障排查进程名与主文档统一

## [1.3.0] - 2026-08-21

### Removed
- 删除 `epiv-methodology`（转私有保留，不在公开仓库）
- 删除 `legal-ontology-reasoning-framework`（内部方法论，不对外公开）
- 删除 `legal-research-methodology`（内部方法论，不对外公开）

### Notes
- 公开仓库定位收敛：仅保留可执行类技能（4-8），方法论类技能转私有


## [1.2.0] - 2026-08-20

### Added

- `adversarial-review` v1.0：对抗式审查方法论（多视角角色化红队审查 + Kill Mandate + 验证者反驳闸门 + P0-P3 分级）
- `lawyer-letter` v2.0：律师函全流程（G0/G1 双门禁 + 类型矩阵 + 措辞分寸十三条 + 败笔修正表 + 发送留证），附 references（措辞库/事实底稿模板/律协指引要点）
- `document-editing-discipline` v7.1：法律文书排版与编辑纪律（三轨分类 + 修订模式全类型留痕 + OfficeCLI 集成），附 references（排版规格书）
- `wechat-chat-reader` v1.0：微信对话读取方法论（本机本人账号，含合规边界与涉密红线）

### Changed

- README 升级至 8 技能：每个技能补充输入/处理过程/输出/运行环境四段式
- 全仓库脱敏：客户/项目/联系人/机构/个人路径全部泛化为占位符（某公司/联系人A/[用户目录]等）

### Notes

- wechat-chat-reader 仅含方法论与调用约定；解密脚本与密钥缓存（data/）属敏感数据，不随开源仓库分发
- 律师函 references 仅收录通用部分（措辞库/模板/指引要点）；含客户信息的实战范本不随附

## [1.1.0] - 2026-08-20

### Added

- `raw-manuscript-pipeline` v13.2：批量材料全量转录流水线——双引擎 OCR 交叉核对（PaddleOCR + MinerU）+ 四档裁决 + 多模态兜底 + 防偷懒合约，输出 JSON 主 + MD 辅双格式底稿
- `raw-manuscript-pipeline/scripts/`：完整可运行代码（5 个 Python 文件）
  - `assemble_json.py`：底稿 JSON 组装 + Schema 校验 + MD 渲染 + 降级（零外部依赖）
  - `parallel_main.py`：文件级并行调度 + 智能路由 + 双输出闭环入口
  - `ocr_backend.py`：OCR 引擎接口契约 + 参考实现 + Mock 模式（新增，解决工具层依赖）
  - `auto_env_check.py`：OCR API 配置状态检测
  - `test_assemble_json.py`：组装器功能测试（修复原版 MD 渲染断言 bug）

### Changed

- README 全面升级：每个技能补充**输入 / 处理过程 / 输出 / 运行环境**四段式说明，突出 WorkBuddy 运行环境
- `parallel_main.py` / `auto_env_check.py` / `test_assemble_json.py`：私有路径全部环境变量化/本地化，去除 WorkBuddy 专属硬编码路径
- 原始底稿 SKILL.md：内部版本变更记录压缩为版本表，客户/项目信息全部泛化

### Notes

- 开源版去除：个人/机构/客户信息、私有工具链路径、OCR API token 硬编码（改为环境变量注入）

## [1.0.0] - 2026-08-05

### Added

- `epiv-methodology` v9.2：AI 复杂任务执行方法论（探索→规划→执行→验证 + 对抗式审查 + 反作弊门禁）
- `legal-ontology-reasoning-framework` v2.0：法律 AI 深度推理方法论（四层穿透法：现实→事实→法律→程序）
- `legal-research-methodology` v1.3：法律检索与类案检索系统化方法论

### Notes

- 初始开源版。内容从个人 AI 工作台脱敏迁移，去除个人/机构/客户信息与私有工具链依赖。
