from src.core.postprocessing import clean_text

class OCRPipeline:
    def __init__(self, engine):
        self.engine = engine

    def run(self, image):
        processed = self.engine.preprocess(image)
        raw_text = self.engine.extract(processed)
        final_text = clean_text(raw_text)
        return final_text