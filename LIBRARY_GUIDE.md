# 音乐资料库

本仓库以李志作品为第一阶段。`library.json`是总索引，各发行目录内的`album.json`记录曲目、版本和来源。当前是可继续补全的资料库，不宣称穷尽全部非正式录音或全部再版。

## 当前音频规格

按用户要求，音频统一为44.1kHz、固定码率320kbps的MP3，每个已编目曲目只保留一个文件。不同专辑或演出的录音仍按原版本分别编目。整场录音和含未归属片段的长音轨独立保存为MP3。已有符合规格的MP3直接保留，其他文件转码后移除旧副本。

320kbps描述输出编码，不表示原音源质量得到提高。原始编码、时长、来源和疑似转码信息保留在`sourceAudioProperties`、`sourceAssetHistory`与转换报告中；历史来源路径不是当前播放路径。以`localPath`和`tracks.json`为准。转换记录见`reports/mp3-normalization.json`，逐文件抽样解码检查见`reports/mp3-validation.json`。

## 目录与数据

- `artists/李志/`：录音室专辑、单曲。
- `artists/<歌手名>/`：其他歌手按各自名称建立专辑目录；当前每张只录入用户指定曲目，`tracklistCompleteness=partial`。
- `live/李志/`：正式现场专辑、演出录音，二者用`type`区分。
- `collections/李志/`：日本精选系列。
- `covers/originals/`：可获取的OneDrive和网页封面来源文件。专辑目录保存`cover.jpg`和`cover.webp`。
- `reports/covers.json`：逐张记录封面路径、像素尺寸、来源和低分辨率标记。
- `reports/wav-conversions.json`：本地WAV转44.1kHz FLAC的路径与音频参数记录；原WAV在转换检查通过后已移除。
- `reports/metadata-standardization.json`：主音轨重命名和音频标签写入记录。
- `reports/duplicate-onedrive-review.json`：八首同录音的重复来源清理记录；云端OneDrive原件未改动。
- `stream/links.json`：播放／购买页面链接，不能直接用作音频URL。
- `reports/`：来源、缺失、版本冲突、下载结果、音质检查与搜索队列。
- `scripts/`：抓取、整理、下载、检查与播放器导出工具。

所有`localPath`相对仓库根目录。曲目`duration`以秒计；`audioProperties.fileSize`以字节计，采样率以Hz计，码率以bit/s计。不确定字段使用`null`或空字符串，不编造日期或时长。`releaseDatePrecision`保留日期精度。

主音轨统一按`碟号-曲序 - 曲名.扩展名`命名；同曲的其他来源保留独立后缀。FLAC、MP3、M4A和Opus文件写入标题、歌手、专辑、专辑歌手、曲序、碟号、已确认精度的发行日期及内嵌前封面。专辑目录统一保存`cover.jpg`和`cover.webp`；内嵌封面由`cover.jpg`缩小生成，不将低分辨率来源放大伪装为高清图。

音频标签采用白名单重建：写入前清除原评论、网址、歌词、账号、购买信息、私有字段和编辑软件历史，MP3同时移除APEv2与ID3v1。来源与音质疑点保留在JSON记录中。长音轨和录音节选不冒充正式专辑曲目。

`scripts/standardize_metadata.py`对所有实际音频执行清理，存在未映射文件时会停止。`scripts/validate_clean_metadata.py`复读全部文件，检查标签白名单、核心字段、封面图片与音频基本参数；结果见`reports/metadata-clean-validation.json`。macOS的FLAC/Opus封面图标另由`scripts/set_finder_cover_icons.swift`设置，仅影响本机Finder显示，不能替代文件内的封面。

同名歌曲可能有多个现场版本；曲目ID包含发行版本、碟号和曲序。`catalogDuration`保留资料库原始时长，`duration`在取得文件后使用本地测得的时长。长串烧不会被冒充为多个独立录音。

`type`支持`studio`、`ep`、`single`、`live`、`concert`、`compilation`、`special`。未找到可靠发行证据的类型不创建虚构专辑。再版信息放在`editions`与`selectedEdition`中。

## 来源状态

