#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""r5 phase2 —— 执行导入。
A) 歌迷站（lizhinb）配套 lrc：按显式配对表（专辑id,曲序）逐条抓取->清洗->校验->写入音频旁。
   配对依据：多数曲目的 sourceUrl 与音频同源（st.nj1701.com 同文件夹），精选集按站点配套条目
   （每首歌均有录音室版/Live版因版本标签一一对应）。不覆盖任何已有文件。
B) lrclib 开放库：14 个选定条目（歌名+歌手+时长尽量吻合）-> 写入（同步/纯文本）。
所有写入均记录 manifest。站点占位文件（"没有填词的纯音乐"）不创建文件，仅记录。
"""
import json, os, re, time, subprocess, urllib.request, urllib.parse
from urllib.error import HTTPError

ROOT = '/Users/roylyl/Documents/GitHub/Music'
R5 = os.path.join(ROOT, 'reports/lyrics/supplement-20260929-r5')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'
HDRS = {'User-Agent': UA, 'Referer': 'https://www.lizhinb.com/gequ/'}

def safe_url(u):
    if all(ord(c) < 128 for c in u):
        return u
    return urllib.parse.quote(u, safe=":/?&=+,;@!~*()%-'")

_fetch_cache = {}
def http_get(url, tries=3):
    if url in _fetch_cache:
        return _fetch_cache[url]
    last = ''
    u = safe_url(url)
    for i in range(tries):
        try:
            req = urllib.request.Request(u, headers=HDRS)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
                _fetch_cache[url] = (data, 200)
                return data, 200
        except HTTPError as e:
            if e.code == 404:
                _fetch_cache[url] = (None, 404)
                return None, 404
            last = str(e)
        except Exception as e:
            last = str(e)
        time.sleep(0.8 + 0.7 * i)
    try:
        p = '/tmp/r5_curl.out'
        r = subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UA, '-e', 'https://www.lizhinb.com/',
                            '-w', '%{http_code}', '-o', p, u], capture_output=True, text=True)
        code = (r.stdout.strip().split() or ['000'])[-1]
        if code == '200' and os.path.exists(p):
            b = open(p, 'rb').read()
            os.remove(p)
            _fetch_cache[url] = (b, 200)
            return b, 200
        _fetch_cache[url] = (None, code)
        return None, code
    except Exception as e:
        return None, str(e)

# ---------- 清洗 ----------
TS = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]')
OFFTAG = re.compile(r'^\s*\[offset:\s*([+-]?\d+)\s*\]\s*$', re.I)
META = re.compile(r'^\[(ti|ar|al|by|re|ve|au|length):', re.I)
DROP = re.compile(r'https?://|www\.|\.com|\.cn|\.net|\.org|歌词制作|LRC制作|lrc制作|歌词整理|收集整理|搜集整理|编辑整理|更多歌词|歌词下载|下载歌词|QQ群|微信|微博|头条|快手|抖音|酷狗|酷我|QQ音乐|网易云|虾米|关于李志的记忆|李志歌迷站|版权所有|禁止转载|扫描二维码|支持正版|正版购买|购买地址|专辑发布[:：]|专辑介绍[:：]', re.I)
CRED = re.compile(r'^\s*[\u4e00-\u9fffA-Za-z]{1,12}[:：]')
PLACE = ('没有填词', '纯音乐', '请您欣赏')

def tag_ms(m):
    mm, ss, ff = int(m.group(1)), int(m.group(2)), m.group(3)
    fr = 0 if ff is None else (int(ff) if len(ff) == 3 else int(ff) * 10 if len(ff) == 2 else int(ff) * 100)
    return (mm * 60 + ss) * 1000 + fr

def clean_lz(raw_text, local_title, title_line):
    lines = raw_text.splitlines()
    out = []
    stats = {'drop': 0, 'detag': 0, 'empty': 0, 'duptitle': 0}
    nonzero = False
    ordered = []
    for ln in lines:
        s = ln.rstrip()
        if not s.strip():
            continue
        mo = OFFTAG.match(s)
        if mo:
            if int(mo.group(1)) != 0:
                nonzero = True
            continue
        if META.match(s):
            stats['drop'] += 1
            continue
        body = TS.sub('', s).strip()
        tags = list(TS.finditer(s))
        t0 = min(tag_ms(m) for m in tags) if tags else None
        if DROP.search(body):
            stats['drop'] += 1
            continue
        if not body:
            stats['empty'] += 1
            continue
        if body == local_title and (t0 is None or t0 <= 1200):
            stats['duptitle'] += 1
            continue
        if t0 is not None and t0 <= 1200 and (CRED.match(body) or (t0 <= 300 and ('：' in body or ':' in body) and len(body) <= 40)):
            out.append(body)
            stats['detag'] += 1
            continue
        if t0 is None and CRED.match(body) and len(body) <= 30:
            out.append(body)
            continue
        out.append(s)
        for m in tags:
            ordered.append(tag_ms(m))
    first_ts = min(ordered) if ordered else None
    last_ts = max(ordered) if ordered else None
    mono = all(b >= a for a, b in zip(ordered, ordered[1:]))
    meaningful = sum(1 for ln in out if TS.search(ln) and len(TS.sub('', ln).strip()) >= 2)
    return [title_line] + out, dict(ts_count=len(ordered), first_ts=first_ts, last_ts=last_ts,
                                    monotonic=mono, nonzero=nonzero, meaningful=meaningful, **stats)

# ---------- 数据 ----------
tracks = {t['id']: t for t in json.load(open(os.path.join(ROOT, 'tracks.json')))}
def has_lrc(t):
    p = os.path.splitext(t['src'])[0] + '.lrc'
    return os.path.exists(p) and os.path.getsize(p) > 0
missing_ids = {t['id'] for t in tracks.values() if not has_lrc(t)}

index = json.load(open(os.path.join(ROOT, 'reports/lyrics/supplement-20260929-r3/lizhinb-lyrics-index.json')))
byk = {(e['album_id'], e['song_index']): e for e in index}

def resolve(album_frag, fname_frag):
    for t in tracks.values():
        if (album_frag in t['album'] or album_frag in t['src']) and fname_frag in t['src']:
            return t
    return None

# (album_frag, fname_frag, site_album, site_idx, flags)
# flags: cc=内容核查; manual=人工批准; retry=404重试(源URL推导)
A = [
 ('108个关键词', '01-01 - 她+我们不能失去信仰+1990年的春', 49, 1, ''),
 ('108个关键词', '01-06 - 来了', 49, 6, ''),
 ('108个关键词', '01-09 - 墙上的向日葵', 49, 9, ''),
 ('108个关键词', '01-10 - 阿兰', 49, 10, ''),
 ('108个关键词', '01-17 - 姐姐', 49, 15, ''),
 ('2019 - Best Selection Songs 2004-2018/', '01-01 - 黑色信封', 67, 1, ''),
 ('2019 - Best Selection Songs 2004-2018/', '01-04 - 苍井空', 67, 7, ''),
 ('2019 - Best Selection Songs 2004-2018/', '01-06 - 墙上的向日葵', 67, 11, ''),
 ('2019 - Best Selection Songs 2004-2018/', '01-09 - 杭州', 67, 17, ''),
 ('2019 - Best Selection Songs 2004-2018/', '01-10 - 这个世界会好吗', 67, 19, ''),
 ('2019 - Best Selection Songs 2004-2018/', '02-06 - 墙上的向日葵', 67, 12, 'manual'),
 ('2019 - Best Selection Songs 2004-2018/', '02-07 - 关于郑州的记忆', 67, 13, ''),
 ('2019 - Best Selection Songs 2004-2018/', '02-09 - 杭州', 67, 18, ''),
 ('2019 - Best Selection Songs 2004-2018/', '02-10 - 这个世界会好吗', 67, 20, ''),
 ('Vol.2 - Ballads', '01-01 - 被禁忌的游戏', 68, 1, ''),
 ('Vol.2 - Ballads', '02-01 - 被禁忌的游戏', 68, 2, ''),
 ('Vol.2 - Ballads', '01-04 - 结婚', 68, 7, ''),
 ('Vol.2 - Ballads', '02-04 - 结婚', 68, 8, ''),
 ('Vol.2 - Ballads', '01-10 - 热河', 68, 19, ''),
 ('Vol.2 - Ballads', '02-02 - 梵高先生', 68, 4, 'cc'),
 ('Vol.2 - Ballads', '02-03 - 妈妈', 68, 6, ''),
 ('Vol.2 - Ballads', '02-05 - 铅笔', 68, 10, ''),
 ('Vol.2 - Ballads', '02-08 - 下雨', 68, 16, ''),
 ('Vol.2 - Ballads', '01-12 - 你离开了南京', 68, 23, 'cc'),
 ('Vol.2 - Ballads', '02-12 - 你离开了南京', 68, 24, 'cc'),
 ('Vol.3 - 倒影', '01-06 - 尽头（2011）', 70, 11, ''),
 ('Vol.3 - 倒影', '01-07 - 大象（2014）', 70, 13, ''),
 ('Vol.3 - 倒影', '01-08 - 定西（2014）', 70, 15, ''),
 ('Vol.3 - 倒影', '01-09 - 一个夜晚（2016）', 70, 17, ''),
 ('Vol.3 - 倒影', '01-10 - 倒影（2009）', 70, 19, ''),
 ('Vol.3 - 倒影', '02-02 - 董卓瑶', 70, 4, ''),
 ('Vol.3 - 倒影', '02-03 - 翁庆年的六英镑', 70, 6, ''),
 ('Vol.3 - 倒影', '02-04 - 爱', 70, 8, ''),
 ('Vol.3 - 倒影', '02-05 - 忽然', 70, 10, ''),
 ('Vol.3 - 倒影', '02-06 - 尽头', 70, 12, ''),
 ('Vol.3 - 倒影', '02-07 - 大象', 70, 14, ''),
 ('Vol.3 - 倒影', '02-08 - 定西', 70, 16, ''),
 ('Vol.3 - 倒影', '02-09 - 一个夜晚', 70, 18, ''),
 ('Vol.3 - 倒影', '02-10 - 倒影', 70, 20, ''),
 ('2015 - i／O', '01-01 - 杭州', 54, 1, ''),
 ('2015 - i／O', '01-02 - 墙上的向日葵', 54, 2, ''),
 ('2015 - i／O', '01-03 - 铅笔', 54, 3, ''),
 ('2015 - i／O', '01-04 - 来了', 54, 4, ''),
 ('2015 - i／O', '01-05 - 下雨+董卓瑶+忽然', 54, 5, ''),
 ('2015 - i／O', '01-07 - 妈妈', 54, 7, ''),
 ('2015 - i／O', '01-08 - 定西', 54, 8, ''),
 ('2015 - i／O', '01-10 - 鸵鸟+天空之城', 54, 10, ''),
 ('2015 - i／O', '01-11 - 山阴路的夏天', 54, 11, ''),
 ('十月十六日事件', '01-01 - 黒色信封', 43, 1, ''),
 ('十月十六日事件', '01-08 - 被禁忌的游戯', 43, 7, ''),
 ('十月十六日事件', '02-08 - 驼鸟', 43, 21, ''),
 ('十月十六日事件', '02-12 - 家郷', 43, 25, ''),
 ('你好，郑州', '01-08 - 路', 44, 8, ''),
 ('勾三搭四', '01-05 - 你的早晨&天空之城&暧昧', 52, 5, 'manual'),
 ('勾三搭四', '01-08 - 离婚', 52, 8, ''),
 ('勾三搭四', '01-16 - 来了', 52, 16, ''),
 ('勾三搭四', '01-17 - 妈妈', 52, 17, ''),
 ('勾三搭四', '01-20 - 杭州&我们不能失去信仰', 52, 20, 'manual'),
 ('叁缺壹吉隆坡站', '01-04 - 逼言逼语', 72, 4, 'cc'),
 ('叁缺壹吉隆坡站', '01-10 - 逼言逼语', 72, 10, 'cc'),
 ('叁缺壹吉隆坡站', '01-25 - 逼言逼语', 72, 25, 'cc'),
 ('工体东路没有人', '01-03 - 来了', 41, 3, ''),
 ('工体东路没有人', '01-06 - 阿兰', 41, 6, ''),
 ('工体东路没有人', '01-08 - 他们', 41, 8, ''),
 ('工体东路没有人', '01-11 - 这个世界会好么', 41, 11, 'manual'),
 ('工体东路没有人', '01-13 - 月亮代表我的心', 41, 13, ''),
 ('工体东路没有人', '01-15 - 青春', 41, 15, ''),
 ('工体东路没有人', '01-16 - 想起了他', 41, 16, 'manual'),
 ('2009 - 我爱南京', '01-03 - 结婚', 42, 3, ''),
 ('2009 - 我爱南京', '02-02 - 听妈妈讲那过去的事情', 42, 11, ''),
 ('2009 - 我爱南京', '02-07 - 再见', 42, 16, 'cc'),
 ('挺 不插电巡演 郑州站', '01-07 - 忽然 余赣宁', 50, 7, ''),
 ('电声与管弦乐/', '01-01 - 序曲', 63, 1, 'cc'),
 ('电声与管弦乐/', '01-02 - 杭州', 63, 2, ''),
 ('电声与管弦乐/', '01-03 - 尽头', 63, 3, ''),
 ('电声与管弦乐/', '01-04 - 定西', 63, 4, ''),
 ('电声与管弦乐/', '01-07 - 铅笔', 63, 7, ''),
 ('电声与管弦乐/', '01-09 - 墙上的向日葵', 63, 9, ''),
 ('管弦乐II', '01-01 - 相信未来序曲', 64, 1, 'cc'),
 ('管弦乐II', '01-02 - 一头偶像', 64, 2, ''),
 ('管弦乐II', '01-03 - 你好明天', 64, 3, ''),
 ('管弦乐II', '01-05 - 山阴路的夏天', 64, 5, ''),
 ('管弦乐II', '01-08 - 家乡', 64, 8, ''),
 ('管弦乐II', '01-09 - 这个世界会好吗', 64, 9, ''),
 ('北京不插电', '01-02 - 鸵鸟', 60, 2, ''),
 ('北京不插电', '01-03 - 大象', 60, 3, ''),
 ('北京不插电', '01-04 - 定西', 60, 4, ''),
 ('北京不插电', '01-05 - 这个世界会好吗', 60, 5, ''),
 ('北京不插电', '01-07 - 关于郑州的记忆', 60, 7, ''),
 ('北京不插电', '01-08 - 杭州', 60, 8, ''),
 ('北京不插电', '01-09 - 热河', 60, 9, ''),
 ('北京不插电', '01-11 - 鼠说', 60, 11, ''),
 ('北京不插电', '01-12 - 山阴路的夏天', 60, 12, ''),
 ('2005 - 梵高先生', '01-01 - 你离开了南京', 38, 1, 'cc'),
 ('2005 - 梵高先生', '01-05 - 广场', None, None, 'skip-nosource'),
 ('2019 - 洗心革面 - 演唱会录音', '01-01 - 一个夜晚', 69, 12, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-02 - 你好明天', 69, 16, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-03 - 你离开了南京', 69, 25, 'retry'),
 ('2019 - 洗心革面 - 演唱会录音', '01-04 - 倒影', 69, 6, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-07 - 哦吼', 69, 18, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-08 - 大象', 69, 21, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-10 - 寻找+忽然+热河', 69, 20, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-12 - 山阴路的夏天', 69, 24, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-17 - 被禁忌的游戏', 69, 17, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-19 - 门', 69, 22, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-21 - 黑色信封', 69, 19, ''),
 ('2019 - 洗心革面 - 演唱会录音', '01-22 - 意味', 69, 1, ''),
 ('洗心革面（歌迷站26轨版）', '01-01 - 意味', 69, 1, ''),
 ('洗心革面（歌迷站26轨版）', '01-02 - 鸵鸟', 69, 2, ''),
 ('洗心革面（歌迷站26轨版）', '01-03 - 墙上的向日葵', 69, 3, ''),
 ('洗心革面（歌迷站26轨版）', '01-04 - 这个世界会好吗', 69, 4, ''),
 ('洗心革面（歌迷站26轨版）', '01-05 - 定西', 69, 5, ''),
 ('洗心革面（歌迷站26轨版）', '01-06 - 倒影', 69, 6, ''),
 ('洗心革面（歌迷站26轨版）', '01-09 - 求婚+结婚', 69, 9, ''),
 ('洗心革面（歌迷站26轨版）', '01-10 - 关于郑州的回忆', 69, 10, ''),
 ('洗心革面（歌迷站26轨版）', '01-11 - 董卓瑶+春末的南方城市', 69, 11, ''),
 ('洗心革面（歌迷站26轨版）', '01-12 - 一个夜晚', 69, 12, ''),
 ('洗心革面（歌迷站26轨版）', '01-16 - 你好明天', 69, 16, ''),
 ('洗心革面（歌迷站26轨版）', '01-17 - 被禁忌的游戏', 69, 17, ''),
 ('洗心革面（歌迷站26轨版）', '01-18 - 哦吼', 69, 18, ''),
 ('洗心革面（歌迷站26轨版）', '01-19 - 黑色信封', 69, 19, ''),
 ('洗心革面（歌迷站26轨版）', '01-20 - 寻找+忽然+热河', 69, 20, ''),
 ('洗心革面（歌迷站26轨版）', '01-21 - 大象', 69, 21, ''),
 ('洗心革面（歌迷站26轨版）', '01-22 - 门', 69, 22, ''),
 ('洗心革面（歌迷站26轨版）', '01-23 - 尽头+来了', 69, 23, ''),
 ('洗心革面（歌迷站26轨版）', '01-24 - 山阴路的夏天', 69, 24, ''),
 ('洗心革面（歌迷站26轨版）', '01-25 - 你离开了南京', 69, 25, 'retry'),
 ('洗心革面（歌迷站26轨版）', '01-26 - 纯洁', 69, 26, ''),
 ('爵士乐与不插电新编12首', '01-02 - 离婚', 65, 2, ''),
 ('爵士乐与不插电新编12首', '01-03 - 关于郑州的记忆', 65, 3, ''),
 ('爵士乐与不插电新编12首', '01-04 - 鸵鸟', 65, 4, ''),
 ('爵士乐与不插电新编12首', '01-09 - 爱', 65, 9, ''),
 ('爵士乐与不插电新编12首', '01-11 - 一个夜晚', 65, 11, ''),
 ('2015 - 看见/', '01-05 - 你离开了南京', 56, 5, ''),
 ('2015 - 看见/', '01-09 - 离婚', 56, 9, ''),
 ('2006 - 这个世界会好吗', '01-04 - 我们不能失去信仰', 39, 4, ''),
 ('2006 - 这个世界会好吗', '01-08 - 交河', 39, 8, 'cc'),
 ('这个世界会好吗（2015版本）', '01-01 - 这个世界会好吗', 57, 1, ''),
 ('THREE MISSING', '01-01 - 关于郑州的记忆+董卓瑶', 71, 1, 'manual'),
 ('THREE MISSING', '01-02 - 苍井空', 71, 2, ''),
 ('THREE MISSING', '01-06 - 天空之城', 71, 6, ''),
 ('THREE MISSING', '01-07 - 鸵鸟+墙上的向日葵+鼠说', 71, 7, ''),
 ('THREE MISSING', '01-08 - 这个世界会好吗', 71, 8, ''),
 ('THREE MISSING', '02-02 - 被禁忌的游戏+定西', 71, 10, ''),
 ('THREE MISSING', '02-03 - 大象+门+来了+热河', 71, 11, ''),
 ('THREE MISSING', '02-04 - 寻找+忽然', 71, 12, ''),
 ('THREE MISSING', '02-06 - 你离开了南京', 71, 14, 'cc'),
 ('在每一条伤心的应天大街上', '01-01 - 在每一条伤心的应天大街上', 61, 1, 'cc'),
 ('2012 - IMAGINE', '02-14 - 结尾', 46, 24, 'retry'),
]

written, placeholders, fails, skipped, warns = [], [], [], [], []
for alb_frag, fn_frag, aid, idx, flags in A:
    t = resolve(alb_frag, fn_frag)
    if not t:
        warns.append(f'UNRESOLVED: {alb_frag} | {fn_frag}')
        continue
    if flags == 'skip-nosource':
        skipped.append({'trackId': t['id'], 'title': t['title'], 'reason': '站点无对应条目（多轮检索确认）'})
        continue
    if t['id'] not in missing_ids:
        skipped.append({'trackId': t['id'], 'title': t['title'], 'reason': '已有歌词文件，跳过（不覆盖）'})
        continue
    if not aid:
        skipped.append({'trackId': t['id'], 'title': t['title'], 'reason': '无源'})
        continue
    e = byk.get((aid, idx))
    if not e:
        warns.append(f'NO-INDEX-ENTRY: {aid}#{idx} for {t["title"]}')
        continue
    url = e['lyricsUrl']
    raw, code = http_get(url)
    if raw is None:
        # retry via sourceUrl-derived .lrc
        su = ''
        try:
            su = json.load(open(os.path.join(ROOT, 'library.json')))
        except Exception:
            su = None
        # fallback: derive from sourceUrl via tracks? sourceUrl lives in library.json
        derived = None
        try:
            lib = su
            libmap = {}
            for a in lib['albums']:
                for tt in a.get('tracks', []):
                    libmap[tt['id']] = tt
            s = libmap.get(t['id'], {}).get('sourceUrl', '') or ''
            if s.lower().endswith('.mp3'):
                derived = s[:-4] + '.lrc'
        except Exception:
            derived = None
        if derived:
            raw2, code2 = http_get(derived)
            if raw2 is not None:
                raw, code = raw2, code2
    if raw is None:
        fails.append({'trackId': t['id'], 'title': t['title'], 'album': t['album'], 'url': url, 'http': str(code)})
        continue
    try:
        txt = raw.decode('utf-8-sig')
    except Exception:
        try:
            txt = raw.decode('gbk')
        except Exception:
            txt = raw.decode('utf-8', errors='replace')
    title_line = '{} - {}'.format(t['title'], t['artist'])
    cleaned, chk = clean_lz(txt, t['title'], title_line)
    body_text = '\n'.join(cleaned)
    is_placeholder = any(x in body_text for x in PLACE) and chk['meaningful'] < 3
    ok = (chk['ts_count'] >= 3 and chk['monotonic'] and not chk['nonzero']
          and chk['last_ts'] is not None and chk['last_ts'] / 1000.0 <= t['duration'] + 1.0
          and chk['meaningful'] >= 3 and not is_placeholder)
    if not ok:
        reason = []
        if is_placeholder:
            reason.append('站点标注为纯音乐/无唱词')
        if chk['ts_count'] < 3:
            reason.append(f"时间戳过少({chk['ts_count']})")
        if chk['meaningful'] < 3:
            reason.append(f"有效行过少({chk['meaningful']})")
        if not chk['monotonic']:
            reason.append('时间戳乱序')
        if chk['last_ts'] is not None and chk['last_ts'] / 1000.0 > t['duration'] + 1.0:
            reason.append(f"末时间戳超音轨({round(chk['last_ts']/1000.0 - t['duration'],2)}s)")
        if chk['nonzero']:
            reason.append('offset非零')
        placeholders.append({'trackId': t['id'], 'title': t['title'], 'album': t['album'],
                             'siteTitle': e['title'], 'url': url, 'reason': '；'.join(reason),
                             'stats': {k: chk[k] for k in ('ts_count', 'meaningful', 'first_ts', 'last_ts')},
                             'flags': flags})
        continue
    tgt = os.path.splitext(os.path.join(ROOT, t['src']))[0] + '.lrc'
    if os.path.exists(tgt):
        skipped.append({'trackId': t['id'], 'title': t['title'], 'reason': '目标已存在（不覆盖）'})
        continue
    # final letter: remove trailing spaces inside lines
    final = '\n'.join(ln.rstrip() for ln in cleaned) + '\n'
    open(tgt, 'w', encoding='utf-8', newline='\n').write(final)
    written.append({
        'trackId': t['id'], 'title': t['title'], 'artist': t['artist'], 'album': t['album'],
        'target': os.path.relpath(tgt, ROOT), 'source': 'lizhinb',
        'siteAlbum': aid, 'siteIndex': idx, 'siteTitle': e['title'], 'url': url,
        'matchType': {'manual': '人工配对（标题变体/笔误）', 'retry': '重试成功（sourceUrl推导）', 'cc': '内容核查通过'}.get(flags, '配套条目配对'),
        'tsCount': chk['ts_count'], 'meaningful': chk['meaningful'],
        'firstTs': round(chk['first_ts'] / 1000.0, 3) if chk['first_ts'] is not None else None,
        'lastTs': round(chk['last_ts'] / 1000.0, 3) if chk['last_ts'] is not None else None,
        'localDuration': round(t['duration'], 3),
        'dropStats': {k: chk[k] for k in ('drop', 'detag', 'empty', 'duptitle')},
        'note': '歌迷站配套lrc（与库内音频同源发行）；文本级校验通过（单调/界内/广告清理）；未逐句听辨'
    })
    print('OK', t['title'][:30], '->', os.path.relpath(tgt, ROOT)[-40:], f"[{chk['ts_count']}ts]", flush=True)

print(f'\n[LZ] written={len(written)} placeholder/skip={len(placeholders)} fails={len(fails)} skipped={len(skipped)} warns={len(warns)}')
for w in warns:
    print('  WARN', w)
for f in fails:
    print('  FAIL', f['title'], f['http'])

# ---------- lrclib ----------
def lrclib_get(eid):
    url = f'https://lrclib.net/api/get/{eid}'
    raw, code = http_get(url)
    if raw is None:
        return None, code
    try:
        return json.loads(raw.decode('utf-8')), code
    except Exception:
        return None, 'parse'

LC = [
    (36184015, '皇后大道东'),
    (28541586, '不再让你孤单'),
    (28213092, '寂寞的季节'),
    (18444203, 'Too Bad'),
    (36774632, '不说'),
    (30621459, '我继续'),
    (30636654, '剪云者'),
    (15770862, '丹宁执着'),
    (28759331, '成长之重量'),
    (29069144, '之乎者也'),
    (17266707, '8:15pm'),
    (12884022, 'Stay With You'),
    (20705522, '伟大的渺小'),
    (36226436, '河流'),
]
lc_written, lc_skipped = [], []
miss_tracks = [t for t in tracks.values() if t['id'] in missing_ids]
for eid, title_kw in LC:
    cands = [t for t in miss_tracks if title_kw in t['title']]
    if not cands:
        lc_skipped.append({'entryId': eid, 'title': title_kw, 'reason': '本地缺失列表中无对应曲目'})
        continue
    j, code = lrclib_get(eid)
    if not j:
        lc_skipped.append({'entryId': eid, 'title': title_kw, 'reason': f'fetch失败 {code}'})
        continue
    dur_e = j.get('duration') or 0
    cands.sort(key=lambda t: abs(t['duration'] - dur_e))
    t = cands[0]
    diff = abs(t['duration'] - dur_e)
    if diff > 1.6:
        lc_skipped.append({'entryId': eid, 'title': title_kw, 'reason': f'时长差过大 Δ{diff:.2f}s'})
        continue
    content = j.get('syncedLyrics') or j.get('plainLyrics') or ''
    has_ts = '[0' in content or bool(re.search(r'\[\d{1,2}:\d{2}', content))
    lines = [ln.rstrip() for ln in content.replace('\r\n', '\n').split('\n')]
    cl = []
    for ln in lines:
        if not ln.strip():
            continue
        if DROP.search(TS.sub('', ln)):
            continue
        if re.match(r'^\[(ti|by|re|ve|au|length):', ln, re.I):
            continue
        cl.append(ln)
    title_line = '{} - {}'.format(t['title'], t['artist'])
    out = [title_line] + cl
    # validate if synced
    if has_ts:
        ordered = []
        for ln in cl:
            for m in TS.finditer(ln):
                ordered.append(tag_ms(m))
        mono = all(b >= a for a, b in zip(ordered, ordered[1:]))
        lastok = (not ordered) or ordered[-1] / 1000.0 <= t['duration'] + 2.5
        if not mono or not lastok:
            lc_skipped.append({'entryId': eid, 'title': title_kw,
                               'reason': f'校验失败 mono={mono} lastOk={lastok}'})
            continue
    tgt = os.path.splitext(os.path.join(ROOT, t['src']))[0] + '.lrc'
    if os.path.exists(tgt):
        lc_skipped.append({'entryId': eid, 'title': title_kw, 'reason': '目标已存在'})
        continue
    open(tgt, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    lc_written.append({
        'trackId': t['id'], 'title': t['title'], 'artist': t['artist'],
        'target': os.path.relpath(tgt, ROOT), 'source': 'lrclib', 'entryId': eid,
        'entryAlbum': j.get('albumName'), 'entryArtist': j.get('artistName'),
        'synced': has_ts, 'durationDiff': round(diff, 3),
        'lineCount': len(out),
        'note': '开放歌词库lrclib条目（用户上传）；按歌名+歌手+时长匹配；同步优先；未逐句听辨'
    })
    print('OK[lrclib]', t['title'][:30], '->', os.path.relpath(tgt, ROOT)[-40:], f"[{'sync' if has_ts else 'plain'}]", flush=True)

json.dump({'generatedAt': '2026-09-29', 'round': 'r5', 'source': 'lizhinb companion lrc (st.nj1701.com)',
           'written': len(written), 'imports': written,
           'placeholders': placeholders, 'fails': fails, 'skipped': skipped, 'warns': warns},
          open(os.path.join(R5, 'lizhinb-imports-r5.json'), 'w'), ensure_ascii=False, indent=1)
json.dump({'generatedAt': '2026-09-29', 'round': 'r5', 'source': 'lrclib.net open database',
           'written': len(lc_written), 'imports': lc_written, 'skipped': lc_skipped},
          open(os.path.join(R5, 'lrclib-imports-r5.json'), 'w'), ensure_ascii=False, indent=1)
print(f"\n[LRCLIB] written={len(lc_written)} skipped={len(lc_skipped)}")
for s in lc_skipped:
    print('  skip', s['title'], '|', s['reason'])
print('DONE. lz written:', len(written), '| lrclib written:', len(lc_written))
