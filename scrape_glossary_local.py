# -*- coding: utf-8 -*-
"""
术语库抓取脚本 - 深入新闻页面抓取术语
运行方式：python scrape_glossary_local.py
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def extract_terms_from_text(text):
    terms = set()
    quoted = re.findall(r"「([^」]{2,25})」", text)
    for t in quoted:
        if not any(c in t for c in ["/", "（", "）", "(", ")"]):
            terms.add(t)
    laws = re.findall(r"《([^》]{2,30})》", text)
    for t in laws:
        terms.add(t)
    patterns = [
        r"([\u4e00-\u9fff]{2,8}(?:委员会|工作组|办公室|专班|小组|谘询委员会))",
        r"([\u4e00-\u9fff]{2,8}(?:计划|机制|沙盒|策略|方案))",
        r"([\u4e00-\u9fff]{2,6}(?:署|局|处|院|所|中心|基金会))",
        r"([\u4e00-\u9fff]{2,6}(?:条例|草案|守则|指引|办法))",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            terms.add(m)
    return terms

def scrape_news_links(base_url, list_url, source_name, max_pages=5):
    terms = set()
    try:
        print(f"  Fetching news list: {list_url}")
        response = requests.get(list_url, timeout=30, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        news_links = []
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if text and len(text) > 8 and re.search(r"[\u4e00-\u9fff]", text):
                if href.startswith("/"):
                    href = base_url + href
                elif not href.startswith("http"):
                    href = base_url + "/" + href
                news_links.append((href, text))
        seen = set()
        unique_links = []
        for href, text in news_links:
            if href not in seen:
                seen.add(href)
                unique_links.append((href, text))
        print(f"  Found {len(unique_links)} news links, scraping top {max_pages}...")
        for i, (href, title) in enumerate(unique_links[:max_pages]):
            try:
                print(f"    [{i+1}/{min(max_pages, len(unique_links))}] {title[:40]}...")
                resp = requests.get(href, timeout=20, headers=HEADERS)
                page_soup = BeautifulSoup(resp.text, "html.parser")
                for script in page_soup(["script", "style"]):
                    script.extract()
                text = page_soup.get_text(separator=" ", strip=True)
                page_terms = extract_terms_from_text(text)
                terms.update(page_terms)
                time.sleep(0.3)
            except Exception as e:
                print(f"    Error: {e}")
    except Exception as e:
        print(f"  Error fetching list: {e}")
    return terms

def scrape_site_page(url, source_name):
    terms = set()
    try:
        print(f"  Scraping: {url}")
        response = requests.get(url, timeout=30, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=" ", strip=True)
        terms = extract_terms_from_text(text)
        print(f"    Found {len(terms)} terms")
    except Exception as e:
        print(f"  Error: {e}")
    return terms

def main():
    print("=" * 60)
    print("术语库自动抓取工具 - 深入新闻页面")
    print("=" * 60)
    all_terms = set()
    
    print("\n[1/6] 施政报告新闻稿...")
    terms = scrape_news_links("https://www.policyaddress.gov.hk", "https://www.policyaddress.gov.hk/2025/sc/press.html", "policyaddress.gov.hk", max_pages=15)
    all_terms.update(terms)
    print(f"  Total: {len(terms)} terms")
    
    print("\n[2/6] 香港政府新闻公报...")
    terms = scrape_news_links("https://www.info.gov.hk", "https://www.info.gov.hk/gia/general/", "info.gov.hk", max_pages=10)
    all_terms.update(terms)
    print(f"  Total: {len(terms)} terms")
    
    print("\n[3/6] 政府部门主页...")
    dept_sites = [
        ("https://www.gov.hk/sc/residents/", "gov.hk"),
        ("https://www.hyab.gov.hk/chs/home/index.htm", "hyab.gov.hk"),
        ("https://www.itib.gov.hk/zh-cn/index.html", "itib.gov.hk"),
        ("https://www.fso.gov.hk/sim/index.htm", "fso.gov.hk"),
        ("https://www.digitalpolicy.gov.hk/sc/", "digitalpolicy.gov.hk"),
        ("https://www.doj.gov.hk/sc/index.html", "doj.gov.hk"),
        ("https://www.immd.gov.hk/hks/services/chinese.html", "immd.gov.hk"),
    ]
    for url, name in dept_sites:
        terms = scrape_site_page(url, name)
        all_terms.update(terms)
    
    print("\n[4/6] HKEX...")
    terms = scrape_site_page("https://www.hkex.com.hk/?sc_lang=zh-HK", "hkex.com.hk")
    all_terms.update(terms)
    
    print("\n[5/6] 政府目录...")
    terms = scrape_site_page("https://www.gov.hk/tc/about/govdirectory/", "gov.hk directory")
    all_terms.update(terms)
    
    print("\n[6/6] 合并现有术语库...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manual_path = os.path.join(script_dir, "glossary_manual.json")
    existing_terms = set()
    if os.path.exists(manual_path):
        with open(manual_path, "r", encoding="utf-8") as f:
            manual = json.load(f)
        for entry in manual:
            existing_terms.add(entry["term"])
        print(f"  Existing terms: {len(existing_terms)}")
    
    new_terms = all_terms - existing_terms
    print(f"  New terms found: {len(new_terms)}")
    
    added = 0
    for term in sorted(new_terms):
        if 2 <= len(term) <= 25:
            manual.append({"term": term, "translation": "", "source": "auto_scrape"})
            added += 1
    
    with open(manual_path, "w", encoding="utf-8") as f:
        json.dump(manual, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 60}")
    print(f"抓取完成！总术语数: {len(manual)}, 新增: {added}")
    print(f"{'=' * 60}")
    
    if new_terms:
        print(f"\n新增术语示例:")
        for term in sorted(new_terms)[:20]:
            print(f"  + {term}")

if __name__ == "__main__":
    main()
