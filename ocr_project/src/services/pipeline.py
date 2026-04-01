from src.core.preprocessing import preprocess
from src.core.postprocessing import clean_text

class OCRPipeline:
    def __init__(self, engine):
        self.engine = engine

    def run(self, image):
        processed = preprocess(image)
        raw_text = self.engine.extract(processed)
        final_text = clean_text(raw_text)
        return final_text