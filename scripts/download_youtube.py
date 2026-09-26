"""Preserve the best exposed audio stream; no lossy-to-lossless conversions."""
from pathlib import Path
import argparse,json,os,shutil
from yt_dlp import YoutubeDL
import imageio_ffmpeg
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--folder',required=True);args=p.parse_args()
out=R/args.folder
if not out.resolve().is_relative_to(R):raise SystemExit('Destination must be inside repository')
out.mkdir(parents=True,exist_ok=True)
options={'format':'bestaudio','outtmpl':str(out/'full-concert.%(ext)s'),'noplaylist':True,'retries':1,'fragment_retries':1,'socket_timeout':30,'ffmpeg_location':imageio_ffmpeg.get_ffmpeg_exe(),'postprocessors':[]}
node=os.environ.get('MUSIC_NODE') or shutil.which('node')
if node:options['js_runtimes']={'node':{'path':node}}
try:
 with YoutubeDL(options) as ydl:info=ydl.extract_info(args.url,download=True)
 record={k:info.get(k) for k in ['id','title','webpage_url','channel','channel_url','upload_date','duration','acodec','asr','abr','audio_channels','chapters','license']}
 record.update(rightsStatus='unverified-third-party',lossless=False,sourceStatus='available',localFiles=[str(f.relative_to(R)) for f in out.glob('full-concert.*') if f.suffix not in ['.part','.json']])
 (out/'recording.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
except Exception as e:
 (out/'youtube-error.json').write_text(json.dumps({'url':args.url,'error':str(e)},ensure_ascii=False,indent=2));raise
