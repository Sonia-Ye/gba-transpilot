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

# app.config['JSON_AS_ASCII'] = False already handles UTF-8 for JSON responses

# Proxy configuration for China network - DISABLED for demo
# PROXY_URL = "http://127.0.0.1:7890"
# os.environ['HTTP_PROXY'] = PROXY_URL
# os.environ['HTTPS_PROXY'] = PROXY_URL
# 
# session = requests.Session()
# session.proxies = {
#     'http': PROXY_URL,
#     'https': PROXY_URL
# }

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
    # Common Chinese words
    "美": {"en": "beautiful", "zh": "美", "zh-HK": "美"},
    "beautiful": {"en": "beautiful", "zh": "美丽", "zh-HK": "美麗"},
    "好": {"en": "good", "zh": "好", "zh-HK": "好"},
    "good": {"en": "good", "zh": "好", "zh-HK": "好"},
    "啊": {"en": "ah", "zh": "啊", "zh-HK": "啊"},
    "很": {"en": "very", "zh": "很", "zh-HK": "很"},
    "非常": {"en": "very", "zh": "非常", "zh-HK": "非常"},
    "我": {"en": "I", "zh": "我", "zh-HK": "我"},
    "你": {"en": "you", "zh": "你", "zh-HK": "你"},
    "他": {"en": "he", "zh": "他", "zh-HK": "他"},
    "她": {"en": "she", "zh": "她", "zh-HK": "她"},
    "它": {"en": "it", "zh": "它", "zh-HK": "它"},
    "是": {"en": "is", "zh": "是", "zh-HK": "是"},
    "有": {"en": "have", "zh": "有", "zh-HK": "有"},
    "在": {"en": "in", "zh": "在", "zh-HK": "在"},
    "和": {"en": "and", "zh": "和", "zh-HK": "和"},
    "的": {"en": "'s", "zh": "的", "zh-HK": "的"},
    "了": {"en": "了", "zh": "了", "zh-HK": "了"},
    "呢": {"en": "?", "zh": "呢", "zh-HK": "呢"},
    "吗": {"en": "?", "zh": "吗", "zh-HK": "嗎"},
    "什么": {"en": "what", "zh": "什么", "zh-HK": "什麼"},
    "什么": {"en": "what", "zh": "什么", "zh-HK": "什麼"},
    "哪里": {"en": "where", "zh": "哪里", "zh-HK": "哪裡"},
    "when": {"en": "when", "zh": "什么时候", "zh-HK": "什麼時候"},
    "为什么": {"en": "why", "zh": "为什么", "zh-HK": "為什麼"},
    "how": {"en": "how", "zh": "怎么", "zh-HK": "怎麼"},
    "这": {"en": "this", "zh": "这", "zh-HK": "這"},
    "that": {"en": "that", "zh": "那", "zh-HK": "那"},
    "这里": {"en": "here", "zh": "这里", "zh-HK": "這裡"},
    "there": {"en": "there", "zh": "那里", "zh-HK": "那裡"},
    "时间": {"en": "time", "zh": "时间", "zh-HK": "時間"},
    "time": {"en": "time", "zh": "时间", "zh-HK": "時間"},
    "地点": {"en": "place", "zh": "地点", "zh-HK": "地點"},
    "place": {"en": "place", "zh": "地点", "zh-HK": "地點"},
    "食物": {"en": "food", "zh": "食物", "zh-HK": "食物"},
    "food": {"en": "food", "zh": "食物", "zh-HK": "食物"},
    "水": {"en": "water", "zh": "水", "zh-HK": "水"},
    "water": {"en": "water", "zh": "水", "zh-HK": "水"},
    "钱": {"en": "money", "zh": "钱", "zh-HK": "錢"},
    "money": {"en": "money", "zh": "钱", "zh-HK": "錢"},
    "电话": {"en": "phone", "zh": "电话", "zh-HK": "電話"},
    "phone": {"en": "phone", "zh": "电话", "zh-HK": "電話"},
    "帮助": {"en": "help", "zh": "帮助", "zh-HK": "幫助"},
    "help": {"en": "help", "zh": "帮助", "zh-HK": "幫助"},
    "紧急": {"en": "emergency", "zh": "紧急", "zh-HK": "緊急"},
    "emergency": {"en": "emergency", "zh": "紧急", "zh-HK": "緊急"},
    "医院": {"en": "hospital", "zh": "医院", "zh-HK": "醫院"},
    "hospital": {"en": "hospital", "zh": "医院", "zh-HK": "醫院"},
    "警察": {"en": "police", "zh": "警察", "zh-HK": "警察"},
    "police": {"en": "police", "zh": "警察", "zh-HK": "警察"},
    "消防": {"en": "fire", "zh": "消防", "zh-HK": "消防"},
    "fire": {"en": "fire", "zh": "火", "zh-HK": "火"},
    "银行": {"en": "bank", "zh": "银行", "zh-HK": "銀行"},
    "bank": {"en": "bank", "zh": "银行", "zh-HK": "銀行"},
    "商店": {"en": "shop", "zh": "商店", "zh-HK": "商店"},
    "shop": {"en": "shop", "zh": "商店", "zh-HK": "商店"},
    "购物": {"en": "shopping", "zh": "购物", "zh-HK": "購物"},
    "shopping": {"en": "shopping", "zh": "购物", "zh-HK": "購物"},
    "地图": {"en": "map", "zh": "地图", "zh-HK": "地圖"},
    "map": {"en": "map", "zh": "地图", "zh-HK": "地圖"},
    "方向": {"en": "direction", "zh": "方向", "zh-HK": "方向"},
    "direction": {"en": "direction", "zh": "方向", "zh-HK": "方向"},
    "左边": {"en": "left", "zh": "左边", "zh-HK": "左邊"},
    "left": {"en": "left", "zh": "左边", "zh-HK": "左邊"},
    "右边": {"en": "right", "zh": "右边", "zh-HK": "右邊"},
    "right": {"en": "right", "zh": "右边", "zh-HK": "右邊"},
    "前": {"en": "front", "zh": "前", "zh-HK": "前"},
    "front": {"en": "front", "zh": "前", "zh-HK": "前"},
    "后": {"en": "back", "zh": "后", "zh-HK": "後"},
    "back": {"en": "back", "zh": "后", "zh-HK": "後"},
    "上": {"en": "up", "zh": "上", "zh-HK": "上"},
    "up": {"en": "up", "zh": "上", "zh-HK": "上"},
    "下": {"en": "down", "zh": "下", "zh-HK": "下"},
    "down": {"en": "down", "zh": "下", "zh-HK": "下"},
    # Common phrases
    "香港好美啊": {"en": "Hong Kong is so beautiful!", "zh": "香港好美啊", "zh-HK": "香港好靚啊"},
    "香港好美": {"en": "Hong Kong is beautiful", "zh": "香港好美", "zh-HK": "香港好靚"},
    "我爱香港": {"en": "I love Hong Kong", "zh": "我爱香港", "zh-HK": "我愛香港"},
    "I love Hong Kong": {"en": "I love Hong Kong", "zh": "我爱香港", "zh-HK": "我愛香港"},
    "请问": {"en": "Excuse me", "zh": "请问", "zh-HK": "請問"},
    "Excuse me": {"en": "Excuse me", "zh": "请问", "zh-HK": "請問"},
    "多少钱": {"en": "How much", "zh": "多少钱", "zh-HK": "多少錢"},
    "How much": {"en": "How much", "zh": "多少钱", "zh-HK": "多少錢"},
    "在哪里": {"en": "Where is", "zh": "在哪里", "zh-HK": "在哪裡"},
    "Where is": {"en": "Where is", "zh": "在哪里", "zh-HK": "在哪裡"},
    "我想": {"en": "I want", "zh": "我想", "zh-HK": "我想"},
    "I want": {"en": "I want", "zh": "我想", "zh-HK": "我想"},
    "需要": {"en": "need", "zh": "需要", "zh-HK": "需要"},
    "need": {"en": "need", "zh": "需要", "zh-HK": "需要"},
    "可以": {"en": "can", "zh": "可以", "zh-HK": "可以"},
    "can": {"en": "can", "zh": "可以", "zh-HK": "可以"},
    "不可以": {"en": "cannot", "zh": "不可以", "zh-HK": "不可以"},
    "cannot": {"en": "cannot", "zh": "不可以", "zh-HK": "不可以"},
    "知道": {"en": "know", "zh": "知道", "zh-HK": "知道"},
    "know": {"en": "know", "zh": "知道", "zh-HK": "知道"},
    "不知道": {"en": "don't know", "zh": "不知道", "zh-HK": "不知道"},
    "don't know": {"en": "don't know", "zh": "不知道", "zh-HK": "不知道"}
}

