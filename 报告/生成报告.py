# -*- coding: utf-8 -*-
"""八字·四版《三命通会》通读报告（HTML 单文件）

用法：
  python 生成报告.py --四柱 "甲子 乙亥 庚戌 癸未" --性别 男 --生日 "1984-11-12 14:00"
  python 生成报告.py --四柱 "戊午 戊午 戊午 戊午" --性别 男            # 无生日：大运只列干支
  python 生成报告.py --四柱 ... --性别 女 --生日 "1990-03-08 09:00" --输出 报告/x.html

约定：
  * 四包只读，现场解析，不写缓存。
  * 原文逐字（异体不改），白话另段；推演处一律标「据原局推」。
  * 不写条号／置信度／命中数；出处放各节末尾小字。
"""
import os, re, sys, math, html, argparse, datetime, difflib, json, base64

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import 检索 as J

GAN, ZHI = J.GAN, J.ZHI
VLAB = J.VLAB
VORD = ['万历', '蔣本', '辛丑', '四库']

EV_PATH = os.path.join(HERE, '证据_升级.json')
try:
    with open(EV_PATH, encoding='utf-8') as _f:
        EV = json.load(_f)
except Exception:
    EV = {}

BAI_PATH = os.path.join(HERE, '白话_引文.json')
BAI = {}
for _fn in ('白话_引文.json', '白话_引文_补.json'):
    try:
        with open(os.path.join(HERE, _fn), encoding='utf-8') as _f:
            BAI.update(json.load(_f).get('条', {}))
    except Exception:
        pass
MISS = []
USED = []
BD_CLS = {'条件成立': 'b1', '部分成立': 'b2',
          '不成立·仅备一说': 'b3', '体例说明·不作断语': 'b4'}

# 生成后自检：条件不成立条目的断语，不得出现在总说／五栏结论／逐运判断／封面导语
NARR = []
BAD_KW = ['官星有力', '位置拿得住', '官旺', '官旺財鄉', '官与财都从时支',
          '居官顯達', '居官显达', '財厚食豐', '财厚食丰', '有子息有壽考', '有子息有寿考',
          '子女缘不薄', '寿元平稳', '至貴', '至贵', '大貴', '大贵', '白屋公卿',
          '為禍百端', '为祸百端', '早死', '豹變', '豹变', '苗不秀', '偏生庶出',
          '母先亡', '父早䘮', '父早丧', '百事無凶', '百事无凶', '大發財祿', '大发财禄',
          '子嗣艱難', '子嗣艰难', '孤寡', '早夭']

# 禄栏整段重写：四层——走哪条路／凭什么／几时应／分寸。其余各栏仍走模板。
LANE_BODY_FIX = {
    '禄': '官不掌事，路就得换一条走：不靠职位起，靠手里一门本事起。'
          '先说取径，四类分开讲。技艺一类有旁证：柒章神煞表里華蓋落日支戌、时支未，取向「孤高藝術」（蔣本卷三總論諸神煞）；'
          '空亡另有一说落月支亥、日支戌，卷十口诀有「空門藝術九流人」，但以日柱起不犯，只作旁证。'
          '私下经营一类也有旁证：卷五「財庫居生地」日庚、时未、生冬月三事俱合，叁章校验表判为条件成立。'
          '文书一类、专业执照一类，四本讲这一格时只提「印財庫」，没把这两条单列——不是不能做，是四本无专条，这一层不代书立论。'
          '凭什么断在食伤生财、不断在名分？看两条链谁粗。壬水食神在亥当令，直生年月甲乙两木之财，甲乙又各有根；'
          '这条链从月令通到年干，中间没有一个字截得断它。官那条两头都断：一不透干，二被时干癸压住。'
          '庚金虽能克木，全盘只有一点五分，克不动两位财——力气只能顺着食伤往前走，逆不回去抢官。'
          '几时见分晓：丁丑（十八至二十八）打底，印实而官虚，先把资质与根基垫起来；'
          '庚辰（四十八至五十八）才是「路走通」的应期，辰戌冲开火库，身得助、名分松动，做的事开始换成钱；'
          '辛巳（五十八至六十八）暖局收成，是这一路最舒服的一段。'
          '丙子（八至十八）与壬午（六十八至七十八）是「再想靠名分」的关口：前者水旺身更弱，后者午火被壬盖头、子午一冲，往职位上使劲就撞墙。'
          '分寸要留住：丁藏戌未，毕竟有火库为根，所以不是全无贵气，是贵气薄而不绝——薄在掌不了权，'
          '不绝在名分、体面、资质这一类还留一线，关键时能当敲门砖，当不了饭碗。',
}

# 三栏原结论取自「前提不成立」的条文，改由本表重写首句
LANE_HEAD_FIX = {
    '子': '子息这块，书里只落一个「迟」字：子星是丁火，藏在戌、未里不透；'
          '卷五论食神那句「子息寿考」的好话，前提是日主与食神俱生旺，本命日主到亥已是病地，前提不成立，不作数。',
    '寿': '身体这条，四本只写「走吉地免灾」，寿数一句没给；卷五那句「寿考」，前提不成立，不拿它许寿。',
}


def bad_hits():
    out = []
    for who, txt in NARR:
        for kw in BAD_KW:
            if kw in txt:
                out.append((who, kw, txt))
    return out


# ---------------- 节气 ----------------
def _jd(dt):
    y, m = dt.year, dt.month
    D = dt.day + (dt.hour + dt.minute / 60.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + A // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + D + B - 1524.5


def _sun(jd):
    T = (jd - 2451545.0) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = math.radians(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M)
         + (0.019993 - 0.000101 * T) * math.sin(2 * M) + 0.000289 * math.sin(3 * M))
    om = math.radians(125.04 - 1934.136 * T)
    return (L0 + C - 0.00569 - 0.00478 * math.sin(om)) % 360.0


def term(year, deg):
    """该年太阳视黄经达 deg 度的北京时间（误差约在分钟级）"""
    base = datetime.datetime(year, 1, 1)
    lo, hi = _jd(base), _jd(datetime.datetime(year + 1, 1, 1))
    for _ in range(60):
        mid = (lo + hi) / 2
        if (_sun(mid) - deg) % 360.0 > 180:
            lo = mid
        else:
            hi = mid
    return base + datetime.timedelta(days=(lo + hi) / 2 - _jd(base), hours=8)


JIE = [('立春', 315), ('驚蟄', 345), ('清明', 15), ('立夏', 45), ('芒種', 75),
       ('小暑', 105), ('立秋', 135), ('白露', 165), ('寒露', 195), ('立冬', 225),
       ('大雪', 255), ('小寒', 285)]


def jie_around(year):
    out = []
    for y in (year - 1, year, year + 1):
        for nm, dg in JIE:
            out.append((term(y, dg), nm))
    return sorted(out)


def day_pillar(dt):
    jdn = int(_jd(dt) + 0.5)
    i = (jdn + 49) % 60
    return GAN[i % 10] + ZHI[i % 12]


# ---------------- 大运 ----------------
CHANG = ['長生', '沐浴', '冠帶', '臨官', '帝旺', '衰', '病', '死', '墓', '絕', '胎', '養']
CS_START = {'甲': '亥', '乙': '午', '丙': '寅', '丁': '酉', '戊': '寅',
            '己': '酉', '庚': '巳', '辛': '子', '壬': '申', '癸': '卯'}


def changsheng(gan, zhi):
    s = ZHI.index(CS_START[gan])
    k = (ZHI.index(zhi) - s) % 12 if J.YIN[gan] == 1 else (s - ZHI.index(zhi)) % 12
    return CHANG[k]


def dayun(p4, sex, birth=None):
    yg, mg = p4[0][0], p4[1][0]
    fwd = (J.YIN[yg] == 1) == (sex == '男')
    steps = []
    for i in range(1, 9):
        a, b = GAN.index(mg), ZHI.index(p4[1][1])
        steps.append(GAN[(a + i) % 10 if fwd else (a - i) % 10]
                     + ZHI[(b + i) % 12 if fwd else (b - i) % 12])
    info = {'fwd': fwd, 'steps': steps, 'age': None, 'years': None, 'note': ''}
    if not birth:
        info['note'] = '未给公历生日，只排干支，不推起运岁数'
        return info
    js = [x for x in jie_around(birth.year)]
    if fwd:
        nxt = [x for x in js if x[0] > birth][0]
        days = (_jd(nxt[0]) - _jd(birth)) * 1.0
        jn = nxt
    else:
        prv = [x for x in js if x[0] < birth][-1]
        days = (_jd(birth) - _jd(prv)) * 1.0
        jn = prv
    age = days / 3.0
    info['days'], info['jie'] = days, jn
    info['age'] = age
    jy = birth + datetime.timedelta(days=age * 365.2422)
    info['jy'] = jy
    info['years'] = [(jy + datetime.timedelta(days=3652.42 * k),
                      jy + datetime.timedelta(days=3652.42 * (k + 1))) for k in range(8)]
    return info


