# subtitle/cache_manager.py
"""
缓存管理模块
支持 ASR 结果缓存、翻译缓存、工作流断点续传
"""
import json
import time
from pathlib import Path
from typing import List, Optional
from subtitle.model import Segment


def save_asr_cache(video_path: str, segments: List[Segment], whisper_model: str) -> None:
    """
    保存 ASR 结果到缓存文件
    
    Args:
        video_path: 视频文件路径
        segments: ASR 识别结果
        whisper_model: 使用的 Whisper 模型名称
    """
    try:
        video = Path(video_path)
        cache_file = video.with_suffix(".asr_cache.json")
        cache_data = {
            "whisper_model": whisper_model,
            "timestamp": time.time(),
            "segment_count": len(segments),
            "segments": [seg.to_dict() for seg in segments]
        }
        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Cache] ASR 缓存已保存: {cache_file.name} ({len(segments)} 段落)")
    except Exception as e:
        print(f"[Cache] 保存 ASR 缓存失败（不影响主流程）: {e}")


def load_asr_cache(video_path: str, whisper_model: str) -> Optional[List[Segment]]:
    """
    加载 ASR 缓存，如果 whisper_model 不同则返回 None
    
    Args:
        video_path: 视频文件路径
        whisper_model: 当前使用的 Whisper 模型名称
    
    Returns:
        缓存的 Segment 列表，如果没有缓存或模型不匹配则返回 None
    """
    try:
        video = Path(video_path)
        cache_file = video.with_suffix(".asr_cache.json")
        if not cache_file.exists():
            return None
        
        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        
        # 检查模型是否匹配
        if cache_data.get("whisper_model") != whisper_model:
            print(f"[Cache] ASR 缓存模型不匹配: 缓存={cache_data.get('whisper_model')}，当前={whisper_model}，跳过缓存")
            return None
        
        segments = [Segment.from_dict(d) for d in cache_data.get("segments", [])]
        print(f"[Cache] ASR 缓存命中: {len(segments)} 段落（模型: {whisper_model}）")
        return segments
    except Exception as e:
        print(f"[Cache] 加载 ASR 缓存失败: {e}")
        return None


def save_translate_cache(video_path: str, source_texts: List[str], translated_texts: List[str], target_lang: str) -> None:
    """
    保存翻译结果到缓存文件
    
    Args:
        video_path: 视频文件路径
        source_texts: 原文列表
        translated_texts: 翻译结果列表
        target_lang: 目标语言
    """
    try:
        video = Path(video_path)
        cache_file = video.with_suffix(".translate_cache.json")
        cache_data = {
            "target_lang": target_lang,
            "timestamp": time.time(),
            "source_texts": source_texts,
            "translated_texts": translated_texts
        }
        cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Cache] 翻译缓存已保存: {cache_file.name}")
    except Exception as e:
        print(f"[Cache] 保存翻译缓存失败（不影响主流程）: {e}")


def load_translate_cache(video_path: str, source_texts: List[str], target_lang: str) -> Optional[List[str]]:
    """
    加载翻译缓存，仅当源文本完全一致时命中
    
    Args:
        video_path: 视频文件路径
        source_texts: 当前原文列表
        target_lang: 目标语言
    
    Returns:
        缓存的翻译结果列表，否则返回 None
    """
    try:
        video = Path(video_path)
        cache_file = video.with_suffix(".translate_cache.json")
        if not cache_file.exists():
            return None
        
        cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        
        # 检查语言和文本是否匹配
        if cache_data.get("target_lang") != target_lang:
            return None
        
        cached_sources = cache_data.get("source_texts", [])
        if len(cached_sources) != len(source_texts):
            return None
        
        # 逐条比对源文本
        for i, (cached, current) in enumerate(zip(cached_sources, source_texts)):
            if cached != current:
                return None
        
        translated = cache_data.get("translated_texts", [])
        print(f"[Cache] 翻译缓存命中: {len(translated)} 段落（语言: {target_lang}）")
        return translated
    except Exception as e:
        print(f"[Cache] 加载翻译缓存失败: {e}")
        return None


def save_workflow_progress(video_dir: str, step_name: str, data: dict) -> None:
    """
    保存工作流进度
    
    Args:
        video_dir: 工作目录
        step_name: 当前完成的步骤名称
        data: 步骤相关的数据
    """
    try:
        progress_file = Path(video_dir) / ".workflow_progress.json"
        progress = {}
        if progress_file.exists():
            try:
                progress = json.loads(progress_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        progress["last_step"] = step_name
        progress["timestamp"] = time.time()
        progress.setdefault("steps", {})
        progress["steps"][step_name] = data
        
        progress_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Cache] 工作流进度已保存: {step_name}")
    except Exception as e:
        print(f"[Cache] 保存工作流进度失败（不影响主流程）: {e}")


def load_workflow_progress(video_dir: str) -> Optional[dict]:
    """
    加载工作流进度
    
    Args:
        video_dir: 工作目录
    
    Returns:
        进度数据，无进度则返回 None
    """
    try:
        progress_file = Path(video_dir) / ".workflow_progress.json"
        if not progress_file.exists():
            return None
        progress = json.loads(progress_file.read_text(encoding="utf-8"))
        if progress:
            print(f"[Cache] 工作流进度已加载，上次步骤: {progress.get('last_step', '未知')}")
        return progress
    except Exception as e:
        print(f"[Cache] 加载工作流进度失败: {e}")
        return None


def clear_workflow_progress(video_dir: str) -> None:
    """
    清理工作流进度文件
    
    Args:
        video_dir: 工作目录
    """
    try:
        progress_file = Path(video_dir) / ".workflow_progress.json"
        if progress_file.exists():
            progress_file.unlink()
            print("[Cache] 工作流进度文件已清理")
    except Exception as e:
        print(f"[Cache] 清理工作流进度失败: {e}")
