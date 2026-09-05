# -*- coding: utf-8 -*-
"""管理员诊断：查清 C 盘 40GB 隐藏占用到底在哪"""
import subprocess, os, sys

out = []
def log(s):
    out.append(str(s))

# 1. 卷影存储
try:
    r = subprocess.run(['vssadmin', 'list', 'shadowstorage'], capture_output=True, timeout=60)
    log('=== vssadmin list shadowstorage ===')
    log(r.stdout.decode('gbk', errors='replace'))
    log(r.stderr.decode('gbk', errors='replace'))
except Exception as e:
    log(f'vssadmin 失败: {e}')

# 2. NTFS 元数据（MFT 大小）
try:
    r = subprocess.run(['fsutil', 'fsinfo', 'ntfsinfo', 'C:'], capture_output=True, timeout=60)
    log('=== fsutil ntfsinfo ===')
    log(r.stdout.decode('gbk', errors='replace'))
except Exception as e:
    log(f'fsutil 失败: {e}')

# 3. System Volume Information 实际大小
def scan(p):
    total = 0; n = 0
    stack = [p]
    while stack:
        cur = stack.pop()
        try:
            entries = os.scandir(cur)
        except Exception:
            continue
        for e in entries:
            try:
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    total += st.st_size; n += 1
            except Exception:
                pass
    return n, total

log('=== System Volume Information ===')
n, s = scan(r'C:\System Volume Information')
log(f'文件 {n} 个, 共 {s/2**30:.2f} GB')

for d in ['C:\\$Recycle.Bin', 'C:\\Config.Msi', 'C:\\Recovery', 'C:\\Windows\\CSC']:
    if os.path.isdir(d):
        n, s = scan(d)
        log(f'{d}: {n} 文件, {s/2**30:.2f} GB')

# 4. 磁盘空间
import shutil
t, u, f = shutil.disk_usage('C:/')
log(f'C 盘: 总 {t/2**30:.1f} GB, 已用 {u/2**30:.2f} GB, 可用 {f/2**30:.2f} GB')

with open(r'E:\C盘迁移\admin_diag.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
