import requests
import pandas as pd
from bs4 import BeautifulSoup

BASE_URL = "https://www.kentrepertory.com/"
COLOR_TO_GRADE = {
    "green": 1,
    "yellow": 2,
    "red": 3
}

df = pd.read_csv("section.csv")

for _, row in df.iterrows():
    section_name = row['name']
    url = BASE_URL + row['url']
    print(f"\n=== SECTION: {section_name} ===")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # -------- Remedies --------
        print("\n--- Remedies and Grades ---")
        remedy_tags = soup.select('div.panel-body ul.list-inline a.remedy')

        if remedy_tags:
            for tag in remedy_tags:
                name = tag.text.strip()
                classes = tag.get("class", [])
                grade = next(
                    (COLOR_TO_GRADE[color] for color in COLOR_TO_GRADE if any(color in cls for cls in classes)),
                    "Unknown"
                )
                print(f"{name} => Grade {grade}")
        else:
            print("No remedies found.")

        # -------- Sub-symptoms --------
        print("\n--- Sub-symptoms ---")
        sub_symptom_lists = soup.select('ul.list-unstyled.equal-height-list')

        found_any = False
        for ul in sub_symptom_lists:
            links = ul.find_all("a")
            for link in links:
                sub_name = link.text.strip()
                sub_url = BASE_URL + link.get("href")
                print(f"{sub_name} => {sub_url}")
                found_any = True

        if not found_any:
            print("No sub-symptoms found.")

    except Exception as e:
        print(f"Error while processing section '{section_name}': {e}")
