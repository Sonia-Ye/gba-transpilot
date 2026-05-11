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
    "https://www.gov.hk/",
    "https://www.doj.gov.hk/",
    "https://www.elegislation.gov.hk/",
    "https://www.hkex.com.hk/",
    "https://www.gov.cn/",
    "https://www.state.gov.cn/",
    "https://www.court.gov.cn/",
    "https://www.npc.gov.cn/"
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
    if not WHOOSH_AVAILABLE or ix is None:
        return
    
    glossary_entries = []
    
    for site in GOVERNMENT_SITES:
        try:
            print(f"Scraping {site}...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(site, timeout=30, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            text = soup.get_text(separator=' ', strip=True)
            
            chinese_terms, english_terms = extract_proper_nouns(text)
            
            chinese_terms = chinese_terms[:50]
            english_terms = english_terms[:50]
            
            for term in chinese_terms:
                if len(term) >= 2:
                    translation = translate_term(term, 'en')
                    glossary_entries.append({
                        "term": term,
                        "translation": translation,
                        "source": site,
                        "type": "proper_noun"
                    })
            
            for term in english_terms:
                if len(term) >= 3:
                    translation = translate_term(term, 'zh')
                    glossary_entries.append({
                        "term": term,
                        "translation": translation,
                        "source": site,
                        "type": "proper_noun"
                    })
            
            print(f"Extracted {len(chinese_terms)} Chinese terms and {len(english_terms)} English terms from {site}")
            
        except Exception as e:
            print(f"Error scraping {site}: {e}")
    
    seen_terms = set()
    unique_entries = []
    for entry in glossary_entries:
        term_key = entry['term'] + entry['source']
        if term_key not in seen_terms:
            seen_terms.add(term_key)
            unique_entries.append(entry)
    
    try:
        writer = ix.writer()
        for entry in unique_entries:
            writer.add_document(
                term=entry['term'], 
                translation=entry['translation'], 
                source=entry['source']
            )
        writer.commit()
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
                    line = re.sub(r'[\-–—]$', '', line)
                    processed_lines.append(line)
                else:
                    # 这是有意换行或者是句子边界
                    processed_lines.append(line)
            else:
                # 最后一行
                processed_lines.append(line)
        
        # 合并处理后的行（直接连接，不额外添加空格）
        result = ''.join(processed_lines)
        
        # 最后一次清理多余空格
        result = re.sub(r'[ \t]+', ' ', result).strip()
        
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
                    line = re.sub(r'[\-–—]$', '', line)
                    processed_lines.append(line)
                else:
                    processed_lines.append(line)
            else:
                processed_lines.append(line)
        
        result = ''.join(processed_lines)
        result = re.sub(r'[ \t]+', ' ', result).strip()
        
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
    if not PYTESSERACT_AVAILABLE:
        return jsonify({"error": "OCR feature is not available (pytesseract not installed)", "success": False}), 503

    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    filename = file.filename.lower()

    try:
        if filename.endswith('.pdf'):
            with pdfplumber.open(file) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
        else:
            # Image file
            image = Image.open(file)
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')

        return jsonify({
            "text": text.strip(),
            "success": True
        })
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/back-translate', methods=['POST'])
def back_translate():
    data = request.json
    text = data.get('text', '')
    target_lang = data.get('target_lang', 'zh')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        prompt = f"""First translate this text to English, then translate it back to {target_lang}.
        Show both translations:

        Original: {text}"""

        result = call_qwen(prompt)
        
        return jsonify({
            "result": result,
            "success": True
        })
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
            mode_prompts = {
                'paraphrase': "Rewrite the following text while keeping the original meaning. IMPORTANT: You MUST output in the SAME LANGUAGE as the input. If the input is in Chinese, output in Chinese. If the input is in English, output in English. Do not change the language.",
                'pre-edit': "Pre-edit this text to make it clearer and easier to translate. IMPORTANT: You MUST output in the SAME LANGUAGE as the input. If the input is in Chinese, output in Chinese. If the input is in English, output in English. Do not change the language.",
                'polish': "Polish and improve the following text for better quality and professionalism. IMPORTANT: You MUST output in the SAME LANGUAGE as the input. If the input is in Chinese, output in Chinese. If the input is in English, output in English. Do not change the language."
            }

            style_descriptions = {
                'standard': 'standard style',
                'formal': 'formal and professional style',
                'casual': 'casual and conversational style',
                'academic': 'academic and scholarly style',
                'business': 'business and corporate style'
            }

            style_text = f"Use {style_descriptions.get(style, style_descriptions['standard'])}."
            prompt = f"{mode_prompts.get(mode, mode_prompts['paraphrase'])} {style_text}\n\n{text}"
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
        style_descriptions = {
            'general': 'standard and natural style',
            'standard': 'standard and natural style',
            'formal': 'formal and professional style',
            'casual': 'casual and conversational style',
            'academic': 'academic and scholarly style',
            'business': 'business and corporate style'
        }

        style_text = "Use " + style_descriptions.get(style, style_descriptions['general']) + "."
        prompt = "Polish and improve the following text for better quality, fluency, and professionalism. " + style_text + "\nIMPORTANT: You MUST output in the SAME LANGUAGE as the input. If the input is in Chinese, output in Chinese. If the input is in English, output in English. Do not change the language.\n\n" + text

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
    """Transcribe audio using Qwen qwen-audio-turbo model."""
    try:
        # Read audio file and encode to base64
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')

        # Determine audio format from file extension
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        if not ext:
            ext = 'wav'

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        headers = {
            "Authorization": "Bearer " + QWEN_API_KEY,
            "Content-Type": "application/json"
        }

        # Build language instruction
        lang_instruction = ""
        if language and language != 'auto':
            lang_map = {
                'zh': '中文',
                'en': 'English',
                'ja': '日本語',
                'ko': '한국어',
                'fr': 'Français',
                'de': 'Deutsch',
                'es': 'Español',
                'ru': 'Русский',
                'ar': 'العربية',
                'pt': 'Português',
                'it': 'Italiano',
            }
            lang_name = lang_map.get(language, language)
            lang_instruction = f" Please transcribe in {lang_name}."

        data = {
            "model": "qwen-audio-turbo",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"audio": f"data:audio/{ext};base64,{audio_base64}"},
                            {"text": f"Transcribe the following audio.{lang_instruction} Output only the transcribed text without any additional explanation or formatting."}
                        ]
                    }
                ]
            }
        }

        response = requests.post(url, headers=headers, json=data, timeout=120)

        if response.status_code == 200:
            result = response.json()
            # Extract text from qwen-audio-turbo response
            if "output" in result and "choices" in result["output"]:
                text = result["output"]["choices"][0]["message"]["content"]
                return text.strip() if text else None
            elif "output" in result and "text" in result["output"]:
                text = result["output"]["text"]
                return text.strip() if text else None
            else:
                print(f"Qwen Audio API unexpected response: {result}")
                return None
        else:
            print(f"Qwen Audio API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Qwen audio transcription error: {e}")
        return None


