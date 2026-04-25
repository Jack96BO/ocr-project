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
            use_angle_cls=False,
            cls_model_dir=None,            # Disabilita classificazione per evitare download corrotto
            det_db_thresh=0.25,
            det_db_box_thresh=0.3,
            det_db_unclip_ratio=2.5,
            rec_batch_num=6,
            drop_score=0.15,
            return_word_box=True
        )
        # Correzione ortografica per lingue supportate
        # pyspellchecker supporta: en, es, fr, de, pt (no italiano)
        try:
            if lang == 'en':
                self.spell = SpellChecker(language='en')
            elif lang == 'es':
                self.spell = SpellChecker(language='es')
            elif lang == 'fr':
                self.spell = SpellChecker(language='fr')
            elif lang == 'de':
                self.spell = SpellChecker(language='de')
            elif lang == 'pt':
                self.spell = SpellChecker(language='pt')
            else:
                self.spell = None
        except (ValueError, Exception):
            # Se la lingua non è supportata, disabilita spell check
            self.spell = None

    def preprocess(self, image):
        """
        Pre-processing conservativo: migliora contrasto senza binarizzazione aggressiva.
        """
        if image is None:
            return image

        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Denoise bilaterale (mantiene bordi, riduce rumore)
        gray = cv2.bilateralFilter(gray, 5, 50, 50)

        # Contrasto adattivo (CLAHE) moderato
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Upscale moderato solo per immagini piccole
        h, w = gray.shape[:2]
        min_side = min(h, w)
        if min_side < 600:
            scale = 2.0
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        elif min_side < 900:
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

            if confidence < 0.15:
                continue

            cleaned = self.clean_text(text)
            if cleaned:
                texts.append((cleaned, confidence))

        return texts

    def clean_text(self, text):
        """
        Pulisce e corregge il testo OCR con correzioni post-OCR e spell check.
        """
        text = re.sub(r'\s+', ' ', text).strip()

        # Correzioni comuni di errori OCR
        text = text.replace("'rno", "rno")     # apostrofo spurio
        text = text.replace("'o", "o")         # apostrofo spurio
        text = text.replace("won", "buon")     # w->b + correzione u
        text = text.replace("Wn", "Buon")      # maiuscola
        text = text.replace("bongiorno", "buongiorno")  # correzione specifica comune
        
        # Rimuovi apostrofi isolati in mezzo alle parole
        text = re.sub(r"(\w)'(\w)", r"\1\2", text)
        
        text = re.sub(r'\s+', ' ', text).strip()

        # Correzione ortografica con spell checker (solo per lingue supportate)
        if self.spell is not None and text:
            words = text.split()
            corrected_words = []
            for word in words:
                # Salta parole troppo corte, numeri, caratteri speciali
                if len(word) <= 2 or not any(c.isalpha() for c in word):
                    corrected_words.append(word)
                    continue

                # Estrai solo lettere per il controllo
                alpha_only = ''.join(c for c in word if c.isalpha())
                if alpha_only.lower() in self.spell or len(alpha_only) <= 2:
                    corrected_words.append(word)
                    continue

                candidates = self.spell.candidates(alpha_only.lower())
                if candidates:
                    best = min(candidates, key=lambda x: abs(len(x) - len(alpha_only)))
                    corrected_words.append(best)
                else:
                    corrected_words.append(word)

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