import os
from src.adapters.paddle_ocr_engine import PaddleOCREngine
from src.services.pipeline import OCRPipeline
from src.services.image_service import load_image
from src.services.pdf_service import pdf_to_images
from src.utils.logger import get_logger

logger = get_logger()

def process_file(path, pipeline):
    if path.lower().endswith(".pdf"):
        images = pdf_to_images(path)
        results = []

        for img in images:
            results.append(pipeline.run(img))

        return "\n".join(results)

    else:
        image = load_image(path)
        return pipeline.run(image)


def main():
    input_path = "data/input/test.png"  # cambia qui

    engine = PaddleOCREngine()
    pipeline = OCRPipeline(engine)

    logger.info(f"Processing: {input_path}")

    text = process_file(input_path, pipeline)

    print("\n=== OCR RESULT ===\n")
    print(text)


if __name__ == "__main__":
    main()