@app.route('/api/glossary', methods=['GET', 'POST'])
def query_glossary():
    if not WHOOSH_AVAILABLE or ix is None:
        return jsonify({"error": "Glossary search is not available (whoosh not installed)", "success": False}), 503

    if request.method == 'GET':
        query = request.args.get('query', '')
        target_lang = request.args.get('lang', 'en')
    else:
        data = request.json
        query = data.get('query', '') if data else ''
        target_lang = data.get('target_lang', 'en') if data else 'en'

    if not query:
        return jsonify({"result": [], "success": True})

    results = []
    try:
        # First search in local index
        with ix.searcher(weighting=scoring.BM25F()) as searcher:
            qp = QueryParser("term", ix.schema)
            q = qp.parse(query)
            hits = searcher.search(q, limit=5)

            for hit in hits:
                translated = translate_term(hit['term'], target_lang)
                results.append({
                    "term": hit['term'],
                    "translation": translated,
                    "source": hit['source']
                })

        # Also translate the query term directly for more results
        if len(results) < 10:
            translated = translate_term(query, target_lang)
            if translated != query:
                results.append({
                    "term": query,
                    "translation": translated,
                    "source": "AI Translation"
                })
    except Exception as e:
        print(f"Glossary search error: {e}")
        # Fallback: direct translation
        try:
            translated = translate_term(query, target_lang)
            results.append({
                "term": query,
                "translation": translated,
                "source": "AI Translation"
            })
        except:
            pass

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
        return jsonify({"error": "Glossary feature is not available (whoosh not installed)", "success": False}), 503

    try:
        scrape_government_sites()
        return jsonify({
            "success": True,
            "message": "Glossary updated successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

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

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
