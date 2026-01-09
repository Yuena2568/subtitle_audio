# 字幕音频处理工具

一个功能强大的视频字幕处理工具，支持从 YouTube 下载到最终视频生成的全流程自动化。集成 ASR 语音识别、智能字幕优化、翻译、TTS 语音合成、音频替换等功能。

## ✨ 主要功能

### 核心功能

1. **📥 视频下载**
   - 支持 YouTube 视频下载
   - 自动下载字幕文件（VTT 格式）
   - 自动合并视频和音频流

2. **🎤 ASR 语音识别**
   - 使用 OpenAI Whisper 进行高精度语音转文字
   - 支持多种模型大小（tiny/base/small/medium/large）
   - 自动提取视频音频并识别

3. **🔄 ASR 对比融合**（推荐）
   - 智能对比 ASR 识别结果与 VTT 字幕
   - 基于权重的智能融合，优先使用 ASR 结果（准确性更高）
   - 自动过滤低质量、重复的段落
   - 即使没有 VTT 文件也能正常工作，直接使用 ASR 生成字幕

4. **📝 字幕优化**
   - 自动去重（相邻重复和内部重复）
   - 合并过短段落
   - 文本清理和规范化
   - 权重筛选低质量段落

5. **🌍 翻译功能**
   - 支持 Google 翻译 API
   - 自动语言检测，避免重复翻译
   - 批量翻译优化

6. **🤖 AI 改写**（可选）
   - 使用本地 HuggingFace 模型进行文本改写
   - 支持风格化处理
   - 需要本地模型支持

7. **🔊 TTS 语音合成**
   - 使用 Edge-TTS 生成高质量语音
   - 自动合成完整音频时间线
   - 自动清理临时文件

8. **🎬 视频处理**
   - 自动替换视频音轨
   - 支持批量处理
   - 保持视频原始质量

9. **📦 批量处理**
   - 支持目录批量处理
   - 自动匹配视频和字幕文件
   - 进度显示和错误处理

## 🛠️ 环境要求

- **Python**: >= 3.12
- **uv**: 现代 Python 包管理工具（推荐使用）
- **FFmpeg**: 用于音视频处理（通过 `imageio-ffmpeg` 自动管理）
- **CUDA**（可选）: 如果有 NVIDIA GPU，可以加速 AI 模型运行

## 📦 安装步骤

### 1. 安装 uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 克隆或下载项目

```bash
git clone https://github.com/Yuena2568/subtitle_audio.git
cd subtitle_audio
```

### 3. 安装项目依赖

```bash
# 使用 uv 安装所有依赖
uv sync
```

这将自动安装以下依赖：
- `yt-dlp`: YouTube 视频下载
- `openai-whisper`: ASR 语音识别
- `edge-tts`: TTS 语音合成
- `transformers`: AI 模型支持
- `torch`: PyTorch 深度学习框架
- `pydub`: 音频处理
- `imageio-ffmpeg`: FFmpeg 包装器（自动管理 FFmpeg）
- 其他必要的依赖...

### 4. 验证安装

```bash
# 查看帮助信息
uv run python workflow.py --help

# 或者测试主程序
uv run python main.py --help
```

**✅ 安装完成！** 现在你可以开始使用了。

## 🤖 需要的模型

### 1. Whisper ASR 模型（必需）

项目使用 OpenAI Whisper 进行语音识别。**首次使用时会自动下载**，你只需要选择模型大小：

- **tiny** (39MB): 最快，准确度较低
- **base** (74MB): 平衡选择
- **small** (244MB): **推荐**，准确度和速度的平衡
- **medium** (769MB): 更准确，速度较慢
- **large** (1550MB): 最准确，速度最慢，需要更多显存

**模型会自动下载到缓存目录**，无需手动下载。

### 2. AI 改写模型（可选）

如果你想使用 AI 改写功能，需要下载 HuggingFace 模型。支持任何支持文本生成的模型，例如：

