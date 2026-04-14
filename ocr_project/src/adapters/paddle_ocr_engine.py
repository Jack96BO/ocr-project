# src/core/ocr_engine.py
from paddleocr import PaddleOCR
import cv2
import re
import numpy as np
from spellchecker import SpellChecker
from src.config.settings import LANGUAGE

class PaddleOCREngine:
    def __init__(self):
        """Inizializza il motore OCR con parametri ottimizzati per testo generale."""
        self.ocr = PaddleOCR(
            lang=LANGUAGE,
            use_textline_orientation=True,
            text_det_thresh=0.15,          # Soglia detection (più sensibile)
            text_det_box_thresh=0.4,      # Soglia per i box di testo
            text_det_unclip_ratio=2.2,    # Miglior gestione dei bordi
            text_recognition_batch_size=6, # Batch size per prestazioni
            text_rec_score_thresh=0.3,     # Scarta risultati con confidenza bassa
            return_word_box=True
        )
        self.spell = SpellChecker(language='it' if LANGUAGE == 'it' else 'en')  # Assumo italiano o inglese

    def preprocess(self, image):
        """
        Pre-processing avanzato per PaddleOCR.
        Include deskew, denoising e miglioramento contrasto.
        """
        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Riduzione rumore con bilateral filter
        gray = cv2.bilateralFilter(gray, 9, 75, 75)

        # Correzione inclinazione (deskew)
        gray = self.deskew(gray)

        # Ridimensionamento
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        # Miglioramento contrasto con CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

        # Thresholding adattivo per binarizzazione
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        return gray

    def deskew(self, image):
        """
        Corregge l'inclinazione del testo nell'immagine.
        """
        coords = np.column_stack(np.where(image > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated

    def clean_text(self, text):
        """
        Pulisce il testo OCR da errori comuni e caratteri indesiderati.
        Include correzioni avanzate, normalizzazione e correzione ortografica.
        """
        text = text.lower()
        corrections = {
            "0": "o",
            "1": "i",
            "l": "i",
            "|": "i",
            "€": "e",
            "5": "s",
            "8": "b",
            "6": "b",
            "9": "g",
            "2": "z",
            "3": "e",
            "4": "a",
            "7": "t",
            "q": "g",
            "w": "u",
            "x": "k"
        }

        for k, v in corrections.items():
            text = text.replace(k, v)

        # Rimuove caratteri non alfanumerici tranne spazi e punteggiatura base
        text = re.sub(r'[^a-z0-9\s.,;:!?€$%&@"]', '', text)

        # Normalizza spazi multipli
        text = re.sub(r'\s+', ' ', text)

        # Correzione ortografica parola per parola
        words = text.split()
        corrected_words = []
        for word in words:
            if word in self.spell:
                corrected_words.append(word)
            else:
                candidates = self.spell.candidates(word)
                if candidates:
                    corrected_words.append(list(candidates)[0])  # Prendi il primo candidato
                else:
                    corrected_words.append(word)

        text = ' '.join(corrected_words)

        # Rimuove spazi iniziali/finali
        return text.strip()

    def extract(self, image):
        """
        Esegue l'OCR su un'immagine e restituisce il testo pulito con confidenza.
        """
        processed = self.preprocess(image)
        result = self.ocr.predict(processed, use_textline_orientation=True, return_word_box=True)

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