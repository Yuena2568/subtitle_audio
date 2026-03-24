from typing import List, Optional
from subtitle.model import Segment
from subtitle.translator import translate_segment, translate_batch
from subtitle.tts import speak
from subtitle.optimizer import optimize_subtitles
from subtitle.personality_config import PERSONA_CONFIG


def detect_language(text: str) -> str:
    """
    简单检测文本语言
    
    Args:
        text: 待检测的文本
    
    Returns:
        'zh' 如果是中文, 'en' 如果是英文, 'unknown' 如果无法确定
    """
    if not text or not text.strip():
        return "unknown"
    
    # 统计中文字符数量
    chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    # 统计字母和数字数量（作为总字符数）
    total_chars = len([c for c in text if c.isalnum()])
    
    if total_chars > 0:
        chinese_ratio = chinese_chars / total_chars
        # 如果中文字符占比超过30%，认为是中文
        if chinese_ratio > 0.3:
            return "zh"
        # 如果有中文字符但比例不高，也可能是混合，优先判断为中文
        elif chinese_chars > 0:
            return "zh"
    
    # 默认认为是英文
    return "en"

# 可选导入 AI Rewriter（如果没有 transformers 模块，则在运行时处理）
try:
    from subtitle.ai_rewriter import AIRewriter
    AI_REWRITER_AVAILABLE = True
except ImportError:
    AI_REWRITER_AVAILABLE = False
    AIRewriter = None

