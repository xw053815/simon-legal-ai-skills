---
name: wechat-chat-reader
description: 微信对话读取——按联系人/群名 + 时间段读取本人微信聊天记录，供起草邮件、案件证据梳理、内部复盘等下游任务使用。仅限本人账号本机数据，含合规边界与涉密红线说明。
version: "1.0"
license: MIT
author: Simon Xie
triggers:
  - 用户要求读取/查看/整理微信聊天记录
  - 用户提到"微信对话""聊天记录""昨天的对话""和XX的聊天"等
  - 起草邮件/文书/报告前需要微信上下文
---


# 微信对话读取（wxchat-reader）

> ⚠️ **脚本分发说明**：本仓库只含本技能的方法论文档（SKILL.md）。解密与查询脚本（`wcdb_key_tool_windows.py`/`wxquery.py`/`wxmedia.py`）与密钥缓存（`data/`）属于私有实现与敏感数据，**不随本仓库分发**。解密工具基于开源项目 TANGandXUE/wcdb-key-tool（MIT）。使用本技能前需自行实现或获取等价脚本。
>
> ⚠️ **合规边界（强制）**：本技能只读取**用户本人微信账号、本机**的聊天记录。禁止用于获取他人设备/账号数据。导出内容不得上传第三方，注意隐私保护。

> 🔴 **涉密红线（律师-客户保密义务）**：
> 1. 涉密案件（客户委托、在办案件、敏感谈判）的聊天内容**仅用于本地分析**，整理成果写入本地文件；**不得原样粘贴到云端 AI 对话**（除非已脱敏）。
> 2. 导出文件（`--save-files`）涉及客户材料的，遵循"阅后即焚"——用完即删，或移入案件 `01_input/` 受控目录，不在 02_scratch 长期残留明文。
> 3. 数据目录（data/decrypted + all_keys.json）已 ACL 收紧为仅当前用户可读；电脑外借/送修前需先清空。

## 核心使用闭环（读微信 → 进模型上下文 → 干活）

用户的真实场景：**微信聊天记录是关键工作上下文**，Skill 替代手动截图，直接喂给模型。

| 场景 | 调用方式 |
|------|---------|
| 读对话进上下文分析 | `--contact "X" --since ... --format text` → 直接作为我（AI）的工作输入 |
| 起草邮件/文书需微信依据 | 先读对话 → 提取关键事实（时间/人物/承诺/数据）→ 起草 |
| 保存客户发的文件 | `--contact "X" --save-files <目录> --file-filter 关键词` |
| 长对话替代截图 | 一次性读取全时段（去掉 --limit 限制）→ 模型直接分析 |
| 多选合并转发内容 | 自动递归展开 recorditem 子消息 |

## 触发场景

- "读一下我和 XX 的聊天记录 / 对话"
- "看看 XX 群昨天聊了什么"
- "帮我查 XX 提到 XX 的消息"
- "把 XX 发我的 XX 文件保存下来"
- 起草邮件/文书/总结前的微信上下文收集

## 运行环境

- Python: `python3`（含 zstandard）
- 微信 PC 版（4.1.x）需**登录运行中**（仅解密更新时必需；缓存有效时无需）
- **⚠️ 微信 4.x 主进程名是 `Weixin.exe`（不是 WeChat.exe）**——`tasklist | grep -i Weixin.exe | grep -v WeChatAppEx` 才是正确检测命令；`WeChatAppEx.exe` 是小程序进程不算
- 数据目录：本技能 `data/`（decrypted/ 解密库缓存 + all_keys.json 密钥缓存）

## 调用流程

### 第 1 步：解析用户意图（参数提取）

| 参数 | 说明 | 示例 |
|------|------|------|
| 联系人/群 | 昵称/备注名/wxid，模糊匹配 | "联系人A"、"某公司"、"xxx@chatroom" |
| 时间范围 | 自然语言转 `--since/--until` | "昨天"="今天-1天 00:00 至 今天-1天 23:59"；"最近3天"；"8月1日到8月5日" |
| 关键词 | 可选内容过滤 | --keyword 合同 |

时间范围解析规则：
- "昨天" → since=昨日00:00, until=今日00:00
- "今天" → since=今日00:00
- "最近N天" → since=今日-N天00:00
- "X月X日" / "X月X日到X月X日" → 对应日期

### 第 2 步：数据新鲜度检查（每次调用前）

```bash
# 比较原始库与解密库的时间戳：原始 message_0.db 比解密版新 → 需重新解密
ls -l "<微信数据根目录>/xwechat_files\<你的wxid>\db_storage\message\message_0.db"
ls -l "<技能安装目录>\data\decrypted\message\message_0.db"
```

若原始库更新（mtime 更新）→ 执行第 3 步刷新；否则直接第 4 步。

### 第 3 步：刷新解密（仅在需要时）

