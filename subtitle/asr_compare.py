# subtitle/asr_compare.py
"""
ASR 对比融合模块
使用 Whisper ASR 重新识别音频，与 VTT 字幕对比，选择更准确的版本
支持权重筛选，提高 ASR 权重占比
"""
from typing import List, Tuple, Optional
from difflib import SequenceMatcher
from pathlib import Path
from subtitle.model import Segment
from subtitle.asr import extract_audio, audio_to_segments
from subtitle.segmenter import parse_vtt
from subtitle.optimizer import clean_text


def align_segments_by_time(
    asr_segments: List[Segment],
    vtt_segments: List[Segment],
    time_tolerance: float = 2.0  # 时间容差（秒）
) -> List[Tuple[Segment, Optional[Segment]]]:
    """
    将 ASR 和 VTT 段落按时间对齐
    
    Args:
        asr_segments: ASR 生成的段落列表
        vtt_segments: VTT 解析的段落列表
        time_tolerance: 时间容差（秒），在此范围内的段落被认为是对应的
    
    Returns:
        [(asr_seg, vtt_seg), ...] 列表，如果没有对应的 VTT 段落则为 None
    """
    if not vtt_segments:
        return [(seg, None) for seg in asr_segments]
    
    aligned = []
    vtt_index = 0
    
    for asr_seg in asr_segments:
        best_match = None
        best_score = -1
        best_index = -1
        
        # 在 VTT 段落中寻找时间最接近的段落
        # 搜索范围：从当前位置向前后各搜索20个段落
        search_start = max(0, vtt_index - 5)
        search_end = min(len(vtt_segments), vtt_index + 20)
        
        for i in range(search_start, search_end):
            vtt_seg = vtt_segments[i]
            
            # 计算时间重叠度
            overlap_start = max(asr_seg.start, vtt_seg.start)
            overlap_end = min(asr_seg.end, vtt_seg.end)
            time_overlap = max(0, overlap_end - overlap_start)
            
            if time_overlap > 0:
                # 计算文本相似度
                text_similarity = SequenceMatcher(
                    None, 
                    asr_seg.text.lower().strip(), 
                    vtt_seg.text.lower().strip()
                ).ratio()
                
                # 综合评分：时间重叠 + 文本相似度
                # 时间重叠权重更高（因为时间轴是主要对齐依据）
                combined_score = time_overlap * 0.6 + text_similarity * 0.4
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = vtt_seg
                    best_index = i
        
        # 如果找到合理的匹配（时间重叠>0.5秒或相似度>0.3）
        if best_match and (best_score > 0.1 or 
                          (overlap_end - overlap_start > 0.5) or
                          SequenceMatcher(None, asr_seg.text.lower(), best_match.text.lower()).ratio() > 0.3):
            aligned.append((asr_seg, best_match))
            vtt_index = best_index + 1
        else:
            # 没有找到匹配的 VTT 段落
            aligned.append((asr_seg, None))
    
    return aligned


