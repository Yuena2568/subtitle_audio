# subtitle/segmenter.py
from typing import List
from subtitle.model import Segment
from pathlib import Path
import re

MIN_CHARS = 40

# TXT 分段
def segment_text(text: str) -> List[Segment]:
    lines = text.splitlines()
    raw_lines: List[str] = [line.strip() for line in lines if line.strip()]
    segments: List[Segment] = []
    buffer = ""
    index = 1

    for line in raw_lines:
        if not buffer:
            buffer = line
            continue
        if len(buffer) < MIN_CHARS:
            buffer += " " + line
        else:
            segments.append(Segment(index=index, text=buffer))
            index += 1
            buffer = line

    if buffer:
        segments.append(Segment(index=index, text=buffer))
    return segments

# SRT
def parse_srt(file_path: str) -> List[Segment]:
    """
    解析 SRT 字幕文件
    返回 Segment 列表，start 和 end 为 float 类型（秒）
    """
    segments: List[Segment] = []
    try:
        # 尝试不同的编码
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]
        content = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError(f"无法读取文件 {file_path}，编码不支持")

    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    except Exception as e:
        raise RuntimeError(f"读取 SRT 文件失败: {e}")

    pattern = re.compile(
        r"(\d+)\s*\r?\n"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*\r?\n"
        r"([\s\S]*?)(?=\r?\n\r?\n|\Z)",
        re.MULTILINE
    )
    matches = pattern.findall(content)

    for match in matches:
        try:
            index = int(match[0])
            # 确保 start 和 end 是 float 类型
            start = float(_parse_time_srt(match[1]))
            end = float(_parse_time_srt(match[2]))
            text = match[3].replace("\r\n", " ").replace("\n", " ").strip()
            if text:  # 只添加非空文本
                segments.append(Segment(index=index, text=text, start=start, end=end))
        except (ValueError, IndexError) as e:
            print(f"[Warning] 跳过错误的 SRT 条目: {match}, error={e}")
            continue
    
    print(f"[SRT] {len(segments)} segments loaded from {file_path}")
    return segments

def _parse_time_srt(time_str: str) -> float:
    h, m, s_ms = time_str.split(":")
    s, ms = s_ms.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def time_str_to_seconds(t: str) -> float:
    """
    将时间字符串转换为秒数（float）
    支持格式: HH:MM:SS.mmm, MM:SS.mmm, SS.mmm 或纯数字
    """
    if not t:
        raise ValueError("时间字符串为空")
    
    # 去掉可能的空白和属性（如 align:start）
    t = t.strip().split()[0]
    
    # 处理逗号和点号都作为小数点
    t = t.replace(",", ".")
    
    parts = t.split(":")
    if len(parts) == 3:
        # HH:MM:SS.mmm 格式
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        # MM:SS.mmm 格式
        m, s = parts
        return int(m) * 60 + float(s)
    else:
        # 纯数字格式（秒）
        return float(t)

