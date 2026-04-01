from pdf2image import convert_from_path
import numpy as np

def pdf_to_images(pdf_path):
    pages = convert_from_path(pdf_path)

    images = []
    for page in pages:
        images.append(np.array(page))

    return images