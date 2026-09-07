---
name: li-transcript
description: |
  当用户说「获取逐字稿」「转录视频」「提取文稿」「帮我扒一下」「这个视频说了什么」「这个博主说了啥」，或直接给一个视频链接要求提取内容时，应使用本 skill。即使用户只是丢了一个视频链接没说要干嘛，只要上下文涉及对标分析或内容提取，也应主动触发。
  按平台分流调用脚本：小红书（xiaohongshu.com）用 xhs_note.py，其余平台（B站/抖音/YouTube）用 video2text.py（yt-dlp）。AI 校对常见语音识别错误，识别作者后归档到对标博主目录。
  不应触发：分析爆款规律（用 li-analyzer）、记录自己的选题想法（用 li-recorder）、写自己的脚本（用 li-writer）。
  Use when the user wants to "get transcript", "transcribe video", "extract script", or gives a video link for content extraction. Runs speech-to-text, AI proofreads, and archives to benchmark blogger directory.
---

# 视频逐字稿提取 + 对标归档

从视频链接提取逐字稿，AI 校对后归档到对标博主目录。

---

## 运行环境约定

**解释器统一用仓库根 venv**（已装 `tencentcloud-sdk-python-asr`），不在 skill 目录下另建 venv：

- Python：`/Users/xiebingfeng/pythonSpaces/Li-Skills/.venv/bin/python3`
- 补装 SDK：`/Users/xiebingfeng/pythonSpaces/Li-Skills/.venv/bin/pip install tencentcloud-sdk-python-asr`
- 系统依赖（下载/转码，仅首次）：`brew install yt-dlp ffmpeg`

**腾讯云密钥**（控制台 https://console.cloud.tencent.com/cam/capi 申请），键名统一 `TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY`，三个来源按优先级加载（后者覆盖前者）：
① 环境变量 ② `~/.cc-switch/skills/.env` ③ 当前工作目录 `.env`。任选其一，格式均 `TENCENTCLOUD_SECRET_ID=你的_id`（值不带引号）。

**封面 OCR 工具（skill 自带 `scripts/cover_ocr.swift`）**——封面/截图文字的识别**一律优先用它**，不要用 Read 看图，也不要现场新写 OCR 脚本：

- 本环境模型读不了图片（无视觉）；即使个别模型能读图，为保持归档一致也先走此工具
- 首次 / 工具缺失时编译（产出 `/tmp/ocr`；`/tmp` 重启即清，发现缺失就重建）：
  ```bash
  swiftc /Users/xiebingfeng/pythonSpaces/Li-Skills/li-skills/li-transcript/scripts/cover_ocr.swift -o /tmp/ocr
  ```
- 调用：`/tmp/ocr <图片路径>` → 逐行输出识别文字，带 `[y=.. x=..]` 坐标（y 越大越靠上）；图打不开会打印 `无法加载图片`
- 依赖 macOS 系统自带 Vision 框架，无需装包（系统依赖 ffmpeg 仍按上文装）

---

## 工作流程

### Step 1：转录视频

**先按平台分流**（两个脚本都在 skill 的 `scripts/` 目录下）：

- 链接含 `xiaohongshu.com` → **小红书专用脚本 `xhs_note.py`**
- 其他平台（B站/抖音/YouTube）→ **`video2text.py`**（基于 yt-dlp，小红书不可用）

**小红书**：

```bash
/Users/xiebingfeng/pythonSpaces/Li-Skills/.venv/bin/python3 \
  /Users/xiebingfeng/pythonSpaces/Li-Skills/li-skills/li-transcript/scripts/xhs_note.py \
  "<小红书 explore 链接>" [--out 输出目录]
```

脚本会输出：
- stderr：进度信息 + `[标题] xxx` + `[作者] xxx`
- stdout：**单个 JSON**，关键字段：
  - `noteId` / `type`（video 或 normal） / `title` / `desc` / `tags`（话题数组）
  - `author`：`{nickname, userId, profile_url}`——**作者不用再猜，直接取**
  - `interact`：`{liked, collected, commented, shared}`——归档数据块直接填
  - `duration_s` / `cover` / `video` / `audio`：本地文件路径（在 `out_dir` 下）
  - `text`：去时间戳的逐字稿；`text_timed`：带 `[t0,t1]` 时间戳原文