def mock_translate(text, source_lang, target_lang):
    """Mock translation function for demo mode"""
    # Check exact matches first
    if text in MOCK_TRANSLATIONS:
        return MOCK_TRANSLATIONS[text].get(target_lang, text)
    
    # Try to translate word by word (for English)
    words = text.split()
    if len(words) > 1:
        result = []
        for word in words:
            if word in MOCK_TRANSLATIONS:
                result.append(MOCK_TRANSLATIONS[word].get(target_lang, word))
            else:
                if target_lang == 'en':
                    result.append(word + '(en)')
                elif target_lang == 'zh-HK':
                    result.append(word + '(粤)')
                else:
                    result.append(word + '(zh)')
        return ' '.join(result)
    
    # For Chinese characters without spaces
    # Try to translate character by character
    result = []
    for char in text:
        if char in MOCK_TRANSLATIONS:
            result.append(MOCK_TRANSLATIONS[char].get(target_lang, char))
        else:
            result.append(char)
    
    translated = ''.join(result)
    
    # If nothing was translated, add suffix to show it was processed
    if translated == text:
        if target_lang == 'en':
            translated = text + ' (en)'
        elif target_lang == 'zh-HK':
            translated = text + ' (粤)'
        else:
            translated = text + ' (zh)'
    
    return translated