- `facebook/opt-1.3b`: 小型模型，适合快速改写
- `tiiuae/falcon-7b-instruct`: 中型模型，效果更好
- 其他兼容的生成式模型...

**查找本地已有模型**：

```bash
uv run python find_models.py
```

这会扫描你的 HuggingFace 缓存目录（通常在 `~/.cache/huggingface/hub/`），列出所有可用的模型。

**手动下载模型**（如果需要）：

```bash
# 使用 huggingface-cli 下载
pip install huggingface_hub
huggingface-cli download facebook/opt-1.3b
```

## 🚀 使用方法

### 方式一：完整工作流（推荐）

这是最简单的方式，一键完成从下载到最终视频生成的全流程：

```bash
# 基础用法：下载视频并处理
uv run python workflow.py "https://www.youtube.com/watch?v=VIDEO_ID"

# 指定 Whisper 模型大小
uv run python workflow.py "https://www.youtube.com/watch?v=VIDEO_ID" --whisper-model medium

# 禁用翻译（如果视频已经是目标语言）
uv run python workflow.py "https://www.youtube.com/watch?v=VIDEO_ID" --no-translate

# 禁用权重筛选
uv run python workflow.py "https://www.youtube.com/watch?v=VIDEO_ID" --no-weight-filter

# 完整参数示例
uv run python workflow.py "https://www.youtube.com/watch?v=VIDEO_ID" `
    --whisper-model medium `
    --min-weight 0.5 `
    --language zh `
    --no-replace
```

**完整工作流参数说明**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | YouTube 视频 URL | 必需 |
| `--whisper-model` | Whisper 模型大小 (tiny/base/small/medium/large) | small |
| `--no-asr-compare` | 不使用 ASR 对比（使用原始 VTT） | False |
| `--no-weight-filter` | 禁用权重筛选 | False |
| `--min-weight` | 最小权重阈值（低于此值的段落将被删除） | 0.4 |
| `--no-translate` | 不翻译 | False |
| `--language` | 目标语言 (zh/en) | zh |
| `--ai-rewrite` | 启用 AI 改写（需要模型） | False |
| `--model-path` | AI 改写模型路径 | None |
| `--no-replace` | 不替换视频音轨 | False |

**完整工作流执行步骤**：

1. ✅ 下载视频和字幕（如果可用）
2. ✅ 查找下载的文件（自动处理没有 VTT 的情况）
3. ✅ ASR 对比 + 翻译 + TTS
4. ✅ 查找生成的音频文件
5. ✅ 替换视频音轨
6. ✅ 清理临时文件

### 方式二：单文件处理

如果你已经有视频文件或字幕文件，可以直接处理：

```bash
# 处理单个字幕文件（仅优化和导出）
uv run python main.py --file "path/to/subtitle.vtt" --export

# 使用 ASR 对比模式（需要视频文件）
uv run python main.py `
    --file "path/to/video.mp4" `
    --vtt "path/to/subtitle.vtt" `
    --use-asr-compare `
    --whisper-model small `
    --export

# 只使用视频进行 ASR（没有 VTT 文件）
uv run python main.py `
    --file "path/to/video.mp4" `
    --use-asr-compare `
    --whisper-model medium `
    --export

# 添加翻译和 TTS
uv run python main.py `
    --file "path/to/video.mp4" `
    --use-asr-compare `
    --translate `
    --language zh `
    --tts `
    --export

# 替换视频音轨
uv run python main.py `
    --file "path/to/video.mp4" `
    --use-asr-compare `
    --translate `
    --tts `
    --video-replace "path/to/video.mp4" `
    --export

# 使用 AI 改写（需要模型路径）
uv run python main.py `
    --file "path/to/subtitle.vtt" `
    --ai-rewrite `
    --model-path "~/.cache/huggingface/hub/models--facebook--opt-1.3b/snapshots/xxx" `
    --export
```

### 方式三：批量处理

处理整个目录下的文件：

```bash
# 批量处理 VTT 文件
uv run python main.py --dir "download/videos" --pattern "*.vtt" --export

