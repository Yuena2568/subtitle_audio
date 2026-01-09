# subtitle/translator.py
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

def translate_segment(text: str, target_lang: str = "zh") -> str:
    """
    翻译单段文本。
    当前使用免费 API（示例为百度翻译开放接口或谷歌翻译网页接口）
    可替换为其他免费 API 或本地翻译库。
    
    Args:
        text: 待翻译的文本
        target_lang: 目标语言，例如 'zh', 'en', 'ja'
        
    Returns:
        翻译后的文本
    """
    if not REQUESTS_AVAILABLE:
        print("[Warning] requests 模块未安装，翻译功能不可用。请使用 pip install requests 安装")
        return text  # 没有 requests 时返回原文
    
    if not text or not text.strip():
        return text
    
    # 简单示例：调用 Google 翻译网页版 API
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",           # 自动检测源语言
            "tl": target_lang,      # 目标语言
            "dt": "t",
            "q": text
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        # 返回结构：[ [ [translated_text, original_text, ...], ...], ... ]
        result = response.json()
        translated_text = "".join([item[0] for item in result[0] if item[0]])
        return translated_text if translated_text else text
    except Exception as e:
        print(f"[Translator] 翻译失败: {e}")
        return text  # 失败时返回原文


def translate_batch(texts: list[str], target_lang: str = "zh", batch_size: int = 10) -> list[str]:
    """
    批量翻译文本列表
    
    Args:
        texts: 待翻译的文本列表
        target_lang: 目标语言
        batch_size: 每批处理的文本数量（Google API 建议不要超过10个）
        
    Returns:
        翻译后的文本列表
    """
    if not REQUESTS_AVAILABLE:
        print("[Warning] requests 模块未安装，批量翻译功能不可用")
        return texts
    
    if not texts:
        return []
    
    translated = []
    
    # 分批处理
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            # 合并多个文本，用换行符分隔（Google 翻译支持多行）
            combined_text = "\n".join(batch)
            
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": "auto",
                "tl": target_lang,
                "dt": "t",
                "q": combined_text
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            
            # 提取翻译结果
            if result and result[0]:
                # Google 翻译返回的格式：每个句子对应一个翻译
                translated_lines = []
                for item in result[0]:
                    if item and len(item) > 0:
                        translated_lines.append(item[0] if item[0] else "")
                
                # 如果翻译行数与原文行数一致，直接使用
                if len(translated_lines) == len(batch):
                    translated.extend(translated_lines)
                else:
                    # 如果不一致，尝试按换行符分割
                    combined_translated = "".join([item[0] for item in result[0] if item[0]])
                    # 简单处理：如果不能正确分割，逐段翻译
                    if len(batch) == 1:
                        translated.append(combined_translated)
                    else:
                        # 回退到逐段翻译
                        for text in batch:
                            translated.append(translate_segment(text, target_lang))
            else:
                # 回退到逐段翻译
                for text in batch:
                    translated.append(translate_segment(text, target_lang))
                    
        except Exception as e:
            print(f"[Translator] 批量翻译失败（批次 {i//batch_size + 1}），回退到逐段翻译: {e}")
            # 回退到逐段翻译
            for text in batch:
                translated.append(translate_segment(text, target_lang))
    
    return translated if len(translated) == len(texts) else texts
