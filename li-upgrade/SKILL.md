---
name: li-upgrade
description: |
  升级 li-skills 到最新版本。
  触发方式：/li-upgrade、「升级skills」、「更新li-skills」
  Upgrade li-skills to the latest version.
  Trigger: /li-upgrade, "upgrade skills", "update li-skills"
---

# 升级 li-skills

将你的 li-skills 升级到最新版本。

---

## 步骤

### 第一步：确认当前版本

```bash
cat ~/.claude/skills/VERSION 2>/dev/null || echo "VERSION 文件不存在"
```

也可以查看安装路径：
```bash
ls ~/.claude/skills/ | grep ^li-
```

### 第二步：执行升级

**方法一（推荐）：使用 curl 直接安装**

```bash
curl -fsSL https://raw.githubusercontent.com/jiangjiax/li-skills/main/install.sh | bash
```

**方法二：手动 git pull（如果已 clone）**

```bash
cd /path/to/li-skills
git pull origin main
cp -r skills/* ~/.claude/skills/
```

### 第三步：验证版本

```bash
cat ~/.claude/skills/VERSION
```

---

## 注意事项

- 升级会覆盖同名 skill 文件，不会删除其他 skill
- 如有自定义修改，建议先备份对应 SKILL.md
- 升级后重启 Claude Code 会话以加载新版本

---

## 获取帮助

- GitHub: https://github.com/jiangjiax/li-skills
- Issues: https://github.com/jiangjiax/li-skills/issues