def calculate_segment_weight(
    segment: Segment,
    all_segments: List[Segment],
    asr_seg: Optional[Segment] = None,
    vtt_seg: Optional[Segment] = None,
    text_similarity: float = 1.0,
    time_overlap: float = 0.0
) -> float:
    """
    计算段落的综合权重（0-1之间）
    提高 ASR 权重占比，因为 ASR 准确性比 VTT 高
    使用加权平均而非连乘，避免权重被过度压低
    
    Args:
        segment: 当前段落
        all_segments: 所有段落列表（用于重复检测）
        asr_seg: 对应的 ASR 段落（如果存在）
        vtt_seg: 对应的 VTT 段落（如果存在）
        text_similarity: ASR 和 VTT 的文本相似度
        time_overlap: 时间重叠度（秒）
    
    Returns:
        权重分数（0-1），越高越好
    """
    scores = []
    weights = []
    
    # 1. 可信度分数（20%权重）
    # - 文本相似度：ASR 和 VTT 相似度越高，说明内容越可靠
    credibility_score = text_similarity * 0.4
    
    # - 时间重叠度：重叠度越高，时间轴越准确
    # 归一化时间重叠（假设正常段落长度 2-5 秒）
    normalized_overlap = min(time_overlap / 3.0, 1.0)
    credibility_score += normalized_overlap * 0.6
    
    scores.append(credibility_score)
    weights.append(0.2)
    
    # 2. 质量分数（25%权重）
    text_len = len(segment.text.strip())
    duration = segment.end - segment.start
    
    # 文本长度评分（理想长度：10-100 字符）
    if text_len < 5:
        length_score = 0.3  # 太短
    elif text_len < 10:
        length_score = 0.6  # 较短
    elif text_len <= 100:
        length_score = 1.0  # 理想
    elif text_len <= 200:
        length_score = 0.8  # 稍长
    else:
        length_score = 0.5  # 太长
    
    # 时长评分（理想时长：1-5 秒）
    if duration < 0.1:
        duration_score = 0.2  # 极短（可能是重复片段）
    elif duration < 0.5:
        duration_score = 0.5  # 很短
    elif duration <= 5.0:
        duration_score = 1.0  # 理想
    elif duration <= 10.0:
        duration_score = 0.8  # 稍长
    else:
        duration_score = 0.6  # 太长
    
    quality_score = (length_score * 0.6 + duration_score * 0.4)
    scores.append(quality_score)
    weights.append(0.25)
    
    # 3. 唯一性分数（15%权重）
    # 检测与其他段落的相似度
    max_similarity_to_others = 0.0
    for other_seg in all_segments:
        if other_seg is segment or other_seg.index == segment.index:
            continue
        
        # 计算文本相似度
        similarity = SequenceMatcher(
            None, 
            segment.text.lower().strip(),
            other_seg.text.lower().strip()
        ).ratio()
        
        # 如果时间接近，相似度权重更高
        time_gap = abs((segment.start + segment.end) / 2 - (other_seg.start + other_seg.end) / 2)
        if time_gap < 2.0:  # 2秒内
            similarity *= 1.5  # 时间接近的重复更严重
        
        max_similarity_to_others = max(max_similarity_to_others, min(similarity, 1.0))
    
    # 相似度越高，唯一性越低（重复内容权重低）
    uniqueness_score = 1.0 - min(max_similarity_to_others * 1.2, 1.0)  # 重复惩罚
    scores.append(max(uniqueness_score, 0.1))  # 至少保留10%
    weights.append(0.15)
    
    # 4. 来源分数（40%权重）- 提高 ASR 权重占比
    # ASR 准确性比 VTT 高，所以 ASR 来源权重更高
    if asr_seg and vtt_seg:
        # 有 ASR 和 VTT 对比，ASR 更可靠（给更高权重）
        # 如果相似度高，说明两者都认可，权重更高
        if text_similarity > 0.7:
            source_score = 1.0  # ASR 和 VTT 一致，非常可靠
        else:
            source_score = 0.95  # 有 ASR，但 VTT 不同，ASR 更可靠
    elif asr_seg:
        # 只有 ASR（ASR 通常更准确）- 给高权重
        source_score = 0.9  # ASR 单独存在，权重很高
    elif vtt_seg:
        # 只有 VTT（可能质量较差，重复多）
        source_score = 0.5  # VTT 单独存在，权重较低
    else:
        # 未知来源
        source_score = 0.4
    
    scores.append(source_score)
    weights.append(0.4)  # 来源权重最高（40%）
    
    # 检查文本质量（是否有明显问题）
    text = segment.text.strip()
    if not text:
        return 0.05  # 空文本权重极低
    
    # 检测明显的重复短语（段落内部）- 作为惩罚因子
    penalty = 1.0
    words = text.split()
    if len(words) > 5:
        # 检查是否有重复的短语（至少3个词）
        for i in range(len(words) - 3):
            phrase = " ".join(words[i:i+3])
            if phrase in " ".join(words[i+3:]):
                penalty = 0.75  # 有重复短语，降低权重
                break
    
    # 加权平均
    final_score = sum(s * w for s, w in zip(scores, weights)) * penalty
    
    return min(max(final_score, 0.0), 1.0)  # 确保在 0-1 范围内