要点：
- 默认输出到临时目录（脚本不清理）；要保留素材（如后续做封面 OCR）可给 `--out 目录`
- 图文笔记（type=normal）不转录，`text` 为空 → 改对 `cover`/图集做 OCR（工具见上文「封面 OCR 工具」）
- 封面下载失败时 `cover: null`，可退而用视频首帧做封面 OCR
- 视频下载优先走 backup 源（稳定、支持续传），失败才兜底 master 源
- 调试可用 `--meta-only` 只看元数据，不下载不转录

**通用（非小红书）**：

```bash
/Users/xiebingfeng/pythonSpaces/Li-Skills/.venv/bin/python3 \
  /Users/xiebingfeng/pythonSpaces/Li-Skills/li-skills/li-transcript/scripts/video2text.py \
  "<视频链接>"
```

- stderr：进度信息 + `[标题] xxx`
- stdout：去除时间戳的纯文本逐字稿

脚本报错时的排查顺序：
1. 密钥是否已配置（键名 `TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY`），来源三选一：环境变量、`~/.cc-switch/skills/.env`、当前工作目录下的 `.env`
2. 仓库根 `.venv` 是否装了 SDK（补装：`/Users/xiebingfeng/pythonSpaces/Li-Skills/.venv/bin/pip install tencentcloud-sdk-python-asr`）
3. 小红书链接报"抓取失败/找不到 __INITIAL_STATE__" → 链接失效、需登录或 xsec_token 过期；其他平台报错 → 链接是否被 yt-dlp 支持

---

### Step 2：AI 校对

对原始逐字稿做文字校对，只改错字不改内容：

- 同音/近音字纠错：根据上下文推断（如「艺人公司」→「一人公司」、「四动会」→「私董会」、「体校」→「提效」）
- 专有名词修正：技术术语、产品名、人名、英文词汇
- 明显的 ASR 乱码：替换为合理推断

保留口语表达（「啊」「嗯」「就是说」），不改写句子结构，不美化风格。

校对直接执行，不逐条列出差异——用户想核对可以自己对比原文。

---

### Step 3：识别作者 & 归档

**识别作者**——按优先级：
1. 用户已告知 → 直接使用
2. 小红书 → 直接用脚本 JSON 的 `author.nickname`
3. 逐字稿中有自我介绍（「大家好我是XXX」「我是XXX」）→ 提取
4. 都没有 → 问用户

**匹配对标**——按笔记类型路由到对应分类目录，读取 `05-选题研究/对标博主/` 下相应分类的目录列表：
- **图文笔记（type=normal，无逐字稿）** → `05-选题研究/对标博主/图文/`
- **视频笔记（type=video）** → `05-选题研究/对标博主/短视频/`
- 匹配到已有博主 → 归档到该博主目录
- 没匹配到 → 问用户「[名字]还不在对标列表里，创建吗？」，同意则在对应分类目录下创建博主目录

作者和是否创建对标可以合并为一次提问，减少来回。

**确定标题**——优先用脚本输出的原标题（video2text 的 stderr `[标题]` 行 / xhs_note 的 JSON `title`），获取不到则从逐字稿内容概括一个。

---

### 新建博主目录时：创建 `00-博主档案.md`

当创建新博主目录时，必须同时创建 `00-博主档案.md`，格式如下：

```markdown
---
博主: [博主名]
平台: 小红书
主页: https://www.xiaohongshu.com/user/profile/[userId]
建档日期: YYYY-MM-DD
状态: 追踪中（X 篇样本，待补充）
---

# [博主名] · 博主档案

## 个人简介

> [从内容署名与行文风格推断的人设描述，附校注说明]

## 人设画像

- **背景**：[背景推断]
- **视角标签**：[2-4 个标签]
- **内容身份**：[内容定位描述]

## 内容赛道

以 **[核心赛道]** 为主轴，细分：

1. **[细分方向 1]**（[说明]）
2. **[细分方向 2]**（[说明]）
3. **[细分方向 3]**（[说明]）

## 内容样本（截至 YYYY-MM-DD 首页 X 条）

| 点赞 | 收藏 | 评论 | 分享 | 收/赞比 | 标题 | 类型 |
|---|---|---|---|---|---|---|
| ♥X | X | X | X | X.X | [标题] | [类型] |

> 校注：[数据说明，如"仅单篇样本，数据为发布 X 天快照"]

## 爆款规律观察

- **[规律 1]**
- **[规律 2]**
- **[规律 3]**

## 赛道判断与可借鉴点

- **[与现有博主对照 1]**
- **[与现有博主对照 2]**

## 归档内容

| 日期 | 标题 | 点赞 | 链接文件 |
|---|---|---|---|
| YYYY-MM-DD | [标题] | X | [YYYY年M月/[标题].md](YYYY 年 M 月/[标题].md) |

## 衍生沉淀

| 文件 | 说明 |
|---|---|
| [0X-内容拆解报告-XXX.md](0X-内容拆解报告 -XXX.md) | [拆解报告说明] |
| [方法论模板.md](../../../../内容素材库/核心概念库/方法论模板.md) | 方法论入库 → [核心概念库](../../../../内容素材库/核心概念库/方法论模板.md) |
```

