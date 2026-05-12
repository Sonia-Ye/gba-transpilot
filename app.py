from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import requests
import base64
import datetime
from threading import Thread

# Optional imports (may fail on Python 3.14 due to removed find_loader)
PYTESSERACT_AVAILABLE = False
WHOOSH_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    print("Warning: pytesseract is not available (OCR features disabled)")

try:
    import whoosh.index as index
    from whoosh.fields import Schema, TEXT, ID
    from whoosh.qparser import QueryParser
    from whoosh import scoring
    WHOOSH_AVAILABLE = True
except ImportError:
    print("Warning: whoosh is not available (glossary search features disabled)")

try:
    from PIL import Image
except ImportError:
    print("Warning: Pillow is not available (image processing disabled)")

try:
    import pdfplumber
except ImportError:
    print("Warning: pdfplumber is not available (PDF processing disabled)")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Warning: beautifulsoup4 is not available (web scraping disabled)")

try:
    import schedule
    import time
except ImportError:
    print("Warning: schedule is not available (scheduled tasks disabled)")
    schedule = None
    time = None

# Qwen API configuration
QWEN_API_KEY = os.environ.get('QWEN_API_KEY', 'sk-ab3828c98786402992377e7088054b17')
QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
QWEN_MODEL = "qwen-turbo"

