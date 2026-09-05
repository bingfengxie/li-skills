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
- 图文笔记（type=normal）不转录，`text` 为空 → 改对 `cover`/图集做 OCR
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

**匹配对标**——读取 `05-选题研究/对标博主/短视频/` 目录列表：
- 匹配到已有博主 → 归档到该目录
- 没匹配到 → 问用户「[名字]还不在对标列表里，创建吗？」，同意则创建目录

作者和是否创建对标可以合并为一次提问，减少来回。

**确定标题**——优先用脚本输出的原标题（video2text 的 stderr `[标题]` 行 / xhs_note 的 JSON `title`），获取不到则从逐字稿内容概括一个。

---

### Step 4：保存文件

**路径**：`05-选题研究/对标博主/短视频/[博主名]/[YYYY年M月]/[视频标题].md`

时间目录不存在则创建。

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
- 封面花字：小红书封面已由脚本下载到 `out_dir/cover.jpg`，先做 OCR 再填入；**识别不全或封面缺失时，在该节加"校注：……"标注，不要臆补**（图源失效时可用视频首帧 OCR 兜底）

保存后一句话告知路径。
