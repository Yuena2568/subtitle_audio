# 字幕处理工具使用指南

## 功能概览

本项目支持以下功能：
1. ✅ **字幕解析**：支持 VTT、SRT、TXT 格式
2. ✅ **文字优化**：去重、合并短句
3. ✅ **AI 改写**：使用本地 HuggingFace 模型进行文本改写
4. ✅ **翻译功能**：使用 Google 翻译 API
5. ✅ **TTS 生成**：使用 Edge TTS 生成语音
6. ✅ **批量处理**：支持目录批量处理

## 环境要求

- Python 3.12+
- uv（项目依赖管理）
- 已安装的依赖（通过 `uv sync` 安装）

## 快速开始

### 1. 查找本地模型

```bash
# 使用 uv 运行模型查找脚本
uv run python find_models.py
```

这会扫描你的 HuggingFace 缓存目录，列出所有可用的模型。

**当前找到的模型：**
- `facebook/opt-1.3b` - 适合英文文本改写
- `tiiuae/falcon-7b-instruct` - 更大的模型，效果更好

### 2. 单文件处理

#### 基础处理（仅优化和导出）
```bash
uv run python main.py --file test.srt --export
```

#### AI 改写
```bash
uv run python main.py --file test.srt \
    --ai-rewrite \
    --model-path "~/.cache/huggingface/hub/models--facebook--opt-1.3b/snapshots/xxx" \
    --export
```

#### 翻译
```bash
uv run python main.py --file test.srt \
    --translate \
    --language zh \
    --export
```

#### 完整流程（AI 改写 + 翻译 + TTS）
```bash
uv run python main.py --file test.srt \
    --ai-rewrite \
    --model-path "~/.cache/huggingface/hub/models--facebook--opt-1.3b/snapshots/xxx" \
    --translate \
    --language zh \
    --tts \
    --export
```

### 3. 批量处理

#### 批量处理 VTT 文件
```bash
uv run python main.py --dir videos \
    --pattern "*.vtt" \
    --export
```

#### 批量处理 + AI 改写 + 翻译
```bash
uv run python main.py --dir videos \
    --pattern "*.vtt" \
    --ai-rewrite \
    --model-path "~/.cache/huggingface/hub/models--facebook--opt-1.3b/snapshots/xxx" \
    --translate \
    --language zh \
    --export
```

## 命令行参数说明

### 文件输入
- `--file FILE`: 处理单个文件
- `--dir DIR`: 批量处理目录
- `--vtt VTT`: 指定 VTT 字幕文件（单文件模式）
- `--pattern PATTERN`: 批量处理时的文件匹配模式（默认: `*.vtt`）
- `--output-dir OUTPUT_DIR`: 批量处理时的输出目录（默认: `input_dir/output`）

### 处理选项
- `--ai-rewrite`: 启用 AI 改写
- `--model-path MODEL_PATH`: AI 模型路径（启用 `--ai-rewrite` 时必需）
- `--translate`: 启用翻译功能
- `--language LANGUAGE`: 目标语言 `zh`/`en`（默认: `zh`）
- `--tts`: 生成 TTS 音频
- `--live-tts`: 即时朗读（仅单文件模式）
- `--export`: 导出字幕文件（默认启用）
- `--no-export`: 不导出字幕文件

## 模型路径

### 使用本地模型路径
```bash
--model-path "~/.cache/huggingface/hub/models--facebook--opt-1.3b/snapshots/xxx"
```

### 使用 HuggingFace 模型 ID（自动下载）
```bash
--model-path "facebook/opt-1.3b"
```

## 测试脚本

### 完整流程测试
```bash
# 注意：test_full_pipeline.py 已从项目中移除
# 请使用 workflow.py 进行完整流程测试
uv run python workflow.py "YOUTUBE_URL"
```

这会测试：
1. 视频下载
2. ASR 识别
3. 字幕优化
4. 翻译
5. TTS 生成
6. 视频音轨替换

## 输出文件

处理完成后会生成：
- `*.srt`: SRT 格式字幕
- `*.json`: JSON 格式字幕（包含时间轴和文本）
- `*.wav` 或 `*.mp3`: TTS 生成的音频文件（如果启用了 `--tts`）

## 常见问题

### 1. 模型加载失败
- 检查模型路径是否正确
- 确保模型文件完整（检查 `config.json` 和 `tokenizer.json` 是否存在）
- 尝试使用 HuggingFace 模型 ID 让系统自动下载

### 2. 翻译失败
- 检查网络连接（需要访问 Google 翻译 API）
- 如果失败，会使用原文继续处理

### 3. TTS 生成失败
- 确保已安装 `edge-tts`：`uv add edge-tts`
- 检查 `edge-tts` 命令行工具是否可用：`edge-tts --list-voices`

### 4. 批量处理输出位置
- 默认输出到 `input_dir/output` 目录
- 可以使用 `--output-dir` 指定自定义输出目录

## 性能优化建议

1. **AI 改写**：如果处理大量文件，考虑使用 GPU（如果有）
2. **批量处理**：可以分批处理，避免内存不足
3. **TTS 生成**：TTS 生成较慢，可以单独处理或使用 `--no-export` 跳过

## 下一步

- [ ] 优化 AI 改写的提示词格式
- [ ] 支持更多翻译 API
- [ ] 添加进度条显示
- [ ] 支持配置文件


