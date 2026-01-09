# subtitle/ai_rewriter.py
from subtitle.model import Segment

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

class AIRewriter:
    def __init__(self, model_path: str, device: str = "auto"):
        """
        初始化 AI Rewriter
        
        Args:
            model_path: 模型路径（本地路径或 HuggingFace 模型 ID）
            device: 设备类型，"auto"（自动选择）、"cuda" 或 "cpu"
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers 模块未安装，请使用 uv add transformers 安装")
        
        # 自动选择设备
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"[AIRewriter] 加载模型: {model_path}")
        print(f"[AIRewriter] 设备: {device}")
        
        try:
            # 尝试加载 tokenizer 和 model（更灵活的方式）
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if device == "cuda" and torch.cuda.is_available() else torch.float32,
                device_map="auto" if device == "cuda" and torch.cuda.is_available() else None,
                low_cpu_mem_usage=True,
            )
            if device == "cpu" or not torch.cuda.is_available():
                self.model = self.model.to(device)
            
            # 设置 pad_token（如果不存在）
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # 创建 pipeline
            self.generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if device == "cuda" and torch.cuda.is_available() else -1,
            )
            print(f"[AIRewriter] 模型加载成功")
            
        except Exception as e:
            print(f"[AIRewriter] 使用简化 pipeline 模式: {e}")
            # 如果失败，使用简化的 pipeline（自动下载和加载）
            try:
                self.generator = pipeline(
                    "text-generation",
                    model=model_path,
                    device=0 if device == "cuda" and torch.cuda.is_available() else -1,
                )
                # 尝试获取 tokenizer
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                    if self.tokenizer.pad_token is None:
                        self.tokenizer.pad_token = self.tokenizer.eos_token
                except:
                    self.tokenizer = None
                print(f"[AIRewriter] 简化模式加载成功")
            except Exception as e2:
                raise RuntimeError(f"无法加载模型 {model_path}: {e2}")

    def rewrite_segments(self, segments, prompt: str = ""):
        """
        改写字幕段落
        
        Args:
            segments: Segment 列表
            prompt: 改写提示词（例如："请将以下文本改写为严谨的科普风格："）
        
        Returns:
            改写后的 Segment 列表
        """
        new_segments = []
        
        for seg in segments:
            try:
                # 构建提示词
                if prompt:
                    # 如果有自定义提示词，使用它
                    full_prompt = f"{prompt}\n原文：{seg.text}\n改写："
                else:
                    # 默认提示词
                    full_prompt = f"请改写以下文本，使其更加清晰专业：\n{seg.text}\n改写："
                
                # 计算合适的生成长度
                input_length = len(self.tokenizer.encode(full_prompt)) if hasattr(self, 'tokenizer') and self.tokenizer else len(full_prompt.split())
                max_new_tokens = min(input_length * 2, 256)  # 限制生成长度
                min_length = max(input_length + 10, len(seg.text) // 3)  # 最小长度
                
                # 生成改写文本
                result = self.generator(
                    full_prompt,
                    max_new_tokens=max_new_tokens,
                    min_length=min_length,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.1,  # 减少重复
                    truncation=True,
                    pad_token_id=self.tokenizer.eos_token_id if hasattr(self, 'tokenizer') and self.tokenizer else None,
                )
                
                # 提取生成的文本
                generated_text = result[0]['generated_text']
                
                # 移除提示词部分，只保留改写后的文本
                if "改写：" in generated_text:
                    rewritten_text = generated_text.split("改写：")[-1].strip()
                elif "原文：" in generated_text:
                    # 如果模型返回了完整文本，提取改写部分
                    parts = generated_text.split("原文：")
                    if len(parts) > 1:
                        rewritten_text = parts[-1].split("\n")[0].strip()
                    else:
                        rewritten_text = generated_text.replace(full_prompt, "").strip()
                else:
                    # 直接移除提示词
                    rewritten_text = generated_text.replace(full_prompt, "").strip()
                
                # 清理文本（移除可能的重复提示词）
                rewritten_text = rewritten_text.split("\n")[0].strip()  # 只取第一行
                rewritten_text = rewritten_text.replace("改写：", "").strip()
                
                # 如果改写失败或为空，使用原文
                if not rewritten_text or len(rewritten_text) < len(seg.text) // 3:
                    print(f"[AIRewriter] 段落 {seg.index} 改写结果不理想，使用原文")
                    rewritten_text = seg.text
                
                new_segments.append(Segment(
                    index=seg.index,
                    text=rewritten_text,
                    start=seg.start,
                    end=seg.end
                ))
                
            except Exception as e:
                print(f"[AIRewriter] 改写段落 {seg.index} 失败: {e}")
                import traceback
                traceback.print_exc()
                # 失败时使用原文
                new_segments.append(seg)
        
        return new_segments
