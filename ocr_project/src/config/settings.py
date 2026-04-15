import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_DIR = os.path.join(BASE_DIR, "../data/input")
OUTPUT_DIR = os.path.join(BASE_DIR, "../data/output")

LANGUAGE = "en"
USE_GPU = False
CONFIDENCE_THRESHOLD = 0.35