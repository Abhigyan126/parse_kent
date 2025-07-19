import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time
from datetime import datetime

BASE_URL = "https://www.kentrepertory.com/"
COLOR_TO_GRADE = {"green": 1, "yellow": 2, "red": 3}

visited_links = set()

def fetch_section(url: str, level: int = 0):
    if url in visited_links:
        return None
    visited_links.add(url)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remedies
        remedies = []
        remedy_tags = soup.select('div.panel-body ul.list-inline a.remedy')
        for tag in remedy_tags:
            name = tag.text.strip()
            classes = tag.get("class", [])
            grade = next(
                (COLOR_TO_GRADE[color] for color in COLOR_TO_GRADE if any(color in cls for cls in classes)),
                "Unknown"
            )
            remedies.append({"name": name, "grade": grade})

        # Sub-symptoms
        subsymptoms = {}
        sub_symptom_lists = soup.select('ul.list-unstyled.equal-height-list')
        for ul in sub_symptom_lists:
            for link in ul.find_all("a", href=True):
                name = link.text.strip()
                href = urljoin(BASE_URL, link["href"])
                result = fetch_section(href, level + 1)
                subsymptoms[name] = result if result else {"remedies": [], "subsymptoms": {}}

        return {
            "remedies": remedies,
            "subsymptoms": subsymptoms
        }

    except Exception as e:
        print(f"{'  ' * level}❌ Error fetching {url}: {e}")
        return None

def print_section_structure(section_name, section_data, level=0):
    indent = "  " * level
    print(f"{indent}- {section_name}")
    if section_data and "subsymptoms" in section_data:
        for sub_name in section_data["subsymptoms"]:
            print_section_structure(sub_name, section_data["subsymptoms"][sub_name], level + 1)

# --- MAIN EXECUTION ---

df = pd.read_csv("section.csv")
full_data = {}

for _, row in df.iterrows():
    section = row["name"]
    url = urljoin(BASE_URL, row["url"])
    print(f"\n🔵 START SECTION: {section} at {datetime.now().strftime('%H:%M:%S')}")
    start_time = time.time()

    data = fetch_section(url)
    full_data[section] = data

    print(f"📑 Structure for section: {section}")
    print_section_structure(section, data)

    end_time = time.time()
    print(f"✅ FINISHED SECTION: {section} at {datetime.now().strftime('%H:%M:%S')} | Entries: {len(data.get('subsymptoms', {}))} | Time: {round(end_time - start_time, 2)} sec")

# Save to JSON
with open("kent_repertory.json", "w", encoding="utf-8") as f:
    json.dump(full_data, f, indent=2, ensure_ascii=False)

print("\n💾 Data saved to kent_repertory.json")
