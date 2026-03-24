# li-skills

> AI 内容创作者工具箱 — 一套为自媒体创作者设计的 Claude Code skills
>
> AI creator toolkit — A suite of Claude Code skills for content creators

**Version**: 1.0.0 | **License**: CC BY-NC 4.0

---

## 什么是 li-skills？ / What is li-skills?

li-skills 是一套针对 AI 自媒体内容创作的 Claude Code skills，从选题记录到脚本生成、封面配文、开头优化，覆盖创作全流程。

A suite of Claude Code skills covering the full content creation workflow: topic ideation, script writing, cover generation, and opening hook optimization.

---

## 安装 / Installation

```bash
# 克隆到你的 Claude skills 目录
# Clone to your Claude skills directory
git clone https://github.com/jiangjiax/li-skills ~/.claude/skills/li-skills-repo

# 复制 skills 到安装目录
# Copy skills to installation directory
cp -r ~/.claude/skills/li-skills-repo/li* ~/.claude/skills/
```

重启 Claude Code 即可使用所有 `/li-*` 指令。

Restart Claude Code to activate all `/li-*` commands.

---

## Skills 列表 / Skill List

| Skill | 功能 / Function | 触发方式 / Trigger |
|-------|-----------------|-------------------|
| `/li` | 主入口，自动路由 / Main entry, auto-route | `/li` |
| `/li-writer` | 视频脚本 + 长文生成 / Script & article writer | `/li-writer`, 「生成脚本」 |
| `/li-topic` | 选题深化 + 大纲设计 / Topic strategy & outline | `/li-topic`, 「深化选题」 |
| `/li-recorder` | 选题记录 + 模板匹配 / Topic recorder & matcher | `/li-recorder`, 「记录选题」 |
| `/li-opening` | 视频开头钩子优化 / Opening hook optimizer | `/li-opening`, 「优化开头」 |
| `/li-cover` | 小红书封面配文生成 / XHS cover text generator | `/li-cover`, 「生成封面」 |
| `/li-analyzer` | 爆款规律分析 / Viral pattern analyzer | `/li-analyzer`, 「数据复盘」 |
| `/li-workflow` | 创作流程优化 / Workflow optimizer | `/li-workflow`, 「优化流程」 |
| `/li-factory` | Skill 开发工厂 / Skill development factory | `/li-factory`, 「创建skill」 |
| `/li-upgrade` | 升级到最新版本 / Upgrade to latest | `/li-upgrade` |

---

## 标准工作流 / Standard Workflow

```
1. 记录选题灵感     →  /li-recorder
2. 深化选题大纲     →  /li-topic
3. 生成视频脚本     →  /li-writer
4. 优化视频开头     →  /li-opening  ← 必做 / Required
5. 生成封面配文     →  /li-cover    ← 必做 / Required
```

---

## 设计理念 / Design Philosophy

- **实践者视角**：内容由真实使用经验驱动，不是理论堆砌
- **认知劫持理论**：选题和开头基于认知心理学的注意力捕获机制
- **平等对话风格**：「分享」而非「教导」，真实而非表演
- **一鱼多吃**：一个选题覆盖视频脚本、长文、短文多种形式

---

## 升级 / Upgrade

```bash
/li-upgrade
```

---

## 许可证 / License

[CC BY-NC 4.0](LICENSE) — 自由使用和改编，但不可用于商业目的。
Free to use and adapt, but not for commercial purposes.
