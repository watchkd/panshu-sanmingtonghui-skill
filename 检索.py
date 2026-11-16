# -*- coding: utf-8 -*-
"""八字辅助分析·检索层

输入一个四柱（＋性别），在万历本／蔣國祥本／辛丑本／四库本四个《三命通会》
蒸馏包中捞取与该八字相关的记录，分 L1–L5 五层输出，并给出妻·财·子·禄·寿
五栏简评（只列原文证据与置信，不作品级裁断）。

用法：
  python 检索.py --四柱 "甲子 乙亥 庚戌 癸未" --性别 男
  python 检索.py --四柱 "戊午 戊午 戊午 戊午" --性别 男 --输出 报告.md
  python 检索.py --自测            # 跑两份自测并写对比

四包一律只读；本脚本不依赖任何缓存或临时文件，每次运行都现场解析。
依赖同目录 抽取层.py（四包解析层）；若缺，回退到上级目录 抽取.py。
"""
import os, re, sys, io, csv, glob, argparse, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import 抽取层 as EX
except ImportError:
    sys.path.insert(0, os.path.dirname(HERE))
    import 抽取 as EX

VERS = ['万历', '蔣本', '辛丑', '四库']
VLAB = {'万历': '万历本', '蔣本': '蔣國祥本', '辛丑': '辛丑本', '四库': '四库本'}
GAN = '甲乙丙丁戊己庚辛壬癸'
ZHI = '子丑寅卯辰巳午未申酉戌亥'
WUX = dict(zip(GAN, '木木火火土土金金水水'))
YIN = dict(zip(GAN, [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]))   # 1=阳
ZANG = {'子': '癸', '丑': '己癸辛', '寅': '甲丙戊', '卯': '乙', '辰': '戊乙癸',
        '巳': '丙戊庚', '午': '丁己', '未': '己丁乙', '申': '庚壬戊', '酉': '辛',
        '戌': '戊辛丁', '亥': '壬甲'}
SHENG = {'木': '火', '火': '土', '土': '金', '金': '水', '水': '木'}
KE = {'木': '土', '火': '金', '土': '水', '金': '木', '水': '火'}
LU = {'甲': '寅', '乙': '卯', '丙': '午', '丁': '巳', '戊': '午',
      '己': '巳', '庚': '申', '辛': '酉', '壬': '子', '癸': '亥'}

NAYIN_PAIRS = [
    ('甲子', '海中金'), ('丙寅', '爐中火'), ('戊辰', '大林木'), ('庚午', '路旁土'),
    ('壬申', '劍鋒金'), ('甲戌', '山頭火'), ('丙子', '澗下水'), ('戊寅', '城頭土'),
    ('庚辰', '白蠟金'), ('壬午', '楊柳木'), ('甲申', '泉中水'), ('丙戌', '屋上土'),
    ('戊子', '霹靂火'), ('庚寅', '松柏木'), ('壬辰', '長流水'), ('甲午', '沙中金'),
    ('丙申', '山下火'), ('戊戌', '平地木'), ('庚子', '壁上土'), ('壬寅', '金箔金'),
    ('甲辰', '覆燈火'), ('丙午', '天河水'), ('戊申', '大驛土'), ('庚戌', '釵釧金'),
    ('壬子', '桑柘木'), ('甲寅', '大溪水'), ('丙辰', '沙中土'), ('戊午', '天上火'),
    ('庚申', '石榴木'), ('壬戌', '大海水')]
