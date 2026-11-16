# -*- coding: utf-8 -*-
"""四版并置器·抽取层：把四个只读包解析成统一条目流。
不改动任何原包文件；仅读。
"""
import io, os, re, sys, json, glob, csv

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ZIP = 'panshu-sanmingtonghui-data-v1.0.0.zip'
DATA_URL = ('https://github.com/watchkd/panshu-sanmingtonghui-skill/releases/download/'
            'data-v1.0.0/' + DATA_ZIP)

# 取数顺序：技能目录下 data/ → 环境变量指定 → 报错退出
REQUIRED = [('万历', '已校'), ('万历', '技能包'), ('蔣本', '已校'),
            ('辛丑', '包'), ('四库', '五库'), ('索引', )]


def _fail(msg):
    sys.stderr.write(
        '\n[数据包缺失] %s\n\n'
        '这个技能不含四版原文数据，需要单独下载数据包：\n'
        '  1) 下载 %s\n'
        '  2) 解压到技能目录，使路径成为 %s\n'
        '  3) 若放在别处，设环境变量 三命通会_数据 指向该目录\n'
        '  下载地址：%s\n'
        '  校验：sha256 059f390ae099e8d25c67d770f5b48fece966bf3f003fc1048f16ab1053d6848d\n'
        % (msg, DATA_ZIP, os.path.join(HERE, 'data'), DATA_URL))
    raise SystemExit(2)


def _check(root):
    miss = []
    for parts in REQUIRED:
        p = os.path.join(root, *parts)
        if not os.path.exists(p):
            miss.append('/'.join(parts))
    if miss:
        _fail('目录 %s 下缺少：%s' % (root, '、'.join(miss)))
    return root


def data_root():
    cands = []
    env = os.environ.get('三命通会_数据') or os.environ.get('SANMING_DATA')
    if env:
        cands.append(env)
    cands.append(os.path.join(HERE, 'data'))
    cands.append(os.path.join(os.path.dirname(HERE), 'data'))
    for c in cands:
        if c and os.path.isdir(c):
            return _check(os.path.abspath(c))
    _fail('未找到数据目录（已试：%s）' % '、'.join(cands))


DATA_ROOT = data_root()
W_ROOT = os.path.join(DATA_ROOT, '万历')
J_ROOT = os.path.join(DATA_ROOT, '蔣本')
X_ROOT = os.path.join(DATA_ROOT, '辛丑', '包')
S_ROOT = os.path.join(DATA_ROOT, '四库')

GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'
AMB = '己已巳'
ZHI_ALIAS = {'𫑗': '卯', '夘': '卯', '丣': '酉', '戍': '戌', '末': '未',
             '𡩟': '寅', '丒': '丑', '㐪': '亥', '㠯': '巳'}
GAN_ALIAS = {'己': '己', '已': '己', '巳': '己'}
SEPCH = ' \u3000、・·，,；;／/。〈〉「」（）()'
SUFFIX = '年月日時时'


def is_gan(c):
    return c in GAN or c in AMB


def is_zhi(c):
    return c in ZHI or c in AMB


def canon_pair(a, b):
    g = '己' if a in AMB else a
    z = '巳' if b in AMB else ZHI_ALIAS.get(b, b)
    if z in ('己', '已'):
        z = '巳'
    g = GAN_ALIAS.get(g, g)
    return g + z


def _skip_sep(s, i):
    n = len(s)
    c = 0
    while i < n and s[i] in SEPCH and c < 3:
        i += 1
        c += 1
    return i


def _pair_at(s, i):
    if i + 1 >= len(s):
        return None
    a, b = s[i], s[i + 1]
    if not (is_gan(a) and is_zhi(b)):
        return None
    return canon_pair(a, b), i + 2


def scan_pillars(s):
    """返回 [(start, end, [柱...])]，柱为规范写法。"""
    out = []
    i, n = 0, len(s)
    while i < n:
        p = _pair_at(s, i)
        if not p:
            i += 1
            continue
        start = i
        cur = [p[0]]
        j = p[1]
        while len(cur) < 8:
            k = _skip_sep(s, j)
            if k < n and s[k] in SUFFIX:
                k = _skip_sep(s, k + 1)
            np = _pair_at(s, k)
            if not np:
                break
            cur.append(np[0])
            j = np[1]
        out.append((start, j, cur))
        i = j
    return out


