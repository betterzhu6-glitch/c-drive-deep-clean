---
name: c-drive-deep-clean
description: 扫描 Windows C 盘占用，备份并清理当前用户的旧缓存，核实实际空间变化；也支持经用户指定的目录迁移和存储诊断。适用于系统盘空间不足，不用于随意删除应用数据或绕过安全限制。
---

# Windows C 盘清理与空间迁移

优先用只读扫描找出实际占用，再按本次会话中用户授权的范围执行。所有报告和备份写入其他盘；扫描清单可能包含私人路径，不提交到公开仓库。

## 扫描与分类

```powershell
python -X utf8 scripts/scan_disk.py C: --json E:\cleanup-reports\scan.json
```

脚本跳过路径上及目录中的 reparse point（junction、symlink、云占位符等），记录不可访问项。可指定目录缩小扫描范围。没有权限的目录表示未知，不能当作空目录；不要反复扫描同一批大目录。

输出为文件逻辑长度，不是物理分配空间。硬链接、压缩、稀疏文件、访问失败及排除目录都会影响对账，不能用“已用空间减可见文件大小”准确推断隐藏占用。

- **旧缓存候选**：当前用户 Temp、CrashDumps、D3DSCache、npm 的 `_cacache`、pip 的 `cache`。先预览；默认仅考虑创建和修改时间均早于 7 天的文件，跳过锁定或发生变化的文件。
- **需要单独判断**：回收站、安装包、驱动包、Downloads、聊天记录、浏览器会话和站点存储、应用数据库、模型、备份及用户项目。不能统称为“零风险垃圾”。
- **系统管理范围**：Windows\Installer、WinSxS、DriverStore、恢复分区、pagefile、hiberfil 等不能手动删除。需要系统维护时使用 Windows 官方功能并明确说明影响。

## 备份后清理旧缓存

使用 PowerShell 7 和 `scripts/safe_cleanup.ps1`。它的默认模式只生成报告，不删文件：

```powershell
./scripts/safe_cleanup.ps1 -ReportDirectory E:\cleanup-reports\audit-001
```

检查 `plan.csv`、类别合计及 `audit-issues.json`，向用户说明范围和预计大小。若已有明确的清理授权，可以继续执行该范围内的备份式缓存清理；用户仅要求诊断时不能执行删除。超出授权范围或不可逆操作，须在展示具体清单后取得明确授权。

```powershell
./scripts/safe_cleanup.ps1 -Mode Apply `
  -PlanPath E:\cleanup-reports\audit-001\plan.csv `
  -ReviewedPlanSha256 <预览输出的SHA256> `
  -ReportDirectory E:\cleanup-reports\apply-001 `
  -BackupDirectory E:\cleanup-backups\run-001
```

脚本固定限制在当前用户的上述缓存目录，校验完整计划及路径，拒绝联接路径、重复项、近期文件和复用备份目录。逐文件复制到其他盘，核对长度及 SHA256，再复查源文件未变化，只删除单个文件，保留目录。清理正在写入的应用前应先正常退出；不能强杀用户程序。元数据及哈希复查不能完全消除并发替换竞态，不应将此工具用于不受信任的共享目录。

`operations.jsonl` 记录已校验备份、源文件不存在及失败项。锁定、无权限或变化的文件保留，并使退出码为 2（部分完成）；未通过备份校验不删源。不要把计划大小、已备份大小或命令退出 0 当成实际释放量。

恢复时按日志将 E 盘副本复制回原路径；先退出所属应用，只恢复原路径仍不存在的文件，冲突时保留两份，不覆盖新文件。隔离备份至少保留 1–2 周，未经另行授权不自动删除。

## 迁移大目录

仅在用户指定源目录、目标位置和可接受停机范围后执行。应用优先使用自带迁移设置。确需 junction 时：退出应用；用 robocopy `/E /XJ /COPY:DAT /DCOPY:DAT /R:1 /W:1` 复制到全新目标；退出码 >=8 为失败。逐相对路径核对文件集、长度及 SHA256，不能使用总字节数容差作为完整性证明。目录含 reparse point、ADS 或应用特殊存储时应单独评估，不能假设普通复制覆盖全部语义。

先保留源目录并改名用于回滚，再建立原路径 junction，验证目标及应用可用。保留源副本期间不会释放对应空间，报告中如实说明；验证完成且已获授权后才移除源副本。不要对运行中的数据库、同步目录或包含虚拟环境的项目直接套用迁移。

## 存储诊断和回收站

```powershell
python -X utf8 scripts/admin_diag.py --drive C --output E:\cleanup-reports\diag.json
python -X utf8 scripts/recycle_purge.py --drive C
```

诊断脚本只读；返回权限错误时通过正常授权渠道请求所需权限，不能切换解释器、改用另一 shell 或提权脚本来绕过沙箱拦截。

回收站脚本默认仅预览。清空前说明无法撤销并取得该盘的明确授权；授权后才添加 `--apply --confirm-drive C --output <全新报告文件>`。它调用 Windows `Clear-RecycleBin`，限当前用户指定盘，不直接删除全部 SID 的回收站目录。

普通清理不删除 VSS/系统还原点，不缩减其配额，不关闭保留存储、休眠或分页文件。这些操作影响系统恢复或运行能力，需要单独诊断和明确授权。

## 收尾

报告列出：扫描范围与盲区、计划及成功移除的逻辑字节数、失败项、清理前后 C 盘实际可用字节数、期间观测到的差值、备份位置及恢复方法。磁盘同时可能有写入，差值只能称为观测变化，不能保证全部由本次清理造成。