# 批量处理 + ASR 对比 + 翻译 + TTS
uv run python main.py `
    --dir "download/videos" `
    --pattern "*.vtt" `
    --use-asr-compare `
    --translate `
    --tts `
    --batch-video-replace `
    --export

# 指定输出目录
uv run python main.py `
    --dir "download/videos" `
    --output-dir "output/processed" `
    --export
```

## 📁 项目结构

```
subtitle_audio/
├── main.py                 # 主处理脚本（单文件和批量处理）
├── workflow.py             # 完整工作流脚本（推荐使用）
├── download_youtobe.py     # YouTube 下载模块
├── pyproject.toml          # 项目依赖配置
├── subtitle/               # 核心处理模块
│   ├── segmenter.py        # 字幕解析（VTT/SRT/TXT/JSON）
│   ├── asr.py              # ASR 语音识别
│   ├── asr_compare.py      # ASR 对比融合（核心功能）
│   ├── optimizer.py        # 字幕优化（去重、合并等）
│   ├── translator.py       # 翻译功能
│   ├── ai_rewriter.py      # AI 改写
│   ├── tts.py              # TTS 语音合成
│   ├── video.py            # 视频处理
│   ├── exporter.py         # 导出功能
│   └── pipeline.py         # 处理流程编排
├── download/               # 下载文件目录
│   └── [视频名]_[时间戳]/  # 每个视频一个目录
│       ├── merged_video.mp4
│       └── *.vtt (如果可用)
├── output/                 # 输出目录
│   ├── json/               # JSON 字幕文件
│   ├── video/              # 处理后的视频
│   └── audio/              # TTS 音频文件
└── README.md               # 本文档
```

## 📋 处理流程详解

### 标准处理流程

```
输入（视频/VTT/字幕文件）
    ↓
[可选] ASR 识别（使用 Whisper）
    ↓
[可选] ASR 对比融合（如果同时有 VTT 和视频）
    ↓
字幕优化（去重、合并、清理）
    ↓
[可选] 翻译（使用 Google Translate）
    ↓
[可选] AI 改写（使用本地模型）
    ↓
[可选] TTS 生成（使用 Edge-TTS）
    ↓
导出（JSON/SRT）
    ↓
[可选] 替换视频音轨
    ↓
完成
```

### ASR 对比融合流程

这是项目的核心创新功能，大大提高字幕质量：

1. **ASR 识别**：使用 Whisper 从视频音频中识别文字
2. **VTT 解析**：解析 YouTube 提供的 VTT 字幕（如果存在）
3. **时间对齐**：基于时间戳对齐 ASR 和 VTT 段落
4. **相似度计算**：计算每个段落对的文本相似度
5. **权重计算**：基于以下因素计算每个段落的权重：
   - **可信度**：ASR 和 VTT 的相似度和时间重叠
   - **质量**：文本长度和段落时长
   - **唯一性**：与其他段落的相似度
   - **来源**：优先 ASR（准确性更高）
6. **权重筛选**：删除低权重和重复段落
7. **融合输出**：生成高质量的字幕 JSON

## ⚙️ 配置说明

### 下载配置

下载目录默认位于项目根目录下的 `download` 文件夹。可以通过环境变量自定义：

```bash
# Windows PowerShell
$env:SUBTITLE_DOWNLOAD_ROOT = "D:\my_downloads"

