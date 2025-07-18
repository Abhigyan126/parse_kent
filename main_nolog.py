import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time

BASE_URL = "https://www.kentrepertory.com/"
COLOR_TO_GRADE = {
    "green": 1,
    "yellow": 2,
    "red": 3
}
visited_links = set()

def fetch_and_parse(url: str, depth=0) -> dict:
    indent = "│   " * depth + "├──"

    if url in visited_links:
        return {}
    visited_links.add(url)

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"{indent} ❌ Error: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    result = {
        "url": url,
        "remedies": [],
        "subsymptoms": {}
    }

    # ==== Extract Remedies ====
    remedy_tags = soup.select('div.panel-body ul.list-inline a.remedy')
    grade_counts = {1: 0, 2: 0, 3: 0}

    if remedy_tags:
        print(f"{indent} [INFO] Remedies found: {len(remedy_tags)}")
        for tag in remedy_tags:
            name = tag.text.strip()
            classes = tag.get("class", [])
            grade = next(
                (COLOR_TO_GRADE[color] for color in COLOR_TO_GRADE if any(color in cls for cls in classes)),
                None
            )
            grade_label = f"(Grade {grade})" if grade else "(Unknown grade)"
            print(f"{indent}    🧪 Remedy: {name} {grade_label}")
            if grade: grade_counts[grade] += 1
            result["remedies"].append({"name": name, "grade": grade})
    else:
        pass
    # ==== Extract Sub-symptoms ====
    sub_ul_lists = soup.select('ul.list-unstyled.equal-height-list')
    sub_found = False

    for ul in sub_ul_lists:
        for li in ul.find_all("li"):
            a = li.find("a", href=True)
            if a:
                name = a.text.strip()
                link = urljoin(BASE_URL, a['href'])
                sub_found = True
                result["subsymptoms"][name] = fetch_and_parse(link, depth + 1)

    if not sub_found:
        pass

    return result

# ==== Main Execution ====
def main():
    print("📥 Loading section list from section.csv...\n")
    df = pd.read_csv("section.csv")
    data = {}

    for i, row in df.iterrows():
        name = row['name'].strip()
        url = urljoin(BASE_URL, row['url'])
        print(f"\n📦 Processing Section [{i+1}/{len(df)}]: {name}")
        section_data = fetch_and_parse(url)
        data[name] = section_data
        print(f"✅ Finished Section: {name}\n" + "-"*80)

    print("\n💾 Writing data to kentrepertory.json...")
    with open("kentrepertory.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ All done! Data saved to 'kentrepertory.json'.")

if __name__ == "__main__":
    main()
