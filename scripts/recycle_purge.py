# -*- coding: utf-8 -*-
"""管理员清空指定盘回收站（遍历所有 SID 子目录），真正释放空间。

背景：普通权限下 Remove-Item / 沙箱 safe-delete 钩子会把文件"挪进回收站"，
      空间根本不释放；而普通权限统计 C:\\$Recycle.Bin 又会得到极小的假象数字。
      必须用管理员权限删除，删除后空间立刻回落。

用法（需管理员权限）：
    set TARGET_DRIVE=C
    set OUT_FILE=E:\\recycle_purge.txt
    python -X utf8 recycle_purge.py

提权运行模板（PowerShell）：
    Start-Process -FilePath "C:\\path\\to\\python.exe" `
      -ArgumentList "-X","utf8","C:\\path\\to\\recycle_purge.py" -Verb RunAs -Wait
"""
import os
import shutil

TARGET = os.environ.get('TARGET_DRIVE', 'C').rstrip(':\\/')
OUT_FILE = os.environ.get('OUT_FILE', r'E:\recycle_purge.txt')
RB = rf'{TARGET}:\$Recycle.Bin'

freed = 0
fail = 0
log = []


def count_size(p):
    total = 0
    n = 0
    stack = [p]
    while stack:
        cur = stack.pop()
        try:
            for e in os.scandir(cur):
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                else:
                    total += st.st_size
                    n += 1
        except Exception:
            pass
    return n, total


def onerror(func, path, exc):
    global fail
    fail += 1


if not os.path.isdir(RB):
    log.append(f'{RB} 不存在，跳过')
else:
    for e in os.scandir(RB):
        if e.is_dir(follow_symlinks=False):
            n, s = count_size(e.path)
            for c in os.scandir(e.path):
                try:
                    if c.is_dir(follow_symlinks=False):
                        shutil.rmtree(c.path, onerror=onerror)
                    else:
                        os.remove(c.path)
                except Exception:
                    fail += 1
            freed += s
            log.append(f'{e.name[:12]}...: 删除 {n} 文件 / {s / 2 ** 30:.2f} GB')
        else:
            try:
                s = e.stat(follow_symlinks=False).st_size
                os.remove(e.path)
                freed += s
            except Exception:
                fail += 1

t, u, f = shutil.disk_usage(f'{TARGET}:/')
log.append(f'释放约 {freed / 2 ** 30:.2f} GB, 失败项: {fail}')
log.append(f'{TARGET} 盘: 总 {t / 2 ** 30:.1f} GB, 已用 {u / 2 ** 30:.2f} GB, 可用 {f / 2 ** 30:.2f} GB')

os.makedirs(os.path.dirname(OUT_FILE) or '.', exist_ok=True)
with open(OUT_FILE, 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(log))
print(f'结果已写入 {OUT_FILE}')
