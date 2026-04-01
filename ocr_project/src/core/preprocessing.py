from paddleocr import PaddleOCR
from src.core.ocr_engine import OCREngine
from src.config.settings import LANGUAGE
import cv2
import re


class PaddleOCREngine(OCREngine):
    def __init__(self):
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang=LANGUAGE,

            # 🔥 DETECTION FIX
            det_db_thresh=0.15,
            det_db_box_thresh=0.4,
            det_db_unclip_ratio=2.2,

            # recognition
            rec_algorithm='SVTR_LCNet',
            rec_batch_num=6,

            use_space_char=True,
            drop_score=0.3
        )

    # =========================
    # PREPROCESS (FIX ERROR cv2)
    # =========================
    def preprocess(self, image):
        # gestisce grayscale/BGR
        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # upscale
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        # contrasto leggero
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # blur leggero
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        return gray

    # =========================
    # POST-PROCESSING TESTO
    # =========================
    def clean_text(self, text):
        text = text.lower()

        corrections = {
            "0": "o",
            "1": "i",
            "|": "i",
            "€": "e"
        }

        for k, v in corrections.items():
            text = text.replace(k, v)

        text = re.sub(r'[^a-z0-9\s.,;:!?€]', '', text)

        return text.strip()

    # =========================
    # OCR
    # =========================
    def extract(self, image):
        # preprocessing
        processed = self.preprocess(image)

        # OCR
        result = self.ocr.ocr(
            processed,
            cls=True,
            det=True,
            rec=True
        )

        if not result:
            return []

        texts = []

        for line in result:
            if not line:
                continue

            for word_info in line:
                if not word_info:
                    continue

                try:
                    text = word_info[1][0]
                    confidence = word_info[1][1]

                    if confidence < 0.5:
                        continue

                    text = self.clean_text(text)

                    if len(text) > 1:
                        texts.append((text, confidence))

                except (IndexError, TypeError):
                    continue

        return texts