def call_qwen(prompt, system_message="You are a helpful assistant."):
    """Call Qwen API with the given prompt and return the response text."""
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": QWEN_MODEL,
        "input": {
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        }
    }
    try:
        response = requests.post(QWEN_API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        # Extract text from Qwen response format
        if "output" in result and "text" in result["output"]:
            return result["output"]["text"].strip()
        elif "output" in result and "choices" in result["output"]:
            return result["output"]["choices"][0]["message"]["content"].strip()
        else:
            return str(result)
    except Exception as e:
        print(f"Qwen API error: {e}")
        raise

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Enable UTF-8 encoding for all responses
app.config['JSON_AS_ASCII'] = False

# DEMO MODE: Use local mock translation instead of Qwen
DEMO_MODE = False

# Mock translation dictionary for demo
MOCK_TRANSLATIONS = {
    "香港": {"en": "Hong Kong", "zh": "香港", "zh-HK": "香港"},
    "Hong Kong": {"en": "Hong Kong", "zh": "香港", "zh-HK": "香港"},
    "中国": {"en": "China", "zh": "中国", "zh-HK": "中國"},
    "China": {"en": "China", "zh": "中国", "zh-HK": "中國"},
    "广州": {"en": "Guangzhou", "zh": "广州", "zh-HK": "廣州"},
    "Guangzhou": {"en": "Guangzhou", "zh": "广州", "zh-HK": "廣州"},
    "深圳": {"en": "Shenzhen", "zh": "深圳", "zh-HK": "深圳"},
    "Shenzhen": {"en": "Shenzhen", "zh": "深圳", "zh-HK": "深圳"},
    "澳门": {"en": "Macao", "zh": "澳门", "zh-HK": "澳門"},
    "Macao": {"en": "Macao", "zh": "澳门", "zh-HK": "澳門"},
    "旅游": {"en": "Tourism", "zh": "旅游", "zh-HK": "旅遊"},
    "Tourism": {"en": "Tourism", "zh": "旅游", "zh-HK": "旅遊"},
    "酒店": {"en": "Hotel", "zh": "酒店", "zh-HK": "酒店"},
    "Hotel": {"en": "Hotel", "zh": "酒店", "zh-HK": "酒店"},
    "餐厅": {"en": "Restaurant", "zh": "餐厅", "zh-HK": "餐廳"},
    "Restaurant": {"en": "Restaurant", "zh": "餐厅", "zh-HK": "餐廳"},
    "地铁": {"en": "MTR", "zh": "地铁", "zh-HK": "地鐵"},
    "MTR": {"en": "MTR", "zh": "地铁", "zh-HK": "地鐵"},
    "机场": {"en": "Airport", "zh": "机场", "zh-HK": "機場"},
    "Airport": {"en": "Airport", "zh": "机场", "zh-HK": "機場"},
    "签证": {"en": "Visa", "zh": "签证", "zh-HK": "簽證"},
    "Visa": {"en": "Visa", "zh": "签证", "zh-HK": "簽證"},
    "今天天气怎么样": {"en": "How is the weather today?", "zh": "今天天气怎么样", "zh-HK": "今日天氣如何"},
    "How is the weather today": {"en": "How is the weather today?", "zh": "今天天气怎么样", "zh-HK": "今日天氣如何"},
    "谢谢你": {"en": "Thank you", "zh": "谢谢你", "zh-HK": "多謝"},
    "Thank you": {"en": "Thank you", "zh": "谢谢你", "zh-HK": "多謝"},
    "你好": {"en": "Hello", "zh": "你好", "zh-HK": "你好"},
    "Hello": {"en": "Hello", "zh": "你好", "zh-HK": "你好"},
    "再见": {"en": "Goodbye", "zh": "再见", "zh-HK": "再見"},
    "Goodbye": {"en": "Goodbye", "zh": "再见", "zh-HK": "再見"},
    "基本法": {"en": "Basic Law", "zh": "基本法", "zh-HK": "基本法"},
    "Basic Law": {"en": "Basic Law", "zh": "基本法", "zh-HK": "基本法"},
    "立法会": {"en": "Legislative Council", "zh": "立法会", "zh-HK": "立法會"},
    "Legislative Council": {"en": "Legislative Council", "zh": "立法会", "zh-HK": "立法會"},
    "香港交易所": {"en": "Hong Kong Exchanges and Clearing", "zh": "香港交易所", "zh-HK": "香港交易所"},
    "HKEX": {"en": "HKEX", "zh": "香港交易所", "zh-HK": "香港交易所"},
    "律政司": {"en": "Department of Justice", "zh": "律政司", "zh-HK": "律政司"},
    "Department of Justice": {"en": "Department of Justice", "zh": "律政司", "zh-HK": "律政司"},
}

def mock_translate(text, source_lang, target_lang):
    """Mock translation function for demo mode"""
    if text in MOCK_TRANSLATIONS:
        return MOCK_TRANSLATIONS[text].get(target_lang, text)
    return text

# Initialize Whoosh index for glossary (conditional on availability)
GLOSSARY_DIR = "glossary_index"
ix = None

if WHOOSH_AVAILABLE:
    schema = Schema(term=TEXT(stored=True), translation=TEXT(stored=True), source=TEXT(stored=True))
    if not os.path.exists(GLOSSARY_DIR):
        os.mkdir(GLOSSARY_DIR)
        ix = index.create_in(GLOSSARY_DIR, schema)
        print(f"Created new glossary index in {GLOSSARY_DIR}")
    else:
        try:
            ix = index.open_dir(GLOSSARY_DIR)
            print(f"Opened existing glossary index in {GLOSSARY_DIR}")
        except Exception as e:
            print(f"Error opening glossary index, creating new one: {e}")
            import shutil
            shutil.rmtree(GLOSSARY_DIR)
            os.mkdir(GLOSSARY_DIR)
            ix = index.create_in(GLOSSARY_DIR, schema)

# Global variable to track glossary last update time
# FIX: Initialize with date-only format
glossary_last_update = datetime.datetime.now().strftime('%Y-%m-%d')

# History storage
HISTORY_FILE = "translation_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(item):
    history = load_history()
    history.insert(0, item)
    if len(history) > 100:
        history = history[:100]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def detect_language(text):
    """Detect the language of the input text."""
    import re
    cantonese_chars = set('嘅咗喺咁唔喇叻啱靓哋冇睇喥嗰啲乜嘢冚唞噃')
    has_cantonese = bool(cantonese_chars & set(text))
    if has_cantonese:
        return 'yue'
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'

def load_manual_glossary():
    """Load manual glossary from glossary_manual.json and add to index."""
    global glossary_last_update
    if not WHOOSH_AVAILABLE or ix is None:
        return
    
    manual_file = "glossary_manual.json"
    if not os.path.exists(manual_file):
        print(f"Manual glossary file {manual_file} not found, skipping...")
        return
    
    try:
        with open(manual_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        entries = data.get('glossary_entries', [])
        if not entries:
            print("No entries found in manual glossary")
            return
        
        writer = ix.writer()
        added_count = 0
        
        for entry in entries:
            term = entry.get('term', '')
            translation = entry.get('translation', '')
            source = entry.get('source', 'Manual')
            
            if term:
                writer.add_document(
                    term=term,
                    translation=translation,
                    source=source
                )
                added_count += 1
        
        writer.commit()
        glossary_last_update = datetime.datetime.now().strftime('%Y-%m-%d')
        print(f"Loaded {added_count} entries from manual glossary")
        
        # Verify index
        with ix.searcher() as searcher:
            doc_count = searcher.doc_count()
            print(f"Glossary index now contains {doc_count} documents")
            
    except Exception as e:
        print(f"Error loading manual glossary: {e}")
        import traceback
        traceback.print_exc()

# Load manual glossary on startup
load_manual_glossary()

@app.route('/')
def index():
    template_path = os.path.join(app.root_path, 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    response = app.response_class(
        response=html_content,
        status=200,
        mimetype='text/html; charset=utf-8'
    )
    return response

@app.route('/api/translate', methods=['POST'])
def translate_text():
    data = request.json
    text = data.get('text', '')
    source_lang = data.get('source_lang', 'auto')
    target_lang = data.get('target_lang', 'zh')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        if DEMO_MODE:
            translation = mock_translate(text, source_lang, target_lang)
        else:
            prompt = f"""Translate the following text from {source_lang} to {target_lang}.
Keep the meaning accurate and natural:

{text}"""
            translation = call_qwen(prompt)
        
        save_history({
            "text": text,
            "translation": translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return jsonify({
            "result": translation,
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/back-translate', methods=['POST'])
def back_translate():
    data = request.json
    text = data.get('text', '')
    source_lang = data.get('source_lang', 'auto')  # Original source language
    target_lang = data.get('target_lang', 'zh')    # Target language of translation

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # FIX: Back-translation logic
        # We need to translate the translated text BACK to the original source language
        # source_lang is the original language (e.g., 'zh' for Chinese input)
        # text is the translation result (e.g., English translation)
        # We need to translate text back to source_lang
        
        lang_names = {
            'zh': 'Chinese (Simplified)',
            'zh-HK': 'Cantonese (Traditional Chinese)',
            'yue': 'Cantonese (Traditional Chinese)',
            'en': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'fr': 'French',
            'de': 'German',
            'es': 'Spanish',
            'auto': 'the original language'
        }
        
        # The language we want to translate back TO is the original source language
        back_translate_lang = source_lang if source_lang != 'auto' else 'zh'
        back_translate_lang_name = lang_names.get(back_translate_lang, back_translate_lang)
        
        prompt = f"""Task: Back-translation verification.

You are given a TRANSLATED text. Your task is to translate it back to {back_translate_lang_name}.

IMPORTANT RULES:
1. The input text below is a TRANSLATION (not the original)
2. Translate this text back to {back_translate_lang_name}
3. Output ONLY the back-translated text in {back_translate_lang_name}
4. Do NOT show intermediate steps, explanations, or any other text
5. Keep the meaning as close as possible to the input text

Input text (translation):
{text}

Back-translation to {back_translate_lang_name}:"""

        result = call_qwen(prompt)

        return jsonify({
            "result": result,
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/ocr', methods=['POST'])
def ocr_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    filename = file.filename.lower()

    try:
        # Determine MIME type
        mime_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.bmp': 'image/bmp',
            '.gif': 'image/gif', '.tiff': 'image/tiff',
            '.webp': 'image/webp', '.pdf': 'application/pdf'
        }
        ext = os.path.splitext(filename)[1].lower()
        mime_type = mime_map.get(ext, 'image/jpeg')

        # Try pytesseract if available
        if PYTESSERACT_AVAILABLE:
            try:
                if filename.endswith('.pdf'):
                    with pdfplumber.open(file) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() + "\n"
                else:
                    image = Image.open(file)
                    text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                
                if text and text.strip():
                    return jsonify({
                        "text": text.strip(),
                        "success": True
                    })
            except Exception as e:
                print(f"pytesseract failed, falling back to qwen-vl-max: {e}")
        
        # Fallback: use qwen-vl-max
        file.seek(0)
        file_bytes = file.read()
        
        # FIX: Check file size - if too large, compress or reject
        max_size = 5 * 1024 * 1024  # 5MB limit
        if len(file_bytes) > max_size:
            return jsonify({
                "error": f"Image file too large ({len(file_bytes)} bytes). Maximum size is 5MB.",
                "success": False
            }), 400
        
        file_b64 = base64.b64encode(file_bytes).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{file_b64}"

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # FIX: Use correct message format for qwen-vl-max
        data = {
            "model": "qwen-vl-max",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": data_uri},
                            {"type": "text", "text": "请识别图片中的所有文字，只输出文字内容，不要任何解释"}
                        ]
                    }
                ]
            }
        }
        
        print(f"Calling qwen-vl-max OCR API...")
        print(f"Image MIME type: {mime_type}")
        print(f"Image data URI length: {len(data_uri)}")
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        print(f"OCR API response status: {response.status_code}")
        if response.status_code != 200:
            print(f"OCR API error response: {response.text}")
            return jsonify({
                "error": f"OCR API error: {response.status_code} - {response.text}",
                "success": False
            }), 500
        
        result = response.json()
        print(f"OCR API response: {result}")
        
        # FIX: Handle different response formats
        text = None
        if "output" in result:
            if "choices" in result["output"] and len(result["output"]["choices"]) > 0:
                choice = result["output"]["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    text = choice["message"]["content"]
                elif "text" in choice:
                    text = choice["text"]
            elif "text" in result["output"]:
                text = result["output"]["text"]
        
        if text is None:
            print(f"OCR API unexpected response format: {result}")
            return jsonify({"error": "OCR model returned unexpected format", "success": False}), 500

        return jsonify({
            "text": text.strip(),
            "success": True
        })
    except Exception as e:
        print(f"OCR error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded", "success": False}), 400

    file = request.files['file']
    source_lang = request.form.get('source_lang', 'auto')
    target_lang = request.form.get('target_lang', 'zh')

    if not file.filename:
        return jsonify({"error": "No file selected", "success": False}), 400

    try:
        import tempfile

        suffix = os.path.splitext(file.filename)[1] or '.wav'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            transcript = _transcribe_with_qwen(tmp_path, source_lang)

            if transcript:
                result = {"transcript": transcript, "success": True}

                # Auto-translate if target_lang is specified
                if target_lang and target_lang != source_lang and transcript:
                    try:
                        translation = call_qwen(
                            "Translate the following text to " + target_lang + ". Keep the translation natural and accurate:\n\n" + transcript
                        )
                        result["translation"] = translation
                    except Exception as e:
                        print(f"Translation error: {e}")
                        pass

                return jsonify(result)
            else:
                return jsonify({
                    "error": "Audio transcription failed. Please check your QWEN_API_KEY and try again.",
                    "success": False
                }), 503
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        print(f"Transcribe error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500

def _transcribe_with_qwen(file_path, language='auto'):
    """Transcribe audio using DashScope Paraformer API."""
    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions"

        # Build language parameter
        lang_param = None
        if language and language != 'auto':
            lang_map = {
                'zh': 'zh',
                'zh-HK': 'yue',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko',
                'fr': 'fr',
                'de': 'de',
                'es': 'es',
                'ru': 'ru',
            }
            lang_param = lang_map.get(language, language)

        # Determine audio MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac',
            '.ogg': 'audio/ogg',
            '.webm': 'audio/webm',
        }
        mime_type = mime_types.get(ext, 'audio/wav')

        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        # FIX: Check file size
        max_size = 50 * 1024 * 1024  # 50MB limit
        if len(audio_data) > max_size:
            print(f"Audio file too large: {len(audio_data)} bytes")
            return None
        
        files = {
            'file': (os.path.basename(file_path), audio_data, mime_type)
        }
        data = {
            'model': 'paraformer-v2',
        }
        if lang_param:
            data['language'] = lang_param

        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
        }

        print(f"Calling Paraformer API for transcription...")
        print(f"  File: {os.path.basename(file_path)}")
        print(f"  MIME type: {mime_type}")
        print(f"  Language: {lang_param or 'auto'}")
        print(f"  File size: {len(audio_data)} bytes")
        
        response = requests.post(url, headers=headers, files=files, data=data, timeout=120)

        print(f"Paraformer API response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Paraformer API response: {result}")
            if "text" in result:
                text = result["text"]
                return text.strip() if text else None
            elif "output" in result and "text" in result["output"]:
                text = result["output"]["text"]
                return text.strip() if text else None
            else:
                print(f"Paraformer API unexpected response format: {result}")
                return None
        else:
            print(f"Paraformer API error: {response.status_code}")
            print(f"Error response body: {response.text}")
            try:
                error_json = response.json()
                print(f"Error JSON: {error_json}")
            except:
                pass
            return None
    except Exception as e:
        print(f"Paraformer audio transcription error: {e}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/api/glossary', methods=['GET', 'POST'])
def query_glossary():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库搜索功能不可用（whoosh 未安装）", "success": False}), 503

    if request.method == 'GET':
        query = request.args.get('query', '')
    else:
        data = request.json
        query = data.get('query', '') if data else ''

    if not query:
        return jsonify({"results": [], "success": True})

    print(f"Glossary search query: '{query}'")
    results = []
    try:
        with ix.searcher(weighting=scoring.BM25F()) as searcher:
            doc_count = searcher.doc_count()
            print(f"Glossary index contains {doc_count} documents")
            
            qp = QueryParser("term", ix.schema)
            q = qp.parse(query)
            print(f"Parsed query: {q}")
            hits = searcher.search(q, limit=10)
            print(f"Found {len(hits)} hits in term field")

            for hit in hits:
                results.append({
                    "term": hit['term'],
                    "translation": hit['translation'],
                    "source": hit['source']
                })

        # If no results from index, try exact match on translation field
        if not results:
            print("No results in term field, searching translation field...")
            with ix.searcher(weighting=scoring.BM25F()) as searcher:
                qp = QueryParser("translation", ix.schema)
                q = qp.parse(query)
                hits = searcher.search(q, limit=10)
                print(f"Found {len(hits)} hits in translation field")

                for hit in hits:
                    results.append({
                        "term": hit['term'],
                        "translation": hit['translation'],
                        "source": hit['source']
                    })

    except Exception as e:
        print(f"Glossary search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "术语库查询出错", "success": False}), 500

    print(f"Returning {len(results)} results")
    return jsonify({
        "results": results,
        "success": True
    })

# FIX: Add new route to list all glossary terms
@app.route('/api/glossary-list', methods=['GET'])
def glossary_list():
    """Return all glossary terms (limited to first 100)."""
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库功能不可用（whoosh 未安装）", "success": False}), 503

    try:
        results = []
        limit = request.args.get('limit', 100, type=int)
        
        with ix.searcher() as searcher:
            # Get all documents
            from whoosh.query import Every
            q = Every()
            hits = searcher.search(q, limit=limit)
            
            for hit in hits:
                results.append({
                    "term": hit.get('term', ''),
                    "translation": hit.get('translation', ''),
                    "source": hit.get('source', '')
                })
        
        return jsonify({
            "success": True,
            "terms": results,
            "total": len(results)
        })
    except Exception as e:
        print(f"Glossary list error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/glossary-status', methods=['GET'])
def glossary_status():
    """Return the last glossary update time and availability status."""
    global glossary_last_update
    
    doc_count = 0
    if WHOOSH_AVAILABLE and ix is not None:
        try:
            with ix.searcher() as searcher:
                doc_count = searcher.doc_count()
        except:
            pass
    
    # FIX: Ensure date-only format
    if glossary_last_update and 'T' in str(glossary_last_update):
        glossary_last_update = glossary_last_update.split('T')[0]
    
    return jsonify({
        "available": WHOOSH_AVAILABLE and ix is not None,
        "last_update": glossary_last_update,
        "doc_count": doc_count,
        "success": True
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    history = load_history()
    return jsonify({"history": history})

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({"success": True})

@app.route('/api/add-term', methods=['POST'])
def add_term():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "Glossary feature is not available (whoosh not installed)", "success": False}), 503

    data = request.json
    term = data.get('term', '')
    translation = data.get('translation', '')
    source = data.get('source', 'Manual Entry')

    if not term or not translation:
        return jsonify({"error": "Term and translation are required", "success": False}), 400

    try:
        writer = ix.writer()
        writer.add_document(
            term=term,
            translation=translation,
            source=source
        )
        writer.commit()
        
        # FIX: Update last_update time
        global glossary_last_update
        glossary_last_update = datetime.datetime.now().strftime('%Y-%m-%d')
        
        return jsonify({
            "success": True,
            "message": "Term added successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
