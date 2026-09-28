# Music

Roylyl的个人音乐资料库。仓库以李志作品为主，按发行版本保存音频、封面、曲目资料和来源记录，也收录其他歌手的部分作品。网页播放器入口：[Roylyl Music](https://roylyl.github.io/music/)。

[总目录](library.json) · [播放器索引](tracks.json) · [数据说明](LIBRARY_GUIDE.md) · [曲目检查报告](reports/track-file-audit.json)

## 当前收录

截至2026年9月28日，总目录包含180个发行条目、855条版本化曲目记录。其中848条有本地MP3文件，另有7条暂未取得本地音轨（6条标记为`missing`，1条为`streaming-only`）。播放器索引收录848条可播放曲目。

当前仓库共有850个MP3文件：848个编目分轨，以及《这个世界会好吗》的完整来源音轨和《我们也爱南京》的独立长录音。同名歌曲如果来自不同专辑、现场演出或不同版本，会分别保留；曲目以发行版本、碟号和曲序区分。

这些数字取自当前总索引与播放器索引。原[曲目检查报告](reports/track-file-audit.json)记录的是导入前的状态；QQ音乐批次的来源与结果见[导入报告](reports/qq-import-results.json)。

## 目录结构

```text
Music/
├── library.json       总目录，包含已有音源及待补曲目
├── tracks.json        网页播放器使用的可播放曲目索引
├── playlists.json     歌单与收藏曲目资料
├── artists/           按歌手和发行版本整理的作品
├── live/              现场专辑及演出录音
├── collections/       精选与合集
├── covers/            封面来源素材
├── stream/            播放或购买入口记录
├── reports/           检查、来源与待核资料
└── scripts/           目录整理和索引导出工具
```

每张发行目录使用`album.json`记录名称、日期、类型、曲序、时长和来源；封面保存为`cover.jpg`与`cover.webp`。音频路径相对仓库根目录，例如`artists/李志/2004 - 被禁忌的游戏/01-01 - 黑色信封.mp3`，不会写入作者电脑的绝对路径。

`library.json`是完整目录入口。`tracks.json`只列出有本地音频的曲目，包含`id`、`title`、`artist`、`album`、`src`、`cover`、`duration`等字段；`duration`单位为秒。播放页优先读取此索引，再按`src`请求仓库中的音频文件。

## 音频与来源记录

当前播放索引中的文件格式均为MP3。资料库的整理目标是44.1kHz、固定码率320kbps；该规格描述保存文件的编码，不代表低码率来源被转码后恢复了细节。原始来源及其音频参数可在曲目记录的`sourceAudioProperties`等字段中查看。

`sourceStatus`使用`available`、`purchasable`、`streaming-only`和`missing`。音频是否可播放与是否允许公开再分发分别记录；`rightsStatus`和`redistributionAllowed`不能由下载成功自动推定。来源包括用户提供的文件、音乐服务页面、公开分享和视频音轨，相关地址与核查结果保存在总目录和`reports/`中。

## 维护索引

在仓库根目录使用Python3运行以下脚本。导出和路径检查只依赖Python标准库；其他抓取、转码和标签整理脚本所需依赖列在[requirements.txt](requirements.txt)中。

```sh
python3 scripts/export_tracks.py
python3 scripts/check_track_files.py
```

第一条根据`library.json`重建`tracks.json`。第二条核对每条曲目的本地路径、曲目ID、专辑资料和额外MP3，并更新[曲目检查报告](reports/track-file-audit.json)。报告中的`validLocalTrackMapping`覆盖的检查范围比播放器读取路径更广。

原检查报告记录了导入前691条播放器路径的状态。新批次已经更新总索引、播放器索引和网页备用索引；完整检查报告尚未针对本批次重跑，不能把旧报告当作本次验证结果。

## 资料边界与许可

本目录持续补充中；部分发行只编入已取得的曲目，演出分轨和不同版本仍有待核资料。`reports/`保留缺失音源、封面来源、音质疑点和版本差异记录。

仓库没有统一的`LICENSE`文件。音频、封面和其他第三方素材的可下载性不等于可再分发许可；使用或公开传播前应分别核对权利状态。
