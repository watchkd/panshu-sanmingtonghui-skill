# -*- coding: utf-8 -*-
"""构建四版《三命通会》数据包（分发用）。

只收运行时真正读取的文件：
  万历/已校（命例·格局·规则·反例·术语）＋技能包/格局库 ＋原文（补脱后逐卷＋卷十二）
  蔣本/已校（同前五类）＋原文（38 块）
  辛丑/包（五库 CSV＋附录C）＋原文（正文合并为单文件）
  四库/五库＋原文/分卷
  索引/（四柱·格名两套索引＋两张归一表）

过程稿、页图、工作目录一律不进。

用法（源目录用环境变量给，不写死本机路径）：
  三命通会_源_万历、三命通会_源_蔣本、三命通会_源_辛丑、三命通会_源_四库
  可选 三命通会_源_索引（默认取本脚本上一级目录）
  python -X utf8 构建数据包.py
产出：data/（解压后的数据目录）＋ dist/panshu-sanmingtonghui-data-v1.0.0.zip
"""
import os, io, sys, csv, glob, json, zipfile, hashlib, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data')
DIST = os.path.join(HERE, 'dist')
VER = '1.0.0'


def _src(env, hint):
    """源目录从环境变量取，不写死任何本机路径。"""
    v = os.environ.get(env)
    if v and os.path.isdir(v):
        return v
    sys.stderr.write('[缺少源目录] 环境变量 %s 未设置或不存在；应指向%s。\n' % (env, hint))
    raise SystemExit(2)


W_SRC = _src('三命通会_源_万历', '万历本蒸馏包（含 已校/技能包/原文）')
J_SRC = _src('三命通会_源_蔣本', '蔣國祥本蒸馏包（含 已校/原文）')
X_SRC = _src('三命通会_源_辛丑', '辛丑本蒸馏包（含 包/正文）')
S_SRC = _src('三命通会_源_四库', '四库本蒸馏包（含 五库/原文）')
IDX_SRC = os.environ.get('三命通会_源_索引') or os.path.dirname(HERE)

LIBS = ('命例', '格局', '规则', '反例', '术语')
report = {'版本': VER, '目录': {}, '表': {}}


