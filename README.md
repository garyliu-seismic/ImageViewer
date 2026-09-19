# 图片 / 漫画浏览器

本地图片 / 漫画阅读器，含 **桌面版**（Python + tkinter）和 **网页版**（单文件 HTML）。

## 文件说明

| 文件 | 说明 |
|------|------|
| `image_viewer.py` | 桌面版主程序（tkinter + Pillow） |
| `image-viewer.html` | 网页版（单文件，浏览器直接打开） |
| `caption_engine.py` | 视频实时字幕引擎（vosk 识别 + 翻译） |
| `translation_engine.py` | 离线字幕翻译（Argos / ctranslate2） |
| `dlna_cast.py` | DLNA 投屏（SSDP 发现 + AVTransport SOAP 控制 + 本地流媒体） |
| `viewer.ico` | 程序图标 |
| `image_viewer.json` | 阅读进度（运行时自动生成，不纳入版本控制） |

## 运行

### 桌面版

```bash
pip install Pillow        # 必需
pip install python-vlc    # 可选：播放视频需要（另需安装 VLC）
pip install vosk sounddevice          # 可选：视频实时字幕需要
pip install ctranslate2 sentencepiece # 可选：字幕翻译成中文需要
python image_viewer.py
```

视频页可点击 **CC 字幕** 开启本地实时字幕（基于 vosk，离线识别，无需联网），旁边
两个下拉框选**音频语言**（中文 / 英文 / 日语）和**字幕**（原声 / 中文翻译 / AI 翻译；
选中文音频时翻译选项不可用）。默认模型路径：

| 语言 | 默认路径 | 环境变量覆盖 |
|------|----------|--------------|
| 中文 | `C:\models\vosk-model-small-cn-0.22` | `VOSK_MODEL_PATH_ZH` |
| 英文 | `C:\models\vosk-model-small-en-us-0.15` | `VOSK_MODEL_PATH_EN` |
| 日语 | `C:\models\vosk-model-small-ja-0.22` | `VOSK_MODEL_PATH_JA` |

**字幕翻译**有两种方式：

- **中文翻译（离线）**：用 [Argos Open Tech](https://www.argosopentech.com/) 的
  离线模型（ctranslate2 格式），默认放在 `C:\models\argos\en_zh` 和
  `C:\models\argos\ja_en`（日语没有直接的日译中模型，走 日→英→中 两跳），
  环境变量 `ARGOS_MODELS_DIR` 可指定其他目录。翻译只在识别出一整句（不是逐字）
  时才做一次，所以翻译字幕比原声字幕多一点延迟，跟 YouTube 自动翻译字幕一致。
- **AI 翻译（在线，LLM）**：字幕下拉选「AI 翻译」，走 OpenAI 兼容接口实时翻译。
  需先在 **帮助 → AI 字幕翻译设置** 里配置：
  - 服务商预设：DeepSeek / OpenAI / 通义千问 / 本地 Ollama / 自定义（自动填好
    API Base 和模型，如 `deepseek-chat`、`gpt-4o-mini`、`qwen-plus`）；
  - API Key（必填）；未配置或调用失败时自动回退到离线 Argos 翻译。

视频页还支持 **外挂字幕**（`.srt` / `.ass`），在 视图 → 外挂字幕 或按 `S` 选择，
可自动加载与视频同名的字幕文件。

开启字幕后播放音质会降到 16kHz 单声道（vosk 识别要求的格式）。关闭字幕后声音会
保留（音频输出仍由字幕引擎透传播放，避免「开字幕有声音、关字幕变无声」），但
音量滑块依然不生效、音质也仍停留在 16kHz 单声道——直到切换到下一个视频才会恢复
VLC 原生音频输出。

### 投屏（视频页）

视频条右侧「📺 投屏」按钮（或 视图 → 投屏到电视 / 设备）可把当前视频投到局域网里的
DLNA 设备（极米投影仪 / 电视 / 盒子等）。原理是 DLNA：本地起一个 HTTP 服务器把视频
暴露给设备，设备自己解码播放，本地通过 SOAP 控制播放/暂停/进度条。

- 需要设备支持 DLNA（极米/小米/海信等国产设备普遍支持），且与电脑连同一 WiFi
- 投屏后播放/暂停/进度条由本地控制投影仪；音量由投影仪控制
- 支持格式取决于投屏设备（mp4 一般没问题；mkv 视设备而定）
- DLNA 不支持倍速、画面缩放；本地 vosk 实时字幕不跟投
- 再点一次按钮可取消投屏、恢复本地播放（自动续播到原进度）

### 网页版

用浏览器打开 `image-viewer.html` 即可。

## 功能

- 打开 **文件夹 / 多张图片 / zip·cbz 压缩包 / 播放列表（m3u/m3u8）**
- 双页模式、日漫右→左阅读方向、图片对比模式（两图并排）
- 断点续读、跳到指定页、自动翻页
- 自动裁白边、旋转、缩放 / 平移、适应窗口 / 宽度 / 高度
- 缩略图浏览
- 视频播放（mp4 等，需 VLC）
  - 播放控制：倍速 0.5×~60×、进度条拖动跳转、音量、快进/快退（±5s，Ctrl=±30s）
  - 循环模式：A-B 循环 / 单曲循环 / 列表循环 / 列表随机
  - 投屏：把视频投到局域网里的 Chromecast / DLNA 电视 / 盒子（视频条「📺 投屏」按钮）
- 视频实时字幕（vosk 离线识别）+ 离线翻译（Argos）+ AI 翻译（LLM）+ 外挂字幕（.srt/.ass）
- 支持格式：png / jpg / jpeg / gif / webp / bmp / tif / tiff / avif / jfif

## 快捷键

| 按键 | 功能 |
|------|------|
| ← → / PageUp / PageDown | 图片页：翻页；视频页：快退/快进 ±5s（Ctrl=±30s） |
| Home / End | 第一页 / 最后一页 |
| 空格 | 图片页：下一页；视频页：播放 / 暂停 |
| 滚轮 / 触控板上下滑 | 缩放（以鼠标为中心） |
| 触控板捏合（Ctrl+滚轮） | 缩放 |
| 触控板左右滑 | 翻页 |
| + / - | 放大 / 缩小 |
| 拖拽 | 平移 |
| 点击画面左 / 右边缘 | 翻页（方向随阅读方向） |
| 双击画面中间 | 适应窗口 ↔ 实际大小 |
| R / Shift+R | 顺时针 / 逆时针旋转 90° |
| 0 / 1 / 2 / 3 | 适应窗口 / 实际大小 / 适应宽度 / 适应高度 |
| D | 双页模式 开 / 关 |
| M | 阅读方向 左→右 / 右→左（日漫） |
| C | 裁白边 开 / 关 |
| G | 跳到指定页 |
| A | 自动翻页 开 / 关 |
| [ / ] | 自动翻页停留时间 - / + 0.5 秒 |
| 回车 / F / F11 | 全屏 |
| T | 显示 / 隐藏缩略图 |
| S | 视频页：外挂字幕 (.srt/.ass) |
| ? | 帮助 |
