class OCRResult:
    def __init__(self, text, confidence, bbox=None):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox

    def to_dict(self):
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox
        }