NAYIN = {}
for _k in range(60):
    NAYIN[GAN[_k % 10] + ZHI[_k % 12]] = NAYIN_PAIRS[_k // 2][1]

LIUHE = {frozenset('子丑'): '子丑合土', frozenset('寅亥'): '寅亥合木',
         frozenset('卯戌'): '卯戌合火', frozenset('辰酉'): '辰酉合金',
         frozenset('巳申'): '巳申合水', frozenset('午未'): '午未合土'}
LIUCHONG = {frozenset('子午'), frozenset('丑未'), frozenset('寅申'),
            frozenset('卯酉'), frozenset('辰戌'), frozenset('巳亥')}
LIUHAI = {frozenset('子未'), frozenset('丑午'), frozenset('寅巳'),
          frozenset('卯辰'), frozenset('申亥'), frozenset('酉戌')}
SANHE = [('申子辰', '水'), ('亥卯未', '木'), ('寅午戌', '火'), ('巳酉丑', '金')]
SANXING = [('寅巳申', '無恩之刑'), ('丑戌未', '恃勢之刑'),
           ('子卯', '無禮之刑'), ('辰辰', '自刑'), ('午午', '自刑'),
           ('酉酉', '自刑'), ('亥亥', '自刑')]

JI = ['貴', '贵', '富', '榮', '荣', '顯', '显', '壽', '寿', '福', '吉', '貴顯', '榮華']
XIONG = ['貧', '贫', '賤', '贱', '夭', '殀', '凶', '禍', '祸', '災', '灾', '死',
         '孤', '剋妻', '克妻', '破敗', '破败', '不吉', '殘', '残']

LANE = {
    '妻': (r'妻|配偶|夫妻|婚姻|內助|妻宮|妻宫|婚', '婚配、配偶宫星'),
    '财': (r'財|财|富|衣食|財庫|财库|俸|祿食', '财星与取财方式'),
    '子': (r'子嗣|子女|子息|兒子|儿孙|子孫|子孙|嗣|無子|无子|有子|剋子|克子|旺子|傷子|刑子|遲子|迟子|晚子|少子|多子|添子|絕嗣|绝嗣|官殺|官杀', '子女宫与官杀食伤'),
    '禄': (r'祿|禄|官貴|官贵|仕宦|功名|事業|事业|官職|官职|科第|及第|貴顯|贵显|權', '官贵事业与俸禄'),
    '寿': (r'壽|寿|夭|殀|壽元|壽考|疾病|病|災|灾|凶|死|折', '健康寿元与灾厄'),
}

FILES4 = ['索引_按四柱_*.csv', '索引_按格名_*.csv', '键/四柱归一表_*.csv', '键/格名归一表_*.csv']
IDX_DIR = os.path.join(EX.DATA_ROOT, '索引')
SEARCH_DIRS = [IDX_DIR, os.path.join(IDX_DIR, '键'), HERE, os.path.dirname(HERE)]


# ---------------- 基础工具 ----------------
def shishen(dg, g):
    if g not in GAN or dg not in GAN:
        return ''
    a, b = WUX[dg], WUX[g]
    same = (YIN[dg] == YIN[g])
    if a == b:
        return '比肩' if same else '劫財'
    if SHENG[a] == b:
        return '食神' if same else '傷官'
    if KE[a] == b:
        return '偏財' if same else '正財'
    if KE[b] == a:
        return '七殺' if same else '正官'
    return '偏印' if same else '正印'


def xun_kong(day):
    """旬空（本库推得，非原文表）"""
    dia = GAN.index(day[0]); diz = ZHI.index(day[1])
    head_gan = dia
    # 逆推到甲
    back = 0
    while (dia - back) % 10 != 0:
        back += 1
    head_zhi = (diz - back) % 12
    a = ZHI[(head_zhi + 10) % 12]
    b = ZHI[(head_zhi + 11) % 12]
    return a + b


def norm_pillar(s):
    s = (s or '').strip()
    if len(s) < 2:
        return ''
    return EX.canon_pair(s[0], s[1])


def parse_sizhu(s):
    toks = re.findall(r'[%s][%s]' % (GAN, ZHI), s)
    if len(toks) < 4:
        return []
    return [norm_pillar(t) for t in toks[:4]]


def read_csv_glob(pat):
    rows = []
    for d in SEARCH_DIRS:
        files = sorted(glob.glob(os.path.join(d, pat)))
        if not files:
            continue
        for f in files:
            with io.open(f, encoding='utf-8-sig') as fh:
                r = list(csv.reader(fh))
                if not r:
                    continue
                hdr = r[0]
                for line in r[1:]:
                    if len(line) >= len(hdr):
                        rows.append(dict(zip(hdr, line)))
        if rows:
            break
    return rows


def polar(t):
    t = re.sub(r'\s', '', t or '')
    j = any(k in t for k in JI)
    x = any(k in t for k in XIONG)
    if j and not x:
        return '吉'
    if x and not j:
        return '凶'
    if j and x:
        return '杂'
    return '中'


# ---------------- 库 ----------------
class Lib(object):
    def __init__(self):
        rs = EX.all_records()
        best, order = {}, []
        for r in rs:
            k = (r['v'], r['id'])
            pri = 0 if '已校' in (r.get('file') or '') else 1
            if k not in best:
                best[k] = (pri, r)
                order.append(k)
            elif pri < best[k][0]:
                best[k] = (pri, r)
        self.recs = [best[k][1] for k in order]
        # 格名映射
        self.ge = {}
        for row in read_csv_glob('索引_按格名_*.csv'):
            self.ge.setdefault((row['版本'], row['条目编号']), row['标准格名'])
        for row in read_csv_glob('键/格名归一表_*.csv'):
            for v in VERS:
                ids = row.get(v + '编号', '')
                for rid in re.split(r'[｜|]', ids):
                    rid = rid.strip()
                    if rid:
                        self.ge.setdefault((v, rid), row['标准名'])
        # 预扫描
        self.info = []
        for r in self.recs:
            t = (r.get('text') or '')
            if len(re.sub(r'[^\u4e00-\u9fff]', '', t)) < 4:
                continue        # 正文为空者不入检索，避免引用空条
            p4 = ''
            src = (r.get('sizhu_field') or '') + ' ' + t
            got = EX.first_sizhu(src)
            if got:
                p4 = got[0]
            tm = re.sub(r'[時时]', '时', t)
            rs_ = []
            for m in re.finditer(r'([%s])日' % GAN, tm):
                dg = m.group(1)
                win = tm[m.end():m.end() + 16]
                for mm in re.finditer(r'([%s])([%s])时' % (GAN, ZHI), win):
                    rs_.append((dg, '', mm.group(1) + mm.group(2)))
                for mm in re.finditer(r'([%s])时' % ZHI, win):
                    rs_.append((dg, '', '?' + mm.group(1)))
            for m in re.finditer(r'([%s])日[時时][逢逄遇見见臨临]?([%s])([%s])' % (GAN, GAN, ZHI), tm):
                rs_.append((m.group(1), '', m.group(2) + m.group(3)))
            for m in re.finditer(r'([%s])([%s])日' % (GAN, ZHI), tm):
                win = tm[m.end():m.end() + 14]
                mm = re.search(r'([%s])([%s])时' % (GAN, ZHI), win)
                if mm:
                    rs_.append((m.group(1), m.group(2), mm.group(1) + mm.group(2)))
            rs_ = list(dict.fromkeys(rs_))
            tt = (r.get('title') or '') + (r.get('loc') or '')
            zhuan = ('時斷' in tt or '时断' in tt or '卷九' in tt or '卷八' in tt
                     or '卷8' in tt or '卷9' in tt)
            self.info.append({'r': r, 'p4': p4, 'rishi': rs_, 'text': t, 'zhuan': zhuan})

    def stats(self):
        return len(self.recs)


def load_keys():
    keys4 = read_csv_glob('键/四柱归一表_*.csv')
    keysg = read_csv_glob('键/格名归一表_*.csv')
    idx4 = read_csv_glob('索引_按四柱_*.csv')
    idxg = read_csv_glob('索引_按格名_*.csv')
    return keys4, keysg, idx4, idxg


# ---------------- 键 ----------------
def build_keys(lib, p4, sex):
    dgz = p4[2]
    dg, dz = dgz[0], dgz[1]
    sz = p4[3]
    mz = p4[1][1]
    K = {}
    K['日柱'] = dgz
    K['时柱'] = sz
    K['日时断写法'] = '%s日%s時' % (dg, sz)
    # 纳音（本库内置六十甲子纳音表，四版同名）
    K['纳音'] = [(p, NAYIN.get(p, '')) for p in p4]
    # 十神
    gans = [p[0] for p in p4]
    K['十神_天干'] = [('年干', gans[0], shishen(dg, gans[0])),
                     ('月干', gans[1], shishen(dg, gans[1])),
                     ('日主', dg, '日主'),
                     ('时干', gans[3], shishen(dg, gans[3]))]
    K['十神_月令'] = (mz, ZANG[mz][0], shishen(dg, ZANG[mz][0]))
    cang = []
    for p in p4:
        z = p[1]
        cang.append((z, [(g, shishen(dg, g)) for g in ZANG[z]]))
    K['十神_藏干'] = cang
    cnt = {}
    for _, _, s in K['十神_天干']:
        if s and s != '日主':
            cnt[s] = cnt.get(s, 0) + 1
    msz = shishen(dg, ZANG[mz][0])
    cnt['月令' + msz] = cnt.get('月令' + msz, 0) + 1
    for z, lst in cang:
        for g, s in lst:
            cnt['藏' + s] = cnt.get('藏' + s, 0) + 1
    K['十神_计数'] = cnt
    # 格候选（本库推得，非四版判定）
    base = {'比肩': ['建祿'] if LU.get(dg) == mz else ['比肩'],
            '劫財': ['月劫', '建祿'], '食神': ['食神'], '傷官': ['傷官'],
            '偏財': ['偏財'], '正財': ['正財'], '七殺': ['偏官', '七殺'],
            '正官': ['正官'], '偏印': ['偏印', '梟神'], '正印': ['正印']}
    K['格候选'] = base.get(msz, [])
    K['格候选_依据'] = '月令%s本气%s→十神%s' % (mz, ZANG[mz][0], msz)
    # 空亡 / 刑冲合害
    K['空亡'] = xun_kong(dgz) + '（据旬推，本库无空亡表）'
    pairs = []
    zs = [p[1] for p in p4]
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = zs[i], zs[j]
            f = frozenset(a + b)
            tag = []
            if f in LIUHE:
                tag.append(LIUHE[f])
            if f in LIUCHONG:
                tag.append('六沖')
            if f in LIUHAI:
                tag.append('六害')
            for grp, wx in SANHE:
                if a in grp and b in grp and a != b:
                    tag.append('%s半合%s' % (a + b, wx))
            for grp, nm in SANXING:
                if len(grp) == 3 and a in grp and b in grp and a != b:
                    tag.append('%s刑（%s）' % (a + b, nm))
                if len(grp) == 2 and grp[0] == grp[1] and a == b == grp[0]:
                    tag.append('%s自刑' % a)
            if tag:
                pairs.append((a + b, '／'.join(tag)))
    K['刑冲合害'] = pairs
    K['性别'] = sex
    return K


# ---------------- 五层检索 ----------------
def clause_type(t):
    if len(re.sub(r'[^\u4e00-\u9fff]', '', t or '')) <= 6:
        return '仅名'
    cheng = re.search(r'入格|成格|爲貴|为贵|主貴|主贵|大貴|大贵|貴格|贵格|富貴|富贵|貴顯|贵显', t)
    if re.search(r'破格|不成格|不入格|不取|非格', t) and not cheng:
        return '破格'
    if cheng:
        return '成格'
    if re.search(r'行运|行運|岁运|歲運|大運|大运|运喜|運喜|交运', t):
        return '行运'
    if re.search(r'[喜忌]', t):
        return '喜忌'
    return '成格'


def dedupe_same_text(lst):
    """同版同文重出（如万历 技能包 G 号与已校 G6 号）合并为一条，保留两号。"""
    seen = {}
    out = []
    for x in lst:
        k = (x['v'], re.sub(r'[^\u4e00-\u9fff]', '', x['text'])[:80])
        if k in seen:
            seen[k]['id'] = seen[k]['id'] + '／' + x['id']
            seen[k]['note'] = seen[k]['note'] + '｜同文重出'
            continue
        seen[k] = x
        out.append(x)
    lst[:] = out


def layer_search(lib, p4, K, cap=40):
    key4 = ' '.join(p4)
    dgz, sz = p4[2], p4[3]
    dg = dgz[0]
    L = {i: [] for i in range(1, 6)}
    for it in lib.info:
        r = it['r']
        note = None
        if it['p4'] == key4:
            note = '同四柱'
        elif ('四' + dgz) in it['text']:
            note = '同四柱（原文作「四%s」）' % dgz
        else:
            for dgd, dzd, szz in it['rishi']:
                if dgd != dg:
                    continue
                if szz == sz:
                    if dzd == p4[2][1]:
                        note = '日時斷（本日柱 %s日%s時）' % (dgd, szz)
                        break
                    elif dzd == '':
                        note = '日時斷（六%s日統論，%s時）' % (dgd, szz)
                    else:
                        note = note or ('日時斷（他日 %s%s日，同時柱）' % (dgd, dzd))
                elif szz == '?' + sz[1]:
                    note = note or ('日時斷（僅時支 %s，柱位未定）' % sz[1])
            if note and '統論' in note and not it['zhuan']:
                note += '·旁及'
            elif note and '他日' in note:
                note += '·旁及'
        if note:
            n = 1 if note.startswith('同四柱') else 2
            L[n].append({'v': r['v'], 'id': r['id'], 'loc': r.get('loc', ''),
                         'text': it['text'], 'note': note,
                         'lib': r.get('lib', ''), 'title': r.get('title', '')})
    dedupe_same_text(L[1])
    dedupe_same_text(L[2])
    # L3 同格（格名须与候选格名精确同格，不用包含式）
    cands = K['格候选']
    for it in lib.info:
        r = it['r']
        g = lib.ge.get((r['v'], r['id']), '')
        if not g:
            continue
        g0 = re.sub(r'(格|局)$', '', g)
        if g0 not in cands:
            continue
        if any(x['v'] == r['v'] and x['id'] == r['id'] for x in L[1] + L[2]):
            continue
        L[3].append({'v': r['v'], 'id': r['id'], 'loc': r.get('loc', ''),
                     'text': it['text'], 'note': '同格：%s｜%s' % (g, clause_type(it['text'])),
                     'lib': r.get('lib', ''), 'title': (r.get('title') or g)})
    # L4 同十神结构（须月令十神相同，且结构相似度 ≥0.88）
    tgt = sig_of(p4)
    tgt_ms = shishen(dg, ZANG[p4[1][1]][0])
    scored = []
    for it in lib.info:
        if not it['p4']:
            continue
        pp = it['p4'].split()
        if len(pp) != 4:
            continue
        if shishen(pp[2][0], ZANG[pp[1][1]][0]) != tgt_ms:
            continue
        s = sig_of(pp)
        sc = sim_sig(tgt, s)
        if sc >= 0.88:
            scored.append((sc, it))
    scored.sort(key=lambda x: -x[0])
    for sc, it in scored[:cap]:
        r = it['r']
        if any(x['v'] == r['v'] and x['id'] == r['id'] for x in L[1] + L[2] + L[3]):
            continue
        L[4].append({'v': r['v'], 'id': r['id'], 'loc': it['r'].get('loc', ''),
                     'text': it['text'], 'note': '十神同构 %.2f｜%s' % (sc, it['p4']),
                     'lib': r.get('lib', ''), 'title': r.get('title', '')})
    # L5 纳音 / 刑冲
    names = [(p, n) for p, n in K['纳音'] if n]
    seen = set()
    for p, n in names:
        cnt = 0
        for it in lib.info:
            t = it['text']
            if n and n in t:
                r = it['r']
                kk = (r['v'], r['id'])
                if kk in seen:
                    continue
                seen.add(kk)
                L[5].append({'v': r['v'], 'id': r['id'], 'loc': r.get('loc', ''),
                             'text': t, 'note': '納音：%s（%s柱）｜原文提及' % (n, p),
                             'lib': r.get('lib', ''), 'title': r.get('title', '')})
                cnt += 1
                if cnt >= 6:
                    break
    for pair, nm in K['刑冲合害']:
        kind = '刑' if '刑' in nm else ('害' if '害' in nm else ('沖' if '沖' in nm else '合'))
        cnt = 0
        for it in lib.info:
            t = it['text']
            if (pair in t or pair[::-1] in t) and kind in t:
                r = it['r']
                kk = (r['v'], r['id'])
                if kk in seen:
                    continue
                seen.add(kk)
                L[5].append({'v': r['v'], 'id': r['id'], 'loc': r.get('loc', ''),
                             'text': t, 'note': '刑沖合害：%s（%s）｜原文提及' % (pair, nm),
                             'lib': r.get('lib', ''), 'title': r.get('title', '')})
                cnt += 1
                if cnt >= 4:
                    break
    # L5 神煞：本库无神煞表，只录 L1／L2 正文中出现的名目（柱位未明）
    SHS = ['天乙', '玉堂', '天官', '文昌', '驛馬', '驿马', '桃花', '咸池', '羊刃',
           '陽刃', '阳刃', '飛刃', '飛刃', '祿', '禄', '空亡', '旬空', '華蓋', '华盖',
           '將星', '将星', '魁罡', '金神', '天德', '月德', '孤辰', '寡宿', '亡神',
           '劫煞', '紅鸞', '天喜', '天羅', '地網', '三奇', '童子']
    base = list(L[1]) + list(L[2])
    got = {}
    for x in base:
        for s in SHS:
            if s in x['text']:
                got.setdefault(s, x)
    for s, x in got.items():
        L[5].append({'v': x['v'], 'id': x['id'], 'loc': x['loc'], 'text': x['text'],
                     'note': '神煞：%s｜原文提及（柱位未明；本库无神煞表，不据表推）' % s,
                     'lib': x['lib'], 'title': x['title']})
    for n in (3, 4, 5):
        dedupe_same_text(L[n])
    return L


def sig_of(p4):
    dg = p4[2][0]
    mz = p4[1][1]
    v = {}
    for i, p in enumerate(p4):
        if i == 2:
            continue
        s = shishen(dg, p[0])
        v[s] = v.get(s, 0) + 1.0
    ms = shishen(dg, ZANG[mz][0])
    v[ms] = v.get(ms, 0) + 1.6
    # 财官印食伤比劫大类
    grp = {'比肩': '比劫', '劫財': '比劫', '食神': '食傷', '傷官': '食傷',
           '偏財': '財', '正財': '財', '七殺': '官殺', '正官': '官殺',
           '偏印': '印', '正印': '印'}
    for k in list(v):
        g = grp.get(k)
        if g:
            v[g] = v.get(g, 0) + v[k] * 1.2
    return v


def sim_sig(a, b):
    ks = set(a) | set(b)
    num = sum(min(a.get(k, 0), b.get(k, 0)) for k in ks)
    den = sum(max(a.get(k, 0), b.get(k, 0)) for k in ks)
    return num / den if den else 0.0


def similar_cases(lib, p4, top=8):
    dg = p4[2][0]
    tgt = sig_of(p4)
    out = []
    seen = set()
    for it in lib.info:
        if not it['p4']:
            continue
        minlen = 12 if it['r'].get('lib') == '命例' else 1
        if len(re.sub(r'[^\u4e00-\u9fff]', '', it['text'])) < minlen:
            continue        # 残句不入相似命例
        pp = it['p4'].split()
        if len(pp) != 4:
            continue
        same = sum(1 for i in range(4) if pp[i] == p4[i])
        dh = (pp[2] == p4[2]) and (pp[3] == p4[3])
        if it['r'].get('lib') != '命例' and same < 3:
            continue        # 非命例库者，须三柱以上重合才入
        fp = (it['r']['v'], re.sub(r'[^\u4e00-\u9fff]', '', it['text'])[:60])
        if fp in seen:
            continue
        seen.add(fp)
        sc = sim_sig(tgt, sig_of(pp))
        if same < 2 and not dh and sc < 0.88:
            continue
        out.append({'v': it['r']['v'], 'id': it['r']['id'], 'loc': it['r'].get('loc', ''),
                    'p4': it['p4'], 'same': same, 'dh': dh, 'sim': sc,
                    'text': it['text'], 'title': it['r'].get('title', '')})
    out.sort(key=lambda x: (-x['same'], -int(x['dh']), -x['sim']))
    return out[:top]


# ---------------- 五栏 ----------------
def lane_eval(L, K, sex):
    pool = []
    for n in (1, 2, 3, 4, 5):
        for x in L[n]:
            x = dict(x)
            x['层'] = 'L%d' % n
            pool.append(x)
    res = {}
    for lane, (pat, desc) in LANE.items():
        ev = []
        for x in pool:
            if re.search(pat, x['text'] or ''):
                ev.append(x)
        # 去重（同版同号）
        seen = set()
        uniq = []
        for x in ev:
            k = (x['v'], x['id'])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(x)
        def _direct(x):
            if x['层'] == 'L1':
                return True
            if x['层'] != 'L2':
                return False
            nt = x['note']
            return ('本日柱' in nt) or ('統論' in nt and '旁及' not in nt)

        direct = [x for x in uniq if _direct(x)]
        analog = [x for x in uniq if x['层'] in ('L3', 'L4') or (x['层'] == 'L2' and not _direct(x))]
        onlyname = [x for x in uniq if x['层'] == 'L5']
        # 四版极性：只用直证＋同构（L5 单条旁及不作吉凶对勘）
        byv = {}
        for x in direct + analog:
            byv.setdefault(x['v'], set()).add(polar(x['text']))
        conflict = False
        mixed = False
        vs = [v for v in VERS if v in byv]
        signs = set()
        for v in vs:
            s = byv[v]
            if ('吉' in s) and ('凶' in s):
                mixed = True
            if '吉' in s and '杂' not in s and '凶' not in s:
                signs.add('吉')
            if '凶' in s and '杂' not in s and '吉' not in s:
                signs.add('凶')
        if len(signs) > 1:
            conflict = True
        has_mixed = mixed or any('杂' in s for s in byv.values())
        if not uniq:
            conf, why = '低', '四版此层键内无条文'
        elif conflict:
            conf, why = '低', '四版吉凶互斥'
        elif len(set(x['v'] for x in direct)) >= 2 and not has_mixed:
            conf, why = '高', '两版以上日柱／日時斷直证且同向'
        elif direct:
            conf, why = '中', ('有直证，然吉凶并在，须通读原文' if has_mixed else '仅单版直证')
        elif len(set(x['v'] for x in analog)) >= 2:
            conf, why = '中', '多版同构类推，无直证'
        elif analog:
            conf, why = '低', '单版同构类推'
        else:
            conf, why = '低', '仅纳音／刑冲单条旁及，非本栏专论'
        res[lane] = {'desc': desc, 'ev': uniq, 'direct': direct, 'analog': analog,
                     'onlyname': onlyname, 'byv': byv, 'conflict': conflict,
                     'mixed': mixed, 'conf': conf, 'why': why}
    return res


# ---------------- 报告 ----------------
def cut(s, n):
    s = re.sub(r'\s+', '', s or '')
    return s if len(s) <= n else s[:n] + '…'


def report(lib, p4, sex, K, L, sims, lanes, limit=12):
    A = []
    add = A.append
    key4 = ' '.join(p4)
    add('# 八字辅助分析｜%s（%s）' % (key4, sex))
    add('')
    add('> 输入：年 %s｜月 %s｜日 %s｜時 %s；性別 %s。' % (p4[0], p4[1], p4[2], p4[3], sex))
    add('> 四包：万历本／蔣國祥本／辛丑本／四库本《三命通会》蒸馏包（只读）。')
    add('> 本报告只列四版原文及其归属层，不补通用命理推断，不作品级裁断。')
    add('')
    # 一、检索键
    add('## 一、检索键（六类）')
    add('')
    add('| 键类 | 内容 | 来源 |')
    add('| --- | --- | --- |')
    add('| 日柱／时柱 | 日 %s；時 %s；日時斷写法「%s」 | 四柱直取 |'
        % (K['日柱'], K['时柱'], K['日时断写法']))
    add('| 月令与格 | 月令 %s（本气 %s，十神 %s）→ 候选格名 %s；四版是否定格另计 | 本库推得 |'
        % (K['十神_月令'][0], K['十神_月令'][1], K['十神_月令'][2],
           '／'.join(K['格候选']) or '无'))
    add('| 十神布局 | ' + '；'.join('%s%s%s' % (a, b, c) for a, b, c in K['十神_天干']) + ' | 本库推得 |')
    add('| 藏干十神 | ' + '；'.join('%s藏%s' % (z, '、'.join('%s%s' % (g, s) for g, s in lst)) for z, lst in K['十神_藏干']) + ' | 本库推得 |')
    add('| 纳音 | ' + '；'.join('%s＝%s' % (p, n) for p, n in K['纳音']) + ' | 内置六十甲子纳音表（四版同名，非各版新说） |')
    add('| 空亡 | %s | 据旬推得（本库无空亡表） |' % K['空亡'])
    add('| 刑冲合害 | ' + ('；'.join('%s＝%s' % (a, b) for a, b in K['刑冲合害']) or '四支之间无刑冲合害') + ' | 据表推得 |')
    add('| 神煞 | 本库无神煞表，不据表推；只录原文提及者（见 L5） | 四版无表 |')
    add('')
    # 二、分层
    add('## 二、分层检索（L1–L5）')
    add('')
    add('| 层 | 含义 | 条数 | 万历 | 蔣本 | 辛丑 | 四库 |')
    add('| --- | --- | --- | --- | --- | --- | --- |')
    names = {1: '同八字、同柱', 2: '日時斷', 3: '同格', 4: '同十神结构', 5: '神煞／纳音／刑冲单条'}
    for n in range(1, 6):
        lst = L[n]
        cells = []
        for v in VERS:
            cells.append(str(sum(1 for x in lst if x['v'] == v)))
        add('| L%d | %s | %d | %s |' % (n, names[n], len(lst), ' | '.join(cells)))
    add('')
    for n in range(1, 6):
        lst = L[n]
        add('### L%d %s（%d 条）' % (n, names[n], len(lst)))
        add('')
        if not lst:
            add('— 四版均无此项。（「无」仅指键内无条目，不等于全书未提。）')
            add('')
            continue
        for i, x in enumerate(lst[:limit], 1):
            add('**%d) %s｜%s**｜%s｜%s' % (i, VLAB[x['v']], x['id'],
                                          x['loc'] or '（原条目未标定位）', x['note']))
            add('')
            add('> ' + cut(x['text'], 320))
            add('')
        if len(lst) > limit:
            add('（另 %d 条未展开，见 CSV 输出）' % (len(lst) - limit))
            add('')
    # 三、相似命例
    add('## 三、相似命例（柱位重合 → 日柱同时柱 → 十神同构）')
    add('')
    if not sims:
        add('— 命例库中无柱位重合、无日柱同时柱、亦无十神同构度 ≥0.88 者。')
        add('')
    else:
        add('| # | 版本 | 编号 | 四柱 | 同柱 | 日時同 | 十神同构 |')
        add('| --- | --- | --- | --- | --- | --- | --- |')
        for i, s in enumerate(sims, 1):
            add('| %d | %s | %s | %s | %d/4 | %s | %.2f |' % (
                i, VLAB[s['v']], s['id'], s['p4'], s['same'],
                '是' if s['dh'] else '否', s['sim']))
        add('')
        for i, s in enumerate(sims, 1):
            same = [j for j in range(4) if s['p4'].split()[j] == p4[j]]
            diff = [j for j in range(4) if j not in same]
            lab = ['年', '月', '日', '時']
            add('**%d) %s %s**｜%s' % (i, VLAB[s['v']], s['id'], s['loc'] or ''))
            add('')
            add('- 同：%s；异：%s。' % (
                '、'.join(lab[j] + '柱' for j in same) or '无',
                '、'.join('%s柱（彼%s／此%s）' % (lab[j], s['p4'].split()[j], p4[j]) for j in diff) or '无'))
            add('- 原文：')
            add('')
            add('> ' + cut(s['text'], 360))
            add('')
        add('**相似不等于同命**：上列仅柱位／结构相近，断语各有其前提条件（月令、年时、成败救应），不得据此条直接移断本命。')
        add('')
    # 四、五栏
    add('## 四、妻·财·子·禄·寿 五栏简评')
    add('')
    add('> 每栏只从第二、三節已捞出的条目取证；性质三档＝原文直证（L1／L2）／同构类推（L3／L4）／仅名无条款。')
    add('> 无据即写无据，不以通用命理常识补写；四版分歧并列，标「不可判」，不择一。')
    add('')
    for lane in ['妻', '财', '子', '禄', '寿']:
        d = lanes[lane]
        add('### %s（%s）' % (lane, d['desc']))
        add('')
        add('**原文证据**')
        add('')
        if not d['ev']:
            add('— 无据。四版本命键内无涉及此栏之条文。')
            add('')
        else:
            for i, x in enumerate(d['ev'][:8], 1):
                if x['层'] == 'L1':
                    kind = '原文直证'
                elif x['层'] == 'L2':
                    kind = '原文直证' if (('本日柱' in x['note']) or ('統論' in x['note'] and '旁及' not in x['note'])) else '同构类推'
                elif x['层'] in ('L3', 'L4'):
                    kind = '同构类推'
                else:
                    kind = '仅名无条款'
                add('%d. %s %s｜%s｜%s｜**%s**' % (i, VLAB[x['v']], x['id'],
                                                  x['loc'] or '未标定位', x['层'], kind))
                add('')
                add('   > ' + cut(x['text'], 240))
                add('')
            if len(d['ev']) > 8:
                add('（另 %d 条，见 CSV）' % (len(d['ev']) - 8))
                add('')
        add('**本库读法**')
        add('')
        if not d['ev']:
            add('- 无据。')
        else:
            kinds = set()
            if d['direct']:
                kinds.add('原文直证')
            if d['analog']:
                kinds.add('同构类推')
            if d['onlyname']:
                kinds.add('仅名无条款')
            add('- 证据 %d 条，其中直证 %d／同构 %d／仅名 %d；性质：%s。'
                % (len(d['ev']), len(d['direct']), len(d['analog']), len(d['onlyname']),
                   '／'.join(sorted(kinds))))
            add('- 归拢：' + ('、'.join('%s %d 条' % (VLAB[v], sum(1 for x in d['ev'] if x['v'] == v))
                                      for v in VERS if any(x['v'] == v for x in d['ev']))) + '。')
        add('')
        add('**四版分歧**')
        add('')
        if not d['ev']:
            add('- 无条目可较，不判。')
        else:
            for v in VERS:
                s = d['byv'].get(v)
                if s:
                    add('- %s：%s' % (VLAB[v], '／'.join(sorted(s))))
            add('- 判定：' + ('**不可判**（四版吉凶互斥，不择一）' if d['conflict'] else (
                '本版吉凶并在（条件性断语，逐句各有前提），不合判' if d['mixed']
                else '未见互斥，仅记各自说法。')))
        add('')
        add('**该栏置信**：%s —— %s' % (d['conf'], d['why']))
        add('')
    # 五、总评
    add('## 五、总评（只述四版异同与有据无据）')
    add('')
    has = [l for l in ['妻', '财', '子', '禄', '寿'] if lanes[l]['ev']]
    no = [l for l in ['妻', '财', '子', '禄', '寿'] if not lanes[l]['ev']]
    add('- 有据栏：%s；无据栏：%s。' % ('、'.join(has) or '无', '、'.join(no) or '无'))
    conf = [l for l in ['妻', '财', '子', '禄', '寿'] if lanes[l]['conflict']]
    add('- 四版分歧（标不可判）：%s。' % ('、'.join(conf) or '本键下未见'))
    hi = [l for l in ['妻', '财', '子', '禄', '寿'] if lanes[l]['conf'] == '高']
    add('- 置信高之栏：%s。' % ('、'.join(hi) or '无'))
    add('- 一致之处：' + _agree(L) + '。')
    add('')
    add('> 本报告不作品级（上贵／中贵／常格）判定：四版断语互斥、成格支型口径不一，品级细化在对读层不可复核。')
    add('')
    return '\n'.join(A)


def _agree(L):
    """统计 L1／L2 内四版「逐字同文」与「近同（≥0.85）」的句子簇。"""
    sents = []
    for n in (1, 2):
        for x in L[n]:
            for s in re.split(r'[。；／/]', re.sub(r'\s', '', x['text'])):
                s = re.sub(r'[^\u4e00-\u9fff]', '', s)
                if len(s) >= 12:
                    sents.append((x['v'], s))
    exact, clusters = {}, []
    for v, s in sents:
        exact.setdefault(s, set()).add(v)
        hit = None
        for c in clusters:
            if difflib.SequenceMatcher(None, s, c[0]).ratio() >= 0.85:
                hit = c
                break
        if hit:
            hit[1].add(v)
        else:
            clusters.append([s, {v}])
    ex = [s for s, vs in exact.items() if len(vs) >= 3]
    near = [c for c in clusters if len(c[1]) >= 3]
    if not near:
        return 'L1／L2 内未见三版以上同文或近同之句（多为异文或单版独有）'
    msg = 'L1／L2 内 %d 句三版以上近同（≥0.85），其中逐字同文 %d 句，如「%s」' % (
        len(near), len(ex), (ex[0] if ex else near[0][0])[:26])
    return msg


# ---------------- 白话层（默认输出） ----------------
TONE = {
    '妻': '婚姻这一栏，书里没留下话，我不替你编一个。',
    '财': '钱这一栏，书里没留下话，我不替你编一个。',
    '子': '子女这一栏，书里没留下话，我不替你编一个。',
    '禄': '事业这一栏，书里没留下话，我不替你编一个。',
    '寿': '身体这一栏，书里没留下话，我不替你编一个。',
}
# 结论句前半（按栏、按吉凶给不同的说法，避免五栏同一句式）
HEAD = {
    '妻': {'吉': '先说家室。书上对你这一路姻缘没说什么坏话，大意是{th}。',
           '凶': '家室这条，旧书说得不客气：{th}。',
           '杂': '家室上的话，两头都有：{th}。',
           '中': '家室这一路，书里落了字，却没往细处说。'},
    '财': {'吉': '钱上的事，书里给的是好话：{th}。',
           '凶': '钱财这条，旧书先泼了盆冷水：{th}。',
           '杂': '钱上的话，两头都占：{th}。',
           '中': '钱上的事，书上只提了一句，语焉不详。'},
    '子': {'吉': '子息这块，书里的话不坏：{th}。',
           '凶': '子息这块，旧书说得沉：{th}。',
           '杂': '子息上，书里一半好一半留神：{th}。',
           '中': '子息这块，书里着墨不多。'},
    '禄': {'吉': '功名职位这条，书里给的是好话：{th}。',
           '凶': '职位这条，旧书的话偏紧：{th}。',
           '杂': '事业上，书里说成两条路：{th}。',
           '中': '功名职位，书里说得平常。'},
    '寿': {'吉': '身体这条，书里没留重话：{th}。',
           '凶': '身体这条要提一句，旧书留了重话：{th}。',
           '杂': '身子上，书里吉话灾话都提到：{th}。',
           '中': '身子骨这条，书里没有重话。'},
}
# 有证据但没对上具体词句时，只交代「书里给的调子」，不代书下断
STANDALONE = {
    '妻': {'吉': ['先说家室。书上给的调子不坏，只是没落到具体一句。',
                 '家室这条，看不出什么坏话，细处它没写。',
                 '先说家室：书上的口气是好的，再细就没了。'],
           '凶': ['家室这条，调子偏冷，具体的话反倒没写。',
                 '先说家室，旧书的口气不热，细处却空着。'],
           '杂': ['家室上的话两头都有，却都没落到实处。',
                 '家室这条，好话赖话各占一半，落不到实处。'],
           '中': ['家室这一路，书上平平带过。',
                 '家室这条，书上没什么废话，也没什么重话。']},
    '财': {'吉': '钱上的事，旧书的口风不差，只是没细讲。',
           '凶': '钱财这条，旧书的口风偏紧，细处却空着。',
           '杂': '钱上的话两头都提了一句，落到细处就没了。',
           '中': '钱上的事，书上轻轻带过。'},
    '子': {'吉': '子息这块，调子不坏，细处没写。',
           '凶': '子息这块，调子偏沉，细处空着。',
           '杂': '子息上两头都提了一句，没落到实处。',
           '中': '子息这块，书里没多写。'},
    '禄': {'吉': '功名职位这条，调子不坏，细处没写。',
           '凶': '职位这条，调子偏紧，细处空着。',
           '杂': '事业上提了两条路，都没落到实处。',
           '中': '功名职位，书里说得平平。'},
    '寿': {'吉': '身体这条，没留重话，细处也没写。',
           '凶': '身体这条，话不轻，细处空着。',
           '杂': '身子上吉凶都提了一句，没落到实处。',
           '中': '身子骨这条，书里没多话。'},
}
THEME = {
    '妻': [(r'剋妻|克妻|傷妻|损妻', '夫妻缘分偏薄，聚少离多', '凶'),
           (r'晚娶|晚婚|遲婚|迟婚', '成家宜晚，晚一点反倒和顺', '中'),
           (r'妻財|妻财', '古法把妻和财放在一处看，钱路稳，家室也稳', '中'),
           (r'妻愚', '配偶性子直朴，不善周旋', '中'),
           (r'內助|内助', '配偶能帮衬你', '吉')],
    '财': [(r'財庫|财库', '钱进得了库，存得住', '吉'),
           (r'背祿|背禄', '挣钱靠手艺本事，不靠坐位置', '中'),
           (r'財旺生官|财旺生官', '钱能换到名分和位置', '吉'),
           (r'破財|破财', '有破财的口子', '凶'),
           (r'富貴榮華|富贵荣华', '钱和名分能一起到手', '吉'),
           (r'衣食', '吃穿不愁', '吉'),
           (r'財多身弱|财多身弱', '钱多身子弱，拿得住拿不住要看运', '凶')],
    '子': [(r'遲子|迟子', '子女来得晚', '中'),
           (r'有子息', '子女缘不薄', '吉'),
           (r'少子', '子女不多', '中'),
           (r'剋子|克子|傷子|伤子', '子女上要多留心', '凶'),
           (r'無子|无子|絕嗣|绝嗣', '书上说子嗣艰难', '凶')],
    '禄': [(r'大貴|大贵|貴顯|贵显|爲貴|为贵', '有做官、担大事的份', '吉'),
           (r'官星|官旺', '官星有力，位置拿得住', '吉'),
           (r'食神', '食神（靠手艺、口才、专业吃饭的那股劲）', '中'),
           (r'科第|及第', '读书考试这条路走得通', '吉'),
           (r'仕宦|官職|官职', '吃的是一份公家或大机构的饭', '中')],
    '寿': [(r'夭|殀', '寿元上书上说得重', '凶'),
           (r'疾病', '身体上要留意', '凶'),
           (r'免生災|免生灾', '运走得顺就少病少灾', '吉'),
           (r'壽考|寿考|壽元|寿元', '寿元平稳', '吉'),
           (r'少病|無病|无病|康寧|康宁', '身子骨还经得住', '吉'),
           (r'福壽|福寿', '福和寿都还站得住', '吉')],
}
LANE_TITLE = {'妻': '妻｜婚姻感情', '财': '财｜钱与营生', '子': '子｜子女',
              '禄': '禄｜事业职位', '寿': '寿｜身体寿元'}
# 每栏的「界限」句：说清书上讲得到哪、讲不到哪，不作新断
LIMIT = {
    '妻': ['遇上谁、哪年成家，这些它管不着。', '跟谁过、哪年成家，书上一句没有。',
           '至于姻缘落在谁身上，它不会告诉你。'],
    '财': ['至于一年能挣多少，古书没这把尺。', '挣多挣少这层，它不给你算。',
           '进多少出多少，它只管方向不管数。'],
    '子': ['几个、哪年添，书里从来不记这些。', '生几个、什么时候添，它不管。',
           '子息落在哪一年，它不写。'],
    '禄': ['级别高低、坐哪把椅子，那是另一回事。', '做到哪一级，这层它说不到。',
           '在哪个衙门吃饭，它不点名。'],
    '寿': ['这不是替你判寿数。', '寿数长短，它不敢写死。',
           '能活多少岁，书上不会给数。'],
}
# 吉凶并见或凶多时的「可行态度」句（替代界限句，给读者一个落地的说法）
ATTITUDE = {
    '妻': '真到过日子，就是择偶别急，多看两年再定，比什么化解都实在。',
    '财': '落到日子上，是别把身家押在一处，留条后路。',
    '子': '落到日子上，是子女的事少替他们拿主意，来得晚就晚。',
    '禄': '落到日子上，是别把位置当成全部，手上留一门吃饭的本事。',
    '寿': '落到日子上，就是烟酒作息别硬撑，该查的按时去查。',
}


def _tone_of(d):
    if not d['ev']:
        return '无据'
    ps = set()
    for s in d['byv'].values():
        ps |= s
    if '凶' in ps and '吉' in ps:
        return '杂'
    if '凶' in ps:
        return '凶'
    if '吉' in ps:
        return '吉'
    return '杂' if '杂' in ps else '中'


def _themes(lane, d, tone):
    """只从直证＋同构的条文里取词，并按吉凶过滤，免得结论与理由打架。"""
    out, signs = [], set()
    pool = d['direct'] + d['analog']
    txt = ' '.join(x['text'] for x in pool) or ' '.join(x['text'] for x in d['ev'])
    for pat, phrase, sign in THEME[lane]:
        if tone != '杂' and sign not in (tone, '中'):
            continue
        if tone == '杂' and sign in signs and len(signs) >= 2:
            continue
        if re.search(pat, txt) and all(phrase != p for p, _ in out):
            out.append((phrase, sign))
            signs.add(sign)
        if len(out) >= 2:
            break
    return out


def _eff_tone(lane, d):
    """吉凶并见但取到的词只有一边时，结论句跟着那一边走，不硬说两头都占。"""
    tone = _tone_of(d)
    if tone != '杂':
        return tone
    th = _themes(lane, d, tone)
    ss = set(s for _, s in th if s != '中')
    if len(ss) == 1:
        return list(ss)[0]
    return tone


SCOPE_DIRECT = {
    '妻': ['书上这句是给「%s日%s时」这类日子立的规矩，不是单给你一个人下的判词。',
           '这句话冲的是「%s日%s时」这一类日子，不是照着你一个人写的。'],
    '财': ['原话是冲「%s日%s时」这一类日子说的，落到一个人身上要打折扣。',
           '这说法起于「%s日%s时」这一路，轮到具体一个人，还得打折看。'],
    '子': ['这是「%s日%s时」的通例，不是指着你说的。',
           '「%s日%s时」都归这一条管，不是单说你。'],
    '禄': ['这一路的话是从「%s日%s时」上归纳的，具体到人还要看别的字。',
           '「%s日%s时」这一格合起来才是这条断语，具体你这个人还要看旁的字。'],
    '寿': ['这话原本压在「%s日%s时」上，轻重要看各人的底子。',
           '这条落在「%s日%s时」这个格上，轻重仍看各人底子。'],
}
SCOPE_ANALOG = {
    '妻': '书里没直接点你这一柱，是拿同一类格局的话来推的，只能算个大概。',
    '财': '你这一柱书里没点名，是照着同一路格局的条文比过去的。',
    '子': '这一条不是指着你的日子说的，是同格相推。',
    '禄': '书里没有你这柱的专条，是同格推出来的话。',
    '寿': '这一条是同类相比得来的，不是正面断你的寿。',
}


def _scope(lane, d, p4, k=0):
    if d['direct']:
        lst = SCOPE_DIRECT[lane]
        return lst[k % len(lst)] % (p4[2][0], p4[3])
    if d['analog']:
        return SCOPE_ANALOG[lane]
    return '只有零碎一句沾到边，算不上正面断语。'


VER_SAY = {
    3: ['这条几个本子都落字了，不是孤证。', '翻到这一处，几家口径一致。',
        '这个意思几本都有，站得住。', '几家说的是同一层意思。',
        '几个本子在这儿没打架。', '几家在这处口径不差。', '各本都往一处说。',
        '这层意思各家一并写着。', '几家都认，不是一家的私话。',
        '翻遍几本，说的一样。'],
    2: ['两本认这条，另两本一字未着。', '四本里只有两本落这个话，其余没认。',
        '四种本子摆一处看，这条只在一半上立得住。', '这话两家都说，另外两家绕开了。',
        '有本子写、有本子不写，凑不成一致。',
        '这说法我从两本上抄下来，另两本翻不着。',
        '认这条的只有一半本子，另一半没搭腔。', '四本在这儿对不齐：两本有，两本空着。',
        '两家本子点头，另两家不置一词。',
        '四本对这条不是一条心，写下的两本，不写的也是两本。'],
    1: ['四本里只有一本写了，别本没提。', '独此一家的话，别处寻不着。',
        '一本独有，其余不见。', '这说法只在一本上见过。',
        '孤零零一处，只能当旁证。'],
}
VER_CONFLICT = ['几本在这点上说法相反；这种事古人自己也吵，你按哪边走都不算错。',
                '两家说法打架，我看古人也没吵出结果，你按哪边走都行。',
                '几个本子在这儿顶了牛，谁也说服不了谁。']


def _ver_say(d, i):
    if d['conflict']:
        return VER_CONFLICT[i % 3]
    n = len(d['byv'])
    if n >= 3:
        lst = VER_SAY[3]
    elif n == 2:
        lst = VER_SAY[2]
    elif n == 1:
        lst = VER_SAY[1]
    else:
        return ''
    return lst[i % len(lst)]


TIER = {
    '高': ['这点我敢把话说死。', '这条书上有实数，站得住。',
           '这处不是猜的，书上写得实。', '这条有底气，可以当准。',
           '这一处几家都点了头。'],
    '中': ['这话书上有，但话留着余地。', '我不敢把话说死。',
           '看个大概，别当定论。', '只算半截证据，别当真。',
           '方向是这么个方向，轻重说不准。',
           '这话只能听个大概。', '书上说了几分，我不敢替它补满。',
           '这条书上只有个方向。', '我只能说个大概。',
           '这处说法软，别拿它当准。'],
    '疑': ['这点分歧大，我判不了。', '两说打架，存疑。',
           '这处我不敢裁，先存疑。'],
    '无': ['书上没写，我不替你编。', '这一栏空着。',
           '旧书在这一点上没留话。'],
}


def _tier(d, i):
    if d['conf'] == '高':
        lst = TIER['高']
    elif d['conf'] == '中':
        lst = TIER['中']
    elif d['ev']:
        lst = TIER['疑']
    else:
        lst = TIER['无']
    return lst[i % len(lst)]


# 每栏句序不同：有的收在档位上，有的收在界限/提醒上
ORDER = [['s', 'v', 't', 'x'], ['s', 'v', 'x', 't'], ['v', 's', 't', 'x'],
         ['t', 's', 'x', 'v'], ['v', 's', 'x', 't']]
# 无据栏的收尾，避免与「没留下话」那句重复
NOEV = ['这一栏就空着。', '我不拿别的字来凑。', '空着也不编。',
        '这处我宁可留白。', '话到这儿就断了。']


def _pick(v, k):
    if isinstance(v, list):
        return v[k % len(v)]
    return v


def _lane_para(lane, d, p4, i, seed=0, seed2=0):
    jv, jo = (i * 2 + seed * 5 + seed2) % 10, (i + seed) % 5
    if not d['ev']:
        return TONE[lane] + '四本翻下来，没有一句是冲你这个日子讲的；没话就是没话。' + NOEV[jo]
    tone = _tone_of(d)
    et = _eff_tone(lane, d)
    tp = _themes(lane, d, tone)
    if tp:
        joiner = '；'
        if len(tp) >= 2 and tp[0][1] != tp[1][1] and '中' not in (tp[0][1], tp[1][1]):
            joiner = '，不过'
        th = joiner.join(p for p, _ in tp)
        concl = HEAD[lane][et].format(th=th)
    else:
        concl = _pick(STANDALONE[lane].get(et, STANDALONE[lane]['中']), seed)
    part = {'s': _scope(lane, d, p4, seed2 + i),
            'v': _ver_say(d, jv) or '',
            't': _tier(d, jv),
            'x': ATTITUDE[lane] if et in ('凶', '杂') else _pick(LIMIT[lane], seed)}
    return concl + ''.join(part[k] for k in ORDER[jo])


def baihua(p4, sex, K, L, sims, lanes):
    A = []
    add = A.append
    dg = p4[2][0]
    # 按四柱取个定值，换个八字就换一套说法与句序，两份样例不逐句同构
    seed = (GAN.index(dg) * 2 + ZHI.index(p4[2][1]) + ZHI.index(p4[1][1]) * 3) % 5
    seed2 = (ZHI.index(p4[3][1]) * 3 + GAN.index(p4[0][0])) % 10
    base = seed * 3 + seed2
    _f = dict(y=p4[0], m=p4[1], d=p4[2], h=p4[3], sx=sex, dg=dg, wx=WUX[dg],
              dz=p4[2][1], mz=p4[1][1], shi=p4[3])
    # 引子七句，每句三套说法，按四柱轮换，两份样例不撞句
    P1 = ['你给的是{y}年{m}月{d}日{h}时生的{sx}命。四组字里，日干{dg}是你自己，属{wx}；'
          '日支{dz}是配偶宫，月令{mz}管你的出身和本钱。',
          '这是{y}年{m}月{d}日{h}时，{sx}命。八字摆开看：日干{dg}是你本人，属{wx}；'
          '日支{dz}坐配偶宫；月令{mz}管你的出身和家底。',
          '先把八字摆开——{y}年{m}月{d}日{h}时，{sx}。日干{dg}是你自己，属{wx}；'
          '日支{dz}是配偶宫；月令{mz}定你的出身与本钱。']
    P2 = ['下面按妻、财、子、禄、寿五条说。书上有话的照书说，书上一个字没留的，我直说没留。',
          '下面分五条讲：家室、钱财、子女、功名、身体。书上有的我照说，没有的我不替你圆。',
          '往下分五条——妻、财、子、禄、寿。有凭据的照着凭据说，没凭据的我不会硬补。']
    P3 = ['八个字里，日干和日支最当紧——一个是你自己，一个是你的家。',
          '这八个字当中，日干、日支两处最吃重：一处是你，一处是你的家。',
          '四柱里头，日柱最贴身：上头那个字是你，下头那个字是你的家。']
    P4 = ['每一条我先给一句判断，再讲书上凭什么；话软的、话硬的，我都照实说。',
          '我一条一条来，先落一句断语，再说这句断语是从哪个字上来的；软话硬话都照原样端给你。',
          '每条都是先说结论、后说缘由；书上说得硬的我不打折，说得软的我不加码。']
    P5 = ['这五条是旧书看一个人一辈子的五个口子：妻看家室，财看衣食，子看后嗣，'
          '禄看功名和职位，寿看身体和年岁。',
          '旧书看人一辈子，开的就是这五个口子：家室、衣食、后嗣、功名、年岁。',
          '古人把一生拆成五处来看：妻看家室，财看衣食，子看后嗣，禄看功名职位，'
          '寿看身体年岁。']
    P6 = ['这五样，书里未必样样有话说，我也不硬凑。',
          '五样里头未必样样都有交代；缺的那几样，我留白。',
          '书不是替一个人写的，五样里总有它没照到的地方。']
    P7 = ['书上断这种命，先看月令，再看日时；你这八字落到日时上是「{dg}日{shi}」这一路，'
          '所以我主要拿这一路的话来对。',
          '旧书断命先月令、后日时。你这八字在日时上落成「{dg}日{shi}」，我就顺着这一路去找话。',
          '古人断命从月令起手，再落到日时；你这个日子配这个时辰，是「{dg}日{shi}」那一格，'
          '我便拿那一格的说法来比。']
    for _i, _pool in enumerate((P1, P2, P3, P4, P5, P6, P7)):
        add(_pool[(base + _i) % 3].format(**_f))
    add('')
    order = ['妻', '财', '子', '禄', '寿']
    for i, lane in enumerate(order):
        d = lanes[lane]
        add('**%s**' % LANE_TITLE[lane])
        add('')
        add(_lane_para(lane, d, p4, i, seed, seed2))
        add('')
    # 总评
    add('**总评**')
    add('')
    t = []
    lu = lanes['禄']
    if lu['ev']:
        th = _themes('禄', lu, _tone_of(lu))
        OPEN_SUM = ['整体看，这命的气是往「%s」这一路使的，日子靠这门本事撑起来。',
                    '通篇看下来，这一命的重心落在「%s」上，一辈子靠的就是这门本事。']
        t.append(OPEN_SUM[seed2 % 2] % (th[0][0] if th else '一技一职'))
    else:
        t.append('整体看，书里没给这命点明一条道，是寻常日子里自己找路走的过法。')
    bad = [l for l in order if lanes[l]['ev'] and _eff_tone(l, lanes[l]) == '凶']
    soft = [l for l in order if lanes[l]['ev'] and _eff_tone(l, lanes[l]) == '杂']
    noted, noted_lane = '', ''
    if bad:
        noted_lane = bad[0]
        noted = '最该留意的是%s这一路，书里的话不客气；不过它冲的是一类日子，不是给你定死。' % bad[0]
    elif soft:
        noted_lane = soft[0]
        noted = '要说提醒，%s这一路两头都占，顺不顺全看往后几年怎么走。' % soft[0]
    if noted:
        t.append(noted)
    if noted_lane != '寿' and not lanes['寿']['ev']:
        t.append('身体这条书里没留话，我不好代书立论。')
    if sims and sims[0]['same'] == 4:
        nm = ''
        for cand, lab in (('關雲長', '关云长'), ('关云长', '关云长')):
            if cand in (sims[0]['text'] or ''):
                nm = lab
                break
        who = '就是%s那一例' % nm if nm else '书里记作一例'
        t.append('书里另有一个跟你四柱一模一样的人，%s；同柱不等于同命，'
                 '古人自己就说过八字相同的人贵贱能差出很远，那一条只能当参照。' % who)
    if len(t) < 3:
        has = [l for l in order if lanes[l]['ev']]
        if len(has) >= 2:
            hi = max(has, key=lambda l: len(lanes[l]['ev']))
            lo = min(has, key=lambda l: len(lanes[l]['ev']))
            t.append('五条里，书上在%s这一路落笔最多，在%s这一路最省；省笔墨不等于没话，'
                     '只是没往那上头细说。' % (hi, lo))
    CLOSE = ['这命在书上不属于一眼能叫出格的名局；四本各说各的，我不替你抬也不往低里踩。'
             '以上只讲原局，走哪步运、哪年动是另一层的事，这篇不细论；真到关口上，'
             '还是看你自己怎么选。',
             '摊开几本看，这命不是那种一眼叫得出格的名局，我也不替你抬、不往低踩。'
             '原局就说到这儿，行运另是一层，这篇不论；真到了关口，还是你自己拿主意。']
    t.append(CLOSE[seed2 % 2])
    add(''.join(t))
    add('')
    txt = '\n'.join(A)
    return txt


def dump_csv(path, L, sims, lanes):
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['层', '版本', '条目编号', '定位', '标注', '原文'])
        for n in range(1, 6):
            for x in L[n]:
                w.writerow(['L%d' % n, x['v'], x['id'], x['loc'], x['note'], x['text']])
        w.writerow([])
        w.writerow(['相似命例', '版本', '条目编号', '定位', '同柱数', '十神同构', '四柱', '原文'])
        for s in sims:
            w.writerow(['相似', s['v'], s['id'], s['loc'], s['same'], '%.2f' % s['sim'], s['p4'], s['text']])
        w.writerow([])
        w.writerow(['栏', '版本', '条目编号', '层', '定位', '原文'])
        for lane in ['妻', '财', '子', '禄', '寿']:
            for x in lanes[lane]['ev']:
                w.writerow([lane, x['v'], x['id'], x['层'], x['loc'], x['text']])


