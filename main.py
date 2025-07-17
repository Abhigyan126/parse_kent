import re
import csv
from collections import defaultdict

def parse_remedies(text):
    # Remove inline "See ..." references
    text = re.sub(r'\(See\s+.*?\)', '', text)

    # Split and process remedies
    tokens = [t.strip(" ,.") for t in text.split(",") if t.strip()]
    parsed = []
    for token in tokens:
        if '**' in token:
            r = re.sub(r'\*+', '', token)
            parsed.append(f"{r}(3)")
        elif '_' in token:
            r = re.sub(r'_+', '', token)
            parsed.append(f"{r}(2)")
        else:
            parsed.append(f"{token}(1)")
    return parsed

def extract_forword(text):
    # Collect all "See ..." or "see ..." constructs
    matches = re.findall(r'\(See\s+(.*?)\)', text, flags=re.IGNORECASE)
    cleaned = []
    for m in matches:
        # Extract just the keywords from inside "See ..." text
        items = re.split(r'and|also|,', m)
        for item in items:
            name = re.sub(r'\[.*?\]\(.*?\)', '', item).strip()
            if name:
                cleaned.append(name.title())
    return cleaned

def clean_remedy_text(text):
    return text.replace(" :", ":").replace(" ,", ",").replace("..", ".")

# Read markdown
with open("kent.md", "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

data = {}
current_section = ""
current_symptom = ""
modifiers = defaultdict(list)
collected_forwords = []

symptom_pattern = re.compile(r'^\*\*(.+?)\*\*(?:\s*\(See (.+?)\))?\s*:? (.*)?$')
modifier_pattern = re.compile(r'^([a-z0-9 ,\-\.\(\)]+?) ?: (.+)$', re.IGNORECASE)

for line in lines:
    if "©" in line or line.startswith("\\") or "--------" in line:
        continue

    if re.match(r'^[A-Z ]+$', line) and len(line) > 2:
        current_section = line.strip().title()
        continue

    match = symptom_pattern.match(line)
    if match:
        current_symptom = match.group(1).strip().title()
        direct_forword = match.group(2)
        main_remedies_raw = match.group(3)

        # Extract forwords from within remedy section too
        collected_forwords = []

        if direct_forword:
            collected_forwords += extract_forword(direct_forword)

        main_remedies = []
        if main_remedies_raw:
            collected_forwords += extract_forword(main_remedies_raw)
            main_remedies = parse_remedies(clean_remedy_text(main_remedies_raw))

        data[current_symptom] = {
            'section': current_section,
            'symptom': current_symptom,
            'remedies': ', '.join(main_remedies),
            'modifiers': [],
            'forword': ', '.join(sorted(set(collected_forwords)))
        }
        continue

    mod_match = modifier_pattern.match(line)
    if mod_match and current_symptom:
        modifier = mod_match.group(1).strip()
        remedies_text = mod_match.group(2).strip()

        mod_forwords = extract_forword(remedies_text)
        if mod_forwords:
            data[current_symptom]['forword'] += ', ' + ', '.join(sorted(set(mod_forwords)))

        remedies = parse_remedies(clean_remedy_text(remedies_text))
        data[current_symptom]['modifiers'].append(f"{modifier}: {', '.join(remedies)}")

# Clean up forword duplicates
for item in data.values():
    item['forword'] = ', '.join(sorted(set([f.strip() for f in item['forword'].split(',') if f.strip()])))

# Write to CSV
with open("kent_cleaned.csv", "w", newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=["section", "symptom", "modifier", "remedies", "forword"])
    writer.writeheader()
    for item in data.values():
        writer.writerow({
            "section": item['section'],
            "symptom": item['symptom'],
            "modifier": '; '.join(item['modifiers']),
            "remedies": item['remedies'],
            "forword": item['forword']
        })

print("✅ All done. Saved as 'kent_cleaned.csv'")
