# C 盘清理与空间迁移 Skill

为 Codex、WorkBuddy 等支持 `SKILL.md` 的 Windows Agent 提供占用扫描、旧缓存备份清理及目录迁移指导。

## 使用

将此仓库放入 Agent 的 skills 目录，或在对话中指定仓库路径并要求读取 [SKILL.md](SKILL.md)。需要 Python 3.10+；缓存清理脚本需要 PowerShell 7。

```powershell
python -X utf8 scripts/scan_disk.py C: --json E:\cleanup-reports\scan.json
./scripts/safe_cleanup.ps1 -ReportDirectory E:\cleanup-reports\audit-001
```

两条命令都不删除源文件。核对预览清单后，按 SKILL.md 中的 Apply 示例执行备份式清理。

## 脚本

| 脚本 | 行为 |
|---|---|
| `scan_disk.py` | 统计可见文件逻辑长度、最大文件，记录错误并跳过 reparse point；支持 JSON |
| `safe_cleanup.ps1` | 默认预览；仅处理允许目录中至少 7 天的旧缓存，逐文件备份及 SHA256 校验后删除 |
| `admin_diag.py` | 只读查询 VSS、NTFS 和受保护目录；权限失败表示未知 |
| `recycle_purge.py` | 默认仅预览；仅在明确选择执行及重复盘符后清空当前用户指定盘回收站 |

缓存清理使用全新备份目录和经复核的计划 SHA256，生成可核查操作日志。无权限、锁定或发生变化的源文件会保留。文件逻辑长度与实际占用不同，报告单独记录磁盘可用空间的观测变化。

回收站、下载、备份、安装包和应用数据需要单独判断；不会自动删除还原点、关闭保留存储或绕过安全限制。请保留其他盘备份 1–2 周。报告含本机私人路径，不应上传到公共仓库。

## 验证

```powershell
python -m unittest discover -s tests -v
./tests/test_safe_cleanup.ps1
```

## 参考

- [Microsoft：Clear-RecycleBin](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/clear-recyclebin)
- [Microsoft：Reparse Points](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points)
- [Microsoft：NTFS 空间统计差异](https://learn.microsoft.com/en-us/troubleshoot/windows-server/backup-and-storage/disk-space-problems-on-ntfs-volumes)

MIT License。