```bash
cd <技能安装目录>\scripts
python3 wcdb_key_tool_windows.py extract --decrypt --db-dir "<微信数据根目录>/xwechat_files\<你的wxid>\db_storage" --output ..\data\all_keys.json
```

成功标志：`18/18 salts 找到密钥` + `结果: 18 成功, 0 失败`。
失败排查：微信未运行（先启动微信并登录）；微信版本变化（工具自动适配 Config.Cipher）；杀软拦截（管理员运行）。

> ⚠️ **⚠️ 解密输出路径陷阱（实测 2026-08-20）**：`extract --decrypt` 的解密产物输出到**相对路径 `scripts/decrypted/`**（脚本 cwd），**不是** `data/decrypted/`！wxquery.py 读的是 `data/decrypted/`，两者不一致会导致"解密成功但查不到新消息"。
> **刷新后必须手动同步**：
> ```bash
> cd <技能安装目录>
> cp -f scripts/decrypted/message/message_0.db data/decrypted/message/message_0.db
> cp -f scripts/decrypted/contact/contact.db data/decrypted/contact/contact.db
> ```
> 同步后再查询。另注意：contact 表字段无 `type` 列（username/remark/nick_name/local_type）；message 表时间戳字段是 `create_time`（秒或毫秒，脚本自动探测）。

### 第 4 步：查询对话

```bash
# 按联系人/群 + 时间范围
python3 wxquery.py --contact "联系人A" --since "2026-08-10" --until "2026-08-11" --limit 200

# 只查关键词
... wxquery.py --contact "联系人A" --keyword "关键词" --limit 100

# 列出匹配联系人（名字不确定时先用这个）
... wxquery.py --list-contacts "X"
```

### 第 5 步：输出处理

- 将查询结果（时间戳+发送者+内容）提供给下游任务（起草邮件/文书、证据梳理、摘要总结）
- 若输出乱码：确保 stdout 使用 UTF-8（脚本已内置）
- `--format json` 输出结构化数组 `{"contact","is_group","total","truncated","messages":[{"time","sender","type","kind","content","path"?,"items"?}]}`，供程序化消费（起草邮件等场景推荐）

## 富媒体能力（v1.3）

| 类型 | 支持 | 说明 |
|------|------|------|
| 文本 | ✅ | 完整读取 |
| 文件 | ✅ | 解析文件名+大小+**自动定位真实路径**（msg/file/YYYY-MM/原名），`--save-files` 可复制到指定目录 |
| **图片** | ✅ **可解密导出** | `--decrypt-images <目录>` 一键解密该会话全部图片（V2 AES-128+XOR / V1 固定key / 旧XOR 三格式自动识别），PIL 验证可打开 |
| 语音 | ✅（可提取） | 本体在 media_0.db 的 VoiceInfo.voice_data（SILK_V3 格式），需转码 wav/mp3 才能播放/转文字（转码列为改进项） |
| 视频 | ✅（标签） | 显示类型标签；本体未解码 |
| 引用回复 | ✅ | 显示回复内容 + 被引用原文 |
| **合并转发（多选）** | ✅ | 递归展开 recorditem，列出每条消息的发送者+内容 |
| 链接/小程序/视频号 | ✅ | 标题+摘要+URL |
| 系统消息 | ✅ | 撤回/入群/拉人等 |

**保存文件**：`--save-files <目录> [--file-filter 关键词]` — 按文件名模糊匹配，复制会话相关文件本体到指定目录。

**解密图片**：`--decrypt-images <目录>` — 解密该会话全部图片 .dat 为可读 jpg/png（缩略图优先）。实测 10/10 成功、PIL 完整打开。

### 图片解密前置（一次性，已缓存）

图片 AES key 只在点开图片时加载到微信进程内存。**首次使用或 key 过期时**：
1. 微信保持登录运行，点开任意聊天 **2-3 张图片看大图**
2. 立即运行监控提取：`python 02_scratch/tools/wechat-decrypt/find_image_key_monitor.py`（每5秒扫内存，命中即存 `config.json` 的 `image_aes_key`）
3. 把 key 写入 Skill：`data/image_key.json` → `{"image_aes_key": "...", "image_xor_key": 93}`（93=0x5d）

已缓存的 key 存于 `data/image_key.json`，无需重复提取（除非微信版本升级后失效）。

## 硬编码配置（换账号/换电脑必须更新）

| 配置 | 位置 | 说明 |
|------|------|------|
| `SELF_USERNAME` | wxquery.py | 本人 wxid（账号目录名去后缀），变更后"我"的识别失效（脚本会自动警告） |
| `DECRYPTED_DIR` | wxquery.py | 解密缓存路径（data/decrypted/） |
| `WXDATA_ROOT` | wxmedia.py | 微信数据根目录 `<微信数据根目录>/xwechat_files\<wxid>`，文件/图片定位依赖 |
| 数据库路径 | SKILL.md 第 3 步命令 | `<微信数据根目录>/xwechat_files\<wxid>\db_storage`，换账号需改 |

