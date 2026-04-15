# src/core/ocr_engine.py
from paddleocr import PaddleOCR
import cv2
import re
from spellchecker import SpellChecker

class PaddleOCREngine:
    def __init__(self, lang='en'):
        """Inizializza il motore OCR con parametri ottimizzati per testo generale."""
        self.lang = lang
        self.ocr = PaddleOCR(
            lang=lang,
            use_textline_orientation=True,
            text_det_thresh=0.15,          # Soglia detection (più sensibile)
            text_det_box_thresh=0.4,      # Soglia per i box di testo
            text_det_unclip_ratio=2.2,    # Miglior gestione dei bordi
            text_recognition_batch_size=6, # Batch size per prestazioni
            text_rec_score_thresh=0.3,     # Scarta risultati con confidenza bassa
            return_word_box=True
        )
        # La correzione ortografica viene applicata solo in inglese.
        self.spell = SpellChecker(language='en') if lang == 'en' else None

    def preprocess(self, image):
        """
        Pre-processing leggero: migliora leggibilità senza distruggere i dettagli.
        """
        if image is None:
            return image

        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Riduzione rumore leggera.
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Migliora contrasto locale mantenendo i bordi dei caratteri.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Upscale moderato solo per immagini piccole.
        h, w = gray.shape[:2]
        min_side = min(h, w)
        if min_side < 900:
            scale = 1.5
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        return gray

    def _extract_from_image(self, image):
        """Esegue OCR su una singola variante d'immagine."""
        result = self.ocr.ocr(image, cls=False)

        if not result:
            return []

        # paddleocr.ocr per singola immagine restituisce normalmente [lines].
        lines = result[0] if isinstance(result, list) and result and isinstance(result[0], list) else result
        if lines is None:
            return []

        texts = []
        for word_info in lines:
            if not word_info or not isinstance(word_info, (list, tuple)) or len(word_info) < 2:
                continue

            rec_info = word_info[1]
            if not isinstance(rec_info, (list, tuple)) or len(rec_info) < 2:
                continue

            try:
                text = str(rec_info[0])
                confidence = float(rec_info[1])
            except (TypeError, ValueError):
                continue

            if confidence < 0.3:
                continue

            cleaned = self.clean_text(text)
            if cleaned:
                texts.append((cleaned, confidence))

        return texts

    def clean_text(self, text):
        """
        Pulisce il testo OCR senza perdere caratteri di alfabeti non latini.
        """
        text = re.sub(r'\s+', ' ', text).strip()

        # Correzione leggera solo su parole ASCII in inglese.
        if self.spell is not None and text:
            words = text.split()
            corrected_words = []
            for word in words:
                if not word.isascii() or not word.isalpha() or len(word) <= 2:
                    corrected_words.append(word)
                    continue

                if word.lower() in self.spell:
                    corrected_words.append(word)
                    continue

                candidates = self.spell.candidates(word.lower())
                corrected_words.append(next(iter(candidates), word))

            text = ' '.join(corrected_words)

        return text

    def extract(self, image):
        """
        Esegue OCR in due passaggi (originale + preprocess) e sceglie il risultato migliore.
        """
        if image is None:
            return []

        original_texts = self._extract_from_image(image)
        processed = self.preprocess(image)
        processed_texts = self._extract_from_image(processed) if processed is not None else []

        def score(candidates):
            if not candidates:
                return 0.0
            conf_sum = sum(conf for _, conf in candidates)
            char_count = sum(len(text) for text, _ in candidates)
            # privilegia testo più ricco ma con buona confidenza media
            return conf_sum + (0.02 * char_count)

        return processed_texts if score(processed_texts) > score(original_texts) else original_texts