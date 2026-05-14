"""
本地术语库抓取脚本
运行方式：python scrape_glossary_local.py
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os

def scrape_government_sites_local():
    """Scrape government websites for glossary terms."""
    glossary_entries = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 1. GovHK main site
    print("Scraping GovHK main site...")
    try:
        response = requests.get("https://www.gov.hk/sc/residents/", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            if text and 2 <= len(text) <= 50 and re.search(r'[\u4e00-\u9fff]', text):
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "gov.hk/residents"
                })
        print(f"  Found {len(glossary_entries)} entries")
    except Exception as e:
        print(f"  Error: {e}")

    # 2. HKEX
    print("Scraping HKEX...")
    try:
        response = requests.get("https://www.hkex.com.hk/?sc_lang=zh-HK", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        count = 0
        for elem in soup.find_all(['a', 'h2', 'h3', 'span']):
            text = elem.get_text(strip=True)
            if text and 2 <= len(text) <= 30 and re.search(r'[\u4e00-\u9fff]', text):
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "hkex.com.hk"
                })
                count += 1
        print(f"  Found {count} entries")
    except Exception as e:
        print(f"  Error: {e}")

    # 3. DOJ
    print("Scraping DOJ...")
    try:
        response = requests.get("https://www.doj.gov.hk/sc/index.html", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        count = 0
        for elem in soup.find_all(['a', 'h2', 'h3']):
            text = elem.get_text(strip=True)
            if text and 2 <= len(text) <= 30 and re.search(r'[\u4e00-\u9fff]', text):
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "doj.gov.hk"
                })
                count += 1
        print(f"  Found {count} entries")
    except Exception as e:
        print(f"  Error: {e}")

    # 4. ImmD
    print("Scraping ImmD...")
    try:
        response = requests.get("https://www.immd.gov.hk/hks/services/chinese.html", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        count = 0
        for elem in soup.find_all(['a', 'h2', 'h3']):
            text = elem.get_text(strip=True)
            if text and 2 <= len(text) <= 30 and re.search(r'[\u4e00-\u9fff]', text):
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "immd.gov.hk"
                })
                count += 1
        print(f"  Found {count} entries")
    except Exception as e:
        print(f"  Error: {e}")

    # 5. news.gov.hk
    print("Scraping news.gov.hk...")
    try:
        response = requests.get("https://www.news.gov.hk/sc/categories/government/html", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        count = 0
        for elem in soup.find_all(['h3', 'a', 'span']):
            text = elem.get_text(strip=True)
            if text and 5 <= len(text) <= 50 and re.search(r'[\u4e00-\u9fff]', text):
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "news.gov.hk"
                })
                count += 1
        print(f"  Found {count} entries")
    except Exception as e:
        print(f"  Error: {e}")

    # 6. Government Directory
    print("Scraping Government Directory...")
    try:
        response = requests.get("https://www.gov.hk/tc/about/govdirectory/", timeout=30, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        count = 0
        for link in soup.find_all('a', href=True):
            text = link.get_text(strip=True)
            if re.search(r'[\u4e00-\u9fff]{2,10}', text) and len(text) <= 20:
                glossary_entries.append({
                    "term": text,
                    "translation": "",
                    "source": "gov.hk directory"
                })
                count += 1
        print(f"  Found {count} entries")
    except Exception as e:
        print(f"  Error: {e}")

    return glossary_entries

def main():
    print("=" * 50)
    print("本地术语库抓取工具")
    print("=" * 50)
    
    entries = scrape_government_sites_local()
    
    # Remove duplicates
    seen = set()
    unique_entries = []
    for entry in entries:
        if entry['term'] not in seen:
            seen.add(entry['term'])
            unique_entries.append(entry)
    
    print(f"\n总共抓取到 {len(unique_entries)} 条唯一术语")
    
    # Save to file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'glossary_scraped.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(unique_entries, f, ensure_ascii=False, indent=2)
    
    print(f"已保存到: {output_path}")
    
    # Show sample
    print("\n示例术语:")
    for entry in unique_entries[:10]:
        print(f"  - {entry['term']} ({entry['source']})")

if __name__ == '__main__':
    main()