def first_sizhu(text):
    """从任意文本取第一组四柱；返回 (key, 原文串, 备注) 或 None。"""
    if not text:
        return None
    for a, b, ps in scan_pillars(text):
        if len(ps) >= 4:
            raw = text[a:b]
            note = ''
            if len(ps) > 4:
                note = '多柱%d（取前四）' % len(ps)
            return ' '.join(ps[:4]), raw, note
    return None


def read_lines(path):
    with io.open(path, encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


FIELD_RE = re.compile(r'^\s*[-*]?\s*(?:\*\*)?([^：:*｜|]{1,14})(?:\*\*)?\s*[：:]\s*(.*)$')
PILLAR_RE = re.compile(r'(年柱|月柱|日柱|时柱|時柱)\s*[：:]\s*([甲乙丙丁戊己庚辛壬癸己已巳][子丑寅卯辰巳午未申酉戌亥已巳])')


def pillars_from_text(t):
    got = {}
    for m in PILLAR_RE.finditer(t or ''):
        k = m.group(1).replace('時', '时')
        got.setdefault(k, m.group(2))
    order = ['年柱', '月柱', '日柱', '时柱']
    if all(k in got for k in order):
        vals = [got[k] for k in order]
        if all(v and _pair_at(v, 0) and _pair_at(v, 0)[1] == len(v) for v in vals):
            return '／'.join(vals)
    return ''


def section_map(lines):
    """把 ### 小节名 → 首段正文。"""
    d = {}
    cur = None
    buf = []
    for ln in lines:
        m = re.match(r'^###\s+(.+?)\s*$', ln)
        if m:
            if cur and cur not in d:
                d[cur] = '\n'.join(buf).strip()
            cur = m.group(1)
            buf = []
        elif cur is not None:
            buf.append(ln)
    if cur and cur not in d:
        d[cur] = '\n'.join(buf).strip()
    return d
HEAD_ID = re.compile(r'^#{2,3}\s+([RGFMT]\d+(?:-\d+)?|C\d+-\d+|E\d+|格局-[^-\s]+-\d+|命例-\S+)\b')


def parse_fields(lines):
    d = {}
    for ln in lines:
        m = FIELD_RE.match(ln)
        if m:
            k = m.group(1).strip().strip('*')
            v = m.group(2).strip()
            if k and k not in d and len(k) <= 14:
                d[k] = v
    return d


def split_blocks(lines, id_re):
    """按标题切块；返回 [(id, 标题余文, body_lines)]"""
    out = []
    cur = None
    for ln in lines:
        m = id_re.match(ln)
        if m:
            if cur:
                out.append(cur)
            rest = m.group(2).strip() if (m.lastindex or 0) >= 2 else ''
            cur = [m.group(1), rest, []]
        elif cur is not None:
            cur[2].append(ln)
    if cur:
        out.append(cur)
    return out


# ---------------- 万历 ----------------
W_SKIP = ('验证记录', '冲突清单', '去重记录', '表结构核验', '源标注', '统计', '交付说明', '章节覆盖')


def wanli_records():
    recs = []
    for path in sorted(glob.glob(os.path.join(W_ROOT, '已校', '**', '*.md'), recursive=True)):
        base = os.path.basename(path)
        if any(base.startswith(k) or k in base for k in W_SKIP):
            continue
        rel = os.path.relpath(path, W_ROOT).replace('\\', '/')
        lib = None
        for k in ('命例', '格局', '规则', '反例', '术语'):
            if base.startswith(k):
                lib = k
                break
        if not lib:
            continue
        lines = read_lines(path)
        # 表格体
        hdr = None
        for i, ln in enumerate(lines):
            if ln.startswith('|') and '编号' in ln and '---' not in ln:
                hdr = i
                break
        if hdr is not None:
            cols = [c.strip() for c in lines[hdr].strip().strip('|').split('|')]
            for ln in lines[hdr + 1:]:
                if not ln.startswith('|') or set(ln.replace('|', '').strip()) <= set('-: '):
                    continue
                cells = [c.strip() for c in ln.strip().strip('|').split('|')]
                if len(cells) < len(cols) - 1:
                    continue
                row = dict(zip(cols, cells))
                rid = ''
                for c in cols:
                    if '编号' in c:
                        rid = row.get(c, '')
                if not rid:
                    continue
                text = ''
                for c in ('原文（四柱）', '原文', '断语', '原书所断'):
                    if row.get(c):
                        text = row[c]
                        break
                loc = ''
                for c in ('出处', '页·叶', '原文位置'):
                    if row.get(c):
                        loc = row[c]
                        break
                recs.append(dict(v='万历', lib=lib, id=rid, title=row.get('人物/身份') or row.get('姓名（身份）') or '',
                                 text=text, loc=loc, level='完整', sizhu_field=row.get('四柱', ''),
                                 sz_src='四柱字段', file=rel))
            continue
        # 块体
        if lib == '命例':
            ents = []
            for i, ln in enumerate(lines):
                if re.match(r'^###\s+(?:[MC]\d+-\d+|E\d+)\b', ln) or re.match(r'^##\s+命例\s*·', ln):
                    ents.append(i)
            for n, i in enumerate(ents):
                end = ents[n + 1] if n + 1 < len(ents) else len(lines)
                head = lines[i].lstrip('#').strip()
                m = re.match(r'^(?:命例\s*·\s*)?([MC]\d+-\d+|E\d+)\s*(?:[·．]\s*)?(.*)$', head)
                if m:
                    rid, title = m.group(1), m.group(2).strip()
                else:
                    rid, title = '命例-卷-%04d' % n, re.sub(r'^命例\s*·\s*', '', head).strip()
                body = lines[i + 1:end]
                f = parse_fields(body)
                sec = section_map(body)
                sz = pillars_from_text('\n'.join(body)) or f.get('四柱', '')
                text = (f.get('原文摘录') or f.get('原文') or f.get('书中论断') or sec.get('书中论断')
                        or f.get('所断') or sec.get('断语') or '')
                text = text.strip().strip('「」')
                loc = f.get('原文位置') or sec.get('原文位置') or f.get('出处') or ''
                if f.get('条号'):
                    rid = f['条号']
                recs.append(dict(v='万历', lib=lib, id=rid, title=title, text=text, loc=loc,
                                 level='完整', sizhu_field=sz or f.get('四柱', ''),
                                 sz_src=('排盘拼合' if sz else ('四柱字段' if f.get('四柱') else '')), file=rel))
            continue
        # 非命例块（格局/规则/反例/术语）
        id_re = re.compile(r'^(?:#{2,3})\s+(.*)$')
        starts = []
        for i, ln in enumerate(lines):
            m = id_re.match(ln)
            if not m:
                continue
            h = m.group(1)
            if re.match(r'^[RGFMT]\d+(?:-\d+)?\s*[·．]', h) or re.match(r'^(格局|规则|反例|术语)\s*·', h) or re.match(r'^第[一二三四五六七八九十]+', h):
                starts.append(i)
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(lines)
            head = id_re.match(lines[i]).group(1).strip()
            body = lines[i + 1:end]
            f = parse_fields(body)
            rid = ''
            m = re.match(r'^([RGFMT]\d+(?:-\d+)?)\s*[·．]?\s*(.*)$', head)
            if m:
                rid, title = m.group(1), m.group(2)
            else:
                title = re.sub(r'^(格局|规则|反例|术语)\s*·\s*', '', head)
                rid = f.get('条号', '')
            text = f.get('原文摘录') or f.get('原文') or f.get('原文引句') or ''
            loc = f.get('原文位置') or f.get('卷次') or ''
            lvl = '完整'
            cl = f.get('条款完整度', '')
            if cl:
                lvl = '仅名' if '仅名' in cl else ('残缺' if '残缺' in cl else '完整')
            recs.append(dict(v='万历', lib=lib, id=rid or title[:12], title=title, text=text, loc=loc,
                             level=lvl, file=rel))
    return recs


def wanli_geju():
    """万历格局库 G 编号（技能包）"""
    recs = []
    for path in sorted(glob.glob(os.path.join(W_ROOT, '技能包', '格局库_*.md'))):
        rel = os.path.relpath(path, W_ROOT).replace('\\', '/')
        lines = read_lines(path)
        for rid, title, body in split_blocks(lines, re.compile(r'^###\s+(G\d{4})\s*[·．]\s*(.*)$')):
            f = parse_fields(body)
            name = re.sub(r'（.*?）|\(.*?\)', '', title).strip()
            recs.append(dict(v='万历', lib='格局', id=rid, title=name,
                             text=f.get('原文摘录', ''), loc=f.get('原文位置', ''),
                             level='完整' if '完整' in f.get('层级', '完整') else ('仅名' if '仅名' in f.get('层级', '') else '残缺'),
                             file=rel))
    return recs


# ---------------- 蔣本 ----------------
J_SKIP = ('冲突清单', '同词分层', '验证记录')


def jiang_records():
    recs = []
    for path in sorted(glob.glob(os.path.join(J_ROOT, '已校', '*.md'))):
        base = os.path.basename(path)
        if any(base.startswith(k) for k in J_SKIP):
            continue
        lib = None
        for k in ('命例', '格局', '规则', '反例', '术语'):
            if base.startswith(k):
                lib = k
                break
        if not lib:
            continue
        rel = os.path.relpath(path, J_ROOT).replace('\\', '/')
        lines = read_lines(path)
        id_re = re.compile(r'^###\s+([RGFMT]\d+-\d+)\s*(.*)$')
        for rid, title, body in split_blocks(lines, id_re):
            f = parse_fields(body)
            text = f.get('原文', '') or f.get('原文摘录', '')
            loc = f.get('出處', '') or f.get('原文位置', '')
            lvl = f.get('完整度', '完整')
            # 蔣本标题常作「G10-002　10-G-002　金水象」：去掉卷内编号，只留格名
            title = re.sub(r'^\d+-[RGFMT]-\d+\s*[　·．]?\s*', '', title).strip()
            title = re.sub(r'^[RGFMT]\d+-\d+\s*[　·．]?\s*', '', title).strip()
            recs.append(dict(v='蔣本', lib=lib, id=rid, title=title, text=text, loc=loc,
                             level=lvl, sizhu_field=f.get('四柱', ''), sz_src='四柱字段', file=rel, fields=f))
    return recs


# ---------------- 辛丑 ----------------
def xinchou_records():
    recs = []
    name_map = {}
    p = os.path.join(X_ROOT, '附录C_格局异文.csv')
    if os.path.exists(p):
        with io.open(p, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if row.get('句指纹'):
                    name_map[row['句指纹']] = row.get('格名', '')
                if row.get('主条指纹'):
                    name_map.setdefault(row['主条指纹'], row.get('格名', ''))
    for name in ('规则库', '格局库', '命例库', '反例库', '术语库'):
        for path in sorted(glob.glob(os.path.join(X_ROOT, name + '_*.csv'))):
            rel = os.path.relpath(path, X_ROOT).replace('\\', '/')
            with io.open(path, encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    rid = row.get('序号', '')
                    text = row.get('原文引句', '')
                    fp = row.get('句指纹', '')
                    loc = '卷%s %s' % (row.get('卷', ''), row.get('页号-叶', ''))
                    recs.append(dict(v='辛丑', lib=name.replace('库', ''), id=rid, title=name_map.get(fp, ''),
                                     text=text, loc=loc, level=row.get('层', '完整'), file=rel,
                                     biao=row.get('标注', '')))
    return recs


# ---------------- 四库 ----------------
def siku_records():
    recs = []
    for path in sorted(glob.glob(os.path.join(S_ROOT, '五库', '*.md'))):
        base = os.path.basename(path)
        lib = base.split('_')[0].replace('库', '')
        rel = os.path.relpath(path, S_ROOT).replace('\\', '/')
        lines = read_lines(path)
        id_re = re.compile(r'^###\s+([RGFMT]\d+)(?:\s*（匿）)?\s*$')
        for rid, title, body in split_blocks(lines, id_re):
            f = parse_fields(body)
            loc = f.get('定位', '')
            m = re.match(r'卷([^·]+)·([^·]+)·', loc)
            pian = m.group(2) if m else ''
            recs.append(dict(v='四库', lib=lib, id=rid, title=pian, text=f.get('原文引句', ''),
                             loc=loc, level=f.get('完整度', '完整'), file=rel))
    return recs


def all_records():
    return wanli_records() + wanli_geju() + jiang_records() + xinchou_records() + siku_records()


if __name__ == '__main__':
    import collections
    rs = all_records()
    print('total', len(rs))
    c = collections.Counter((r['v'], r['lib']) for r in rs)
    for k in sorted(c):
        print(k, c[k])
    # 四柱可解析率
    cz = collections.Counter()
    for r in rs:
        if r['lib'] != '命例':
            continue
        s = first_sizhu(r.get('sizhu_field') or '') or first_sizhu(r.get('text') or '')
        cz[(r['v'], 'ok' if s else 'none')] += 1
    print(sorted(cz.items()))
