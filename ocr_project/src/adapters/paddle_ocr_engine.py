# src/core/ocr_engine.py
from paddleocr import PaddleOCR
import cv2
import re
from src.config.settings import LANGUAGE

class PaddleOCREngine:
    def __init__(self):
        """Inizializza il motore OCR con parametri ottimizzati per testo generale."""
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang=LANGUAGE,
            det_db_thresh=0.15,          # Soglia detection (più sensibile)
            det_db_box_thresh=0.4,      # Soglia per i box di testo
            det_db_unclip_ratio=2.2,    # Miglior gestione dei bordi
            rec_algorithm='SVTR_LCNet', # Algoritmo di riconoscimento ottimizzato
            rec_batch_num=6,            # Batch size per prestazioni
            use_space_char=True,        # Gestione spazi
            drop_score=0.3              # Scarta risultati con confidenza bassa
        )

    def preprocess(self, image):
        """
        Pre-processing leggero per PaddleOCR.
        Mantiene i bordi e migliorare il contrasto senza binarizzazione aggressiva.
        """
        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)  # Blur leggero
        return gray

    def clean_text(self, text):
        """
        Pulisce il testo OCR da errori comuni e caratteri indesiderati.
        """
        text = text.lower()
        corrections = {
            "0": "o",
            "1": "i",
            "|": "i",
            "€": "e",
            "5": "s",
            "8": "b",
            "6": "b",
            "9": "g"
        }

        for k, v in corrections.items():
            text = text.replace(k, v)

        # Rimuove caratteri non desiderati (tranne spazi, punteggiatura base e simboli comuni)
        text = re.sub(r'[^a-z0-9\s.,;:!?€$%&@"]', '', text)
        return text.strip()

    def extract(self, image):
        """
        Esegue l'OCR su un'immagine e restituisce il testo pulito con confidenza.
        """
        processed = self.preprocess(image)
        result = self.ocr.ocr(processed, cls=True)

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
                    if confidence < 0.5:  # Ignora risultati con confidenza bassa
                        continue
                    text = self.clean_text(text)
                    if len(text) > 1:  # Ignora stringhe troppo corte
                        texts.append((text, confidence))
                except (IndexError, TypeError):
                    continue
        return texts