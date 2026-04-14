from flask import Flask, request, render_template, redirect, url_for, jsonify
import os
import hashlib
import json
from werkzeug.utils import secure_filename
from src.adapters.paddle_ocr_engine import PaddleOCREngine
from src.services.pipeline import OCRPipeline
from src.services.image_service import load_image
from src.services.pdf_service import pdf_to_images
from src.utils.logger import get_logger

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['OUTPUT_FOLDER'] = 'data/output'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Assicurati che le cartelle esistano
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

logger = get_logger()

# Inizializza l'engine OCR
engine = PaddleOCREngine()
pipeline = OCRPipeline(engine)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return render_template('index.html', error='Nessun file selezionato')

    files = request.files.getlist('files')
    results = []

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Calcola hash
            with open(filepath, 'rb') as f:
                file_data = f.read()
                md5_hash = hashlib.md5(file_data).hexdigest()
                sha1_hash = hashlib.sha1(file_data).hexdigest()

            # Processa il file
            if filename.lower().endswith('.pdf'):
                images = pdf_to_images(filepath)
                texts = []
                for img in images:
                    texts.append(pipeline.run(img))
                text = "\n".join(texts)
            else:
                image = load_image(filepath)
                text = pipeline.run(image)

            # Salva risultato in JSON
            result_data = {
                'filename': filename,
                'filepath': os.path.abspath(filepath),
                'md5': md5_hash,
                'sha1': sha1_hash,
                'text': text
            }
            json_filename = f"{md5_hash}.json"
            json_filepath = os.path.join(app.config['OUTPUT_FOLDER'], json_filename)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=4)

            results.append({
                'filename': filename,
                'text': text
            })

            # Rimuovi il file upload dopo elaborazione
            os.remove(filepath)

        except Exception as e:
            logger.error(f"Errore durante l'elaborazione di {filename}: {str(e)}")
            if os.path.exists(filepath):
                os.remove(filepath)

    return render_template('index.html', results=results)
@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Calcola hash
        with open(filepath, 'rb') as f:
            file_data = f.read()
            md5_hash = hashlib.md5(file_data).hexdigest()
            sha1_hash = hashlib.sha1(file_data).hexdigest()

        # Processa il file
        if filename.lower().endswith('.pdf'):
            images = pdf_to_images(filepath)
            texts = []
            for img in images:
                texts.append(pipeline.run(img))
            text = "\n".join(texts)
        else:
            image = load_image(filepath)
            text = pipeline.run(image)

        # Salva risultato in JSON
        result_data = {
            'filename': filename,
            'filepath': os.path.abspath(filepath),
            'md5': md5_hash,
            'sha1': sha1_hash,
            'text': text
        }
        json_filename = f"{md5_hash}.json"
        json_filepath = os.path.join(app.config['OUTPUT_FOLDER'], json_filename)
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)

        # Rimuovi file upload
        os.remove(filepath)

        return jsonify(result_data)

    except Exception as e:
        logger.error(f"Errore API: {str(e)}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)