def run_pipeline(
    segments: List[Segment],
    translate: bool = False,
    ai_rewrite: bool = False,
    model_path: str | None = None,
    tts: bool = False,
    prompt: str | None = None,
    language: str = "zh",
    optimize_json: bool = False,  # 保留此参数以兼容 main.py，但暂不使用
    use_batch_translate: bool = True,  # 是否使用批量翻译（默认启用）
    video_path: str | None = None,  # 用于翻译缓存
) -> List[Segment]:
    """
    核心字幕处理流水线（优化版）
    
    新流程：
    1. 解析字幕（外部完成）
    2. 翻译（批量，如果启用）
    3. 强化优化（去重、合并、清理）
    4. AI改写（可选，默认跳过因为效果不好）
    """
    
    if not segments:
        return []
    
    # -----------------------------
    # 0️⃣ 预处理：基础清理（在翻译之前）
    # -----------------------------
    from subtitle.optimizer import clean_text
    print(f"[Pipeline] 预处理：清理原始文本...")
    for seg in segments:
        seg.text = clean_text(seg.text)
    
    # -----------------------------
    # 1️⃣ 翻译（优先进行，在优化之前）
    # -----------------------------
    if translate:
        # 语言检测：避免重复翻译已翻译的文本
        first_text = segments[0].text if segments else ""
        detected_lang = detect_language(first_text)
        
        if detected_lang == "zh" and language == "zh":
            print(f"[Pipeline] 检测到文本已经是中文（语言检测: {detected_lang}），跳过翻译步骤")
            translate = False
        else:
            print(f"[Pipeline] 开始翻译（目标语言: {language}，检测到源语言: {detected_lang}）...")
            
            # 先尝试翻译缓存
            cached_translated = None
            if video_path:
                from subtitle.cache_manager import load_translate_cache, save_translate_cache
                source_texts = [seg.text for seg in segments]
                cached_translated = load_translate_cache(video_path, source_texts, language)
            
            if cached_translated and len(cached_translated) == len(segments):
                print("[Pipeline] 使用翻译缓存")
                for seg, translated in zip(segments, cached_translated):
                    seg.text = translated
            elif use_batch_translate:
                # 使用批量翻译（并发 + 换行拼接 + 模糊对齐）
                print(f"[Pipeline] 使用批量翻译模式（共 {len(segments)} 个段落）")
                source_texts = [seg.text for seg in segments]
                
                try:
                    translated_texts = translate_batch(source_texts, target_lang=language, batch_size=40)
                    
                    # 每100段打印进度
                    translated_count = 0
                    for i, (seg, translated) in enumerate(zip(segments, translated_texts)):
                        seg.text = translated
                        if translated and translated.strip():
                            translated_count += 1
                        if (i + 1) % 100 == 0:
                            print(f"[Pipeline] 已翻译 {i + 1}/{len(segments)} 个段落")
                    
                    print(f"[Pipeline] 批量翻译完成（成功: {translated_count}/{len(segments)}）")
                    
                    # 保存翻译缓存
                    if video_path:
                        try:
                            from subtitle.cache_manager import save_translate_cache
                            save_translate_cache(video_path, source_texts, translated_texts, language)
                        except Exception:
                            pass
                    
                except Exception as e:
                    print(f"[Pipeline] 批量翻译失败，回退到逐段翻译: {e}")
                    translated_count = 0
                    for i, seg in enumerate(segments):
                        try:
                            if seg.text.strip():
                                translated_text = translate_segment(seg.text, target_lang=language)
                                seg.text = translated_text
                                translated_count += 1
                                if (i + 1) % 100 == 0:
                                    print(f"[Pipeline] 已翻译 {i + 1}/{len(segments)} 个段落")
                        except Exception as e2:
                            print(f"[Pipeline] 段落 {seg.index} 翻译失败: {e2}")
                    print(f"[Pipeline] 逐段翻译完成（成功: {translated_count}/{len(segments)}）")
            else:
                # 逐段翻译模式（兼容旧逻辑）
                print(f"[Pipeline] 使用逐段翻译模式（共 {len(segments)} 个段落）")
                translated_count = 0
                for i, seg in enumerate(segments):
                    try:
                        if seg.text.strip():
                            translated_text = translate_segment(seg.text, target_lang=language)
                            seg.text = translated_text
                            translated_count += 1
                            if (i + 1) % 100 == 0:
                                print(f"[Pipeline] 已翻译 {i + 1}/{len(segments)} 个段落")
                    except Exception as e:
                        print(f"[Pipeline] 段落 {seg.index} 翻译失败: {e}")
                print(f"[Pipeline] 翻译完成（成功: {translated_count}/{len(segments)}）")
    
    # -----------------------------
    # 2️⃣ 强化优化（在翻译之后进行）
    # -----------------------------
    print(f"[Pipeline] 开始优化（去重、合并、清理）...")
    
    # 翻译后再次清理每个段落（移除可能由翻译引入的重复）
    from subtitle.optimizer import clean_text
    for seg in segments:
        seg.text = clean_text(seg.text)
    
    segments_dict = [seg.__dict__ for seg in segments]
    optimized_dicts = optimize_subtitles(segments_dict)
    optimized_segments = [Segment(**d) for d in optimized_dicts]
    
    # 最终清理
    for seg in optimized_segments:
        seg.text = clean_text(seg.text)
    
    print(f"[Pipeline] 优化完成：{len(segments)} -> {len(optimized_segments)} 个段落")

    # -----------------------------
    # 3️⃣ AI rewrite（可选，默认跳过）
    # -----------------------------
    final_segments = optimized_segments
    
    if ai_rewrite and model_path:
        print("[Pipeline] AI Rewrite 功能已启用（注意：当前效果可能不理想）")
        rewriter = None
        if not AI_REWRITER_AVAILABLE:
            print("[Warning] AI Rewriter 不可用，请安装 transformers: pip install transformers")
        else:
            try:
                rewriter = AIRewriter(model_path)
                print("[Pipeline] 开始 AI 改写...")
                
                # 获取人设配置
                persona_config = PERSONA_CONFIG.get(language, {})
                if isinstance(persona_config, dict):
                    persona_prompt = f"{persona_config.get('role', '')}，{persona_config.get('style', '')}"
                else:
                    persona_prompt = str(persona_config)
                
                rewrite_prompt = f"{persona_prompt}\n{prompt}" if prompt else persona_prompt
                
                # AI 改写（批量处理）
                rewritten_segments = rewriter.rewrite_segments(optimized_segments, prompt=rewrite_prompt)
                final_segments = rewritten_segments
                print(f"[Pipeline] AI 改写完成")
            except Exception as e:
                print(f"[Warning] AI Rewriter 初始化或执行失败: {e}")
                print("[Pipeline] 跳过 AI 改写，使用优化后的文本")
    else:
        # 默认跳过 AI 改写（因为效果不好）
        pass

    # -----------------------------
    # 4️⃣ TTS（如果启用）
    # -----------------------------
    if tts:
        for seg in final_segments:
            try:
                speak(seg.text)
            except Exception as e:
                print(f"[TTS] 朗读段落 {seg.index} 失败: {e}")

    # 重新编号
    for i, seg in enumerate(final_segments, start=1):
        seg.index = i

    return final_segments