def clean_vtt_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"</?c[^>]*>", "", text)
    text = re.sub(r"<\d+:\d+:\d+\.\d+>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)  # 修复：\\s+ 应该是 \s+
    return text.strip()

# VTT
def parse_vtt(file_path: str) -> List[Segment]:
    """
    解析 VTT 字幕文件
    支持标准的 WebVTT 格式，处理时间戳和文本内容
    """
    segments: List[Segment] = []
    try:
        # 尝试不同的编码
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]
        lines = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        
        if lines is None:
            raise ValueError(f"无法读取文件 {file_path}，编码不支持")

    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    except Exception as e:
        raise RuntimeError(f"读取 VTT 文件失败: {e}")

    index = 1
    start = None
    end = None
    text_lines = []

    def flush():
        nonlocal index, start, end, text_lines
        if start is None or end is None or not text_lines:
            return
        try:
            text = clean_vtt_text(" ".join(text_lines))
            if text:
                # 确保 start 和 end 是 float 类型
                start_val = float(start)
                end_val = float(end)
                segments.append(Segment(
                    index=index,
                    text=text,
                    start=start_val,
                    end=end_val,
                ))
                index += 1
        except (ValueError, TypeError) as e:
            print(f"[Warning] 跳过错误的时间戳或文本: start={start}, end={end}, error={e}")
        finally:
            start = None
            end = None
            text_lines = []

    for raw in lines:
        line = raw.strip()
        
        # 跳过 VTT 文件头（WEBVTT）
        if line.upper().startswith("WEBVTT"):
            continue
        # 跳过样式和注释块
        if line.startswith("STYLE") or line.startswith("NOTE"):
            continue

        if "-->" in line:
            flush()
            try:
                # 处理可能包含时间戳属性的情况，例如: 00:00:01.000 --> 00:00:03.000 align:start
                parts = line.split("-->")
                if len(parts) != 2:
                    print(f"[Warning] 跳过格式错误的时间戳行: {line}")
                    continue
                a, b = parts
                start_str = a.strip().split()[0]  # 只取时间部分，忽略属性
                end_str = b.strip().split()[0]
                start = time_str_to_seconds(start_str)
                end = time_str_to_seconds(end_str)
                text_lines = []
            except (ValueError, IndexError) as e:
                print(f"[Warning] 解析时间戳失败: {line}, error={e}")
                start = None
                end = None
                text_lines = []

        elif line == "":
            flush()

        elif start is not None:
            # 只有当我们已经有了时间戳时才添加文本
            text_lines.append(line)

    # 处理最后一个段落
    flush()
    
    print(f"[VTT] {len(segments)} segments loaded from {file_path}")
    return segments

# JSON
def parse_json(file_path: str) -> List[Segment]:
    """
    解析 JSON 字幕文件
    支持标准的 JSON 格式，每个段落包含 index, text, start, end
    
    Args:
        file_path: JSON 文件路径
    
    Returns:
        Segment 列表，start 和 end 为 float 类型（秒）
    """
    import json
    segments: List[Segment] = []
    
    try:
        # 尝试不同的编码
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312"]
        content = None
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError(f"无法读取文件 {file_path}，编码不支持")
        
        # 解析 JSON
        data = json.loads(content)
        
        if not isinstance(data, list):
            raise ValueError(f"JSON 文件应该包含一个数组，但得到: {type(data)}")
        
        for item in data:
            try:
                # 确保所有必需的字段都存在
                index = int(item.get("index", 0))
                text = str(item.get("text", "")).strip()
                start = float(item.get("start", 0.0))
                end = float(item.get("end", 0.0))
                
                # 只添加非空文本
                if text:
                    segments.append(Segment(
                        index=index,
                        text=text,
                        start=start,
                        end=end
                    ))
            except (ValueError, TypeError, KeyError) as e:
                print(f"[Warning] 跳过错误的 JSON 条目: {item}, error={e}")
                continue
        
        print(f"[JSON] {len(segments)} segments loaded from {file_path}")
        return segments
        
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")
    except Exception as e:
        raise RuntimeError(f"读取 JSON 文件失败: {e}")


# 自动识别
def parse_txt(file_path: str) -> List[Segment]:
    """
    自动识别文件格式并解析
    支持 .srt, .vtt, .txt, .json 格式
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == ".srt":
        return parse_srt(file_path)
    elif suffix == ".vtt":
        return parse_vtt(file_path)
    elif suffix == ".json":
        return parse_json(file_path)
    else:
        # 纯文本文件，分段处理（没有时间戳）
        try:
            encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312"]
            text = None
            for enc in encodings:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        text = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            
            if text is None:
                raise ValueError(f"无法读取文件 {file_path}，编码不支持")
                
            return segment_text(text)
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在: {file_path}")
        except Exception as e:
            raise RuntimeError(f"读取文件失败: {e}")
