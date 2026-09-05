# -*- coding: utf-8 -*-
"""管理员诊断：查清系统盘隐藏占用到底在哪（VSS / NTFS 元数据 / SVI / 回收站）

用法（需管理员权限，否则回收站和 SVI 会因权限显示假象）：
    set OUT_FILE=E:\\admin_diag.txt
    set TARGET_DRIVE=C
    python -X utf8 admin_diag.py

提权运行模板（PowerShell）：
    Start-Process -FilePath "C:\\path\\to\\python.exe" `
      -ArgumentList "-X","utf8","C:\\path\\to\\admin_diag.py" -Verb RunAs -Wait

结果写到 OUT_FILE 指定的文件（默认 E:\\admin_diag.txt），再回读该文件。
"""
import os
import shutil
import subprocess

TARGET = os.environ.get('TARGET_DRIVE', 'C').rstrip(':\\/')
OUT_FILE = os.environ.get('OUT_FILE', r'E:\admin_diag.txt')

out = []


def log(s):
    out.append(str(s))


def scan(p):
    """返回 (文件数, 总字节数)，遇权限错误静默跳过"""
    total = 0
    n = 0
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
                    total += st.st_size
                    n += 1
            except Exception:
                pass
    return n, total


# 1. 卷影存储（系统还原 / 文件历史占用的空间）
try:
    r = subprocess.run(['vssadmin', 'list', 'shadowstorage'], capture_output=True, timeout=60)
    log('=== vssadmin list shadowstorage ===')
    log(r.stdout.decode('gbk', errors='replace'))
    log(r.stderr.decode('gbk', errors='replace'))
except Exception as e:
    log(f'vssadmin 失败: {e}')

# 2. NTFS 元数据（MFT 大小 / 保留存储）
try:
    r = subprocess.run(['fsutil', 'fsinfo', 'ntfsinfo', f'{TARGET}:'], capture_output=True, timeout=60)
    log(f'=== fsutil ntfsinfo {TARGET}: ===')
    log(r.stdout.decode('gbk', errors='replace'))
except Exception as e:
    log(f'fsutil 失败: {e}')

# 3. 受保护目录实际大小（非管理员权限下这些数字会严重偏小，是"假象"根源）
candidates = [
    rf'{TARGET}:\System Volume Information',
    rf'{TARGET}:\$Recycle.Bin',
    rf'{TARGET}:\Config.Msi',
    rf'{TARGET}:\Recovery',
    rf'{TARGET}:\Windows\CSC',
]
log('=== 受保护目录 ===')
for d in candidates:
    if os.path.isdir(d):
        n, s = scan(d)
        log(f'{d}: {n} 文件, {s / 2 ** 30:.2f} GB')
    else:
        log(f'{d}: 不存在')

# 4. 磁盘空间对账
t, u, f = shutil.disk_usage(f'{TARGET}:/')
log(f'{TARGET} 盘: 总 {t / 2 ** 30:.1f} GB, 已用 {u / 2 ** 30:.2f} GB, 可用 {f / 2 ** 30:.2f} GB')

os.makedirs(os.path.dirname(OUT_FILE) or '.', exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(out))
print(f'结果已写入 {OUT_FILE}')