def put(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def count_rows(path):
    try:
        with io.open(path, encoding='utf-8-sig') as f:
            return max(0, sum(1 for _ in csv.reader(f)) - 1)
    except Exception:
        return 0


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # ---- 万历 ----
    n = 0
    for p in sorted(glob.glob(os.path.join(W_SRC, '已校', '**', '*.md'), recursive=True)):
        b = os.path.basename(p)
        if not b.startswith(LIBS):
            continue
        rel = os.path.relpath(p, W_SRC)
        put(p, os.path.join(OUT, '万历', rel))
        n += 1
    for p in sorted(glob.glob(os.path.join(W_SRC, '技能包', '格局库_*.md'))):
        put(p, os.path.join(OUT, '万历', '技能包', os.path.basename(p)))
        n += 1
    for p in sorted(glob.glob(os.path.join(W_SRC, '原文', '源文件', '*.txt'))):
        put(p, os.path.join(OUT, '万历', '原文', '源文件', os.path.basename(p)))
        n += 1
    p = os.path.join(W_SRC, '原文', '卷十二单列', '万历本_卷十二_未补脱.txt')
    if os.path.exists(p):
        put(p, os.path.join(OUT, '万历', '原文', '卷十二单列', os.path.basename(p)))
        n += 1
    report['目录']['万历'] = n

    # ---- 蔣本 ----
    n = 0
    for p in sorted(glob.glob(os.path.join(J_SRC, '已校', '*.md'))):
        if not os.path.basename(p).startswith(LIBS):
            continue
        put(p, os.path.join(OUT, '蔣本', '已校', os.path.basename(p)))
        n += 1
    for p in sorted(glob.glob(os.path.join(J_SRC, '原文', '*.txt'))):
        put(p, os.path.join(OUT, '蔣本', '原文', os.path.basename(p)))
        n += 1
    report['目录']['蔣本'] = n

    # ---- 辛丑 ----
    n = 0
    keep = ['附录C_格局异文.csv']
    for lib in ('规则库', '格局库', '命例库', '反例库', '术语库'):
        keep += [os.path.basename(f) for f in glob.glob(os.path.join(X_SRC, '包', lib + '_*.csv'))]
    for b in keep:
        p = os.path.join(X_SRC, '包', b)
        if os.path.exists(p):
            put(p, os.path.join(OUT, '辛丑', '包', b))
            n += 1
            if b.endswith('.csv'):
                report['表'][b] = count_rows(p)
    # 正文合并为单文件（1,984 个分页文件，运行时只按整本用）
    pages = sorted(glob.glob(os.path.join(X_SRC, '正文', 'p*.txt')))
    buf = []
    for p in pages:
        t = io.open(p, encoding='utf-8', errors='ignore').read()
        if t.strip():
            buf.append('【%s】\n%s' % (os.path.basename(p)[:-4], t.strip()))
    dst = os.path.join(OUT, '辛丑', '原文', '辛丑_正文合并.txt')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    io.open(dst, 'w', encoding='utf-8').write('\n\n'.join(buf))
    n += 1
    report['目录']['辛丑'] = n
    report['辛丑正文页数'] = len([p for p in pages if io.open(p, encoding='utf-8', errors='ignore').read().strip()])

    # ---- 四库 ----
    n = 0
    for p in sorted(glob.glob(os.path.join(S_SRC, '五库', '*.md'))):
        put(p, os.path.join(OUT, '四库', '五库', os.path.basename(p)))
        n += 1
    for p in sorted(glob.glob(os.path.join(S_SRC, '原文', '分卷', '*.txt'))):
        put(p, os.path.join(OUT, '四库', '原文', '分卷', os.path.basename(p)))
        n += 1
    report['目录']['四库'] = n

    # ---- 索引 ----
    n = 0
    for pat, sub in (('索引_按四柱_*.csv', '索引'), ('索引_按格名_*.csv', '索引'),
                     (os.path.join('键', '四柱归一表_*.csv'), os.path.join('索引', '键')),
                     (os.path.join('键', '格名归一表_*.csv'), os.path.join('索引', '键'))):
        for p in sorted(glob.glob(os.path.join(IDX_SRC, pat))):
            put(p, os.path.join(OUT, sub, os.path.basename(p)))
            n += 1
            if p.endswith('.csv'):
                report['表'][os.path.basename(p)] = count_rows(p)
    report['目录']['索引'] = n

    # ---- 清单 ----
    files = [f for f in glob.glob(os.path.join(OUT, '**', '*'), recursive=True) if os.path.isfile(f)]
    report['文件数'] = len(files)
    report['原始字节'] = sum(os.path.getsize(f) for f in files)
    tree = {}
    for f in files:
        top = os.path.relpath(f, OUT).split(os.sep)[0]
        tree[top] = tree.get(top, 0) + 1
    report['分目录文件数'] = tree
    io.open(os.path.join(OUT, '数据清单.json'), 'w', encoding='utf-8').write(
        json.dumps(report, ensure_ascii=False, indent=2))

    # ---- 打包 ----
    os.makedirs(DIST, exist_ok=True)
    name = 'panshu-sanmingtonghui-data-v%s.zip' % VER
    zp = os.path.join(DIST, name)
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(files):
            z.write(f, os.path.join('data', os.path.relpath(f, OUT)))
        z.write(os.path.join(OUT, '数据清单.json'), 'data/数据清单.json')
    h = hashlib.sha256(io.open(zp, 'rb').read()).hexdigest()
    report['压缩包'] = name
    report['压缩字节'] = os.path.getsize(zp)
    report['sha256'] = h
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
