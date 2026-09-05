# -*- coding: utf-8 -*-
"""精确统计某盘的可见文件总占用，逐顶层目录报告。

与普通 du 的关键区别：正确跳过 junction / symlink（reparse point），
否则迁移后建的目录联接会让源盘数字虚高，导致空间对账算错。

用法：
    python -X utf8 scan_disk.py          # 默认扫 C 盘
    python -X utf8 scan_disk.py D:       # 指定盘符
    python -X utf8 scan_disk.py D:\\work # 也可指定某个目录

输出末尾的"可见文件总计"用于空间对账：
    磁盘已用 − 可见文件总量 = 隐藏占用（回收站 / VSS / 保留存储等）
"""
import os
import sys

REPARSE = 0x400

# 普通权限下必然被拒、且统计不准的目录
PROTECTED = {
    '$Recycle.Bin',
    'System Volume Information',
    'Config.Msi',
    'Recovery',
    'Documents and Settings',
}


def scan(p):
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
                    # 跳过 reparse point（junction / symlink）
                    if st.st_file_attributes & REPARSE:
                        continue
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    total += st.st_size
                    n += 1
            except Exception:
                pass
    return n, total


def fmt(s):
    return f"{s / 2 ** 30:.2f} GB"


target = sys.argv[1] if len(sys.argv) > 1 else 'C:'
t = target.rstrip('\\/')
if (len(t) == 1 and t.isalpha()) or (len(t) == 2 and t.endswith(':')):
    root = t.rstrip(':') + ':/'          # 盘符，如 C / C: / C:\ → C:/
else:
    root = t.replace('\\', '/') + '/'    # 普通目录路径

grand = 0
rows = []
for e in sorted(os.scandir(root), key=lambda x: x.name):
    try:
        if e.is_dir(follow_symlinks=False):
            st = e.stat(follow_symlinks=False)
            if st.st_file_attributes & REPARSE:
                print(f"[skip-junction] {e.name}")
                continue
            if e.name in PROTECTED:
                print(f"[skip-protected] {e.name}")
                continue
            n, s = scan(e.path)
            grand += s
            rows.append((s, e.name, n))
        else:
            s = e.stat(follow_symlinks=False).st_size
            grand += s
            if s > 100 * 2 ** 20:
                print(f"文件 {e.name}: {fmt(s)}")
    except Exception as ex:
        print(f"[err] {e.name}: {ex}")

print()
for s, name, n in sorted(rows, reverse=True):
    print(f"{name}: {fmt(s)} ({n} 文件)")
print(f"\n可见文件总计: {fmt(grand)}")
