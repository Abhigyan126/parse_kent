import requests
import pandas as pd
import json
from bs4 import BeautifulSoup

BASE_URL = "https://www.kentrepertory.com/"
COLOR_TO_GRADE = {
    "green": 1,
    "yellow": 2,
    "red": 3
}

df = pd.read_csv("section.csv")
output_data = []

for _, row in df.iterrows():
    section_name = row['name']
    url = BASE_URL + row['url']
    print(f"Processing: {section_name}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        section_data = {
            "section": section_name,
            "url": url,
            "remedies": [],
            "sub_symptoms": []
        }

        # --- Remedies ---
        remedy_tags = soup.select('div.panel-body ul.list-inline a.remedy')
        for tag in remedy_tags:
            name = tag.text.strip()
            classes = tag.get("class", [])
            grade = next(
                (COLOR_TO_GRADE[color] for color in COLOR_TO_GRADE if any(color in cls for cls in classes)),
                "Unknown"
            )
            section_data["remedies"].append({
                "name": name,
                "grade": grade
            })

        # --- Sub-symptoms ---
        sub_lists = soup.select('ul.list-unstyled.equal-height-list')
        for ul in sub_lists:
            for link in ul.find_all("a"):
                sub_name = link.text.strip()
                sub_url = BASE_URL + link.get("href")
                section_data["sub_symptoms"].append({
                    "name": sub_name,
                    "url": sub_url
                })

        output_data.append(section_data)

    except Exception as e:
        print(f"Error in section '{section_name}': {e}")

# Save to JSON
with open("kent_symptoms.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print("\n✅ Data successfully saved to 'kent_symptoms.json'")