# Linux/macOS
export SUBTITLE_DOWNLOAD_ROOT="/path/to/downloads"
```

或者直接修改 `download_youtobe.py` 中的配置：

```python
DOWNLOAD_ROOT = os.getenv(
    "SUBTITLE_DOWNLOAD_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
)
MAX_RETRY = 10      # 最大重试次数
MAX_HEIGHT = 1080   # 最大下载分辨率
```

### Whisper 模型选择建议

- **开发测试**：使用 `tiny` 或 `base`
- **日常使用**：使用 `small`（推荐）
- **高质量需求**：使用 `medium` 或 `large`
- **GPU 加速**：如果有 NVIDIA GPU，会自动使用 CUDA 加速

### 权重筛选参数

- `--min-weight 0.4`：默认阈值，过滤掉权重低于 0.4 的段落
- 如果字幕质量要求高，可以提高到 `0.5` 或 `0.6`
- 如果希望保留更多内容，可以降低到 `0.3`

## ❓ 常见问题

### Q1: 没有 VTT 文件怎么办？

**A**: 没问题！项目已经支持这种情况。当没有 VTT 文件时，会自动使用 ASR 模型（Whisper）直接从视频生成字幕。只需要确保：

```bash
# 使用完整工作流，会自动处理
uv run python workflow.py "YOUTUBE_URL"

# 或手动指定使用 ASR
uv run python main.py --file "video.mp4" --use-asr-compare
```

### Q2: Whisper 模型首次使用很慢？

**A**: 这是正常的。首次使用某个模型时，会自动从 HuggingFace 下载。下载后会自动缓存，后续使用会很快。

### Q3: 翻译功能需要 API 密钥吗？

**A**: 目前使用 Google 翻译的免费 API，不需要密钥。如果后续需要，可以在 `subtitle/translator.py` 中配置。

### Q4: TTS 生成的音频在哪里？

**A**: TTS 音频文件会保存在视频文件同目录下，文件名与视频文件相同，扩展名为 `.wav`。例如：
- 视频：`video.mp4`
- 音频：`video.wav`

### Q5: 如何处理很长的视频？

**A**: 
- 使用较小的 Whisper 模型（如 `small` 而不是 `large`）
- 考虑分段处理
- 如果有 GPU，会自动加速

### Q6: AI 改写功能效果不好？

**A**: AI 改写功能目前是实验性的。推荐的使用场景：
- 优先使用 ASR 对比融合（已经能大大提高质量）
- 只在特殊需求时使用 AI 改写
- 尝试更大的模型可能效果更好

### Q7: 权重筛选删除的内容太多？

**A**: 可以降低最小权重阈值：
```bash
--min-weight 0.3  # 默认 0.4，降低到 0.3 保留更多内容
```

或者禁用权重筛选：
```bash
--no-weight-filter
```

### Q8: 视频下载失败？

**A**: 
- 检查网络连接
- 确保 YouTube URL 正确
- 可能需要安装 JavaScript 运行时（如 Node.js）来支持某些格式
- 检查 `cookies.txt` 文件是否存在（如果需要登录下载）

## 🔧 故障排除

### 问题：`uv: command not found`

**解决**：确保已经安装 uv，并将其添加到系统 PATH。

### 问题：Whisper 模型下载失败

**解决**：
1. 检查网络连接
2. 如果在中国大陆，可能需要配置代理
3. 可以手动下载模型到缓存目录

### 问题：FFmpeg 错误

**解决**：`imageio-ffmpeg` 会自动管理 FFmpeg。如果仍有问题，可以手动安装 FFmpeg 并添加到 PATH。

### 问题：CUDA 相关错误

**解决**：
- 如果不需要 GPU 加速，PyTorch 会自动使用 CPU
- 如果需要 GPU 加速，确保安装了正确版本的 CUDA 和 PyTorch

## 📝 开发说明

### 添加新功能

1. 在 `subtitle/` 目录下创建新模块
2. 在 `main.py` 或 `workflow.py` 中集成
3. 添加相应的命令行参数

### 测试

```bash
# 测试单文件处理
uv run python main.py --file "test.vtt" --export

# 测试完整工作流
uv run python workflow.py "YOUTUBE_URL"
```

## 🔗 相关链接

- **GitHub 仓库**: https://github.com/Yuena2568/subtitle_audio
- **问题反馈**: https://github.com/Yuena2568/subtitle_audio/issues

## 📄 许可证

[根据项目实际情况填写]

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

[根据项目实际情况填写]

---

**最后更新**: 2025-01-09

**项目版本**: 0.1.0