# Initialize Whoosh index for glossary (conditional on availability)
GLOSSARY_DIR = "glossary_index"
ix = None

if WHOOSH_AVAILABLE:
    schema = Schema(term=TEXT(stored=True), translation=TEXT(stored=True), source=TEXT(stored=True))
    if not os.path.exists(GLOSSARY_DIR):
        os.mkdir(GLOSSARY_DIR)
        ix = index.create_in(GLOSSARY_DIR, schema)
    else:
        ix = index.open_dir(GLOSSARY_DIR)

# Global variable to track glossary last update time
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

# Government websites to scrape for glossary
GOVERNMENT_SITES = [
    "https://www.info.gov.hk/gia/general/",
    "https://www.gov.hk/tc/about/govdirectory/",
]

def extract_proper_nouns(text):
    import re
    
    chinese_pattern = r'[\u4e00-\u9fff]{2,4}'
    chinese_matches = re.findall(chinese_pattern, text)
    
    english_pattern = r'\b[A-Z][a-z]+\b'
    english_matches = re.findall(english_pattern, text)
    
    common_words = {'的', '是', '在', '和', '了', '有', '不', '这', '我', '他', '她', '它',
                   'The', 'A', 'An', 'Is', 'Are', 'Was', 'Were', 'Be', 'Been', 'Being',
                   'Have', 'Has', 'Had', 'Do', 'Does', 'Did', 'Will', 'Would', 'Could',
                   'Should', 'May', 'Might', 'Must', 'Can', 'This', 'That', 'These', 'Those'}
    
    chinese_terms = list(set([m for m in chinese_matches if m not in common_words]))
    english_terms = list(set([m for m in english_matches if m not in common_words]))
    
    return chinese_terms, english_terms

def scrape_government_sites():
    """Scrape Hong Kong government bilingual pages to extract Chinese-English term pairs."""
    import re
    global glossary_last_update
    if not WHOOSH_AVAILABLE or ix is None:
        return

    glossary_entries = []

    # Scrape Hong Kong Government News Gazette (bilingual press releases)
    try:
        print("Scraping Hong Kong Government News Gazette...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get("https://www.info.gov.hk/gia/general/", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find links to individual press release pages
        links = soup.find_all('a', href=True)
        press_links = []
        for link in links:
            href = link.get('href', '')
            if '/gia/general/' in href and href.endswith('.htm'):
                if href.startswith('/'):
                    href = 'https://www.info.gov.hk' + href
                press_links.append(href)

        # Deduplicate and limit
        seen_urls = set()
        unique_links = []
        for url in press_links:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_links.append(url)

        # Scrape up to 10 press release pages
        for url in unique_links[:10]:
            try:
                print(f"  Scraping press release: {url}")
                resp = requests.get(url, timeout=20, headers=headers)
                page_soup = BeautifulSoup(resp.text, 'html.parser')

                # Look for bilingual content - HK government pages often have
                # Chinese and English versions with parallel structure
                # Extract text blocks that contain both Chinese and English
                text = page_soup.get_text(separator='\n', strip=True)

                # Try to find Chinese-English pairs from the page structure
                # Many HK gov pages have tables or divs with bilingual content
                tables = page_soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            cell_texts = [c.get_text(strip=True) for c in cells]
                            for i in range(len(cell_texts) - 1):
                                zh_text = cell_texts[i]
                                en_text = cell_texts[i + 1]
                                # Check if one is Chinese and the other is English
                                has_chinese = bool(re.search(r'[\u4e00-\u9fff]', zh_text))
                                has_english = bool(re.search(r'[a-zA-Z]', en_text)) and not bool(re.search(r'[\u4e00-\u9fff]', en_text))
                                if has_chinese and has_english and len(zh_text) >= 2 and len(en_text) >= 2:
                                    glossary_entries.append({
                                        "term": zh_text,
                                        "translation": en_text,
                                        "source": url,
                                        "type": "bilingual"
                                    })
                                # Also try reverse order
                                has_chinese2 = bool(re.search(r'[\u4e00-\u9fff]', en_text))
                                has_english2 = bool(re.search(r'[a-zA-Z]', zh_text)) and not bool(re.search(r'[\u4e00-\u9fff]', zh_text))
                                if has_chinese2 and has_english2 and len(en_text) >= 2 and len(zh_text) >= 2:
                                    glossary_entries.append({
                                        "term": en_text,
                                        "translation": zh_text,
                                        "source": url,
                                        "type": "bilingual"
                                    })

            except Exception as e:
                print(f"  Error scraping press release {url}: {e}")

        print(f"Extracted {len(glossary_entries)} bilingual entries from press releases")

    except Exception as e:
        print(f"Error scraping government news: {e}")

    # Scrape government directory for organization names
    try:
        print("Scraping Hong Kong Government Directory...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get("https://www.gov.hk/tc/about/govdirectory/", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract organization names - look for links with Chinese text
        org_links = soup.find_all('a', href=True)
        for link in org_links:
            text = link.get_text(strip=True)
            # Filter for Chinese organization names (usually 2-10 characters)
            if re.search(r'[\u4e00-\u9fff]{2,10}', text) and len(text) <= 20:
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "gov.hk directory",
                    "type": "organization"
                })

        print(f"Extracted organization entries from directory")

    except Exception as e:
        print(f"Error scraping government directory: {e}")

    # Deduplicate entries
    seen_terms = set()
    unique_entries = []
    for entry in glossary_entries:
        term_key = entry['term']
        if term_key not in seen_terms:
            seen_terms.add(term_key)
            unique_entries.append(entry)

    # Write to whoosh index
    try:
        writer = ix.writer()
        for entry in unique_entries:
            writer.add_document(
                term=entry['term'],
                translation=entry['translation'],
                source=entry['source']
            )
        writer.commit()
        glossary_last_update = datetime.datetime.now().isoformat()
        print(f"Updated glossary with {len(unique_entries)} unique entries")
    except Exception as e:
        print(f"Error updating glossary index: {e}")

