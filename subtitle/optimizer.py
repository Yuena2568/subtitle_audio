# subtitle/optimizer.py
from typing import List, Dict
from difflib import SequenceMatcher
import re
from subtitle.model import Segment

# -----------------------------
# 文本清理函数
# -----------------------------
def remove_duplicate_phrases(text: str) -> str:
    """
    移除文本中的重复短语（改进版，更激进）
    例如："用于将数据从 Langmith 提取到 util 用于将数据从 Langmith 提取到"
    -> "用于将数据从 Langmith 提取到 util"
    """
    if not text:
        return text
    
    # 先移除明显的重复（完全相同的连续短语）
    # 使用正则表达式检测连续重复的短语
    import re
    # 匹配至少3个词的重复短语（支持中英文）
    pattern = r'(\b[\w\u4e00-\u9fff]+(?:\s+[\w\u4e00-\u9fff]+){2,})\s+\1'
    while re.search(pattern, text):
        text = re.sub(pattern, r'\1', text)
    
    # 分割成单词/短语
    words = text.split()
    if len(words) < 4:
        return " ".join(words)
    
    # 检测重复的短语（更激进的策略）
    max_iterations = 10  # 增加迭代次数
    iteration = 0
    
    while iteration < max_iterations:
        found_duplicate = False
        # 从长到短检测重复短语（增加到15个词）
        for phrase_len in range(min(12, len(words) // 2), 2, -1):
            if found_duplicate:
                break
                
            for i in range(len(words) - phrase_len * 2 + 1):
                phrase = words[i:i + phrase_len]
                phrase_text = " ".join(phrase).strip()
                
                # 跳过太短的短语（降低阈值）
                if len(phrase_text) < 5:
                    continue
                
                # 检查后面的文本中是否有相同或高度相似的短语
                # 扩大搜索范围，不只是紧邻的
                search_start = i + phrase_len
                search_end = min(len(words) - phrase_len + 1, i + phrase_len * 3)  # 限制搜索范围
                
                for j in range(search_start, search_end):
                    candidate = words[j:j + phrase_len]
                    candidate_text = " ".join(candidate).strip()
                    
                    # 完全匹配
                    if phrase == candidate:
                        # 找到重复，移除第二个
                        words = words[:j] + words[j + phrase_len:]
                        found_duplicate = True
                        break
                    
                    # 高度相似（降低阈值到0.75，更激进）
                    similarity = SequenceMatcher(None, phrase_text.lower(), candidate_text.lower()).ratio()
                    if similarity > 0.75 and len(phrase_text) > 5:
                        # 如果相似度高，移除第二个
                        words = words[:j] + words[j + phrase_len:]
                        found_duplicate = True
                        break
                
                if found_duplicate:
                    break
        
        if not found_duplicate:
            break
        
        iteration += 1
    
    result = " ".join(words)
    
    # 最后再次检查并移除明显的重复（如："A B C A B C" -> "A B C"）
    words_final = result.split()
    if len(words_final) >= 6:
        # 检查是否有重复的子序列
        for seq_len in range(len(words_final) // 2, 2, -1):
            first_half = " ".join(words_final[:seq_len])
            second_half = " ".join(words_final[seq_len:seq_len * 2])
            if first_half == second_half:
                # 找到重复，只保留前半部分
                return " ".join(words_final[seq_len:])
    
    return result


def clean_text(text: str) -> str:
    """
    清理文本：移除乱码、多余空格、重复短语等
    """
    if not text:
        return text
    
    # 移除明显的乱码字符（包含大量特殊符号）
    # 允许的字符：字母、数字、中文、常用标点
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
    allowed_chars.update('，。！？、；：""''（）【】.,!?;:()[]"/-\'')
    allowed_chars.update(' ')  # 空格
    
    # 检测乱码：连续出现5个以上非允许字符
    invalid_count = 0
    for char in text:
        if not (char.isalnum() or '\u4e00' <= char <= '\u9fff' or char in allowed_chars):
            invalid_count += 1
            if invalid_count >= 5:
                # 有乱码，进行清理
                cleaned_chars = []
                for char in text:
                    if char.isalnum() or '\u4e00' <= char <= '\u9fff' or char in allowed_chars:
                        cleaned_chars.append(char)
                    else:
                        cleaned_chars.append(' ')
                text = ''.join(cleaned_chars)
                break
        else:
            invalid_count = 0
    
    # 移除多余空格
    text = re.sub(r'\s+', ' ', text)
    
    # 多次应用去重（更激进）
    for _ in range(3):  # 应用3次，确保彻底去重
        new_text = remove_duplicate_phrases(text)
        if new_text == text:  # 如果没有变化，停止
            break
        text = new_text
    
    return text.strip()


def separate_mixed_language(text: str) -> tuple[str, str]:
    """
    分离中英文混合文本
    返回: (中文部分, 英文部分)
    """
    # 检测中文字符
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    english_pattern = re.compile(r'[a-zA-Z]+')
    
    chinese_parts = chinese_pattern.findall(text)
    english_parts = english_pattern.findall(text)
    
    chinese_text = ' '.join(chinese_parts) if chinese_parts else ''
    english_text = ' '.join(english_parts) if english_parts else ''
    
    return chinese_text, english_text


# -----------------------------
# 1️⃣ pipeline 需要的 Segment 操作函数（强化版）
# -----------------------------
def merge_duplicate_segments(segments: List[Segment], similarity_threshold: float = 0.75) -> List[Segment]:
    """
    去掉相邻重复或高度相似的段落（降低阈值，更激进）
    
    Args:
        segments: 段落列表
        similarity_threshold: 相似度阈值（默认0.75，比原来的0.9更激进）
    """
    if not segments:
        return []

    merged: List[Segment] = []
    
    for seg in segments:
        # 先清理文本
        seg.text = clean_text(seg.text)
        
        if not merged:
            merged.append(seg)
            continue
        
        prev = merged[-1]
        
        # 计算相似度
        similarity = SequenceMatcher(None, prev.text, seg.text).ratio()
        duration = seg.end - seg.start
        
        # 更激进的去重策略
        # 1. 超短段落（<0.1秒）且相似度高，直接跳过
        if duration < 0.1 and similarity >= 0.6:
            continue
        
        # 2. 相似度高且持续时间短，跳过
        if similarity >= similarity_threshold and duration < 0.5:
            continue
        
        # 3. 完全相同的文本，跳过
        if prev.text.strip() == seg.text.strip():
            continue
        
        # 4. 如果当前段落是前一段落的子集，跳过
        if seg.text.strip() in prev.text and len(seg.text) < len(prev.text) * 0.8:
            continue
        
        merged.append(seg)
    
    return merged


def merge_short_segments(segments: List[Segment], min_duration: float = 0.3) -> List[Segment]:
    """
    合并过短的段落到前一个段落，保证连贯性（降低阈值，更激进合并）
    
    Args:
        segments: 段落列表
        min_duration: 最小持续时间（默认0.3秒，比原来的0.5更激进）
    """
    if not segments:
        return []

    merged: List[Segment] = []
    buffer = segments[0]
    buffer.text = clean_text(buffer.text)

    for seg in segments[1:]:
        seg.text = clean_text(seg.text)
        duration = seg.end - seg.start
        
        # 超短段落（<0.1秒）直接合并，不管内容
        if duration < 0.1:
            buffer.text += " " + seg.text if seg.text else ""
            buffer.end = seg.end
            continue
        
        # 短段落（<min_duration）且文本合理，合并
        if duration < min_duration and seg.text:
            buffer.text += " " + seg.text
            buffer.end = seg.end
        else:
            # 清理并添加到结果
            buffer.text = clean_text(buffer.text)
            merged.append(buffer)
            buffer = seg
    
    # 处理最后一个段落
    buffer.text = clean_text(buffer.text)
    merged.append(buffer)
    
    return merged


def remove_internal_duplicates(segments: List[Segment]) -> List[Segment]:
    """
    移除段落内部的重复文本
    """
    cleaned = []
    for seg in segments:
        original_text = seg.text
        cleaned_text = clean_text(original_text)
        
        # 如果清理后文本明显变短，说明有重复被移除
        if len(cleaned_text) < len(original_text) * 0.7:
            # 如果清理过度，保留原文
            cleaned_text = original_text
        
        new_seg = Segment(
            index=seg.index,
            text=cleaned_text,
            start=seg.start,
            end=seg.end
        )
        cleaned.append(new_seg)
    
    return cleaned


# -----------------------------
# 2️⃣ 原有 optimize_subtitles（Dict 版本）改进（强化版）
# -----------------------------
def optimize_subtitles(segments: List[Dict]) -> List[Dict]:
    """
    优化字幕（强化版）：
    - 清理文本（移除乱码、重复短语）
    - 移除段落内部重复
    - 合并短句（更激进的合并策略）
    - 去除相邻重复（降低相似度阈值）
    
    segments: List[Dict]，每个 Dict 至少有 index, start, end, text
    返回优化后的 List[Dict]
    """
    if not segments:
        return []

    # 先将 Dict 转为 Segment 对象，确保 start/end 为 float 类型
    seg_objs = []
    for d in segments:
        start_val = d.get("start", 0)
        end_val = d.get("end", 0)
        # 确保 start 和 end 是 float 类型
        if isinstance(start_val, str):
            start_val = float(start_val)
        else:
            start_val = float(start_val)
        if isinstance(end_val, str):
            end_val = float(end_val)
        else:
            end_val = float(end_val)
        
        seg_objs.append(Segment(
            index=d.get("index", 0), 
            start=start_val, 
            end=end_val, 
            text=d.get("text", "")
        ))

    # 优化流程（按顺序执行）
    # 1. 移除段落内部重复
    seg_objs = remove_internal_duplicates(seg_objs)
    
    # 2. 去重（降低阈值到0.75，更激进）
    seg_objs = merge_duplicate_segments(seg_objs, similarity_threshold=0.75)
    
    # 3. 合并短段（降低阈值到0.3秒，更激进）
    seg_objs = merge_short_segments(seg_objs, min_duration=0.3)
    
    # 4. 再次清理（确保最终文本干净）
    for seg in seg_objs:
        seg.text = clean_text(seg.text)
    
    # 5. 重新编号
    for i, seg in enumerate(seg_objs, start=1):
        seg.index = i

    # 再转回 Dict
    optimized = []
    for seg in seg_objs:
        if seg.text.strip():  # 只保留非空文本
            optimized.append({
                "index": seg.index,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            })

    return optimized