|sourceStatus|含义|
|---|---|
|available|已取得可读取的本地文件；授权状态另外记录|
|purchasable|找到对应数字购买入口，尚未购买|
|streaming-only|找到播放入口，尚无对应本地文件|
|missing|本次已核来源中未确认可用数字来源；不是“全网不存在”的证明|

已按用户补充要求纳入公开第三方分享及YouTube音轨。`rightsStatus=unverified-third-party`表示未核实权利人授权；`redistributionAllowed=false`表示尚未确认可公开再分发。脚本不自动提交、推送或部署。

`format`是实际本地文件编码，不是商店宣传格式。Bandcamp出售的格式和采样规格位于`sources`内；尚未购买的曲目不会伪造本地音质参数。

## 音质处理

保留下载文件的实际编码；不进行MP3→FLAC、AAC→FLAC或采样率升频。YouTube选择可用的最佳音频流，保存原始容器；章节拆分用FFmpeg复制音频包，不重新编码。

无损文件的抽样频谱检查只用于发现可疑低通。`suspected_transcode=true`需要人工复核；`false`只代表本次启发式未发现明显特征；`null`表示未检查、不适用或无法判断。该检查不能证明母带无损，也不能可靠区分早期录音限制和有损转码。不会自动删除可疑文件。

## 本地使用

在仓库根目录建立Python虚拟环境后安装`requirements.txt`。基础整理脚本可在Python3.9运行；当前YouTube工具需要Python3.10以上及受支持的JavaScript运行时。`MUSIC_NODE`可指定Node可执行文件。

```sh
python scripts/supplement_catalog.py
python scripts/add_fan_concerts.py
python scripts/add_fan_washing_edition.py
python scripts/refresh_search_queue.py
python scripts/prepare_downloads.py
python scripts/download_public.py
python scripts/audit_audio.py
python scripts/finalize_library.py
python scripts/export_tracks.py
python scripts/report_library.py
```

`download_public.py`读取已经核对的公开链接，不自动购买、不读取浏览器登录信息。已成功且来源相同的文件会跳过。失败原因写入`reports/download-results.jsonl`；更换来源时保留旧文件为alternative版本。

抓取目录元数据使用`fetch_catalog.py`、`fetch_full_editions.py`、`fetch_bandcamp.py`。它们缓存成功响应，避免重复请求。`build_library.py`依据这些资料重建初始目录；之后再次运行`finalize_library.py`恢复已下载资产索引。`import_onedrive.py`只导入可明确匹配专辑和曲名的用户现有FLAC。

## 播放器与部署

`tracks.json`只包含已有本地音频的曲目。提供`id`、`title`、`name`、`artist`、`album`、`src`、`url`、`cover`、`duration`等通用字段。购买页和在线播放页不会混进`src`。

```sh
python scripts/export_tracks.py --base-url https://example.com/music
python scripts/export_tracks.py --public --output reports/public-tracks.json
```

第二条命令只导出已明确确认可公开再分发的曲目；当前可能为空。网站仓库已提供`music/`播放器。播放器读取网站侧的`music/data/catalog.json`统一目录；更新索引后，在网站仓库运行`python3 music/scripts/build-catalog.py`重新生成。音源与歌词保留在本仓库，目录更新和网站发布需分别完成。

## 尚待补全

完整性状态、未取得的分轨、未核实日期、缺封面、时长差异和未执行的搜索组合均在`reports/`内保留。`search-queue.json`中的`pending`是真正未执行的搜索，不能作为已经搜遍互联网的证据。直接检索Bandcamp、公开网盘及歌迷站的逐曲匹配记录与搜索引擎查询分别保存。

## 当前交付报告

总览见[reports/overview.md](reports/overview.md)。原始WAV中发现的不完整来源保留为.part，不进入播放器索引。较大的公开Google Drive文件可能出现常规下载确认页，脚本只提交页面提供的公开下载表单；登录页仍会停止。

歌迷站`lizhinb.com`的26轨《洗心革面》独立保存为特别版本，避免把串烧误配到22轨版本；新增义乌、郑州和杭州演出录音。以上演出均标注正式发行未确认。
