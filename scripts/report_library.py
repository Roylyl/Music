"""Summarize real local assets and unresolved catalog evidence, without hashing."""
from pathlib import Path
from collections import Counter
import json
R=Path(__file__).resolve().parents[1];l=json.loads((R/'library.json').read_text());tracks=[t for a in l['albums'] for t in a['tracks']]
def write(n,d):(R/'reports'/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
errors=[];ids=set()
for a in l['albums']:
 if not (R/a['path']/'album.json').exists():errors.append('Missing album.json: '+a['path'])
 for t in a['tracks']:
  if t['id'] in ids:errors.append('Duplicate id: '+t['id'])
  ids.add(t['id'])
  if t['sourceStatus'] not in ['available','purchasable','streaming-only','missing']:errors.append('Invalid status: '+t['id'])
  for x in [t]+t.get('assets',[]):
   p=x.get('localPath','')
   if p and (Path(p).is_absolute() or '..' in Path(p).parts or not (R/p).is_file()):errors.append('Invalid asset path: '+p)
  if t['sourceStatus']=='available' and not t['localPath']:errors.append('Available track has no file: '+t['id'])
files=[p for base in ['artists','live','collections'] for p in (R/base).rglob('*') if p.suffix.lower() in ['.flac','.wav','.mp3','.m4a','.opus','.webm','.alac','.aiff']]
large=[{'path':str(p.relative_to(R)),'bytes':p.stat().st_size} for p in files if p.stat().st_size>100*1024**2]
write('large-files.json',large)
last={}
for line in (R/'reports/download-results.jsonl').read_text().splitlines():
 d=json.loads(line);last[(d['trackId'],d['sourceUrl'])]=d
fail=[d for d in last.values() if d['status']=='failed'];write('download-failures.json',fail)
upgrades=[{'id':t['id'],'album':t['album'],'title':t['title'],'localFormat':t['format'],'offers':[s for s in t['sources'] if s.get('status')=='purchasable']} for t in tracks if t['localPath'] and t['format'].lower() not in ['flac','wav','wave','alac'] and any(s.get('status')=='purchasable' for s in t['sources'])];write('purchase-upgrades.json',upgrades)
write('validation.json',{'valid':not errors,'errors':errors,'albums':len(l['albums']),'tracks':len(tracks),'checks':['Unique track identifiers','Allowed sourceStatus values','Repository-relative existing audio paths','Every release has album.json'],'hashesComputed':False})
coverissues=[{'album':a['title'],'cover':a.get('cover'),'source':a.get('coverSource')} for a in l['albums'] if not a['cover'] or a.get('coverSource',{}).get('lowResolution')];write('cover-review.json',coverissues)
formats=Counter(t['format'] for t in tracks if t['localPath']);available=sum(bool(t['localPath']) for t in tracks);audioBytes=sum(p.stat().st_size for p in files);unknown=sum(a.get('missingTracklistCount',0) for a in l['albums'])
rows=['# 音乐资料库进度','',f'截至2026-09-27，已建立{len(l["albums"])}个发行／录音条目、{len(tracks)}条版本化曲目记录；其中{available}条已有独立本地音频。另有{unknown}条预期曲目尚缺可靠曲单，不计入已编目总数。', '',f'音频文件合计{audioBytes/1024**3:.2f}GiB，含保留的其他来源版本与全场音轨。未计算文件哈希。','', '## 发行目录','', '|发行日期|歌手|名称|类型|曲目数|本地分轨|','|---|---|---|---|---:|---:|']
for a in l['albums']:rows.append(f'|{a["releaseDate"] or "未确认"}|{a["artist"]}|[{a["title"]}](../{a["path"].replace(" ","%20")}/album.json)|{a["type"]}|{len(a["tracks"])}|{sum(bool(t["localPath"]) for t in a["tracks"])}|')
rows+=['','## 实际音质','', '|主要文件编码|曲目数|','|---|---:|']+[f'|{f}|{n}|' for f,n in formats.items()]
rows+=['','音质参数依据本地文件读取。无损容器不等同于无损母带；频谱抽样结果见[audio-audit.json](audio-audit.json)。没有做有损转无损或升频。','', '## 完整性与版本边界','', '- 《我们也爱南京》确认4CD+4DVD，但完整40轨曲序和逐曲表演者尚缺。已保存的31分钟视频仅为节选。',
'- 其他歌手的9张专辑目前各只收录用户指定的1首，album.json已标记tracklistCompleteness=partial，不能视为完整曲单。',
'- 崔健《一块红布》的本地音频约281秒，所查《解决》曲目资料约371秒，具体版本待复核。黄贯中《年少無知》WAV频谱有约16kHz低通，标记疑似转码并保留原文件。',
'- 《将进酒》主DVD目录已录入；赠碟、采访部分仍待核。YouTube分轨依据上传者章节，未经逐首试听确认边界。',
'- 《i/O》正式11轨专辑与31轨非正式录音分开。全场Opus单独保留，尚未伪造分轨。',
'- 《洗心革面》存在MusicBrainz22轨与歌迷站26轨的不同分段。26轨版已独立入库；串烧与独立分轨不能仅凭曲名互换。',
'- 日期冲突、再版、未证实正式发行的录音均保留notes与来源；不能宣称已穷尽所有发行及非正式录音。',
'- 逐曲执行了已抓取目录的标题和版本匹配；多语言搜索引擎组合仍有未执行项，search-queue.json明确标为pending。','', '## 可继续处理的清单','', '- [缺失独立音轨](missing.json)',
'- [时长或章节边界待复核](version-review.json)',
'- [音质检查](audio-audit.json)',
'- [可购买的无损升级候选](purchase-upgrades.json)',
'- [低分辨率封面](cover-review.json)',
'- [全部封面来源与尺寸](covers.json)',
'- [音频标签白名单与内嵌封面检查](metadata-clean-validation.json)',
'- [MP3统一规格与重复副本清理](mp3-normalization.json)',
'- [MP3逐文件抽样解码检查](mp3-validation.json)',
'- [OneDrive音频目录核对](onedrive-audio-review.md)',
'- [失败来源记录](download-failures.json)：某来源失败不代表曲目最终没有替代文件。',
'- [目录补全线索](catalog-leads.json)','', '## 数据与播放器','', '- [library.json](../library.json)：总资料库。',
'- [tracks.json](../tracks.json)：已有本地分轨的通用播放器索引。',
'- [使用说明](../LIBRARY_GUIDE.md)：脚本、单位、字段和导出方法。',
'- 校验结果见[validation.json](validation.json)。未提交或推送GitHub。','', '## GitHub部署','', f'本地音频已超过GitHub Pages的1GB站点限制，且有{len(large)}个文件超过普通Git单文件100MiB限制。播放器页面与JSON可留在Pages，音频应接入另行配置的资源托管；导出脚本支持--base-url。Git LFS可用于仓库存储，但不能直接作为Pages音频托管。','', '依据：[GitHub大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)、[Pages限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)、[Git LFS与Pages限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)。','', '## 主要资料来源','', '- [MusicBrainz](https://musicbrainz.org/artist/e54bc357-19aa-4e1f-9795-3346e486d5db)：发行版本、碟号、曲序和时长。',
'- [李志Bandcamp](https://lizhilizhi.bandcamp.com/)：现售数字版与逐曲购买入口，上架日期不替代初版日期。',
'- [PANDA RECORD](https://panda-record.com/?page_id=1021)：日本精选系列。',
'- [WWR](https://wwr.com.tw/artists/li-zhi)：2025年东京现场发行。',
'- [公开资源目录](https://github.com/PetalsOnaWet/lizhi)、[歌迷播放目录](https://www.lizhinb.com/gequ/)、[公开MP3整理](https://github.com/lvboda/lizhi-mp3)：文件来源。','', '第三方分享与YouTube文件均记录rightsStatus=unverified-third-party，获取文件不代表已确认可公开再分发。']
(R/'reports/overview.md').write_text('\n'.join(rows)+'\n')
print(json.dumps({'available':available,'audioGiB':round(audioBytes/1024**3,2),'formats':dict(formats),'validationErrors':errors},ensure_ascii=False))