def filter_by_weight(
    segments: List[Segment],
    aligned_info: List[Tuple[Segment, Optional[Segment], Optional[Segment], float, float]],
    min_weight: float = 0.4,
    remove_duplicates: bool = True
) -> List[Segment]:
    """
    根据权重筛选段落，删除低权重和重复的段落
    
    Args:
        segments: 融合后的段落列表
        aligned_info: 对齐信息列表 [(fused_seg, asr_seg, vtt_seg, text_similarity, time_overlap), ...]
        min_weight: 最小权重阈值（低于此值的段落将被删除）
        remove_duplicates: 是否移除重复段落
    
    Returns:
        筛选后的段落列表
    """
    if not segments:
        return []
    
    # 计算每个段落的权重
    weighted_segments = []
    for i, seg in enumerate(segments):
        # 从对齐信息中获取数据
        asr_seg = None
        vtt_seg = None
        text_similarity = 1.0
        time_overlap = 0.0
        
        if i < len(aligned_info):
            _, asr_seg, vtt_seg, text_similarity, time_overlap = aligned_info[i]
        
        weight = calculate_segment_weight(
            seg, 
            segments, 
            asr_seg, 
            vtt_seg, 
            text_similarity, 
            time_overlap
        )
        
        weighted_segments.append((seg, weight))
    
    # 按权重排序（降序）
    weighted_segments.sort(key=lambda x: x[1], reverse=True)
    
    # 筛选：保留权重 >= min_weight 的段落
    filtered = []
    removed_count = 0
    removed_low_weight = 0
    removed_duplicate = 0
    
    for seg, weight in weighted_segments:
        if weight < min_weight:
            removed_low_weight += 1
            removed_count += 1
            continue
        
        # 如果启用去重，检查是否与已有段落重复
        if remove_duplicates:
            is_duplicate = False
            for existing_seg, _ in filtered:
                similarity = SequenceMatcher(
                    None,
                    seg.text.lower().strip(),
                    existing_seg.text.lower().strip()
                ).ratio()
                
                # 如果相似度高且时间接近，认为是重复
                time_gap = abs((seg.start + seg.end) / 2 - (existing_seg.start + existing_seg.end) / 2)
                if similarity > 0.85 and time_gap < 3.0:
                    is_duplicate = True
                    removed_duplicate += 1
                    removed_count += 1
                    break
            
            if is_duplicate:
                continue
        
        filtered.append((seg, weight))
    
    # 按时间顺序重新排序
    filtered.sort(key=lambda x: x[0].start)
    
    # 重新编号
    result = []
    for i, (seg, weight) in enumerate(filtered, 1):
        seg.index = i
        result.append(seg)
    
    print(f"[权重筛选] 完成：")
    print(f"  - 原始段落数: {len(segments)}")
    print(f"  - 筛选后: {len(result)}")
    print(f"  - 删除低权重 (<{min_weight}): {removed_low_weight}")
    print(f"  - 删除重复: {removed_duplicate}")
    print(f"  - 总删除: {removed_count} ({removed_count/len(segments)*100:.1f}%)")
    
    # 显示权重分布
    if filtered:
        weights = [w for _, w in filtered]
        print(f"  - 权重范围: {min(weights):.2f} - {max(weights):.2f}")
        print(f"  - 平均权重: {sum(weights)/len(weights):.2f}")
    
    return result


