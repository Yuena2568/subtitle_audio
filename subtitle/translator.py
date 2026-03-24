# subtitle/translator.py
"""
翻译模块
支持 MyMemory（免费，国内可用）和 Google Translate
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from deep_translator import MyMemoryTranslator
    MYMEMORY_AVAILABLE = True
except ImportError:
    MYMEMORY_AVAILABLE = False


# ================== MyMemory 翻译 ==================
def _mymemory_translate(text: str, target_lang: str = "zh") -> str:
    """使用 MyMemory 翻译单段文本"""
    if not MYMEMORY_AVAILABLE:
        raise ImportError("deep-translator 未安装")
    lang_map = {"zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR"}
    target = lang_map.get(target_lang, target_lang)
    t = MyMemoryTranslator(source="en-US", target=target)
    return t.translate(text)


def _mymemory_batch(texts: List[str], target_lang: str = "zh", batch_size: int = 5) -> List[str]:
    """MyMemory 批量翻译（逐条，因为 MyMemory 不支持批量拼接）"""
    results = []
    for i, text in enumerate(texts):
        try:
            translated = _mymemory_translate(text, target_lang)
            results.append(translated)
        except Exception as e:
            print(f"[MyMemory] 段落 {i} 翻译失败: {e}")
            results.append(text)
        # MyMemory 限速：每秒不超过 4 个请求
        time.sleep(0.3)
        if (i + 1) % 10 == 0:
            time.sleep(1.0)  # 每 10 条额外等 1 秒
    return results


# ================== Google 翻译（备用） ==================
def _google_translate(text: str, target_lang: str = "zh") -> str:
    """使用 Google 翻译单段文本"""
    if not REQUESTS_AVAILABLE:
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": text
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        translated_text = "".join([item[0] for item in result[0] if item[0]])
        return translated_text if translated_text else text
    except Exception as e:
        raise RuntimeError(f"Google 翻译失败: {e}")


# ================== 对外接口 ==================
def translate_segment(text: str, target_lang: str = "zh") -> str:
    """
    翻译单段文本。
    优先 MyMemory（国内可用），失败则回退 Google。
    """
    if not text or not text.strip():
        return text

    # 优先 MyMemory
    if MYMEMORY_AVAILABLE:
        try:
            return _mymemory_translate(text, target_lang)
        except Exception as e:
            print(f"[Translator] MyMemory 失败，回退 Google: {e}")

    # 回退 Google
    try:
        return _google_translate(text, target_lang)
    except Exception as e:
        print(f"[Translator] 翻译失败: {e}")
        return text


def translate_batch(texts: List[str], target_lang: str = "zh", batch_size: int = 10) -> List[str]:
    """
    批量翻译文本列表。
    优先 MyMemory，失败则回退 Google（合并多行翻译）。
    """
    if not texts:
        return []

    # 优先 MyMemory（逐条翻译，但并发加速）
    if MYMEMORY_AVAILABLE:
        try:
            print(f"[Translator] 使用 MyMemory 翻译（{len(texts)} 段）")
            return _mymemory_batch(texts, target_lang)
        except Exception as e:
            print(f"[Translator] MyMemory 批量翻译失败，回退 Google: {e}")

    # 回退 Google（合并多行）
    if not REQUESTS_AVAILABLE:
        print("[Warning] 无可用翻译服务")
        return texts

    print(f"[Translator] 使用 Google 翻译（{len(texts)} 段）")
    translated = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            combined_text = "\n".join(batch)
            translated_text = _google_translate(combined_text, target_lang)
            # 按换行分割回各段
            lines = translated_text.split("\n")
            if len(lines) == len(batch):
                translated.extend(lines)
            else:
                # 行数不匹配，逐段翻译
                for text in batch:
                    try:
                        translated.append(_google_translate(text, target_lang))
                    except Exception:
                        translated.append(text)
        except Exception as e:
            print(f"[Translator] 批次 {i//batch_size + 1} 失败: {e}")
            for text in batch:
                translated.append(text)

    return translated if len(translated) == len(texts) else texts