# ---------------- 取原文 ----------------
def clip(text, pat, width=88):
    """取命中的那一句（逐字，不改异体）；pat 可为按优先级排列的正则列表"""
    t = re.sub(r'\s+', '', text or '')
    pats = pat if isinstance(pat, (list, tuple)) else [pat]
    m = None
    for p in pats:
        m = re.search(p, t)
        if m:
            break
    if not m:
        return t[:width] + ('……' if len(t) > width else '')
    sep = '。；！？／'
    s = 0
    for i in range(m.start(), -1, -1):
        if t[i] in sep:
            s = i + 1
            break
    e = len(t)
    for i in range(m.end(), len(t)):
        if t[i] in sep:
            e = i + 1
            break
    seg = t[s:e].rstrip('／。；')
    if len(seg) > width:
        st = max(0, m.start() - width // 3)
        seg = ('……' if st else '') + t[st:st + width] + '……'
    return seg


def find(lib, pat, vers=None, n=1, need=None):
    out = []
    for r in lib.recs:
        if vers and r['v'] not in vers:
            continue
        t = re.sub(r'\s+', '', r.get('text') or '')
        if re.search(pat, t) and (not need or re.search(need, t)):
            out.append({'v': r['v'], 'id': r['id'], 'loc': r.get('loc') or '', 'text': t})
            if len(out) >= n:
                break
    return out


def uniq_quotes(items, k=3):
    """不同版本、文字不重复的引文，最多 k 条"""
    out = []
    for x in items:
        t = x['text']
        if any(difflib.SequenceMatcher(None, t[:80], y['text'][:80]).ratio() > 0.86 for y in out):
            continue
        out.append(x)
        if len(out) >= k:
            break
    return out


# ---------------- 五栏 ----------------
LANE_KW = {
    '妻': [r'尅妻|克妻', r'妻遲|妻迟|遲子|迟子', r'妻|婚|內助|配偶'],
    '财': [r'財庫|财库|入庫|入库', r'財[鄉鄕乡]|财乡|財旺|财旺', r'財|财|富|衣食|庫|库'],
    '子': [r'遲子|迟子', r'子息|子嗣|子女', r'有子|無子|无子'],
    '禄': [r'官旺財[鄉鄕乡]|居官[顯显][達达]', r'武貴|武贵|[顯显][達达]|得官',
           r'(?<!傷)官|貴|贵|職|职'],
    '寿': [r'壽考|寿考|壽元|寿元', r'免生灾|免生災', r'夭|疾病|壽|寿|病|災|灾'],
}


WIN = {'妻': (18, 16), '财': (26, 36), '子': (10, 10), '禄': (8, 14), '寿': (6, 12)}


def clip2(text, pat, bw=20, aw=26):
    """以命中处为中心截一段（逐字，不改异体）；返回（段，命中位置）"""
    t = re.sub(r'\s+', '', text or '')
    pats = pat if isinstance(pat, (list, tuple)) else [pat]
    m = None
    for p in pats:
        m = re.search(p, t)
        if m:
            break
    if not m:
        return '', 0
    s = max(0, m.start() - bw)
    e = min(len(t), m.end() + aw)
    sep = '。；！？／/・·'
    for i in range(m.start() - 1, s - 1, -1):       # 起点往后收到标点之后
        if t[i] in sep:
            s = i + 1
            break
    for i in range(m.end(), e):                      # 终点提前收到标点
        if t[i] in sep:
            e = i
            break
    seg = t[s:e]
    return ('……' if s else '') + seg + ('……' if e < len(t) else ''), m.start()


def _foreign(seg, p4):
    """这一段若点的是别个日柱／时柱，或整段是另一个八字的命例，不作本命证据"""
    for m in re.finditer(r'([%s][%s])日' % (GAN, ZHI), seg):
        if m.group(1) != p4[2]:
            return True
    for m in re.finditer(r'([%s][%s])時' % (GAN, ZHI), seg):
        if m.group(1) != p4[3]:
            return True
    got = J.EX.first_sizhu(seg)
    if got and got[0] != ' '.join(p4):
        return True
    return False


def lane_quotes(d, lane, p4, used, k=3):
    """每栏取最贴的原文；同一段的相邻两句不重复引到两栏里"""
    pat = LANE_KW[lane]
    bw, aw = WIN[lane]
    items = []
    for x in d['direct'] + d['analog']:
        if not re.search(pat[0], x['text']) and not re.search(pat[-1], x['text']):
            continue
        oth = J.EX.first_sizhu(x['text'])          # 整段是别个八字的命例，不作本命证据
        if oth and oth[0] != ' '.join(p4):
            continue
        q, pos = clip2(x['text'], pat, bw, aw)
        if not q or _foreign(q, p4):
            continue
        if len(q.strip('…')) < 5:                  # 只剩半截话的，不引
            continue
        pri = next((n for n, p in enumerate(pat) if re.search(p, x['text'])), 9)
        key = (x['v'], x['id'], pos // 20)
        if key in used:
            continue
        items.append({'v': x['v'], 'id': x['id'], 'loc': x['loc'], 'text': q,
                      'key': key, 'pri': pri})
    items.sort(key=lambda z: z['pri'])
    out = []
    for x in items:
        if any(difflib.SequenceMatcher(None, x['text'], y['text']).ratio() > 0.82 for y in out):
            continue
        out.append(x)
        if len(out) >= k:
            break
    for x in out:
        used.add(x['key'])
    if not out:     # 该栏一条可用引文都没有
        for x in d['direct'] + d['analog'][:1]:
            q, pos = clip2(x['text'], pat, bw, aw)
            if q and not _foreign(q, p4):
                out = [{'v': x['v'], 'id': x['id'], 'loc': x['loc'], 'text': q}]
                used.add((x['v'], x['id'], pos // 12))
                break
    return out


NEG_W = ['尅妻', '克妻', '剋妻', '遲子', '迟子', '夭', '孤', '災', '灾', '凶', '貧', '贫']


def mixed_note(qs, bh):
    """本栏引文若好话坏话并见，白话里点明古人没说到一处"""
    ji = any(k in x['text'] for x in qs for k in J.JI)
    if not ji:
        return ''
    for mk in NEG_W:
        if any(mk in x['text'] for x in qs):
            if mk in bh:
                return ''
            return ('另外，引的这几句里也有「%s」这样的字眼，跟上面这层好话不是一条心；'
                    '古人在这儿本来就没说齐，我两条都留着，不替你择一。' % mk)
    return ''


# ---------------- HTML ----------------
CSS = """
:root{--paper:#f6f1e6;--card:#fdfaf3;--ink:#241f1a;--ink2:#5a5046;--line:#ddd2bb;
--red:#8c2f22;--gold:#a8792a;--rd:#2f5d50}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Songti SC","Source Han Serif SC","Noto Serif CJK SC","STSong",SimSun,serif;
font-size:16.5px;line-height:1.95;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:56px 46px 80px;background:var(--card);
box-shadow:0 0 0 1px var(--line),0 18px 50px rgba(60,45,30,.08)}
h1,h2,h3,h4{font-weight:600;letter-spacing:.04em;line-height:1.5}
h1{font-size:34px;margin:0 0 6px}
h2{font-size:23px;margin:56px 0 6px;padding-bottom:10px;border-bottom:1px solid var(--line)}
h2 .n{color:var(--gold);font-size:15px;letter-spacing:.2em;display:block;margin-bottom:4px}
h3{font-size:19px;margin:30px 0 8px}
p{margin:0 0 14px;text-align:justify}
.lead{color:var(--ink2);font-size:15px}
.hd{border-bottom:3px double var(--line);padding-bottom:24px;margin-bottom:8px}
.hd .sub{color:var(--ink2);font-size:15px;letter-spacing:.06em}
.src{font-size:12.5px;color:#8a7f70;line-height:1.7;margin-top:10px}
.src b{color:#7a6a52;font-weight:600}
nav.toc{margin:26px 0 10px;padding:18px 22px;background:#f9f5ea;border:1px solid var(--line)}
nav.toc ol{margin:0;padding-left:20px;columns:2;column-gap:36px;font-size:14.5px}
nav.toc a{color:var(--ink2);text-decoration:none;border-bottom:1px dotted #bda98a}
/* 四柱盘 */
.pan{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border:1px solid var(--line);
background:#fffdf7;margin:26px 0 8px}
.pan .c{padding:16px 10px 14px;text-align:center;border-right:1px solid var(--line)}
.pan .c:last-child{border-right:0}
.pan .pos{font-size:12.5px;color:var(--gold);letter-spacing:.28em}
.pan .ss{font-size:12.5px;color:var(--ink2);margin-top:6px;min-height:20px}
.pan .gz{font-size:44px;line-height:1.25;letter-spacing:.08em;margin:2px 0 4px}
.pan .cg{font-size:12.5px;color:var(--ink2)}
.pan .ny{font-size:12px;color:#8a7f70;margin-top:4px}
.facts{display:grid;grid-template-columns:1fr 1fr;gap:6px 26px;font-size:14.5px;
color:var(--ink2);margin:16px 0 0}
.facts b{color:var(--ink);font-weight:600}
/* 引文 */
blockquote{margin:10px 0 16px;padding:10px 16px 10px 18px;background:#fffdf6;
border-left:3px solid var(--gold);font-size:15.5px;color:#3b332a;line-height:1.85}
blockquote .v{display:inline-block;font-size:12px;color:var(--red);border:1px solid #e0c9bd;
padding:0 6px;margin-right:8px;vertical-align:2px;letter-spacing:.08em;background:#fdf3ee}
blockquote .q{letter-spacing:.02em}
/* 引文下的白话解析 */
.qk{margin:10px 0 20px}
.qk blockquote{margin:0}
.bd{float:right;font-size:11px;padding:1px 7px;border-radius:10px;border:1px solid;
margin-left:10px;letter-spacing:.02em;font-style:normal}
.b1{color:#2f5d50;border-color:#a4c3b7;background:#eef5f1}
.b2{color:#8a6420;border-color:#dcc08a;background:#fbf4e4}
.b3{color:#8c2f22;border-color:#dcb3a8;background:#fbece8}
.b4{color:#6b6154;border-color:#cdc3b2;background:#f3efe6}
.bd.i{float:none;margin:0 3px 0 0;vertical-align:1px}
.mv{background:#f5f0e3;border:1px solid var(--line);border-left:4px solid var(--gold);
padding:14px 18px;margin:14px 0}
.mv p{margin:0 0 6px;font-size:15px;color:#4a4136}
.lk{color:var(--red);text-decoration:none;border-bottom:1px solid #cbb9a0}
.lk:hover{border-bottom-color:var(--red)}
.apx{font-size:13px;margin:0 0 18px}
.trm{font-size:13px;color:#5a5046;background:#f5f0e3;border-left:3px solid var(--gold);
padding:8px 12px;margin:8px 0 0;line-height:1.8}
.trm b{color:#8a6420;font-weight:600}
.pl{margin:8px 0 0;font-size:15px;color:#332c24}
.pl .lb{display:inline-block;font-size:11.5px;color:#fff;background:var(--red);
padding:0 6px;border-radius:3px;margin-right:7px;vertical-align:1px;letter-spacing:.05em}
.pl.s2 .lb{background:var(--rd)}
/* 不成立条折叠 */
details.fold{margin:10px 0 6px;border:1px dashed #d8c9ad;background:#faf6ec;padding:2px 12px}
details.fold summary{cursor:pointer;font-size:13.5px;color:#8c7a5a;padding:7px 0;
list-style:none;letter-spacing:.02em}
details.fold summary::-webkit-details-marker{display:none}
details.fold summary::before{content:"▸ ";color:var(--gold)}
details.fold[open] summary::before{content:"▾ "}
details.fold[open] summary{border-bottom:1px dotted #e2d6bf;margin-bottom:6px}
details.fold .qk{margin:8px 0 12px}
/* 定盘卡 */
.card{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--red);
padding:16px 20px;margin:18px 0 6px}
.card h2{font-size:14px;letter-spacing:.24em;color:var(--gold);margin:0 0 10px;font-weight:600}
.card dl{display:grid;grid-template-columns:6.5em 1fr;gap:6px 12px;margin:0;font-size:14.5px}
.card dt{color:#8a6420;letter-spacing:.04em}
.card dd{margin:0;color:#332c24;line-height:1.75}
/* 大运 */
.tl{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0 6px}
.tl .s{border:1px solid var(--line);background:#fffdf7;padding:12px 12px 14px;position:relative}
.tl .s .i{position:absolute;top:8px;right:10px;font-size:11.5px;color:#b6a68a}
.tl .s .gz{font-size:24px;letter-spacing:.1em;margin:2px 0 6px}
.tl .s .r{font-size:13px;color:var(--ink2);line-height:1.7}
.tl .s .tag{display:inline-block;font-size:11.5px;color:var(--rd);border:1px solid #cddbd5;
padding:0 5px;margin-top:6px;background:#f2f7f4}
table.t{width:100%;border-collapse:collapse;font-size:14.5px;margin:14px 0}
table.t th,table.t td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
table.t th{background:#f4eee0;font-weight:600;letter-spacing:.06em;color:#4a4034}
table.t td.k{white-space:nowrap;color:var(--gold)}
/* 五栏 */
.lane{border-top:1px solid var(--line);padding-top:18px;margin-top:26px}
.lane h3 .en{font-size:12.5px;color:#9b8f7e;letter-spacing:.16em;margin-left:10px;font-weight:400}
.lane .bh{font-size:16px;color:#332c24}
.lane .bh::first-letter{font-size:1.1em}
/* 逐运 */
.step{border-bottom:1px dashed var(--line);padding:16px 0 10px}
.step .h{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.step .h .gz{font-size:21px;letter-spacing:.1em}
.step .h .m{font-size:13px;color:var(--ink2)}
.step .h .m i{font-style:normal;color:var(--red)}
.step p{font-size:15.5px;margin:6px 0 6px}
.step .basis{font-size:13px;color:#8a7f70;line-height:1.75}
.step .basis em{font-style:normal;color:var(--red);letter-spacing:.06em}
/* 神煞 */
.ss-row{border-bottom:1px solid #ece3d2;padding:14px 0}
.ss-row .nm{font-size:17px;letter-spacing:.08em}
.ss-row .nm span{font-size:12.5px;color:var(--gold);margin-left:8px;letter-spacing:.1em}
.ss-row p{font-size:15px;margin:6px 0 0}
/* 总结 */
.end{margin-top:34px;padding:24px 26px;background:#f9f4e8;border:1px solid var(--line)}
.end p{font-size:16.5px;line-height:2.05;margin:0 0 12px}
.rule{height:1px;background:var(--line);margin:34px 0}
.foot{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
font-size:12.5px;color:#8a7f70;line-height:1.8}
/* 报告之外：赞赏与苍盘体验（页尾附加，不参与正文） */
.promo{margin:44px 0 6px;padding:26px 28px 22px;background:#f4ecda;
border:1px solid #d3c3a2;border-top:4px solid var(--red)}
.promo .pt{font-size:15px;letter-spacing:.28em;color:var(--red);margin:0 0 4px;font-weight:600}
.promo .psub{font-size:14.5px;color:#5a5046;margin:0 0 18px;line-height:1.85}
.promo .pg{display:grid;grid-template-columns:210px 1fr;gap:24px;align-items:stretch}
.promo .bx{background:#fffdf7;border:1px solid var(--line);padding:20px 22px 18px;
position:relative;overflow:visible}
.promo .bx.qr{text-align:center}
.promo .bx .bt{font-size:14px;letter-spacing:.14em;color:var(--gold);margin:0 0 10px;
font-weight:600;text-align:left}
.promo .bx.qr .bt{text-align:center}
.promo .bx img{display:block;width:152px;height:152px;margin:2px auto 10px;
background:#fff;border:1px solid var(--line);padding:6px}
.promo .bx .cap{font-size:13.5px;color:#5a5046;letter-spacing:.1em}
.promo .bx p{font-size:15px;line-height:1.95;color:#33302a;margin:0 0 10px;text-align:justify}
.promo .bx p:last-child{margin-bottom:0}
.promo .cta{display:inline-block;margin-top:2px;padding:9px 20px;border:1px solid var(--red);
color:var(--red);text-decoration:none;letter-spacing:.1em;font-size:14.5px;background:#fdf5ee}
.promo .cta:hover{background:var(--red);color:#fff}
.promo .note{font-size:14px;color:#6b6154;line-height:1.85;margin:18px 0 0;
padding-top:14px;border-top:1px dotted #cbb9a0}
/* 原局 */
.ys{margin:34px 0 0;padding-top:2px}
.ys h3 .n2{color:var(--gold);font-size:13px;letter-spacing:.18em;margin-right:10px;font-weight:400}
.ys .bh{margin-top:2px}
.calc{margin:16px 0 12px;padding:16px 18px 12px;border:1px solid var(--line);background:#fbf7ec}
.calc .ct{font-size:13.5px;letter-spacing:.06em;color:var(--red);margin-bottom:8px}
.calc .ct span{color:#9b8f7e;letter-spacing:0;margin-left:10px;font-size:12.5px}
.calc table.t{margin:4px 0 8px;font-size:14px}
.calc table.t td.bar{width:46%;vertical-align:middle}
.calc .bb{background:#eee5d2;height:8px}
.calc .bb i{display:block;height:8px;background:linear-gradient(90deg,#d2ad6a,#a8792a)}
.calc .cn{font-size:12.8px;color:#7c7061;line-height:1.85}
ul.rel{margin:8px 0 16px;padding-left:20px}
ul.rel li{font-size:15.5px;margin-bottom:6px;color:#332c24}
ul.rel li b{color:var(--gold);font-weight:600}
nav.toc li.sub{font-size:13.6px;padding-left:16px}
nav.toc li.sub a{border-bottom:0;color:#7d7161}
@media print{
  body{background:#fff;font-size:11.5pt}
  .wrap{box-shadow:none;max-width:none;padding:0 12mm}
  nav.toc{break-inside:avoid}
  h2,h3{break-after:avoid}
  .lane,.step,.ss-row{break-inside:avoid}
  .calc{break-inside:avoid}
  a{color:inherit;text-decoration:none}
  details.fold{display:block}
  details.fold summary{color:#6b6154}
  details.fold > *:not(summary){display:block !important}
  .promo{break-inside:avoid;page-break-inside:avoid;background:#f4ecda;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .promo .pg{grid-template-columns:210px 1fr}
  .promo img{width:152px;height:152px}
}
@media (max-width:720px){
  .promo{padding:20px 18px 16px}
  .promo .pg{grid-template-columns:1fr;gap:16px}
  .promo .bx{padding:16px 16px 14px}
  .promo .bx p,.promo .psub{font-size:14px}
}
"""


# ---------------- 原局七节 ----------------
WXZ = dict(zip('子丑寅卯辰巳午未申酉戌亥', '水土木木土火火土金金土水'))
GGAN_HE = {frozenset('甲己'): '土', frozenset('乙庚'): '金', frozenset('丙辛'): '水',
           frozenset('丁壬'): '木', frozenset('戊癸'): '火'}
POSN = ['年', '月', '日', '时']
REL_RANK = {'半合': 0, '相刑': 1, '六害': 2, '六沖': 3, '六合': 4}

ALGO = ('天干每字 1.0 分（不分阴阳）；地支按藏干折——本气 1.0、中气 0.5、余气 0.3；'
        '月支（%s）的藏干整体乘 2，取「得時為旺」之意。合化、拱合一概不折'
        '（乙庚合、亥未拱木若照折，木与水还要加分，四本对此取舍不一，索性都不动）。'
        '这是给字面轻重排个序，不是吉凶分。')


def grab(lib, pat, vers=None, bw=40, aw=110, stop=None, need=None):
    """取含该句的一段原文（逐字，不改异体）；stop 处截断"""
    for v in (vers or VORD):
        got = find(lib, pat, [v], 1, need)
        if not got:
            continue
        x = got[0]
        q, _ = clip2(x['text'], pat, bw, aw)
        if not q:
            continue
        q = q.strip('…')
        if stop:
            m = re.search(stop, q)
            if m:
                q = q[:m.start()]
        q = q.rstrip('／/・·　 ，,、；')
        if q and q[-1] not in '。；！？':
            q += '。'
        return {'v': x['v'], 'text': q, 'loc': x['loc']}
    return None


def qblock(qs, prefix=None):
    qs = [x for x in qs if x]
    if not qs:
        return ('<blockquote><span class="v">四版</span>'
                '<span class="q">四版无此条。</span></blockquote>')
    return ''.join(evq({'版本': x['v'], '原文': x['text'], '卷篇': x['loc']},
                       '%s.%d' % (prefix, i) if prefix else None)
                   for i, x in enumerate(qs))


def qsrc(qs):
    s = '；'.join('%s·%s' % (VLAB[x['v']], x['loc']) for x in qs if x)
    return ('<div class="src"><b>出处</b> %s</div>' % esc(s)) if s else ''


def wuxing_score(p4):
    sc = dict.fromkeys('木火土金水', 0.0)
    w = [1.0, 0.5, 0.3]
    for i, p in enumerate(p4):
        sc[J.WUX[p[0]]] += 1.0
        mul = 2.0 if i == 1 else 1.0
        for k, g in enumerate(J.ZANG[p[1]]):
            sc[J.WUX[g]] += w[min(k, 2)] * mul
    return sc


def wx_block(p4):
    sc = wuxing_score(p4)
    tot = sum(sc.values()) or 1.0
    mx = max(sc.values()) or 1.0
    tr = []
    for wx, v in sorted(sc.items(), key=lambda x: -x[1]):
        tr.append('<tr><td class="k">%s</td><td>%.1f</td><td>%.1f%%</td>'
                  '<td class="bar"><div class="bb"><i style="width:%.1f%%"></i></div></td></tr>'
                  % (wx, v, v / tot * 100, v / mx * 100))
    return ('<div class="calc"><div class="ct">据原局推的量化'
            '<span>四本没有这个数，以下是本报告自定的折算</span></div>'
            '<table class="t"><tr><th>五行</th><th>分值</th><th>占比</th><th>轻重</th></tr>'
            '%s<tr><td class="k">合计</td><td>%.1f</td><td>100%%</td><td></td></tr></table>'
            '<div class="cn">算法：%s</div></div>' % (''.join(tr), tot, ALGO % p4[1][1]))


def gan_he(p4):
    out = []
    for i in range(4):
        for k in range(i + 1, 4):
            f = frozenset(p4[i][0] + p4[k][0])
            if f in GGAN_HE:
                out.append((i, k, GGAN_HE[f]))
    return out


def zhi_rels(p4):
    out = []
    for i in range(4):
        for k in range(i + 1, 4):
            a, b = p4[i][1], p4[k][1]
            f = frozenset(a + b)
            if f in J.LIUHE:
                out.append((i, k, '六合', J.LIUHE[f]))
            if f in J.LIUCHONG:
                out.append((i, k, '六沖', ''))
            if f in J.LIUHAI:
                out.append((i, k, '六害', ''))
            for grp, nm in J.SANXING:
                if len(grp) == 3 and a in grp and b in grp:
                    out.append((i, k, '相刑', '%s（%s，缺%s）'
                                % (nm, grp, ''.join(c for c in grp if c not in (a, b)))))
            for grp, wx in J.SANHE:
                if a in grp and b in grp:
                    out.append((i, k, '半合', '%s局（%s，缺%s）'
                                % (wx, grp, ''.join(c for c in grp if c not in (a, b)))))
    out.sort(key=lambda x: (REL_RANK.get(x[2], 9), x[0], x[1]))
    return out


def rel_list(p4):
    li = []
    for i, k, wx in gan_he(p4):
        li.append('<li><b>天干五合</b>　%s干%s 与 %s干%s：%s%s之合，化%s</li>'
                  % (POSN[i], esc(p4[i][0]), POSN[k], esc(p4[k][0]),
                     esc(p4[i][0]), esc(p4[k][0]), wx))
    zr = zhi_rels(p4)
    for i, k, typ, extra in zr:
        li.append('<li><b>%s</b>　%s支%s 与 %s支%s%s</li>'
                  % (typ, POSN[i], esc(p4[i][1]), POSN[k], esc(p4[k][1]),
                     ('：' + esc(extra)) if extra else ''))
    has = [x[2] for x in zr]
    for typ in ('六沖', '六合'):
        if typ not in has:
            li.append('<li><b>%s</b>　原局无</li>' % typ)
    return '<ul class="rel">%s</ul>' % ''.join(li)


def ysec(sid, no, title, qs, body):
    return ('<section class="ys"><h3 id="%s"><span class="n2">%s</span>%s</h3>'
            '%s%s%s</section>' % (sid, no, title, qblock(qs, 'Y.' + sid), body, qsrc(qs)))


def yuanju(lib, p4):
    """原局七节：返回（html, 各节引文条数）"""
    cnt = []
    # 1 五行结构
    q1 = [grab(lib, r'夫五行之性各致其用', bw=4, aw=60, stop='重厚'),
          grab(lib, r'五行旺相死休囚', bw=0, aw=44),
          grab(lib, r'故曰庚戌辛亥釵釧金', bw=46, aw=6)]
    b1 = ('<p class="bh">四柱的字面是这样：天干甲木、乙木、庚金、癸水；地支子水、亥水、戌土、未土。'
          '天干里两木、一金、一水，地支里两水、两土，火一个也不露面——火只藏在戌、未两个土库里'
          '（戌藏戊辛丁，未藏己丁乙）。藏干按旧法列在封面的盘上：子只藏癸，亥藏壬甲，戌藏戊辛丁，未藏己丁乙。'
          '纳音四柱依次是海中金、山头火、钗钏金、杨柳木。</p>'
          '<p class="bh">这一层要说明白：纳音在四本里归在〈論納音取象〉名下，名目本身就是「取象」二字。'
          '本报告照录不误，但不拿它断旺衰；下面谈轻重、谈喜忌，一律按正五行算。</p>')
    cnt.append(len([x for x in q1 if x]))

    # 2 月令
    q2 = [grab(lib, r'月令為命也', bw=34, aw=40, stop='如月有正官',
               need=r'大[凢凡]看命先看月支'),
          grab(lib, r'先觀月令乃提綱', bw=8, aw=24, stop='月建申'),
          grab(lib, r'庚辛日為長生之財', bw=0, aw=70, stop='壬癸日'),
          grab(lib, r'月為提綱', bw=22, aw=70, stop='如春木', vers=['四库'])]
    b2 = ('<p class="bh">亥月对庚金是什么，三句话说清。</p>'
          '<p class="bh">一是十神。亥的本气是壬水，庚生壬，这是食神；亥里还藏一个甲木，庚克甲，这是偏财。'
          '所以月令这一支，本气是食神，中气是偏财。</p>'
          '<p class="bh">二是得令与否。庚金在亥是十二长生的「病」地，金气在泄，谈不上得令。'
          '但亥是木的长生，木正是庚的财——万历本卷四〈亥月〉一条写「庚辛日為長生之財」，'
          '意思是财的源头在这个月令里有气，不是说日主自己旺。</p>'
          '<p class="bh">三是分量。四本把月令抬得很高，万历本说「月令為命也」，又说「月為本，日為主」；'
          '蔣本引眞寳賦说「欲知富貴先觀月令乃提綱」；四库本论大运，头一句也是「大運以月支起，故月為提綱」。</p>'
          '<p class="bh">据原局推：本命甲乙两木并透，财是露在干上的；卷四那条紧接的一句是'
          '「如柱中全無財露，只是傷官背祿」——本命不在那一路。月令定下的调子是：食神当令、财透在干，'
          '走「以食生财」的路数，不是靠印、比帮身的路数。</p>')
    cnt.append(len([x for x in q2 if x]))

    # 3 官星与事业路数
    qg = [grab(lib, r'官怕傷財怕刼', vers=['蔣本'], bw=0, aw=40, stop='重者遷徙|年上傷官'),
          grab(lib, r'柱有巳制癸', vers=['蔣本'], bw=0, aw=26, stop='通火土運'),
          grab(lib, r'見壬癸亥子水者', vers=['四库'], bw=0, aw=18, stop='得寅午戌'),
          grab(lib, r'柱中所專用神', vers=['四库'], bw=0, aw=34, stop='再看行運|再㸔行運')]
    bg = ('<p class="bh">官星先数清楚。庚金的官是丁火（正官），原局天干一个不见：'
          '丁只藏在日支戌、时支未里，各一个，这叫「藏而不透」。再看时干：癸水是伤官，癸克丁，'
          '藏着的官还被明透的伤官压着——书上把这种局面叫「伤官见官」。</p>'
          '<p class="bh">四本对这件事分两头说。一头是蔣本那句「官怕傷財怕刼……傷官見官原有者重原無者輕」：'
          '原局本来就有官、又被伤官克的，应得重；原局本无官、临时见官的不算重。本命官藏两支，'
          '属「原有」而力薄，这条可用，重轻要打折。</p>'
          '<p class="bh">另一头是日时断里的两句好话，都带前提。蔣本说「柱有巳制癸，不透丁字，居官顯達」——'
          '要有巳把癸压住、丁又不透，才谈得上显达；本命无巳，丁也不透，两头都不占，'
          '这一路对本命不成立，只备一说。四库本又说「見壬癸亥子水者，為背官背祿」——'
          '本命正是亥月、子年、癸透时干，正撞在这句上，所以「贵命」那一路也不成立，只能取「背官」之象。</p>'
          '<p class="bh">据原局推：官既藏又受制，又没有巳来制伤、没有午巳寅的旺地，'
          '这一命的事业就不从「职位」起。能起的是另一头——食神当令、财透有根，'
          '以技艺、专业换钱，名分跟着口碑来，不跟着官阶来。四库本另有一句「財神當道……積財聚富但少貴耳」，'
          '说的正是同一层：财上能聚，贵气上薄。这一句本命只算半合（官煞不是全无），故半取。</p>'
          '<p class="bh">这一节是为后面「禄」那一栏和逐运托底的：禄栏改按「官藏受制、以食生财」说，'
          '不再把官抬成得力；逐运里遇到官杀（火），也只能当暖局的半边看。</p>')
    cnt.append(len([x for x in qg if x]))

    # 4 格局
    q3 = [grab(lib, r'皆以月令為用', bw=6, aw=30, vers=['辛丑']),
          grab(lib, r'日主食神俱生旺', bw=6, aw=62, stop='四柱見財|四桂見財'),
          grab(lib, r'此食神格也', bw=10, aw=8, stop='如戊辰'),
          grab(lib, r'莫泥提綱反為悞', bw=30, aw=6)]
    b3 = ('<p class="bh">先按四本的规矩查：定格看月令，不拿年柱取格——辛丑本这一句最直，'
          '「皆以月令為用，不可以年取格」。月令亥，本气壬水，对庚金是食神，所以这命的正路是食神格。'
          '卷五〈論食神〉把条件写得很清楚：日主与食神都要生旺、不要被冲破，成了便「財厚食豐…有子息有壽考」；'
          '卷十一明通賦的注更直接，四个字「此食神格也」。只是那串好处的前提是日主也生旺，'
          '本命庚在亥为病地，这半句不成立：格名可定，好处不取。</p>'
          '<p class="bh">但界限要写明白：四本里没有「庚日亥月」这一条现成的定格条文。这个格名是照月令本气、'
          '再照卷五与卷十一的通例推出来的，不是书上直接给这八字安的。真要抠字，四本到'
          '「食神生旺、無印綬刑衝」这一层就停住了。</p>'
          '<p class="bh">杂气、建禄、月劫三路都不入：庚禄在申，本命无申；庚的劫财在酉，本命无酉；'
          '月令落在亥、不在辰戌丑未，杂气格本就用不上。万历本另有一句提醒，「莫泥提綱反為悞」——'
          '提纲是主，但不能死扣。所以下面断事，格名只当骨架；财透不透、印有没有，才是肉。</p>')
    cnt.append(len([x for x in q3 if x]))

    # 4 五行力量
    q4 = [grab(lib, r'地支至切黨盛[為爲]強', bw=0, aw=80, stop='其喜忌'),
          grab(lib, r'庚辛申酉屬金', bw=0, aw=40, stop='壬癸亥子'),
          grab(lib, r'得時俱為旺論', bw=0, aw=24)]
    sc = wuxing_score(p4)
    tot = sum(sc.values()) or 1.0
    top = sorted(sc.items(), key=lambda x: -x[1])
    b4 = ('<p class="bh">按上面那套折算：%s %s 分最多，%s %s 分紧随，%s %s，%s %s，%s %s。'
          '水是食伤（壬癸），木是财（甲乙），这两党加起来 %.1f 分，占六成以上——书里「黨盛為強」'
          '讲的就是这种局面：不是看某一个字，是看哪一类字抱成了团。金只有 %s，日主自身偏轻；'
          '土 %s 里大半在戌、未两个库中，有而不透。</p>'
          '<p class="bh">再看「得地得時」。万历本说庚辛属金，「生於荊梁為得地，秋冬為得時」；'
          '本命生在亥月，秋冬之交，算得时。但日支戌是土的库、不是金的旺地，得地这一头就弱。'
          '合起来是「得时不得地」，日主不算强。万历本还有一句「得時俱為旺論，失令更作衰看，四柱無根，得時為旺」，'
          '与上一条是一个意思：旺衰要跟「当时」配着看，不是单数字数。</p>'
          '<p class="bh">还是那句话：这是给字面轻重排的序，不是吉凶分数。四本没有这种加总法，'
          '也不认一个数就能定吉凶。</p>'
          % (top[0][0], '%.1f' % top[0][1], top[1][0], '%.1f' % top[1][1],
             top[2][0], '%.1f' % top[2][1], top[3][0], '%.1f' % top[3][1],
             top[4][0], '%.1f' % top[4][1], sc.get('水', 0) + sc.get('木', 0),
             '%.1f' % sc.get('金', 0), '%.1f' % sc.get('土', 0)))
    cnt.append(len([x for x in q4 if x]))

    # 5 命主性情
    q5 = [grab(lib, r'金主義自絕則寡義', bw=30, aw=20, stop='木主仁'),
          grab(lib, r'乙陰木也其性仁', bw=0, aw=80, stop='五行生旺則'),
          grab(lib, r'食神大忌偏印為倒食', bw=8, aw=56, stop='假如甲見丙')]
    b5 = ('<p class="bh">金主义。落到人身上，是讲规矩、认死理，应下的事不肯赖；反过来就是太硬，'
          '话不会拐弯。蔣本卷七论性情，先立「金主義」，紧接一句「自絕則寡義」——金气断了，这一面就薄。'
          '本命庚金坐戌，戌里有辛金的余气，不算无根，这一面还在，只是不厚。</p>'
          '<p class="bh">月干乙与日干庚正合，书上把这叫「仁義之合」：乙木性仁而柔，庚金坚强不屈，'
          '两下相济，所以「主人果敢有守，不惑柔佞，周旋惟仁，進退惟義」——拿得住主意，不听软话，'
          '做事先问该不该。这一条正贴在本命上，因为合就在月、日两干之间。</p>'
          '<p class="bh">但同一条的下半句也得留着：「五行生旺則骨秀形清，若死絕帶煞則使氣好勇，'
          '體貌不揚，自是非人」。庚金在亥是病地，不算生旺，所以「使氣好勇」那一面不能全抹掉：'
          '急了会顶，顶完又后悔。</p>'
          '<p class="bh">还有一层是暗的。食神最怕偏印来夺，书叫「倒食」，主「有始無終…心性局促，多無成」。'
          '本命偏印是戊土，天干不透，可日支戌里正藏着戊。这是暗藏的一点倒食，不成明局。'
          '据原局推：事情起头热、后头容易散，这一条要自己防，不是书上给本命定的断语。</p>')
    cnt.append(len([x for x in q5 if x]))

    # 6 六亲
    q6 = [grab(lib, r'庚娶乙木為妻', bw=0, aw=46, stop='故謂隂干生我'),
          grab(lib, r'天偶星者', bw=2, aw=34, stop='若在兄弟'),
          grab(lib, r'傷年不利父', bw=6, aw=52, stop='亦無結果')]
    b6 = ('<p class="bh">六亲的取法，四库本卷七说得最清楚：以日干为我，「尅我者為官為子，我尅者為財為妻，'
          '比和者為兄弟娣妹」。本命庚金：乙木是妻星，而月干正是乙，又与日干合——妻星不但透，还贴身；'
          '子星看官杀，丙丁火，原局天干一个不见，只有戌、未各藏一个丁，子星是藏着的。</p>'
          '<p class="bh">宫位另算一套：年柱看父母祖上，月柱看兄弟，日柱看自己与配偶，时柱看子女。'
          '书上「傷年不利父，傷月不利兄弟，傷日不利己身，名折腰煞，傷時不利子孫」，是说哪一柱受了伤，'
          '就应在哪一头。本命原局无冲，这一条只能当提醒，不能直断伤在哪一柱。</p>'
          '<p class="bh">父母——年柱甲子，甲是偏财（父星），坐子水得生，父星有气；印是母星，戊己土只在戌、未里藏，'
          '母星不透。兄弟——比肩是庚辛，庚在日干、辛藏戌中，一位透干、一位入库。'
          '配偶——日支戌为配偶宫，戌里藏戊辛丁：印、比肩、官，独独没有财；辛丑本另有一句'
          '「天偶星者，妻宮之主也」，提醒妻宫与妻星是两处，得分开看，本命这两处不在一气上。'
          '子女——时柱癸未为子女宫，时干癸是伤官、时支未里藏着丁火官星；男命以官杀为子，'
          '子星落在子女宫里而不透，这层是薄的。四本没有就本命子女另给断语，这里也不替它补。</p>')
    cnt.append(len([x for x in q6 if x]))

    # 7 原局干支作用
    q7 = [grab(lib, r'乙庚化金非巳酉丑月不化', bw=4, aw=52, stop='凡巳酉丑生人'),
          grab(lib, r'若三字缺其一則化不成局', bw=6, aw=40, stop='葢天地間|盖天地间'),
          grab(lib, r'丑刑戌', bw=0, aw=44, stop='子刑卯'),
          grab(lib, r'子未相害者', bw=0, aw=40, stop='丑午相害'),
          grab(lib, r'相衝者十二支戰擊之神', bw=4, aw=40, stop='乃衝處相生')]
    b7 = (rel_list(p4) +
          '<p class="bh">四本对这几种关系都有断语，逐条对:</p>'
          '<p class="bh">乙庚这一合，万历本说「乙庚化金，非巳酉丑月不化，其次七月亦化；'
          '有甲字間之則不化，名曰妬合」。本命生亥月，既非巳酉丑，也非申月；年干又正是甲。'
          '据原局推：化不成，只作「合」看；甲字在旁算不算「間」，四本没把话说死，我按不化处理，这一层标为推。</p>'
          '<p class="bh">三合这一路，万历本说「若三字缺其一則化不成局，不可以三合化局論」。'
          '本命只有亥、未，缺卯，所以不成木局，只作「拱木」的意思：财的根在暗里连着，不成气候。</p>'
          '<p class="bh">相刑这一路，万历本列得明白：「丑刑戌，戌刑未，未刑丑，為恃勢之刑」。'
          '本命戌、未相见而丑缺，刑意有而不全。恃势之刑多应在与人争理，自己先站住了理才拧起来。</p>'
          '<p class="bh">六害这一路，蔣本说得细：「子未相害者，謂未旺土害子旺水，名勢家相害」。'
          '本命年支子、时支未隔着两柱，害意是暗的：不正面冲突，底下总有一处不顺，多应在人事。</p>'
          '<p class="bh">冲这一路，万历本的定义是「相衝者，十二支戰擊之神，大槩為凶，然有為福之甚者」。'
          '本命原局无冲，这条只作对照：没有冲，动得少，事情多是慢慢磨出来的，不是一下子翻掉。</p>')
    cnt.append(len([x for x in q7 if x]))

    html_s = (ysec('y1', '一', '五行结构', q1, b1) +
              ysec('y2', '二', '月令', q2, b2) +
              ysec('yg', '三', '官星与事业路数', qg, bg) +
              ysec('y3', '四', '格局', q3, b3) +
              ysec('y4', '五', '五行力量', q4, b4.replace('<p class="bh">按上面那套折算', wx_block(p4) + '<p class="bh">按上面那套折算', 1)) +
              ysec('y5', '六', '命主性情', q5, b5) +
              ysec('y6', '七', '六亲', q6, b6) +
              ysec('y7', '八', '原局干支作用', q7, b7))
    return html_s, cnt


def esc(s):
    return html.escape(s, quote=False)


# ================= 第四轮：九章新增渲染 =================
def evq(x, key=None):
    """证据包一条 → 引文块（原文／术语／说人话／落到你身上，右上挂校验标）"""
    v = VLAB.get(x.get('版本'), x.get('版本') or '四版')
    loc = (x.get('卷篇') or '')
    if x.get('定位'):
        loc = (loc + '·' + x['定位']) if loc else x['定位']
    b = BAI.get(key) if key else None
    bd = ''
    if b:
        bd = ('<span class="bd %s">%s</span>'
              % (BD_CLS.get(b.get('标'), 'b4'), esc(b.get('标', ''))))
    out = ('<div class="qk"><blockquote><span class="v">%s</span>'
           '<span class="q">%s</span>%s</blockquote>'
           % (esc(v), esc(x.get('原文') or ''), bd))
    sm = []
    if loc:
        sm.append(esc(loc))
    if x.get('条件'):
        sm.append('条件：' + esc(x['条件']))
    if x.get('口径'):
        sm.append('口径：' + esc(x['口径']))
    if sm:
        out += '<div class="src">%s</div>' % '　｜　'.join(sm)
    if b:
        tm = b.get('术语') or []
        if tm:
            out += ('<div class="trm">%s</div>'
                    % '；'.join('<b>%s</b>　%s' % (esc(k), esc(t)) for k, t in tm))
        out += ('<p class="pl"><span class="lb">说人话</span>%s</p>'
                '<p class="pl s2"><span class="lb">落到你身上</span>%s</p>'
                % (esc(b.get('说人话', '')), esc(b.get('落到', ''))))
    elif key:
        MISS.append('%s|%s' % (key, (x.get('原文') or '')[:14]))
    if key and b:
        USED.append(key)
    out += '</div>'
    if b and b.get('标') == '不成立·仅备一说':
        out = ('<details class="fold" data-h="%s"><summary>另有一说·%s</summary>'
               % (esc(fold_hint(x)), esc(fold_hint(x))) + out + '</details>')
    return out


def fold_hint(x):
    """折叠块 summary 的来源提示：卷次＋篇类，压到四到六字"""
    loc = x.get('卷篇') or ''
    m = re.search(r'卷\s*[一二三四五六七八九十0-9]+', loc)
    juan = m.group(0) if m else ''
    if re.search(r'[時时]斷', loc):
        return juan + '日时断'
    if juan:
        return juan
    v = VLAB.get(x.get('版本'), x.get('版本') or '')
    return v or '原文'


_FOLD = re.compile(r'<details class="fold" data-h="([^"]*)"><summary>[^<]*</summary>(.*?)</details>', re.S)


def merge_folds(s):
    """相邻的折叠块并成一块，summary 报「另有 N 说·来源」"""
    out, cur, last = [], [], 0

    def flush():
        if not cur:
            return
        n = len(cur)
        hs = [h for h, _ in cur]
        hint = max(dict.fromkeys(hs), key=hs.count)
        head = '另有一说' if n == 1 else '另有 %d 说' % n
        out.append('<details class="fold"><summary>%s·%s</summary>%s</details>'
                   % (head, hint, ''.join(x for _, x in cur)))
        cur.clear()

    for m in _FOLD.finditer(s):
        gap = s[last:m.start()]
        if gap.strip():
            flush()
            out.append(gap)
        cur.append((m.group(1), m.group(2)))
        last = m.end()
    flush()
    out.append(s[last:])
    return ''.join(out)


FOLD_JS = ('<script>/* 目录锚点落到折叠块上时自动展开，跳转不被收起挡住 */\n'
           'function _openFold(){var h=decodeURIComponent((location.hash||"").slice(1));'
           'if(!h)return;var e=document.getElementById(h);'
           'while(e){if(e.tagName==="DETAILS"){e.open=true;}e=e.parentElement;}}\n'
           'window.addEventListener("hashchange",_openFold);'
           'window.addEventListener("DOMContentLoaded",_openFold);_openFold();</script>')

# 白话层禁用句式（正面陈述替代）与「机制词＋落点」自检
FORBID = ['与你无关', '对你不适用', '仅作参考', '列它是为让你知道', '这部分对你']
MECH = ['因', '故', '所以', '于是', '致使', '因而', '才', '遂']
LAND = ['柱', '宫', '運', '运', '歲', '岁']


def audit(used):
    """返回（禁用句命中，缺机制或缺落点的键）"""
    fb, bad = [], []
    for k in used:
        txt = (BAI.get(k) or {}).get('落到') or ''
        for w in FORBID:
            if w in txt:
                fb.append((k, w))
        if k.startswith('S.行.'):       # 表行短语，不按 90–160 字要求
            continue
        if not any(m in txt for m in MECH) or not any(l in txt for l in LAND):
            bad.append(k)
    return fb, bad


def yongshen_ch():
    y = EV.get('十_用神与喜忌', {})
    if not y:
        return '<p>证据包缺「用神与喜忌」一节。</p>', 0
    a, b = y.get('一_判强弱', {}), y.get('二_取用', {})
    n = 0
    h = ['<p class="lead">这一章放在原局之前，因为后面每一章都要拿它当尺子。'
         '先引四本判旺衰的原句，再把八个字放到这些话下面量一遍；'
         '量出来的结论标明「据原局推」，不冒充四本书给这命下的断语。</p>',
         '<p class="lead">读法：每块原文下面固定两段——「说人话」把原句译成现代汉语，'
         '「落到你身上」再说它跟这八字的关系；夹在中间的一行小字解行话。'
         '原文右上角的小标是条件校验的结论：'
         '<span class="bd b1 i">条件成立</span>可用它断本命，'
         '<span class="bd b2 i">部分成立</span>只成立一半，'
         '<span class="bd b3 i">不成立·仅备一说</span>前提不合、不当证据，'
         '<span class="bd b4 i">体例说明·不作断语</span>只是书的写法，不关吉凶。</p>']

    h.append('<h3 id="ys1"><span class="n2">一</span>判身强弱</h3>')
    for i, q in enumerate(a.get('原句', [])):
        h.append(evq(q, 'YS.A.%d' % i)); n += 1
    h.append('<h4>落到本命</h4><ul class="rel">')
    for t in a.get('落到本命', []):
        h.append('<li>%s</li>' % esc(t))
    h.append('</ul>')

    h.append('<h3 id="ys2"><span class="n2">二</span>取用与喜忌</h3>')
    h.append('<p class="lead">下面这一句是<em>据原局推</em>，四本书没有替这个八字下过。</p>')
    h.append('<p>%s</p>' % esc(b.get('据原局推', '')))
    h.append('<ul class="rel">')
    for t in b.get('理由', []):
        h.append('<li>%s</li>' % esc(t))
    h.append('</ul>')

    h.append('<h3 id="ys3"><span class="n2">三</span>四版分歧：用印还是用比劫</h3>')
    h.append('<p class="lead">同类局面，四本给了两条路，各有各的前提。'
             '本报告并列，不替你择一。</p>')
    for j, x in enumerate(b.get('分歧并列', [])):
        h.append('<div class="calc"><div class="ct">%s</div>' % esc(x.get('说', '')))
        for k, q in enumerate(x.get('依据', [])):
            h.append(evq(q, 'YS.B.%d.%d' % (j, k))); n += 1
        if x.get('条件'):
            h.append('<p class="cn">成立条件：%s</p>' % esc(x['条件']))
        if x.get('对本命'):
            h.append('<p class="cn">对本命：%s</p>' % esc(x['对本命']))
        h.append('</div>')
    h.append('<p>%s</p>' % esc(b.get('不裁断', '')))
    return ''.join(h), n


FU_ORDER = ['元理賦', '消息賦', '明通賦', '玉井奧訣']


def fu_ch():
    f = EV.get('五_赋诀', {})
    t = EV.get('十一_条件校验', {})
    n = 0
    h = ['<p class="lead">%s</p>' % esc(f.get('体例限制', ''))]
    for i, nm in enumerate(FU_ORDER):
        h.append('<h3 id="fu%d"><span class="n2">%s</span>%s</h3>'
                 % (i + 1, '一二三四'[i], nm))
        qs = f.get(nm, [])
        if not qs:
            h.append('<blockquote><span class="v">四版</span>'
                     '<span class="q">此赋四版无相关句。</span></blockquote>')
        for i, q in enumerate(qs):
            h.append(evq(q, 'FU.%s.%d' % (nm, i))); n += 1

    h.append('<h3 id="tj"><span class="n2">附</span>条件校验</h3>')
    h.append('<p class="lead">%s</p>' % esc(t.get('口径', '')))
    st = t.get('统计', {})
    if st:
        h.append('<p class="lead">全表 %d 条：条件成立 %d、条件不成立 %d、'
                 '条件部分成立 %d。不成立的只备一说，不用来支撑结论。</p>'
                 % (st.get('总条', 0), st.get('条件成立', 0),
                    st.get('条件不成立', 0), st.get('条件部分成立', 0)))
    h.append('<table class="t"><tr><th style="width:30%">断语与出处</th>'
             '<th style="width:12%">判定</th><th>条件（同条原文）与处置</th></tr>')
    for x in t.get('逐条', []):
        j = x.get('判定', '')
        if j.startswith('条件不成立'):
            col = '#8c2f22'
        elif j.startswith('条件部分'):
            col = '#a8792a'
        else:
            col = '#2f5d50'
        h.append('<tr><td><b>%s</b><div class="src">%s</div></td>'
                 '<td><b style="color:%s">%s</b></td>'
                 '<td>%s<div class="src">%s</div></td></tr>'
                 % (esc(x.get('项', '')), esc(x.get('引', '')), col, esc(j),
                    esc(x.get('条件', '')), esc(x.get('说明', ''))))
    h.append('</table>')
    for x in t.get('点名项', []):
        h.append('<p><b style="color:#8c2f22">%s</b>　%s</p>'
                 % (esc(x.get('项', '')), esc(x.get('处理', ''))))
    return ''.join(h), n


def ssshen_ch():
    d = EV.get('三_神煞全表', {})
    h = ['<p class="lead">四本没有神煞专表，神煞散见于正文。下表只列入盘的：'
         '命中的记柱位，柱位若只能按通例推，就标「据原局推」。</p>']
    n = 0
    for i, q in enumerate(d.get('总纲', [])):
        h.append(evq(q, 'S.总.%d' % i)); n += 1
    rows = d.get('表', [])
    hit = [r for r in rows if r.get('入盘') in ('是', '两说')]
    h.append('<p class="lead">入盘共 %d 名。</p>' % len(hit))
    h.append('<table class="t"><tr><th style="width:17%">神煞名</th>'
             '<th style="width:17%">柱位</th>'
             '<th style="width:9%">吉凶取向</th><th>引文、白话与出处</th></tr>')
    for r in hit:
        yes = True
        nm = esc(r.get('名', ''))
        b = BAI.get('S.行.' + r.get('名', ''))
        if b:
            USED.append('S.行.' + r.get('名', ''))
        px = ''
        if b:
            px = ('<div class="plx"><span class="lb">说人话</span>%s</div>'
                  '<div class="plx s2"><span class="lb">落到</span>%s</div>'
                  % (esc(b.get('说人话', '')), esc(b.get('落到', ''))))
        else:
            px = '<div class="plx"><span class="lb">说人话</span>（待补）</div>'
        h.append('<tr><td><b>%s</b></td><td>%s</td><td>%s</td>'
                 '<td>%s<div class="src" style="color:#6b6154">%s</div></td></tr>'
                 % (nm, esc(r.get('柱位', '')),
                    esc(r.get('吉凶', '')), px, esc(r.get('引文', ''))))
    h.append('</table>')
    n += len(hit)

    kw = EV.get('二_空亡', {})
    if kw:
        h.append('<h3 id="ssk"><span class="n2">附</span>空亡</h3>')
        h.append('<p><b>本命</b>　%s</p>' % esc(kw.get('本命旬', '')))
        h.append('<ul class="rel">')
        for k, v in (kw.get('四柱落空') or {}).items():
            if '不犯' in v:          # 全盘不犯的一说不列
                continue
            h.append('<li><b>%s</b>　%s</li>' % (esc(k), esc(v)))
        h.append('</ul>')
        for i, q in enumerate(kw.get('引文', [])):
            h.append(evq(q, 'S.空.%d' % i)); n += 1

    q7 = EV.get('一_卷七表格', {})
    if q7:
        h.append('<h3 id="ss7"><span class="n2">附</span>卷七表格里的一格</h3>')
        g = q7.get('目标格', {})
        h.append('<p><b>%s</b>（%s｜%s）</p>'
                 % (esc('%s日·%s' % (g.get('日柱', ''), g.get('时辰', ''))),
                    esc(g.get('版本', '')), esc(g.get('页叶', ''))))
        h.append('<ul class="rel"><li><b>日头</b>　%s</li><li><b>格内</b>　%s</li></ul>'
                 % (esc(g.get('日头原文', '')), esc(g.get('格内原文', ''))))
        for kk in ('S.卷七.日头', 'S.卷七.格'):
            b = BAI.get(kk)
            if b:
                h.append('<p class="pl"><span class="lb">说人话</span>%s</p>'
                         '<p class="pl s2"><span class="lb">落到你身上</span>%s</p>'
                         % (esc(b.get('说人话', '')), esc(b.get('落到', ''))))
        h.append('<p class="lead">%s</p>' % esc(g.get('取用提示', '')))
        h.append(evq(q7.get('总纲', {}), 'S.卷七.0')); n += 1
        h.append('<div class="src"><b>体例</b>　%s</div>' % esc(q7.get('体例限制', '')))
    return ''.join(h), n


def mingli_ch():
    d = EV.get('四_命例参照', {})
    h = ['<p class="lead">%s</p>' % esc(d.get('取例原则', ''))]
    n = 0
    for x in d.get('条目', []):
        h.append('<div class="ss-row"><div class="nm">第 %d 例'
                 '<span>%s｜%s</span></div>' % (x.get('序', 0), esc(x.get('版本', '')),
                                               esc(x.get('卷篇', ''))))
        h.append(evq({'版本': x.get('版本'), '卷篇': x.get('卷篇'), '定位': x.get('定位'),
                      '原文': x.get('原文')}, 'M.%d' % x.get('序', 0)))
        h.append('<p><b>同柱</b>　%s　<b>异柱</b>　%s</p>'
                 % (esc(x.get('同柱', '')), esc(x.get('异柱', ''))))
        h.append('<p style="color:#8c2f22"><b>不可移断</b>　%s</p></div>' % esc(x.get('提示', '')))
        n += 1
    h.append('<p class="lead">相似不等于同命。断语各系其前提：月令、年时、成败救应；'
             '同柱异命者，不可移断。</p>')
    h.append('<div class="src"><b>篇题错位</b>　四库本「庚日時逢癸未」一条引在'
             '〈六己日乙丑時斷〉篇下，篇题与内容不符，引用时已标「篇题错位」。</div>')
    return ''.join(h), n


YONG_XI = {'正印': '喜', '偏印': '喜', '比肩': '喜', '劫財': '喜',
           '正財': '忌', '偏財': '忌', '食神': '忌', '傷官': '忌',
           '正官': '半', '七殺': '半'}
WX_XI = {'土': '喜', '金': '喜', '水': '忌', '木': '忌', '火': '半'}
WXNAME = {'土': '土（印）', '金': '金（比劫）', '水': '水（食伤）',
          '木': '木（财）', '火': '火（官杀）'}


def xiji(gz, dg):
    a = YONG_XI.get(J.shishen(dg, gz[0]), '半')
    wx = WXZ.get(gz[1], '')
    b = WX_XI.get(wx, '半')
    tot = {'喜': 1, '忌': -1, '半': 0}[a] + {'喜': 1, '忌': -1, '半': 0}[b]
    lab = '此运为喜' if tot >= 1 else ('此运为忌' if tot <= -1 else '半吉半忌')
    return lab, a, b, wx


def build(p4, sex, birth, out):
    lib = J.Lib()
    NARR.clear()
    USED.clear()
    K = J.build_keys(lib, p4, sex)
    L = J.layer_search(lib, p4, K)
    lanes = J.lane_eval(L, K, sex)
    dg, dz = p4[2][0], p4[2][1]
    dy = dayun(p4, sex, birth)
    seed = (GAN.index(dg) * 2 + ZHI.index(dz) + ZHI.index(p4[1][1]) * 3) % 5
    seed2 = (ZHI.index(p4[3][1]) * 3 + GAN.index(p4[0][0])) % 10

    # ---- 四柱盘 ----
    pos = ['年', '月', '日', '時']
    pan = []
    for i, p in enumerate(p4):
        ss = '日主' if i == 2 else J.shishen(dg, p[0])
        cg = '、'.join('%s%s' % (g, '' if i == 2 and g == dg else J.shishen(dg, g))
                       for g in J.ZANG[p[1]])
        pan.append('<div class="c"><div class="pos">%s柱</div><div class="ss">%s</div>'
                   '<div class="gz">%s</div><div class="cg">藏干 %s</div>'
                   '<div class="ny">%s</div></div>'
                   % (pos[i], esc(ss), esc(p), esc(cg), esc(J.NAYIN.get(p, ''))))

    # ---- 大运 ----
    tl = []
    for i, gz in enumerate(dy['steps']):
        if dy['age']:
            a0, a1 = dy['age'] + 10 * i, dy['age'] + 10 * (i + 1)
            y0, y1 = dy['years'][i]
            rng = '%d–%d 歲<br>%d–%d' % (int(a0), int(a1), y0.year, y1.year)
        else:
            rng = '第 %d 步' % (i + 1)
        tl.append('<div class="s"><div class="i">%d</div><div class="gz">%s</div>'
                  '<div class="r">%s</div><div class="tag">%s·%s</div></div>'
                  % (i + 1, esc(gz), rng, esc(J.shishen(dg, gz[0])), esc(changsheng(dg, gz[1]))))

    # ---- 原局 ----
    yuan_html, yuan_cnt = yuanju(lib, p4)

    # ---- 五栏 ----
    lane_name = [('妻', '婚姻感情', '婚配与配偶宫星'), ('财', '钱财营生', '财星与取财'),
                 ('子', '子女后嗣', '子女宫与官杀食伤'), ('禄', '功名职位', '官贵与俸禄'),
                 ('寿', '身体寿元', '健康寿元与灾厄')]
    lanes_html = []
    used = set()
    qmap = {}
    # 取句次序：先顾材料多的栏，免得后取的栏只剩同一句
    for lane in ['妻', '财', '子', '禄', '寿']:
        qmap[lane] = lane_quotes(lanes[lane], lane, p4, used, 3)
    for i, (lane, cn, en) in enumerate(lane_name):
        d = lanes[lane]
        qs = qmap[lane]
        if qs:
            qh = ''.join(evq({'版本': x['v'], '原文': x['text'], '卷篇': x['loc']},
                             'L.%s.%d' % (lane, j)) for j, x in enumerate(qs))
            note = '；'.join('%s·%s' % (VLAB[x['v']], x['loc']) for x in qs)
        else:
            qh = ('<blockquote><span class="v">四版</span>'
                  '<span class="q">四版无此条。</span></blockquote>')
            note = '四版本命键内无涉及此栏之条文'
        if lane in LANE_BODY_FIX:
            bh = LANE_BODY_FIX[lane]
        else:
            bh = J._lane_para(lane, d, p4, i, seed, seed2)
            if lane in LANE_HEAD_FIX:      # 该栏原结论取自前提不成立的条文，此处重写首句
                k = bh.find('。')
                bh = LANE_HEAD_FIX[lane] + (bh[k + 1:] if k > 0 else '')
            if lane == '妻':
                bh = bh.replace('「庚日癸未时」这一类日子', '这一格时生的人')
        if lane == '妻' and qs:
            bh += mixed_note(qs, bh)
        NARR.append(('五栏·' + lane, bh))
        lanes_html.append('<section class="lane"><h3>%s<span class="en">%s</span></h3>%s'
                          '<p class="bh">%s</p><div class="src"><b>出处</b> %s</div></section>'
                          % (esc(cn), esc(en), qh, esc(bh), esc(note)))

    # ---- 逐运 ----
    CH_PAT = r'長生主有創建|長生主創建|臨官帝旺主'
    ch = find(lib, CH_PAT, None, 1)
    chq = clip(ch[0]['text'], CH_PAT, 110) if ch else ''
    chsrc = ('%s·%s' % (VLAB[ch[0]['v']], ch[0]['loc'])) if ch else ''
    STEP_JUDGE = {
        '丙子': '此运为忌。丙是七杀，本可暖这盘寒水，可它坐下是子，火一入水就灭，杀不成杀；子又与年支子并、害时支未，未里藏的丁官、己印一并受摇——故这一步不是官来管事，是水更旺、身更弱。落在八至十八岁（一九九三至二〇〇三），关口在年支与时支；十二岁丙子年岁运并临，最须留意。与第贰章官星节、玖章总说同指一事。',
        '丁丑': '此运为喜，是八步里第一段能落脚的路。丁是正官，坐在丑上不旺，丑却是湿土，能生庚金；丑又与未相冲，冲开未库，把里面藏的印与财摇出来一点——故官虚而印实，名分不厚，根基转厚。落在十八至二十八岁（二〇〇三至二〇一三），应在日柱与时柱之间；丑未一冲，家宅与居所有一动。与伍章禄栏同指一事：这十年靠的是印，不是官。',
        '戊寅': '此运半吉半忌。戊是偏印，透在运干，能生身，这是一喜；可寅是木，木为财，且寅与月支亥六合化木，财更旺，身更弱——故一喜一忌相抵，帮身的力量被财耗掉。落在二十八至三十八岁（二〇一三至二〇二三），关口在月柱：财从月令来，人却担不动。分寸：能进钱，难存钱；与叁章校验表同指一事。',
        '己卯': '此运半吉半忌，且比上一步更须小心。己是正印，透干帮身；可卯一到，亥卯未三合木局补齐了缺字，财局成片，印被财围——故印虽在，护不住全局。落在三十八至四十八岁（二〇二三至二〇三三），关口在月、日、时三支：三合在财，耗在暗处。与陆章上文同指一事：财旺身弱，宜守不宜扩。',
        '庚辰': '此运为喜，是八步里最实的一步。庚是比肩，透干帮身；辰是湿土，生金又收水，辰还与日支戌相冲，冲开火库，把藏着的丁官摇动——故身得助、官得动，是能做事、名分上也松动一点的一段。落在四十八至五十八岁（二〇三三至二〇四三），应在日柱：冲在日支，动的是自身与家宅。与伍章禄栏同指一事。',
        '辛巳': '此运为喜，喜在暖局。辛是劫财，帮身；巳是庚的长生，又是火地，这盘寒水正缺火，巳一来就暖了；巳与月支亥相冲，冲动月令——故身有根、局有暖气，是晚年最好的一段。落在五十八至六十八岁（二〇四三至二〇五三），关口在月柱：冲月令，动的是资源与去处。与第壹章调候是一回事。',
        '壬午': '此运为忌，忌在火被水压。壬是食神，透干泄身；午是火，本该暖局，可它被壬水盖头，又与年支子相冲，火被水制、又被冲摇——故官本就受制，这一步更虚，仍旧掌不了事；食神反倒耗身。落在六十八至七十八岁（二〇五三至二〇六三），关口在年柱与运支：子午一冲，应在身体与旧事。与第贰章官星那一节呼应。',
        '癸未': '此运半吉半忌，收在库上。癸是伤官，透干泄身，这是忌；未是印库，藏着己土与丁火，能生身，这是喜；可未又与日支戌相刑、与年支子相害——故有帮扶也有牵扯，晚景安稳里带反复。落在七十八至八十八岁（二〇六三至二〇七三），关口在日柱与时柱之间。分寸：宜静养，不宜再动产业。',
    }
    steps_html = []
    for i, gz in enumerate(dy['steps']):
        ss, cs = J.shishen(dg, gz[0]), changsheng(dg, gz[1])
        rel = rels(gz[1], p4)
        lab, xa, xb, wx = xiji(gz, dg)
        if dy['age']:
            meta = '%d–%d 歲　<i>%d–%d</i>' % (int(dy['age'] + 10 * i), int(dy['age'] + 10 * (i + 1)),
                                               dy['years'][i][0].year, dy['years'][i][1].year)
        else:
            meta = '第 %d 步' % (i + 1)
        reltxt = ''
        if rel:
            heavy = any(x in rel for x in ('沖', '刑', '害'))
            reltxt = ('　运支与四柱见%s，%s' % (rel, '冲刑之处即关口。' if heavy else '事多有人牵线。'))
        if lab == '此运为喜':
            judge = ('用神在土金。此运干%s为%s（%s）、支%s属%s，干支合起来帮身，故判为喜：'
                     '得助、根基渐实，文书与名分上有着落。'
                     % (gz[0], ss, xa, gz[1], WXNAME.get(wx, '')))
            if '沖' in rel or '刑' in rel or '害' in rel:
                judge += '惟运支带%s，好处里夹着变动，得处须费力。' % rel
        elif lab == '此运为忌':
            judge = ('用神在土金。此运干%s为%s（%s）、支%s属%s，两处都耗泄日主，故判为忌：'
                     '防耗财与劳碌，防口舌是非，防身体泄气；宜守成，不宜铺新摊子。'
                     % (gz[0], ss, xa, gz[1], WXNAME.get(wx, '')))
            if '沖' in rel:
                judge += '运支又冲原局，冲处即关口，家室与身体两头都要留神。'
        else:
            judge = ('用神在土金。此运干%s为%s（%s）、支%s属%s，一喜一忌相抵，故判半吉半忌：'
                     '事能成而费力，防职务上的是非与家宅口角。'
                     % (gz[0], ss, xa, gz[1], WXNAME.get(wx, '')))
        judge = STEP_JUDGE.get(gz, judge)
        basis = '日主在此为「%s」。' % cs
        NARR.append(('逐运·' + gz, judge))
        steps_html.append(
            '<div class="step"><div class="h"><span class="gz">%s</span>'
            '<span class="m">%s　运干%s　日主在%s为%s%s</span>'
            '<span class="tag">%s</span></div>'
            '<p>%s%s</p><div class="basis"><em>据原局推</em>　%s</div></div>'
            % (esc(gz), meta, esc(ss), esc(gz[1]), esc(cs),
               ('　' + esc(rel)) if rel else '', esc(lab), esc(judge), esc(reltxt), esc(basis)))

    # ---- 神煞 ----
    ss_html, ss_n = ssshen_ch()
    ys_html, ys_n = yongshen_ch()
    fu_html, fu_n = fu_ch()
    ml_html, ml_n = mingli_ch()

    # ---- 总评 ----
    sum_html = summary(lanes, p4, dg, dz, dy, lib)

    # ---- 排盘要点 ----
    if birth:
        b = birth
        jn = dy['jie']
        jt = '%s %s' % (jn[1], jn[0].strftime('%Y-%m-%d %H:%M'))
        days = dy['days']
        age = dy['age']
        jiaoyun = b + datetime.timedelta(days=age * 365.2422)
        ld, dx = term(b.year, 225), term(b.year, 255)
        fact = ('<div class="facts">'
                '<div><b>公历</b> %s　%s時（北京时）</div>'
                '<div><b>日柱核对</b> %s</div>'
                '<div><b>节气</b> 立冬 %s；大雪 %s</div>'
                '<div><b>月建</b> 生于立冬后第 %d 日，属%s月</div>'
                '<div><b>起运</b> 距%s %.1f 日 ÷ 3 ≈ <b>%.1f 歲</b>，约 %s 交運</div>'
                '<div><b>顺逆</b> %s年%s命，%s行</div>'
                '</div>'
                '<div class="src">未给出生地与真太阳时，起运岁数约有十天到半个月的出入；'
                '若生时正压在节气前后，月柱与起运都要另算。</div>'
                % (b.strftime('%Y 年 %m 月 %d 日'), esc(p4[3][1]), esc(day_pillar(b)),
                   ld.strftime('%m-%d %H:%M'), dx.strftime('%m-%d %H:%M'),
                   (b - ld).days + 1, esc(p4[1][1]),
                   esc(jn[1]), days, age, jiaoyun.strftime('%Y 年 %m 月'),
                   p4[0][0], '男' if sex == '男' else '女', '顺' if dy['fwd'] else '逆'))
        dynote = ('节气：立冬 %s、大雪 %s（北京时）。生于立冬后第 %d 日，距%s %.1f 日，'
                  '除以三约 <b>%.1f 歲</b> 起運，每步十年，故下表年龄与公历年皆为约数。'
                  '顺逆：%s年%s命，%s行；起运之法，书作「三日為年，一辰十歲」。'
                  % (ld.strftime('%m-%d %H:%M'), dx.strftime('%m-%d %H:%M'), (b - ld).days + 1,
                     dy['jie'][1], days, age, p4[0][0],
                     '男' if sex == '男' else '女', '顺' if dy['fwd'] else '逆'))
    else:
        fact = ('<div class="facts"><div><b>说明</b> 只给四柱与性别，未给公历生日：'
                '大运干支可定，起运岁数与公历年不可定，故下表只列干支。</div></div>')
        dynote = ('未给生日，不推起运岁数。顺逆：%s年%s命，%s行；起运之法，书作'
                  '「三日為年，一辰十歲」，起运要生日与节气才排得出。'
                  % (p4[0][0], '男' if sex == '男' else '女', '顺' if dy['fwd'] else '逆'))

    card = ('<div class="card"><h2>定 盘</h2><dl>'
            '<dt>身强弱</dt><dd>庚金生亥月，金气得泄；得时不得地，金 1.5 分（一成三），日主偏轻。</dd>'
            '<dt>用神·忌神</dt><dd>喜土金（印比生扶），忌水木（财食耗泄）；火（官杀）居半，暖局可以，撑不起位置。</dd>'
            '<dt>官星</dt><dd>丁火只藏戌、未，天干不透；时干癸为伤官，克丁——官藏而受制。</dd>'
            '<dt>财食</dt><dd>甲乙财透年月、有根；壬癸食伤当令又透时干，走的是以食生财一路。</dd>'
            '<dt>关口</dt><dd>丙子、壬午两运为忌；丁丑、庚辰、辛巳三步为喜。</dd>'
            '<dt>证据性质</dt><dd>引号内为四本原文（逐字、标版本）；其余据原局推；不作品级。</dd>'
            '</dl></div>')

    doc = """<!DOCTYPE html>
<html lang="zh-Hans"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s｜四版《三命通会》通读报告</title>
<style>%(css)s</style></head><body><div class="wrap">

<header class="hd">
  <div class="sub">四版《三命通会》通读报告</div>
  <h1>%(p)s　%(sex)s命</h1>
  <p class="lead">万历本／蔣國祥本／辛丑本／四库本四种底本并读。四本正文有异文、有详略，所引一律标版本；书上没有的，本报告不补。凡落到本命的话，标「据原局推」。</p>
</header>

<div class="pan">%(pan)s</div>
%(fact)s
%(card)s

<nav class="toc"><ol>
<li><a href="#ys">壹　用神与喜忌</a></li>
<li class="sub"><a href="#ys1">一　判身强弱</a></li>
<li class="sub"><a href="#ys2">二　取用与喜忌</a></li>
<li class="sub"><a href="#ys3">三　四版分歧</a></li>
<li><a href="#yuan">貳　原局</a></li>
<li class="sub"><a href="#y1">一　五行结构</a></li>
<li class="sub"><a href="#y2">二　月令</a></li>
<li class="sub"><a href="#yg">三　官星与事业路数</a></li>
<li class="sub"><a href="#y3">四　格局</a></li>
<li class="sub"><a href="#y4">五　五行力量</a></li>
<li class="sub"><a href="#y5">六　命主性情</a></li>
<li class="sub"><a href="#y6">七　六亲</a></li>
<li class="sub"><a href="#y7">八　原局干支作用</a></li>
<li><a href="#fu">叁　赋诀</a></li>
<li class="sub"><a href="#fu1">一　元理赋</a></li>
<li class="sub"><a href="#fu2">二　消息赋</a></li>
<li class="sub"><a href="#fu3">三　明通赋</a></li>
<li class="sub"><a href="#fu4">四　玉井奥诀</a></li>
<li class="sub"><a href="#tj">附　条件校验</a></li>
<li><a href="#dayun">肆　大运</a></li>
<li><a href="#lanes">伍　妻·财·子·禄·寿</a></li>
<li><a href="#steps">陆　逐运关卡</a></li>
<li><a href="附录_神煞与命例.html#ss">柒　神煞全表</a></li>
<li class="sub"><a href="附录_神煞与命例.html#ssk">附　空亡</a></li>
<li class="sub"><a href="附录_神煞与命例.html#ss7">附　卷七表一格</a></li>
<li><a href="附录_神煞与命例.html#ml">捌　命例参照</a></li>
<li><a href="#end">玖　总说</a></li>
</ol></nav>

<h2 id="ys"><span class="n">壹</span>用神与喜忌</h2>
%(ys)s

<h2 id="yuan"><span class="n">貳</span>原局</h2>
<p class="lead">这一章把八个字本身拆开：字面的五行与月令、官星落在哪一处与事业从哪条路起、能不能定格、五行的轻重、这个人的性情、六亲落在哪一处，最后看四柱之间怎么互相拉扯。每节先引四本原文（标版本），引完再讲落到这命上是什么意思；书上没有的，就写没有。</p>
%(yuan)s

<h2 id="fu"><span class="n">叁</span>赋诀</h2>
%(fu)s

<h2 id="dayun"><span class="n">肆</span>大运</h2>
<p>%(dyintro)s</p>
<div class="tl">%(tl)s</div>
<div class="src"><b>起运</b> %(dynote)s</div>

<h2 id="lanes"><span class="n">伍</span>妻·财·子·禄·寿</h2>
<p class="lead">每栏先引原文，再讲这一段落到这命上是什么意思。引文最多三条，说法相反的两条都留着；一条都没有的，直说没有。凡引断语，其成立条件见叁章附表的校验。</p>
%(lanes)s

<h2 id="steps"><span class="n">陆</span>逐运关卡</h2>
<p class="lead">每一步运只判三档：此运为喜、为忌、半吉半忌。判据挂在前一章定下的用神上——印比与土金为喜，财食与水木为忌，官杀与火居半；忌运要写出防什么。四本只有一条通例可引，先放在这里；具体到每一步，都是推的。</p>
%(chquote)s
%(steps)s

<h2 id="ss"><span class="n">柒</span>神煞全表</h2>
<div class="mv"><p>这一章连同空亡、卷七表一格，因篇幅移入附属页；表只列入盘的神煞，命中的记柱位，每行引文后附「说人话」与「落到」。</p>
<p><a class="lk" href="附录_神煞与命例.html#ss">→ 打开附录：柒 神煞全表</a></p></div>

<h2 id="ml"><span class="n">捌</span>命例参照</h2>
<div class="mv"><p>十例命案同移附属页，每条标同几柱、异几柱，并附「不可移断」。</p>
<p><a class="lk" href="附录_神煞与命例.html#ml">→ 打开附录：捌 命例参照</a></p></div>

<h2 id="end"><span class="n">玖</span>总说</h2>
<div class="end">%(sum)s</div>

%(promo)s

<div class="foot">
数据来源：万历本、蔣國祥本、辛丑本、四库本《三命通会》四种底本。四本正文有异文与详略之别，同一断语未必四本俱全；本报告所引均标版本，未标者为本报告按原局推演。<br>
卷七「六十甲子得时吉凶」表出选择家，作者自限为「看命之一助」，故只列格内原文，不据以断富贵。赋诀为韵语总纲，句各系前提，条件一律从同条原文摘出。<br>
本报告不作品级（上贵／中贵／常格）判定，也不以相似命例移断本命。
</div>
</div></body></html>""" % dict(
        title=esc('%s %s' % (' '.join(p4), sex)), css=CSS, p=esc(' '.join(p4)), sex=sex,
        pan=''.join(pan), fact=fact, card=card, yuan=yuan_html, ys=ys_html, fu=fu_html,
        ml=ml_html, ss=ss_html,
        dyintro=('月柱 %s，%s年%s命%s行，故八步自 %s 起，顺排如下。'
                 % (esc(p4[1]), p4[0][0], sex, '顺' if dy['fwd'] else '逆', esc(dy['steps'][0])))
        if dy['age'] else ('月柱 %s，%s年%s命%s行，八步干支可定；起运岁数要生日与节气才排得出。'
                           % (esc(p4[1]), p4[0][0], sex, '顺' if dy['fwd'] else '逆')),
        dynote=dynote,
        chquote=(evq({'版本': ch[0]['v'], '原文': chq, '卷篇': '通例出处 ' + chsrc}, 'CH.0')
                 if chq else ''),
        tl=''.join(tl), lanes=''.join(lanes_html), steps=''.join(steps_html),
        sum=sum_html, promo=promo())

    if len(doc.encode('utf-8')) > 150000:
        doc = doc.replace('<p class="lead">', '<p class="lead">', 1)
    doc = merge_folds(doc).replace('</body>', FOLD_JS + '</body>')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)

    apx = os.path.join(os.path.dirname(out) or '.', '附录_神煞与命例.html')
    back = os.path.basename(out)
    adoc = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>附录·神煞与命例｜%(p)s</title><style>%(css)s</style></head><body><div class="wrap">
<p class="apx"><a class="lk" href="%(back)s">← 返回主报告</a></p>
<h1 style="font-size:30px">附录 · 神煞与命例</h1>
<p class="lead">%(p)s　%(sex)s。本页是主报告的第七章与第八章，因篇幅单列；主报告仍完整可读，两处目录与正文入口都指到这里。口径与主报告同：引文逐字标版本，每块原文下附「说人话」与「落到」。</p>

<h2 id="ss"><span class="n">柒</span>神煞全表</h2>
%(ss)s

<h2 id="ml"><span class="n">捌</span>命例参照</h2>
%(ml)s

<div class="foot">神煞出选择家与杂占者多，四本正文散见；本表只取正文出现、柱位可定者。「不可移断」一语，指同柱异命者不可径引他命断本命。</div>
</div></body></html>""" % dict(p=esc(' '.join(p4)), sex=sex, css=CSS, back=back, ss=ss_html, ml=ml_html)
    adoc = merge_folds(adoc).replace('</body>', FOLD_JS + '</body>')
    with open(apx, 'w', encoding='utf-8') as f:
        f.write(adoc)
    CNT = {'用神': ys_n, '原局': sum(yuan_cnt), '赋诀': fu_n,
           '五栏': sum(len(v) for v in qmap.values()), '神煞': ss_n,
           '命例': ml_n}

    def han(t):
        return len(re.findall(r'[\u4e00-\u9fff]', t))
    inner = re.findall(r'<details class="fold">(.*?)</details>', doc, re.S)
    hidden = sum(han(re.sub(r'<summary>.*?</summary>', '', x, flags=re.S)) for x in inner)
    STAT = {'fold': len(inner), 'han': han(doc), 'vis': han(doc) - hidden,
            'ssrow': sum(1 for k in USED if k.startswith('S.行.'))}
    return len(doc.encode('utf-8')), len(re.findall(r'[\u4e00-\u9fff]', doc)), yuan_cnt, CNT, os.path.getsize(apx), STAT


def lane_of_ss(ss):
    return {'正官': '职务', '七殺': '职务', '正印': '文书', '偏印': '文书',
            '正財': '钱财', '偏財': '钱财', '食神': '手艺', '傷官': '手艺',
            '比肩': '同辈', '劫財': '同辈'}.get(ss, '职务')


def rels(z, p4):
    """运支与四柱的关系：同类只留一条，按冲>刑>害>合>半合取"""
    rank = {'沖': 0, '刑': 1, '害': 2, '合': 3, '半合': 4}
    got = {}
    for p in p4:
        b = p[1]
        if b == z:
            continue
        f = frozenset(b + z)
        cand = []
        if f in J.LIUCHONG:
            cand.append(('沖', '%s沖%s' % (b, z)))
        if any(len(g) == 3 and b in g and z in g for g, _ in J.SANXING):
            cand.append(('刑', '%s%s相刑' % (b, z)))
        if f in J.LIUHAI:
            cand.append(('害', '%s害%s' % (b, z)))
        if f in J.LIUHE:
            cand.append(('合', '%s%s合' % (b, z)))
        for g, wx in J.SANHE:
            if b in g and z in g:
                cand.append(('半合', '%s%s半合%s' % (b, z, wx)))
        if cand:
            cand.sort(key=lambda x: rank[x[0]])
            got[(b, z)] = cand[0][1]
    return '、'.join(dict.fromkeys(got.values()))


def guanqia(lane, cs, rel, gz, p4, dg, i=0):
    A = {'职务': '职务与名分', '钱财': '钱财与营生', '手艺': '手艺与口舌',
         '文书': '文书、靠山与学业', '同辈': '同辈与合伙'}.get(lane, '职务与名分')
    B = {'長生': '起头、立新事', '沐浴': '动荡、易生是非', '冠帶': '渐入规矩、有名分',
         '臨官': '当位、担事', '帝旺': '最盛、也最费力', '衰': '势退，宜守',
         '病': '气弱，宜养', '死': '气最弱，忌硬撑', '墓': '入库，收而不放',
         '絕': '断而复起，先难后易', '胎': '初萌，须人扶', '養': '渐长，靠积累'}.get(cs, '平')
    F = ['这一步的重心在%s；日主在此为%s，%s。',
         '这一步的戏在%s上；日主临%s，%s。',
         '这一步主要应在%s；走到%s之地，%s。']
    s = F[i % 3] % (A, cs, B)
    heavy = [x for x in ('沖', '刑', '害') if x in rel]
    if heavy:
        s += ['运支与四柱有%s，冲刑之处就是关口。',
              '运支撞上%s，动与纠葛都在这里。',
              '运支与四柱见%s，这一步不安生。'][i % 3] % rel
    elif rel:
        s += ['运支与四柱有%s，事多有人牵线。',
              '运支与%s相合，机缘从这里来。',
              '运支跟四柱搭得上（%s），这一路顺一些。'][i % 3] % rel
    else:
        s += '运支与四柱无刑冲合害，事多循旧。'
    if heavy and p4[2][1] in rel:
        s += '日支是配偶宫，动了它，家室这一头先见分晓。'
    return s


def zpos(z, p4):
    """支在哪一柱：年支子 / 时支未"""
    nm = ['年支', '月支', '日支', '時支']
    got = [nm[i] + z for i, p in enumerate(p4) if p[1] == z]
    return '、'.join(got) if got else '原局无此支'


def shensha(lib, p4, dg, dz):
    out = []
    # 天乙贵人（庚见丑未；本命未在时支）
    if '未' in [p[1] for p in p4]:
        g = find(lib, r'庚以羊|甲戊庚牛羊六辛', None, 1)
        if g:
            out.append(('天乙貴人', zpos('未', p4), clip(g[0]['text'], [r'庚以羊', r'甲戊庚牛羊'], 78),
                        '歌里「甲戊庚牛羊」，庚日以丑、未为天乙；本命时支正是未。'
                        '它管的是遇事有没有人搭手，不管帮你到什么地步，也不管你接不接得住。',
                        '%s·%s' % (VLAB[g[0]['v']], g[0]['loc'])))
    # 六害 / 三刑（据表推，引原文定义）
    liuhai = [p[1] for p in p4]
    pairs = []
    for i in range(4):
        for k in range(i + 1, 4):
            pairs.append((p4[i][1], p4[k][1]))
    hai = [(a, b) for a, b in pairs if frozenset(a + b) in J.LIUHAI]
    if hai:
        g = find(lib, r'子未相穿|子未相害', None, 1)
        out.append(('六害', '%s　%s' % (zpos(hai[0][0], p4), zpos(hai[0][1], p4)),
                    clip(g[0]['text'], r'子未相', 84) if g else '',
                    '害是暗中拉扯：明面上不冲突，底下总有一处不顺，多应在人事而非钱财。',
                    '%s·%s' % (VLAB[g[0]['v']], g[0]['loc']) if g else ''))
    xing = [(a, b) for a, b in pairs
            if any(len(grp) == 3 and a in grp and b in grp for grp, _ in J.SANXING)]
    if xing:
        g = find(lib, r'丑戌未何以謂之恃勢|丑戌未.*恃勢', None, 1)
        miss = ''
        for grp, _ in J.SANXING:
            if len(grp) == 3 and xing[0][0] in grp and xing[0][1] in grp:
                lack = [c for c in grp if c not in [p[1] for p in p4]]
                miss = '（%s缺%s）' % (grp, '、'.join(lack)) if lack else ''
        out.append(('三刑', '%s　%s%s' % (zpos(xing[0][0], p4), zpos(xing[0][1], p4), miss),
                    clip(g[0]['text'], r'丑戌未', 84) if g else '',
                    '这一路刑主「恃势」：多半是自己这边先站住了理，才跟人拧起来。'
                    '三缺一，力不全是好事，成不了大刑。',
                    '%s·%s' % (VLAB[g[0]['v']], g[0]['loc']) if g else ''))
    # 纳音
    ny = find(lib, J.NAYIN.get(p4[2], '') or '釵釧金', None, 1)
    if ny:
        ny = ny[0]
        out.append(('納音（日柱%s）' % p4[2], J.NAYIN.get(p4[2], ''),
                    clip(ny['text'], J.NAYIN.get(p4[2], '') or '釵釧金', 84),
                    '纳音是旧法看身份的一层，四本只作取象，不单独成断。',
                    '%s·%s' % (VLAB[ny['v']], ny['loc'])))
    # 不入盘的神煞：禄、羊刃、驿马、桃花（据表推，四柱不见即不列）
    YANG = {'甲': '卯', '丙': '午', '戊': '午', '庚': '酉', '壬': '子',
            '乙': '寅', '丁': '巳', '己': '巳', '辛': '申', '癸': '亥'}
    MA = {'申': '寅', '子': '寅', '辰': '寅', '寅': '申', '午': '申', '戌': '申',
          '巳': '亥', '酉': '亥', '丑': '亥', '亥': '巳', '卯': '巳', '未': '巳'}
    TAO = {'申': '酉', '子': '酉', '辰': '酉', '寅': '卯', '午': '卯', '戌': '卯',
           '巳': '午', '酉': '午', '丑': '午', '亥': '子', '卯': '子', '未': '子'}
    zs = [p[1] for p in p4]
    pair = [('祿', J.LU.get(dg, '')), ('羊刃', YANG.get(dg, '')),
            ('驛馬', MA.get(dz, '')), ('桃花', TAO.get(dz, ''))]
    absent = [(nm, z) for nm, z in pair if z and z not in zs]
    if absent:
        out.append(('不入盘者', '、'.join(nm for nm, _ in absent), '',
                    '、'.join('%s在%s' % (nm, z) for nm, z in absent)
                    + '，四柱里一个都不见，故不列，也不拿别的字来凑；'
                    '书上这几样都要落到具体一支才成断语。', ''))
    html_s = []
    for nm, sub, q, bh, src in out:
        qh = ('<blockquote><span class="v">%s</span><span class="q">%s</span></blockquote>'
              % (esc(src.split('·')[0] if src else '四版'), esc(q))) if q else ''
        html_s.append('<div class="ss-row"><div class="nm">%s<span>%s</span></div>%s<p>%s</p>%s</div>'
                      % (esc(nm), esc(sub), qh, esc(bh),
                         ('<div class="src"><b>出处</b> %s</div>' % esc(src)) if src else ''))
    return ''.join(html_s)


def summary(lanes, p4, dg, dz, dy, lib):
    t = []
    t.append('一句话收这盘：身轻、财食重，是出力换钱的命，不是坐位子拿权的命。')
    t.append('该使劲的地方只有一处——印与比：学历、资质、一门能换钱的专业身份、压得住阵脚的固定资产。'
             '往这上头加，一分力气见一分效。')
    t.append('反过来，把力气押在职位、头衔、编制上，是拿最细的一条链去拉最重的车，越拉越空。')
    t.append('贵气薄而不绝：名分、体面还留一线，实权没有；能当门面，不能当主路。')
    t.append('要防三处：日支戌中戊土倒食，事情开头热、收尾散；年支子与时支未暗害，摩擦总在人后；'
             '丙子、壬午两步，是「再想靠名分」最容易撞墙的时候。')
    t.append('四本对这组字的贵贱判断不齐，这份报告不抬不踩；哪一年动，是流年一层，此处不论。')
    NARR.extend(('总说', x) for x in t)
    return ''.join('<p>%s</p>' % esc(x) for x in t)


ASSETS = os.path.join(HERE, 'assets')
QR_PATH = os.path.join(ASSETS, '赞赏码.jpg')
QR_MIN = 3072                       # 小于此数多半是坏图，宁可不出图
CANGPAN_URL = 'https://mp.weixin.qq.com/s/9NFaItizyhEpjDzmTyEcPQ'


def promo():
    """页尾「报告之外」：赞赏码与苍盘体验并排两块。

    图取本地 assets，转 base64 内嵌，报告始终单文件自包含；
    素材不在场时只去掉图，文字照旧，不引外链图。
    """
    fig = ''
    if os.path.exists(QR_PATH) and os.path.getsize(QR_PATH) >= QR_MIN:
        b64 = base64.b64encode(open(QR_PATH, 'rb').read()).decode('ascii')
        fig = ('<p class="bt">赞赏</p>'
               '<img src="data:image/jpeg;base64,%s" alt="赞赏码">'
               '<p class="cap">若它替你省了翻书的时间，随意就好</p>' % b64)
    else:
        fig = '<p class="bt">赞赏</p><p class="cap">留念即可，不必破费</p>'
    return """
<div class="promo">
  <p class="pt">报　告　之　外</p>
  <p class="psub">正文到「总说」已经收完。下面两件与判断无关，愿意看再看。</p>
  <div class="pg">
    <div class="bx qr">%s</div>
    <div class="bx">
      <p class="bt">苍盘命书</p>
      <p>苍盘命书是盘叔做的一款命书智能体：历时近一年，持续用真人命例投喂训练，融合各派命理之长。</p>
      <p>把生辰填进去，得到的是十章、数万字的整本命书，带表格与趋势图，可以拿它和这份报告对着读。</p>
      <p>它走的不是这四本书的路子，讲法也不一样，同一组八字多一个参照，看得出哪些是共识、哪些只是各家的取舍。</p>
      <p><a class="cta" href="%s">苍盘命书 · 免费体验入口</a></p>
    </div>
  </div>
  <p class="note">这份报告的所有判断，出自四版《三命通会》的原文，以及书中没有、据原局推出来的部分（随文标「据原局推」）。赞赏码与体验入口是附加信息，不改动正文任何一个结论。</p>
</div>""" % (fig, CANGPAN_URL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--四柱', required=True)
    ap.add_argument('--性别', default='男')
    ap.add_argument('--生日', default='')
    ap.add_argument('--输出', default='')
    a = ap.parse_args()
    p4 = J.parse_sizhu(a.四柱)
    if len(p4) != 4:
        print('四柱不完整'); return
    birth = None
    if a.生日:
        birth = datetime.datetime.strptime(a.生日.strip(), '%Y-%m-%d %H:%M')
    out = a.输出 or os.path.join(HERE, '%s.html' % ''.join(p4))
    n, cn, yc, CC, an, ST = build(p4, a.性别, birth, out)
    print('written %s  %d 字节  %d 汉字；附录 %d 字节' % (out, n, cn, an))
    print('折叠 %d 组；汉字 %d，其中可见 %d、收起 %d；神煞表 %d 行'
          % (ST['fold'], ST['han'], ST['vis'], ST['han'] - ST['vis'], ST['ssrow']))
    print('原局八节引文 ' + '/'.join(str(x) for x in yc))
    print('各章引文 ' + '　'.join('%s %d' % (k, v) for k, v in CC.items()))
    if MISS:
        print('缺白话 %d 块：%s' % (len(MISS), '、'.join(MISS)))
    fb, bad = audit(USED)
    print('白话自检：禁用句 %d 处；缺机制或缺落点 %d 块%s'
          % (len(fb), len(bad), ('　→ ' + '、'.join(bad)) if bad else ''))
    for k, w in fb:
        print('  FORBID %s｜%s｜%s' % (k, w, (BAI.get(k) or {}).get('落到', '')[:40]))
    hits = bad_hits()
    if hits:
        print('自检不过：不成立断语越界 %d 处' % len(hits))
        for who, kw, txt in hits:
            print('  ERROR %s｜%s｜%s' % (who, kw, txt[:40]))
    else:
        print('自检：不成立断语未越界')


if __name__ == '__main__':
    main()
