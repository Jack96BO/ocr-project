from src.config.settings import CONFIDENCE_THRESHOLD

def clean_text(ocr_output):
    lines = []

    for text, conf in ocr_output:
        if conf >= CONFIDENCE_THRESHOLD:
            lines.append(text)

    return "\n".join(lines)