### 档案填充规则

1. **个人简介**：至少 1-2 行推断 + 校注说明"基于 X 篇样本建立，后续补充"
2. **人设画像**：背景/视角标签/内容身份各 1 行，用 `- **标签**：描述` 格式
3. **内容赛道**：以核心赛道为主轴，细分 3-5 个方向，每个方向用 `（说明）` 标注
4. **内容样本**：最多 5 条，按点赞排序，包含关键互动数据
5. **爆款规律观察**：3-5 条观察，每条以 `**关键词**` 开头，后接说明
6. **赛道判断与可借鉴点**：2-4 条，每条对比一个现有博主（清华鑫哥/思敏/清华姜学长/GevinView/techApple）
7. **归档内容**：含日期/标题/点赞/链接文件四列，链接用相对路径
8. **衍生沉淀**：拆解报告 + 方法论入库（如已入库核心概念库）

### 博主对照矩阵

新建博主时，从以下赛道中选择至少 1 条对照：

| 现有博主 | 赛道 | 口径 | 对照点 |
|---|---|---|---|
| 清华鑫哥 | B 端交付/生意 | 钱的口径 | 是否重叠、互补还是竞争 |
| 思敏 | AIPM 求职/面试 | 职场向 | 受众是否重叠 |
| 清华姜学长 | 工具教程/新工具首测 | 工的口径 | 内容是否互补 |
| GevinView | 方法论教程/AI Coding | 方法口径 | 方法论 vs 实操差异 |
| techApple | 技术观点/架构判断 | 决策口径 | 观点 vs 教程差异 |

---

### Step 4：保存文件

**路径**：`05-选题研究/对标博主/{图文|短视频}/[博主名]/[YYYY年M月]/[视频标题].md`

分类按笔记类型选择：图文笔记（type=normal）归 `图文/`，视频笔记（type=video）归 `短视频/`。时间目录不存在则创建。

**格式**——根据视频来源平台调整 YAML 字段名：

```markdown
---
[平台]数据:
  点赞数: 
  收藏数: 
  评论数: 
  分享数: 
  观看数: 
tags: 
---

# 标题

[视频标题]

# 封面花字



# 视频脚本

[校对后的完整逐字稿]
```

平台判断规则：
- URL 含 `xiaohongshu.com` → `小红书数据`
- URL 含 `bilibili.com` → `B站数据`
- URL 含 `douyin.com` → `抖音数据`
- URL 含 `youtube.com` 或 `youtu.be` → `YouTube数据`
- 其他 → `平台数据`

归档补记：
- 小红书把 JSON `interact` 值填入数据块，并建议在 frontmatter 附一行 `noteId: <JSON 的 noteId>` 便于复核
- 封面花字：小红书封面已由脚本下载到 `out_dir/cover.jpg`，用上文**「封面 OCR 工具」**识别后填入——先跑 `/tmp/ocr cover.jpg` 取文字，**不要用 Read 看图、不要现场新写 OCR 脚本**
- 封面缺失 / OCR 返回空或乱码时：在该节加 **"校注：……"** 标注，**不要臆补**；可先用 `ffmpeg -y -loglevel error -ss 0 -i out_dir/video.mp4 -frames:v 1 out_dir/frame.jpg` 抽视频首帧，再 `/tmp/ocr frame.jpg` 兜底

保存后一句话告知路径。
