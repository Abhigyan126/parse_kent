import requests
import pandas as pd
from bs4 import BeautifulSoup

# Define the base URL
BASE_URL = "https://www.kentrepertory.com/"

# Define grading color mapping
COLOR_TO_GRADE = {
    "green": 1,
    "yellow": 2,
    "red": 3
}

# Read CSV
df = pd.read_csv("section.csv")

# Iterate through each URL
for _, row in df.iterrows():
    name = row['name']
    relative_url = row['url']
    full_url = BASE_URL + relative_url

    print(f"\n--- {name} ---")
    try:
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find remedy list
        remedy_list = soup.select('div.panel-body ul.list-inline')[0].find_all('a', class_='remedy')
        if not remedy_list:
            print("No remedies found.")
            continue

        for remedy in remedy_list:
            remedy_name = remedy.text.strip()
            classes = remedy.get('class', [])
            grade = "Unknown"

            for cls in classes:
                if "green" in cls:
                    grade = COLOR_TO_GRADE["green"]
                elif "yellow" in cls:
                    grade = COLOR_TO_GRADE["yellow"]
                elif "red" in cls:
                    grade = COLOR_TO_GRADE["red"]

            print(f"{remedy_name} => Grade {grade}")
    except Exception as e:
        print(f"Error while processing {name}: {e}")