def compare_and_fuse_segments(
    asr_segments: List[Segment],
    vtt_segments: List[Segment],
    prefer_asr: bool = True,  # 默认偏好 ASR（更准确）
    enable_weight_filter: bool = True,  # 是否启用权重筛选
    min_weight: float = 0.4  # 最小权重阈值
) -> List[Segment]:
    """
    对比 ASR 和 VTT 字幕，选择更准确的版本并融合
    支持权重筛选，提高 ASR 权重占比
    
    策略：
    1. 如果 ASR 和 VTT 相似度高（>0.8），使用 ASR（通常更干净、无重复）
    2. 如果差异大（<0.5），可能是 VTT 有错误或重复，使用 ASR
    3. 如果相似度中等，根据 prefer_asr 参数决定（默认偏好 ASR）
    4. 权重筛选：删除低权重段落，保留高质量内容
    
    Args:
        asr_segments: ASR 生成的段落列表
        vtt_segments: VTT 解析的段落列表
        prefer_asr: 是否偏好 ASR（默认 True，因为通常更准确）
        enable_weight_filter: 是否启用权重筛选（默认 True）
        min_weight: 最小权重阈值（默认 0.4）
    
    Returns:
        融合后的段落列表
    """
    print(f"[ASR Compare] 开始对比融合：ASR({len(asr_segments)}) vs VTT({len(vtt_segments)})")
    
    # 1. 时间轴对齐
    aligned = align_segments_by_time(asr_segments, vtt_segments)
    
    fused_segments = []
    aligned_info = []  # 保存对齐信息用于权重计算
    stats = {
        "use_asr": 0,
        "use_vtt": 0,
        "no_vtt_match": 0,
        "high_similarity": 0,
        "low_similarity": 0
    }
    
    for asr_seg, vtt_seg in aligned:
        if vtt_seg is None:
            # 没有对应的 VTT 段落，使用 ASR（ASR 权重高）
            fused_seg = Segment(
                index=len(fused_segments) + 1,
                text=asr_seg.text.strip(),
                start=asr_seg.start,
                end=asr_seg.end
            )
            fused_segments.append(fused_seg)
            aligned_info.append((fused_seg, asr_seg, None, 1.0, 0.0))  # ASR 单独存在，相似度1.0
            stats["no_vtt_match"] += 1
            continue
        
        # 计算文本相似度
        text_similarity = SequenceMatcher(
            None, 
            asr_seg.text.lower().strip(), 
            vtt_seg.text.lower().strip()
        ).ratio()
        
        # 计算时间重叠
        overlap_start = max(asr_seg.start, vtt_seg.start)
        overlap_end = min(asr_seg.end, vtt_seg.end)
        time_overlap = max(0, overlap_end - overlap_start)
        
        # 判断策略：提高 ASR 权重，默认使用 ASR
        use_asr_text = True
        
        if text_similarity > 0.8:
            # 高度相似：使用 ASR（通常更干净、无重复）
            use_asr_text = True
            stats["high_similarity"] += 1
        elif text_similarity < 0.5:
            # 差异大：可能是 VTT 有错误，使用 ASR
            use_asr_text = True
            stats["low_similarity"] += 1
        else:
            # 相似度中等：根据偏好选择（默认偏好 ASR）
            use_asr_text = prefer_asr
        
        # 选择文本和时间轴（优先 ASR）
        if use_asr_text:
            selected_text = asr_seg.text
            # 优先使用 ASR 的时间轴，但如果 VTT 的时间轴更精确（差异小），可以微调
            selected_start = asr_seg.start
            selected_end = asr_seg.end
            
            # 如果 VTT 时间轴与 ASR 接近（差异<1秒），可以平均一下
            if abs(vtt_seg.start - asr_seg.start) < 1.0:
                selected_start = (asr_seg.start + vtt_seg.start) / 2
            if abs(vtt_seg.end - asr_seg.end) < 1.0:
                selected_end = (asr_seg.end + vtt_seg.end) / 2
            
            stats["use_asr"] += 1
        else:
            selected_text = vtt_seg.text
            selected_start = vtt_seg.start
            selected_end = vtt_seg.end
            stats["use_vtt"] += 1
        
        # 清理文本
        selected_text = clean_text(selected_text.strip())
        
        fused_seg = Segment(
            index=len(fused_segments) + 1,
            text=selected_text,
            start=selected_start,
            end=selected_end
        )
        fused_segments.append(fused_seg)
        aligned_info.append((fused_seg, asr_seg, vtt_seg, text_similarity, time_overlap))
    
    # 输出统计信息
    print(f"[ASR Compare] 融合完成：")
    print(f"  - 使用 ASR: {stats['use_asr']} ({stats['use_asr']/len(fused_segments)*100:.1f}%)")
    print(f"  - 使用 VTT: {stats['use_vtt']} ({stats['use_vtt']/len(fused_segments)*100:.1f}%)")
    print(f"  - 无 VTT 匹配: {stats['no_vtt_match']} ({stats['no_vtt_match']/len(fused_segments)*100:.1f}%)")
    print(f"  - 高度相似: {stats['high_similarity']}")
    print(f"  - 差异大: {stats['low_similarity']}")
    
    # 2. 权重筛选（如果启用）
    if enable_weight_filter:
        print(f"\n[权重筛选] 启用权重筛选（最小权重阈值: {min_weight}）...")
        fused_segments = filter_by_weight(
            fused_segments,
            aligned_info,
            min_weight=min_weight,
            remove_duplicates=True
        )
    
    return fused_segments


