import cv2

def load_image(path, max_side=1200):
    """
    Carica un'immagine e la ridimensiona aggressivamente se troppo grande.
    
    Args:
        path: percorso dell'immagine
        max_side: lato massimo consentito (default 1200px - aggressivo per performance)
    
    Returns:
        immagine caricata e ridimensionata se necessario
    """
    image = cv2.imread(path)
    
    if image is None:
        return None
    
    h, w = image.shape[:2]
    max_dim = max(h, w)
    
    # Se l'immagine è più grande del massimo, ridimensiona
    if max_dim > max_side:
        scale = max_side / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    return image