def translate_term(term, target_lang='en'):
    """Translate a single term using Qwen API."""
    try:
        lang_map = {
            'en': 'English',
            'zh': 'Chinese',
            'zh-HK': 'Cantonese'
        }
        prompt = f"Translate this term to {lang_map.get(target_lang, 'English')}: {term}"
        return call_qwen(prompt)
    except:
        return term


def detect_language(text):
    """Detect the language of the input text.
    Returns 'zh' for Chinese, 'yue' for Cantonese, 'en' for English/other.
    """
    import re
    # Cantonese characteristic characters
    cantonese_chars = set('嘅咗喺咁唔喇叻啱靓哋冇睇喥嗰啲乜嘢冚唞噃')
    has_cantonese = bool(cantonese_chars & set(text))
    if has_cantonese:
        return 'yue'
    # Chinese characters (CJK Unified Ideographs)
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'
    return 'en'

def clean_text(text):
    import re
    
    # 规范化各种换行符
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 首先尝试识别自然段落（双换行或空行分隔）
    paragraph_delimiters = r'\n\s*\n|\n{2,}'
    paragraphs = re.split(paragraph_delimiters, text)
    
    cleaned_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 对每个段落，检查是否包含"断行"
        lines = para.split('\n')
        
        if len(lines) == 1:
            # 段落只有一行，直接去除多余空格
            cleaned_paragraphs.append(re.sub(r'[ \t]+', ' ', para).strip())
            continue
        
        # 处理多行段落
        processed_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if i < len(lines) - 1:
                # 检查是否是断行（不是句子结束）
                next_line = lines[i + 1].strip() if lines[i + 1] else ''
                
                # 判断规则：
                # 1. 当前行不以常见句子结束符结尾
                # 2. 下一行以小写字母开头（或者很短，像是单词被折行）
                # 3. 或者当前行以连字符结尾
                ends_with_sentence_end = re.search(r'[。！？.!?…\-–—)）]$', line) is not None
                next_starts_with_lower = re.search(r'^[a-z]', next_line) is not None
                line_ends_with_hyphen = re.search(r'[\-–—]$', line) is not None
                
                if (not ends_with_sentence_end and next_starts_with_lower) or line_ends_with_hyphen:
                    # 这是断行，需要连接，但要去除当前行末尾的连字符
                    line = re.sub(r'[\-–—]$', '', line).rstrip()
                    processed_lines.append(line + ' ')  # 添加空格连接
                else:
                    # 这是有意换行或者是句子边界
                    processed_lines.append(line)
            else:
                # 最后一行
                processed_lines.append(line)
        
        # 合并处理后的行
        result = ''.join(processed_lines)
        
        # 清理行内多余空格（只保留句子间必要的单空格）
        result = re.sub(r'  +', ' ', result).strip()
        
        if result:
            cleaned_paragraphs.append(result)
    
    # 用双换行连接段落，保留段落结构
    return '\n\n'.join(cleaned_paragraphs)

def remove_line_breaks(text):
    import re
    
    # 规范化换行符
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 首先尝试识别自然段落（双换行或空行分隔）
    paragraph_delimiters = r'\n\s*\n|\n{2,}'
    paragraphs = re.split(paragraph_delimiters, text)
    
    cleaned_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 对每个段落，检查是否包含"断行"
        lines = para.split('\n')
        
        if len(lines) == 1:
            # 段落只有一行，直接去除多余空格
            cleaned_paragraphs.append(re.sub(r'[ \t]+', ' ', para).strip())
            continue
        
        # 处理多行段落
        processed_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if i < len(lines) - 1:
                # 检查是否是断行
                next_line = lines[i + 1].strip() if lines[i + 1] else ''
                ends_with_sentence_end = re.search(r'[。！？.!?…\-–—)）]$', line) is not None
                next_starts_with_lower = re.search(r'^[a-z]', next_line) is not None
                line_ends_with_hyphen = re.search(r'[\-–—]$', line) is not None
                
                if (not ends_with_sentence_end and next_starts_with_lower) or line_ends_with_hyphen:
                    line = re.sub(r'[\-–—]$', '', line).rstrip()
                    processed_lines.append(line + ' ')  # 添加空格连接
                else:
                    processed_lines.append(line)
            else:
                processed_lines.append(line)
        
        result = ''.join(processed_lines)
        result = re.sub(r'  +', ' ', result).strip()
        
        if result:
            cleaned_paragraphs.append(result)
    
    # 用空格连接而不是\n\n（去除所有段落分隔）
    return ' '.join(cleaned_paragraphs)