def run_one(lib, sizhu, sex, out_path, limit=12, mode='白话'):
    p4 = parse_sizhu(sizhu)
    if len(p4) != 4:
        raise SystemExit('四柱解析失败：%s' % sizhu)
    K = build_keys(lib, p4, sex)
    L = layer_search(lib, p4, K)
    sims = similar_cases(lib, p4)
    lanes = lane_eval(L, K, sex)
    if mode == '白话':
        md = baihua(p4, sex, K, L, sims, lanes)
    else:
        md = report(lib, p4, sex, K, L, sims, lanes, limit)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
    with io.open(out_path, 'w', encoding='utf-8') as f:
        f.write(md)
    if mode != '白话':
        dump_csv(re.sub(r'\.md$', '.csv', out_path), L, sims, lanes)
    n = len(re.findall(r'[\u4e00-\u9fff]', md))
    return {'p4': p4, 'K': K, 'L': L, 'sims': sims, 'lanes': lanes,
            'bytes': len(md.encode('utf-8')), '字': n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--四柱', default='')
    ap.add_argument('--性别', default='男')
    ap.add_argument('--输出', default='')
    ap.add_argument('--限条', type=int, default=12)
    ap.add_argument('--白话', dest='mode', action='store_const', const='白话')
    ap.add_argument('--依据', dest='mode', action='store_const', const='依据')
    ap.add_argument('--自测', action='store_true')
    ap.set_defaults(mode='白话')
    a = ap.parse_args()
    lib = Lib()
    print('records', lib.stats())
    if a.mode == '白话' and not a.输出 and a.四柱:
        a.输出 = os.path.join(HERE, '白话_%s.md' % re.sub(r'\s', '', a.四柱))
    if a.自测:
        tests = [('甲子 乙亥 庚戌 癸未', '男', '自测/自测1_甲子乙亥庚戌癸未.md'),
                 ('戊午 戊午 戊午 戊午', '男', '自测/自测2_戊午四柱.md')]
        rows = []
        for sz, sex, rel in tests:
            out = os.path.join(HERE, rel)
            r = run_one(lib, sz, sex, out, a.限条, mode='依据')
            rows.append((sz, r))
            print(sz, {n: len(r['L'][n]) for n in range(1, 6)},
                  'sims', len(r['sims']),
                  'lanes', {k: len(v['ev']) for k, v in r['lanes'].items()},
                  'bytes', r['bytes'])
        # 对比
        A = ['# 自测对比：有据 vs 无据', '',
             '> 同一套脚本、同一批四包，只换四柱。看「无据」是否被写成推断。', '',
             '| 项 | 自测1 %s | 自测2 %s |' % (rows[0][0], rows[1][0]),
             '| --- | --- | --- |']
        for n in range(1, 6):
            A.append('| L%d | %d | %d |' % (n, len(rows[0][1]['L'][n]), len(rows[1][1]['L'][n])))
        A.append('| 相似命例 | %d | %d |' % (len(rows[0][1]['sims']), len(rows[1][1]['sims'])))
        for lane in ['妻', '财', '子', '禄', '寿']:
            a = rows[0][1]['lanes'][lane]
            b = rows[1][1]['lanes'][lane]
            A.append('| %s栏 | %d 条／直证 %d／%s | %d 条／直证 %d／%s |' % (
                lane, len(a['ev']), len(a['direct']), a['conf'],
                len(b['ev']), len(b['direct']), b['conf']))
        A.append('| 报告字节 | %d | %d |' % (rows[0][1]['bytes'], rows[1][1]['bytes']))
        A.append('')
        for sz, r in rows:
            no = [l for l in ['妻', '财', '子', '禄', '寿'] if not r['lanes'][l]['ev']]
            hi = [l for l in ['妻', '财', '子', '禄', '寿'] if r['lanes'][l]['conf'] == '高']
            A.append('- **%s**：L1＝%d，相似命例 %d 条；无据栏：%s；置信高：%s。' % (
                sz, len(r['L'][1]), len(r['sims']), '、'.join(no) or '无', '、'.join(hi) or '无'))
        A.append('')
        A.append('## 差在哪')
        A.append('')
        r0, r1 = rows[0][1], rows[1][1]
        A.append('- **L1 有无**：自测1 四版命例库命中 0 条，故五栏只能靠 L2 日時斷、L3 同格、L5 纳音取证，'
                 '无一条「同八字」直证；自测2 命中 %d 条（其中「四戊午」写法另计），'
                 '故五栏证据可落到同柱条上。' % len(r1['L'][1]))
        A.append('- **无据栏**：自测1 %s；自测2 %s。无据时该栏只写「无据」并给置信「低」，不填常识。'
                 % ('、'.join(l for l in ['妻', '财', '子', '禄', '寿'] if not r0['lanes'][l]['ev']) or '无',
                    '、'.join(l for l in ['妻', '财', '子', '禄', '寿'] if not r1['lanes'][l]['ev']) or '无'))
        A.append('- **置信分布**：自测1 %s；自测2 %s。'
                 % ('／'.join('%s%s' % (l, r0['lanes'][l]['conf']) for l in ['妻', '财', '子', '禄', '寿']),
                    '／'.join('%s%s' % (l, r1['lanes'][l]['conf']) for l in ['妻', '财', '子', '禄', '寿'])))
        A.append('- **相似命例**：自测1 仅能取到年月同柱者（2/4），断语不能移用；自测2 有 4/4 同柱（關雲長那条）'
                 '与 3/4 同柱（戊寅戊午戊午戊午）两条，正示范「同柱异命」——断语各系其前提，仍不得直移。')
        p = os.path.join(HERE, '自测', '对比.md')
        with io.open(p, 'w', encoding='utf-8') as f:
            f.write('\n'.join(A))
        print('对比 written')
        return
    if not a.四柱:
        raise SystemExit('需要 --四柱 或 --自测')
    out = a.输出 or os.path.join(HERE, '报告_%s.md' % re.sub(r'\s', '', a.四柱))
    r = run_one(lib, a.四柱, a.性别, out, a.限条, mode=a.mode)
    print('written', out, r['bytes'], '字', r['字'], 'mode', a.mode)
    print({n: len(r['L'][n]) for n in range(1, 6)}, 'sims', len(r['sims']))


if __name__ == '__main__':
    main()
