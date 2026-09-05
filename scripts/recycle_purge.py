# -*- coding: utf-8 -*-
"""管理员清空 C 盘回收站（所有 SID 子目录内容），释放 27.6 GB"""
import os, shutil

rb = r'C:\$Recycle.Bin'
freed = 0
fail = 0

def count_size(p):
    total = 0; n = 0
    stack = [p]
    while stack:
        cur = stack.pop()
        try:
            for e in os.scandir(cur):
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    total += st.st_size; n += 1
        except Exception:
            pass
    return n, total

def onerror(func, path, exc):
    global fail
    fail += 1

log = []
for e in os.scandir(rb):
    if e.is_dir(follow_symlinks=False):
        n, s = count_size(e.path)
        # 删除 SID 子目录内的全部内容（desktop.ini 留不留无所谓，一并删）
        for c in os.scandir(e.path):
            try:
                if c.is_dir(follow_symlinks=False):
                    shutil.rmtree(c.path, onerror=onerror)
                else:
                    os.remove(c.path)
            except Exception:
                fail += 1
        freed += s
        log.append(f'{e.name[:12]}...: 删除 {n} 文件 / {s/2**30:.2f} GB')
    else:
        try:
            s = e.stat(follow_symlinks=False).st_size
            os.remove(e.path)
            freed += s
        except Exception:
            fail += 1

import shutil as _sh
t, u, f = _sh.disk_usage('C:/')
log.append(f'失败项: {fail}')
log.append(f'C 盘: 总 {t/2**30:.1f} GB, 已用 {u/2**30:.2f} GB, 可用 {f/2**30:.2f} GB')

with open(r'E:\C盘迁移\recycle_purge.txt', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(log))