def process_with_asr_comparison(
    video_path: str,
    vtt_path: Optional[str] = None,
    whisper_model: str = "small",
    enable_weight_filter: bool = True,
    min_weight: float = 0.4
) -> List[Segment]:
    """
    使用 ASR 对比处理视频和 VTT
    
    Args:
        video_path: 视频文件路径
        vtt_path: VTT 字幕文件路径（可选，如果不提供则只使用 ASR）
        whisper_model: Whisper 模型大小（tiny/base/small/medium/large）
    
    Returns:
        融合后的段落列表
    """
    print("=" * 60)
    print("[ASR Compare] 开始 ASR 对比融合流程")
    print("=" * 60)
    
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")
    
    # 0. 尝试加载 ASR 缓存
    asr_segments = None
    try:
        from subtitle.cache_manager import load_asr_cache
        asr_segments = load_asr_cache(video_path, whisper_model)
    except Exception:
        pass
    
    if asr_segments is not None:
        print(f"[ASR Compare] 使用缓存的 ASR 结果（{len(asr_segments)} 段落），跳过 ASR 识别")
    else:
        # 1. ASR 生成
        print(f"\n[1/3] ASR 识别：使用 Whisper {whisper_model} 模型...")
        audio_path = video_path_obj.with_suffix(".wav")
        
        try:
            extract_audio(str(video_path), str(audio_path))
            print(f"[ASR Compare] 音频已提取: {audio_path}")
        except Exception as e:
            raise RuntimeError(f"音频提取失败: {e}")
        
        try:
            # 修改 audio_to_segments 以支持模型参数
            from whisper import load_model
            
            print(f"[ASR Compare] 加载 Whisper 模型: {whisper_model}...")
            model = load_model(whisper_model)
            result = model.transcribe(str(audio_path))
            
            asr_segments = []
            for i, seg in enumerate(result["segments"]):
                asr_segments.append(Segment(
                    index=i + 1,
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    text=seg["text"].strip()
                ))
            
            print(f"[ASR Compare] ASR 生成完成：{len(asr_segments)} 个段落")
            
            # 保存 ASR 缓存
            try:
                from subtitle.cache_manager import save_asr_cache
                save_asr_cache(video_path, asr_segments, whisper_model)
            except Exception:
                pass
        except Exception as e:
            raise RuntimeError(f"ASR 识别失败: {e}")
    
    # 2. 解析 VTT（如果提供）
    vtt_segments = []
    if vtt_path:
        print(f"\n[2/3] 解析 VTT 字幕...")
        try:
            vtt_segments = parse_vtt(vtt_path)
            print(f"[ASR Compare] VTT 解析完成：{len(vtt_segments)} 个段落")
        except Exception as e:
            print(f"[Warning] VTT 解析失败: {e}，将只使用 ASR 结果")
            vtt_segments = []
    else:
        print(f"\n[2/3] 未提供 VTT 文件，将只使用 ASR 结果")
    
    # 3. 对比融合 + 权重筛选
    print(f"\n[3/4] 对比融合...")
    if vtt_segments:
        fused_segments = compare_and_fuse_segments(
            asr_segments, 
            vtt_segments, 
            prefer_asr=True,  # 默认偏好 ASR（ASR 准确性更高）
            enable_weight_filter=enable_weight_filter,
            min_weight=min_weight
        )
    else:
        print("[ASR Compare] 直接使用 ASR 结果（无 VTT 对比）")
        fused_segments = asr_segments
        
        # 即使没有 VTT，也可以进行权重筛选（基于 ASR 自身质量）
        if enable_weight_filter:
            print(f"\n[4/4] 权重筛选（仅基于 ASR 质量）...")
            # 创建对齐信息（只有 ASR）
            aligned_info = [(seg, seg, None, 1.0, 0.0) for seg in fused_segments]
            fused_segments = filter_by_weight(
                fused_segments,
                aligned_info,
                min_weight=min_weight,
                remove_duplicates=True
            )
    
    print(f"\n[ASR Compare] 流程完成！最终段落数：{len(fused_segments)}")
    print("=" * 60)
    
    if not enable_weight_filter or not vtt_segments:
        # 如果未启用权重筛选，或没有VTT，直接返回
        if not vtt_segments and not enable_weight_filter:
            print(f"\n[ASR Compare] 流程完成！最终段落数：{len(fused_segments)}")
            print("=" * 60)
    
    return fused_segments

