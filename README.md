# C盘深度清理与空间迁移 Skill (c-drive-deep-clean)

一个为 [WorkBuddy](https://www.workbuddy.cn) / Claude Code 类 Agent 设计的 **Windows C 盘深度清理 Skill**。

实战验证：2026-09-05 单日将一块 156 GB 的 C 盘从**可用 0.03 GB** 清理到**可用 36.43 GB**（释放约 36 GB），全程零数据丢失。

## ✨ 能力

| 阶段 | 内容 |
|------|------|
| 扫描盘点 | 各盘总览、顶层目录占用（正确跳过 junction/无权限目录）、大文件排行 |
| 分类清单 | A 类（可直接删的垃圾）/ B 类（可迁移的大文件）/ C 类（不能手动动的系统目录） |
| 备份删除 | robocopy 先备份到其他盘，文件数 + 字节数双校验一致后才删源 |
| Junction 迁移 | iPhone 备份、Lumion 素材库等迁到其他盘后建目录联接，iTunes / Lumion 照常使用 |
| 隐藏空间回收 | 排查「删了文件空间没涨」的元凶（VSS 卷影副本 / 回收站 / 保留存储），提权回收 |
| 空间对账 | 可见文件字节数 vs 磁盘已用字节数，精确定位隐藏占用 |

## 🧰 核心脚本

- `scripts/scan_disk.py` — 精确全盘扫描，跳过 reparse point，输出可见文件账目
- `scripts/admin_diag.py` — 管理员诊断：VSS 卷影占用、回收站真实大小、保留存储
- `scripts/recycle_purge.py` — 提权清空指定盘回收站（绕过普通权限的"空回收站"假象）

## 📦 安装（WorkBuddy）

```bash
git clone https://github.com/<你的用户名>/c-drive-deep-clean.git \
  ~/.workbuddy/skills/c-drive-deep-clean
```

克隆到 `~/.workbuddy/skills/` 后即可在任意对话中用自然语言唤起，例如：

> "C 盘满了，按流程清理"
> "帮我把 iPhone 备份迁到 E 盘，iTunes 还要能用"

## ⚠️ 安全设计

1. **先扫描出清单，等用户确认，再动手** —— 所有删除操作前必须列出完整清单
2. **先备份后删除** —— 备份到其他盘隔离区，逐文件校验一致才删源
3. **删除后必查实际状态** —— 不信任退出码（详见 SKILL.md 的沙箱陷阱表）
4. 专设「沙箱陷阱表」：记录 Python 删除被钩子拦截、bash rm 静默失败、Remove-Item 实际走回收站等实测坑

详细流程与陷阱表见 [SKILL.md](SKILL.md)。

## License

MIT
