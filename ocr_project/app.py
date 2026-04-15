from flask import Flask, request, render_template, jsonify
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

SUPPORTED_LANGUAGES = {'en', 'it', 'ar', 'ru', 'es', 'fr', 'latin'}


def resolve_lang(lang: str) -> str:
    """Normalizza il codice lingua scelto dall'utente per PaddleOCR."""
    if not lang:
        return 'latin'

    selected = lang.strip().lower()
    if selected == 'auto':
        return 'latin'
    if selected == 'multi':
        return 'latin'
    if selected in SUPPORTED_LANGUAGES:
        return selected
    return 'latin'


def process_uploaded_file(uploaded_file, pipeline):
    """Processa un singolo file caricato e restituisce il payload risultato."""
    filename = secure_filename(uploaded_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    uploaded_file.save(filepath)

    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
            md5_hash = hashlib.md5(file_data).hexdigest()
            sha1_hash = hashlib.sha1(file_data).hexdigest()

        if filename.lower().endswith('.pdf'):
            images = pdf_to_images(filepath)
            texts = []
            for img in images:
                texts.append(pipeline.run(img))
            text = "\n".join(texts)
        else:
            image = load_image(filepath)
            text = pipeline.run(image)

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

        return result_data
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return render_template('index.html', error='Nessun file selezionato')

    lang = resolve_lang(request.form.get('lang', 'en'))
    engine = PaddleOCREngine(lang=lang)
    pipeline = OCRPipeline(engine)

    files = request.files.getlist('files')
    results = []

    for file in files:
        if not file.filename:
            continue

        try:
            result_data = process_uploaded_file(file, pipeline)
            results.append({
                'filename': result_data['filename'],
                'text': result_data['text']
            })
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione di {file.filename}: {str(e)}")

    return render_template('index.html', results=results)


@app.route('/api/ocr', methods=['POST'])
def api_ocr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    lang = resolve_lang(request.form.get('lang', 'en') or request.args.get('lang', 'en'))
    engine = PaddleOCREngine(lang=lang)
    pipeline = OCRPipeline(engine)

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        result_data = process_uploaded_file(file, pipeline)
        return jsonify(result_data)
    except Exception as e:
        logger.error(f"Errore API: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr/batch', methods=['POST'])
def api_ocr_batch():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400

    lang = resolve_lang(request.form.get('lang', 'en') or request.args.get('lang', 'en'))
    engine = PaddleOCREngine(lang=lang)
    pipeline = OCRPipeline(engine)

    results = []
    errors = []

    for file in files:
        if not file.filename:
            continue

        try:
            results.append(process_uploaded_file(file, pipeline))
        except Exception as e:
            logger.error(f"Errore API batch su {file.filename}: {str(e)}")
            errors.append({'filename': file.filename, 'error': str(e)})

    if not results and errors:
        return jsonify({'results': [], 'errors': errors, 'count': 0}), 500

    return jsonify({'results': results, 'errors': errors, 'count': len(results)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
