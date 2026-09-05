# -*- coding: utf-8 -*-
"""精确统计 C 盘可见文件总占用（跳过 junction/symlink，逐顶层目录报告）"""
import os, sys, time

REPARSE = 0x400

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
                    # 跳过 reparse point（junction/symlink）
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
    return f"{s/2**30:.2f} GB"

grand = 0
rows = []
for e in sorted(os.scandir('C:/'), key=lambda x: x.name):
    try:
        if e.is_dir(follow_symlinks=False):
            st = e.stat(follow_symlinks=False)
            if st.st_file_attributes & REPARSE:
                print(f"[skip-junction] {e.name}")
                continue
            if e.name in ('$Recycle.Bin', 'System Volume Information', 'Config.Msi', 'Recovery', 'Documents and Settings'):
                print(f"[skip-protected] {e.name}")
                continue
            n, s = scan(e.path)
            grand += s
            rows.append((s, e.name, n))
        else:
            s = e.stat(follow_symlinks=False).st_size
            grand += s
            if s > 100*2**20:
                print(f"文件 {e.name}: {fmt(s)}")
    except Exception as ex:
        print(f"[err] {e.name}: {ex}")

for s, name, n in sorted(rows, reverse=True):
    print(f"{name}: {fmt(s)} ({n} 文件)")
print(f"\n可见文件总计: {fmt(grand)}")
