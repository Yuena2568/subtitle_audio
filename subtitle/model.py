# subtitle/model.py
from typing import Optional

class Segment:
    def __init__(self, index: int, text: str, start: Optional[float] = None, end: Optional[float] = None):
        """
        字幕段对象
        :param index: 段落序号
        :param text: 文本内容
        :param start: 开始时间（秒，float 类型）
        :param end: 结束时间（秒，float 类型）
        """
        self.index = int(index)
        self.text = str(text) if text else ""
        # 确保 start 和 end 始终为 float 类型
        if start is not None:
            try:
                self.start = float(start)
            except (ValueError, TypeError):
                self.start = 0.0
        else:
            self.start = 0.0
            
        if end is not None:
            try:
                self.end = float(end)
            except (ValueError, TypeError):
                self.end = 0.0
        else:
            self.end = 0.0
        
        # 确保 end >= start
        if self.end < self.start:
            self.end = self.start

    def to_dict(self):
        return {
            "index": self.index,
            "text": self.text,
            "start": self.start,
            "end": self.end
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            index=d["index"],
            text=d["text"],
            start=float(d.get("start", 0.0)),
            end=float(d.get("end", 0.0))
        )