**换账号场景**：更新上述配置 → 删除 data/decrypted 与 all_keys.json → 重新执行第 3 步解密。

## 实测记录（2026-08-11 验证通过）

| 用例 | 命令 | 结果 |
|------|------|------|
| 单聊+时间范围 | `--contact "联系人A" --since 2026-08-10 --until 2026-08-11` | 16 条，发送者正确（我/联系人A） |
| 群聊 | `--contact "某公司群" --limit 20` | 108 条全量，成员识别正常 |
| 关键词 | `--contact "联系人A" --keyword "关键词"` | 4 条命中 |
| 富媒体（v1.2） | `--contact "某公司群"` | 文件自动定位真实路径、系统消息、群聊发送者剥离正常 |
| 保存文件（v1.2） | `--save-files <目录> --file-filter 示例关键词` | 导出告知函 PDF + 统计表 xlsx |
| 结构化 JSON | `--format json` | 含 kind/path/items 字段 |
| 解密图片（v1.3） | `--decrypt-images <目录>` | 10/10 成功，PIL 完整打开（RGB 正常） |
| 联系人搜索 | `--list-contacts "X"` | N 个匹配（含某公司群/联系人A） |
| 富媒体 | 文件/表情/引用消息 | ZSTD 解压为 XML，标题可读 |

已知限制：
- 仅覆盖 message_0.db / biz_message_0.db（微信消息主库）；若目标会话在其他 message_N.db 需扩展 MESSAGE_DBS
- 图片仅解密缩略图（_t.dat）；原图/高清图（_h/无后缀）为更大 .dat 同样可解，可按需扩展
- 语音可提取（SILK_V3 BLOB）但转码未实现；视频本体未解码
- 消息显示内容截断 800 字符/条
- 图片 AES key 随微信版本升级可能失效（需重新走前置流程提取）

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `0/18 salts` | 微信 4.1+ 密钥机制（passphrase+PBKDF2）| 本工具已适配（Config.Cipher 只读扫描），**确认微信主进程（Weixin.exe，4.1+；旧版为 WeChat.exe）正在运行且已登录**——只有 WeChatAppEx.exe 不够 |
| `找不到联系人` | 名称不匹配 | 先 `--list-contacts 关键词` 搜索，或用 wxid |
| 按群名搜不到（截图明确给出群名但报错） | `load_contacts` 只读 `contact` 表的 `nick_name`/`remark`（个人字段），群名不在字典里——**`--list-contacts` 本质上对群名无效**，除非群主/某成员的昵称碰巧包含该群名片段 | 见下方「**群名搜索的诊断路径**」 |
| 无消息 | 该会话在 message_0 无记录 | 可能在其他 message_N.db 或时间范围外 |
| 解密库过期 | 微信写入新消息 | 执行第 3 步刷新 |
| 跑了解密脚本但查不到今天的群消息 | 微信主进程未运行 → 读不到内存密钥 → 解密库停留在旧时间 | **先 tasklist 确认 Weixin.exe 在运行**（`tasklist \| grep -i Weixin.exe \| grep -v WeChatAppEx`），再重跑解密 |
| 图片解密全失败 | 图片 AES key 未提取/已过期 | 走「图片解密前置」重新提取（点开图片+监控提取） |
| 杀软拦截 | 读取进程内存 | 管理员身份运行 + 加白名单 |

### 群名搜索的诊断路径（按群 wxid 或截图给的群名兜底）

用户给截图或群 wxid 时，**不要绕路去 SQL 反查**。直接按以下顺序：

1. **确认微信主进程 Weixin.exe 在运行**（`tasklist \| grep -i Weixin.exe \| grep -v WeChatAppEx`，空结果=主进程未运行，解密库过期）
2. 跑第 3 步刷新解密（输出 `18 成功, 0 失败`）
4. **先用 `--list-contacts 关键词` 试一次**——命中即用 `--contact` 查询
5. **若不命中（90% 新建群）**：从群主 wxid 在 `chat_room` 表反查群 ID（`SELECT username FROM chat_room WHERE owner = '<群主wxid>'`），或从 `SessionTable` 按 `sort_timestamp DESC` 找最近活跃的 chatroom，或从 `message_0.db` 遍历 `Msg_*` 表的 `MAX(create_time)` 找近 24h 有消息的会话
6. 用找到的 `<数字>@chatroom` 直接 `--contact "<数字>@chatroom"` 查询
7. **不要**一开始就 SQL 直查——那是绕路

## 安全与维护

- all_keys.json 与 decrypted/ 为**敏感数据**（明文聊天），权限保护，勿外传
- 密钥随微信登录变化：微信重启后如需刷新解密，重新走第 3 步
- 工具源码来自开源项目（TANGandXUE/wcdb-key-tool，MIT），已安全审查（只读无注入）