# Schedule daily update (conditional on availability)
def scheduled_update():
    while True:
        schedule.run_pending()
        time.sleep(60)

if schedule is not None:
    schedule.every().day.at("02:00").do(scrape_government_sites)
    Thread(target=scheduled_update, daemon=True).start()

@app.route('/')
def index():
    # Read the HTML file directly with UTF-8 encoding
    template_path = os.path.join(app.root_path, 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Return with proper UTF-8 headers
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
        # DEMO MODE: Use mock translation
        if DEMO_MODE:
            translation = mock_translate(text, source_lang, target_lang)
        else:
            prompt = f"""Translate the following text from {source_lang} to {target_lang}.
            Keep the meaning accurate and natural:

            {text}"""

            translation = call_qwen(prompt)
        
        # Save to history
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

@app.route('/api/ocr', methods=['POST'])
def ocr_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    filename = file.filename.lower()

    try:
        # Always use qwen-vl-max for OCR (tesseract not available on Render)
        if False and PYTESSERACT_AVAILABLE:
            # Skip tesseract - use qwen-vl-max instead
            pass
        else:
            # Fallback: use qwen-vl-max multimodal model for OCR
            file.seek(0)
            file_bytes = file.read()

            # Determine MIME type
            mime_map = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.bmp': 'image/bmp',
                '.gif': 'image/gif', '.tiff': 'image/tiff',
                '.webp': 'image/webp', '.pdf': 'application/pdf'
            }
            ext = os.path.splitext(filename)[1].lower()
            mime_type = mime_map.get(ext, 'image/jpeg')

            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            data_uri = f"data:{mime_type};base64,{file_b64}"

            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            headers = {
                "Authorization": f"Bearer {QWEN_API_KEY}",
                "Content-Type": "application/json"
            }
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
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            text = None
            if "output" in result and "choices" in result["output"]:
                text = result["output"]["choices"][0]["message"]["content"]
            elif "output" in result and "text" in result["output"]:
                text = result["output"]["text"]
            if isinstance(text, list):
                text = '\n'.join(str(item) for item in text)
            if not text or not str(text).strip():
                return jsonify({"error": "OCR model returned empty result", "success": False}), 500

        return jsonify({
            "text": str(text).strip(),
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/back-translate', methods=['POST'])
def back_translate():
    data = request.json
    text = data.get('text', '')
    source_lang = data.get('source_lang', 'zh')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        lang_names = {
            'zh': '简体中文', 'en': 'English',
            'zh-HK': '繁體中文（粤語）', 'yue': '繁體中文（粤語）',
        }
        target_lang_name = lang_names.get(source_lang, source_lang)
        prompt = f"""请将以下文本翻译为英文，然后再将英文翻译回{target_lang_name}。
只输出最终回译结果（必须是{target_lang_name}），不要输出任何中间步骤、解释或英文翻译。

输入文本：
{text}

回译结果（{target_lang_name}）："""
        result = call_qwen(prompt)
        return jsonify({"result": result, "success": True})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/dictionary', methods=['GET', 'POST'])
def dictionary_query():
    if request.method == 'GET':
        word = request.args.get('word', '')
    else:
        data = request.json
        word = data.get('word', '') if data else ''

    if not word:
        return jsonify({"error": "No word provided"}), 400

    try:
        # DEMO MODE: Use mock dictionary
        if DEMO_MODE:
            mock_definitions = {
                "Hong Kong": {
                    "en": "Hong Kong is a special administrative region of China, known for its vibrant economy, skyline, and cultural diversity.",
                    "zh": "香港是中国的特别行政区，以其充满活力的经济、天际线和文化多样性而闻名。"
                },
                "China": {
                    "en": "China is a country in East Asia, the world's most populous country, known for its long history and rapid development.",
                    "zh": "中国是东亚的一个国家，是世界上人口最多的国家，以其悠久的历史和快速发展而闻名。"
                },
                "tourism": {
                    "en": "The practice of traveling for pleasure; the business of providing services for tourists.",
                    "zh": "为娱乐而旅行的行为；为游客提供服务的行业。"
                },
                "translation": {
                    "en": "The process of converting text from one language to another while preserving meaning.",
                    "zh": "在保持意思的同时将文本从一种语言转换为另一种语言的过程。"
                }
            }
            definition = mock_definitions.get(word, {"en": f"Definition for '{word}'", "zh": f"'{word}'的定义"})
            return jsonify({
                "definition": f"English: {definition['en']}\n\nChinese: {definition['zh']}",
                "success": True
            })
        else:
            # Try OneLook Dictionary API first
            result = _query_onelook(word)
            if result:
                return jsonify({
                    "definition": result,
                    "success": True
                })

            # Fallback to Qwen API
            prompt = f"""Provide a comprehensive dictionary entry for the word/phrase '{word}' including:
            1. Part of speech
            2. Definitions
            3. Example sentences
            4. Synonyms and antonyms
            5. Related terms

            Output in both English and Chinese."""

            definition = call_qwen(prompt)

            return jsonify({
                "definition": definition,
                "success": True
            })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


def _query_onelook(word):
    """Query OneLook Dictionary API and return formatted definition with Chinese translation."""
    try:
        api_url = f"https://api.onelook.com/definitions?v=4&term={requests.utils.quote(word)}&format=json"
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        entries = []

        # Collect definitions grouped by part of speech
        if 'definitions' in data and data['definitions']:
            pos_defs = {}
            for defn in data['definitions']:
                pos = defn.get('part_of_speech', '')
                def_text = defn.get('definition', '')
                example = defn.get('example', '')
                if not def_text:
                    continue
                if pos not in pos_defs:
                    pos_defs[pos] = []
                entry = def_text
                if example:
                    entry += f"\n  Example: {example}"
                pos_defs[pos].append(entry)

            # Build English definition text
            en_parts = []
            for pos, defs in pos_defs.items():
                pos_label = f"[{pos}]" if pos else ""
                defs_text = "\n  ".join(f"{i+1}. {d}" for i, d in enumerate(defs))
                en_parts.append(f"{pos_label}\n  {defs_text}")
            en_definition = "\n\n".join(en_parts)

            # Return English definition only (no translation)
            result_parts = [f"Word: {word}"]
            result_parts.append(f"\n{en_definition}")

            return "\n".join(result_parts)

        return None
    except Exception:
        return None

@app.route('/api/rewrite', methods=['POST'])
def rewrite_text():
    data = request.json
    text = data.get('text', '')
    mode = data.get('mode', 'paraphrase')  # paraphrase, pre-edit, polish
    style = data.get('style', 'standard')  # standard, formal, casual, academic, business

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # DEMO MODE: Use mock rewrite
        if DEMO_MODE:
            mode_descriptions = {
                'paraphrase': '（意译版）',
                'pre-edit': '（预编辑版）',
                'polish': '（润色版）'
            }
            style_descriptions = {
                'standard': '[标准风格]',
                'formal': '[正式风格]',
                'casual': '[随意风格]',
                'academic': '[学术风格]',
                'business': '[商务风格]'
            }
            result = f"{style_descriptions.get(style, '[标准风格]')}{text}{mode_descriptions.get(mode, '')}"

            return jsonify({
                "result": result,
                "success": True
            })
        else:
            # Detect language and use appropriate prompt directly
            detected_lang = detect_language(text)

            lang_prompts = {
                'zh': {
                    'paraphrase': '请用中文改写以下文本，保持原意不变：',
                    'pre-edit': '请用中文对以下文本进行预编辑，使其更清晰、更易于翻译，保持原意不变：',
                    'polish': '请用中文润色以下文本，提升其质量和专业性，保持原意不变：'
                },
                'yue': {
                    'paraphrase': '請用粵語改寫以下文本，保持原意不變：',
                    'pre-edit': '請用粵語對以下文本進行預編輯，使其更清晰、更易於翻譯，保持原意不變：',
                    'polish': '請用粵語潤色以下文本，提升其質量和專業性，保持原意不變：'
                },
                'en': {
                    'paraphrase': 'Please rewrite the following text in English while preserving its original meaning:',
                    'pre-edit': 'Please pre-edit the following text in English to make it clearer and easier to translate, while preserving its original meaning:',
                    'polish': 'Please polish the following text in English to improve its quality and professionalism, while preserving its original meaning:'
                }
            }

            style_descriptions = {
                'standard': '标准风格',
                'formal': '正式专业风格',
                'casual': '随意自然风格',
                'academic': '学术风格',
                'business': '商务风格'
            }

            lang_mode = lang_prompts.get(detected_lang, lang_prompts['en'])
            base_prompt = lang_mode.get(mode, lang_mode['paraphrase'])

            if detected_lang in ('zh', 'yue'):
                style_text = f"请使用{style_descriptions.get(style, style_descriptions['standard'])}。"
            else:
                style_map_en = {
                    'standard': 'standard style',
                    'formal': 'formal and professional style',
                    'casual': 'casual and natural style',
                    'academic': 'academic style',
                    'business': 'business style'
                }
                style_text = f"Please use a {style_map_en.get(style, style_map_en['standard'])}."

            prompt = f"{base_prompt}\n{style_text}\n\n{text}"
            result = call_qwen(prompt)
        return jsonify({
            "result": result,
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route('/api/polish', methods=['POST'])
def polish_text():
    data = request.json
    text = data.get('text', '')
    style = data.get('style', 'general')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        detected_lang = detect_language(text)

        if detected_lang in ('zh', 'yue'):
            style_descriptions = {
                'general': '标准自然风格',
                'standard': '标准自然风格',
                'formal': '正式专业风格',
                'casual': '随意自然风格',
                'academic': '学术风格',
                'business': '商务风格'
            }
            style_desc = style_descriptions.get(style, style_descriptions['general'])
            if detected_lang == 'yue':
                prompt = f"請用粵語以{style_desc}潤色以下文本，提升其質量、流暢性和專業性，保持原意不變。只輸出潤色後的文本，不要輸出風格說明、格式提示或任何其他內容。\n\n" + text
            else:
                prompt = f"请用中文以{style_desc}润色以下文本，提升其质量、流畅性和专业性，保持原意不变。只输出润色后的文本，不要输出风格说明、格式提示或任何其他内容。\n\n" + text
        else:
            style_map_en = {
                'general': 'natural and standard style',
                'standard': 'natural and standard style',
                'formal': 'formal and professional style',
                'casual': 'casual and natural style',
                'academic': 'academic style',
                'business': 'business style'
            }
            style_desc = style_map_en.get(style, style_map_en['general'])
            prompt = f"Polish and improve the following text using a {style_desc}. Enhance quality, fluency, and professionalism while preserving the original meaning. Output only the polished text without any style descriptions, formatting notes, or additional commentary.\n\n" + text

        result = call_qwen(prompt)
        return jsonify({
            "result": result,
            "success": True
        })
    except Exception as e:
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
                    except:
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
        return jsonify({"error": str(e), "success": False}), 500


def _transcribe_with_qwen(file_path, language='auto'):
    """Transcribe audio using DashScope Paraformer API (OpenAI-compatible)."""
    try:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions"

        # Build language parameter
        lang_param = "zh"  # default
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

        with open(file_path, 'rb') as audio_file:
            files = {
                'file': (os.path.basename(file_path), audio_file)
            }
            data = {
                'model': 'paraformer-v2',
            }
            if language and language != 'auto':
                data['language'] = lang_param
            headers = {
                "Authorization": f"Bearer {QWEN_API_KEY}",
            }

            print(f"Calling Paraformer API for transcription (language={lang_param})...")
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)

        if response.status_code == 200:
            result = response.json()
            print(f"Paraformer API response: {result}")
            # Response format: {"output": {"text": "..."}}
            if "output" in result and "text" in result["output"]:
                text = result["output"]["text"]
                return text.strip() if text else None
            # Alternative format
            elif "text" in result:
                text = result["text"]
                return text.strip() if text else None
            else:
                print(f"Paraformer API unexpected response format: {result}")
                return None
        else:
            print(f"Paraformer API error: {response.status_code} - {response.text}")
            print(f"Request URL: {url}")
            print(f"File exists: {os.path.exists(file_path)}")
            print(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 0}")
            return None
    except Exception as e:
        print(f"Paraformer audio transcription error: {e}")
        return None


@app.route('/api/glossary', methods=['GET', 'POST'])
def query_glossary():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库搜索功能不可用（whoosh 未安装）", "success": False}), 503

    if request.method == 'GET':
        query = request.args.get('query', '')
        target_lang = request.args.get('lang', 'en')
    else:
        data = request.json
        query = data.get('query', '') if data else ''
        target_lang = data.get('target_lang', 'en') if data else 'en'

    if not query:
        return jsonify({"results": [], "success": True})

    results = []
    try:
        with ix.searcher(weighting=scoring.BM25F()) as searcher:
            qp = QueryParser("term", ix.schema)
            q = qp.parse(query)
            hits = searcher.search(q, limit=10)

            for hit in hits:
                results.append({
                    "term": hit['term'],
                    "translation": hit['translation'],
                    "source": hit['source']
                })

        # If no results from index, try exact match on translation field
        if not results:
            with ix.searcher(weighting=scoring.BM25F()) as searcher:
                qp = QueryParser("translation", ix.schema)
                q = qp.parse(query)
                hits = searcher.search(q, limit=10)

                for hit in hits:
                    results.append({
                        "term": hit['term'],
                        "translation": hit['translation'],
                        "source": hit['source']
                    })

    except Exception as e:
        print(f"Glossary search error: {e}")
        return jsonify({"error": "术语库查询出错", "success": False}), 500

    return jsonify({
        "results": results,
        "success": True
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    history = load_history()
    return jsonify({"history": history})

@app.route('/api/save-history', methods=['POST'])
def save_history_api():
    data = request.json
    save_history(data)
    return jsonify({"success": True})

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({"success": True})

@app.route('/api/update-glossary', methods=['POST'])
def update_glossary():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库功能不可用（whoosh 未安装）", "success": False}), 503

    try:
        # Run scraping in background thread to avoid request timeout
        thread = Thread(target=scrape_government_sites, daemon=True)
        thread.start()
        return jsonify({
            "success": True,
            "message": "术语库更新已在后台启动，可能需要几分钟时间。"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.after_request
def after_request(response):
    """Add CORS headers to all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

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
        return jsonify({
            "success": True,
            "message": "Term added successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/list-terms', methods=['GET'])
def list_terms():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "Glossary feature is not available (whoosh not installed)", "success": False}), 503

    try:
        results = []
        with ix.searcher() as searcher:
            reader = searcher.reader()
            for doc_id in range(reader.doc_count_all()):
                doc = reader.stored_fields(doc_id)
                results.append({
                    "term": doc.get('term', ''),
                    "translation": doc.get('translation', ''),
                    "source": doc.get('source', '')
                })
        return jsonify({
            "success": True,
            "terms": results
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/clean-text', methods=['POST'])
def clean_text_api():
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        cleaned = clean_text(text)
        return jsonify({
            "result": cleaned,
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/remove-line-breaks', methods=['POST'])
def remove_line_breaks_api():
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        result = remove_line_breaks(text)
        return jsonify({
            "result": result,
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500



# Load manual glossary on startup
def load_manual_glossary():
    global glossary_last_update
    if not WHOOSH_AVAILABLE or ix is None:
        return
    glossary_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glossary_manual.json')
    if not os.path.exists(glossary_file):
        print("No glossary_manual.json found")
        return
    try:
        with open(glossary_file, 'r', encoding='utf-8') as f:
            terms = json.load(f)
        count = 0
        writer = ix.writer()
        for term_data in terms:
            term = term_data.get('term', '')
            translation = term_data.get('translation', '')
            source = term_data.get('source', 'Manual Glossary')
            if term and translation:
                writer.update_document(term=term, translation=translation, source=source)
                count += 1
        writer.commit()
        glossary_last_update = datetime.datetime.now().strftime('%Y-%m-%d')
        print(f"Loaded {count} manual glossary terms")
    except Exception as e:
        print(f"Error loading manual glossary: {e}")

load_manual_glossary()  # Load manual glossary on startup


@app.route('/api/glossary/download', methods=['GET'])
def download_glossary():
    """Download all glossary terms as JSON file."""
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库功能不可用", "success": False}), 503
    
    try:
        terms = []
        with ix.searcher() as searcher:
            # Get all documents
            for doc in searcher.all_stored_fields():
                terms.append({
                    "term": doc.get('term', ''),
                    "translation": doc.get('translation', ''),
                    "source": doc.get('source', '')
                })
        
        # Create JSON response with download header
        response = jsonify({
            "terms": terms,
            "count": len(terms),
            "success": True
        })
        response.headers['Content-Disposition'] = 'attachment; filename=glossary_export.json'
        return response
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route('/api/glossary/upload', methods=['POST'])
def upload_glossary():
    """Upload custom glossary terms from JSON file."""
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "术语库功能不可用（whoosh 未安装）", "success": False}), 503
    
    if 'file' not in request.files:
        return jsonify({"error": "没有上传文件", "success": False}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({"error": "文件名为空", "success": False}), 400
    
    try:
        # Read JSON file
        file_content = file.read().decode('utf-8')
        data = json.loads(file_content)
        
        # Support both { "terms": [...] } and direct array format
        if isinstance(data, dict) and 'terms' in data:
            terms = data['terms']
        elif isinstance(data, list):
            terms = data
        else:
            return jsonify({"error": "无效的JSON格式，应为数组或{terms: [...]}", "success": False}), 400
        
        # Add terms to index
        count = 0
        writer = ix.writer()
        for term_data in terms:
            if isinstance(term_data, dict):
                term = term_data.get('term', '')
                translation = term_data.get('translation', '')
                source = term_data.get('source', 'User Upload')
            else:
                continue
            
            if term and translation:
                writer.update_document(term=term, translation=translation, source=source)
                count += 1
        
        writer.commit()
        
        # Update last update time
        global glossary_last_update
        glossary_last_update = datetime.datetime.now().strftime('%Y-%m-%d')
        
        return jsonify({
            "success": True,
            "message": f"成功导入 {count} 条术语",
            "count": count
        })
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON解析错误: {str(e)}", "success": False}), 400
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route('/api/glossary-status', methods=['GET'])
def glossary_status():
    global glossary_last_update
    doc_count = 0
    if WHOOSH_AVAILABLE and ix is not None:
        try:
            with ix.searcher() as searcher:
                doc_count = searcher.doc_count()
        except:
            pass
    if glossary_last_update and 'T' in str(glossary_last_update):
        glossary_last_update = str(glossary_last_update).split('T')[0]
    return jsonify({
        "available": WHOOSH_AVAILABLE and ix is not None,
        "last_update": glossary_last_update,
        "doc_count": doc_count,
        "success": True
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
