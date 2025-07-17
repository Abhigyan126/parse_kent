import re
import csv
from collections import defaultdict

def parse_remedies(text):
    if not text or text.strip() == "":
        return []
    
    # Remove all (See ...) blocks and markdown links from remedies
    text = re.sub(r'\(See [^)]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', '', text)
    text = re.sub(r'\(\s*\)', '', text)
    
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
    # Extract all forword references from the text
    cleaned = []
    
    # Method 1: Find all [text](link) inside (See ...) blocks
    forword_blocks = re.findall(r'\(See ([^)]*)\)', text, flags=re.IGNORECASE)
    for block in forword_blocks:
        # Split by comma, 'and', 'also'
        items = re.split(r',|\band\b|\balso\b', block)
        for item in items:
            # Extract text from markdown link or plain text
            m = re.match(r'\[([^\]]+)\]\([^)]+\)', item.strip())
            if m:
                name = m.group(1).strip()
            else:
                name = item.strip()
            if name and name.lower() not in ['also', 'and']:
                cleaned.append(name.title())
    
    # Method 2: Find all standalone markdown links [text](link) anywhere in the text
    # This catches cases like "**AFFECTIONATE** (See [Love](kent0060.htm#LOVE), [Indifference](kent0050.htm#INDIFFERENCE))"
    all_markdown_links = re.findall(r'\[([^\]]+)\]\([^)]+\)', text)
    for link_text in all_markdown_links:
        name = link_text.strip()
        if name and name.lower() not in ['also', 'and']:
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

symptom_pattern = re.compile(r'^\*\*(.+?)\*\*\s*(.*)?$')
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
        rest = match.group(2) or ""

        # Extract forword references from any (See ...) block in rest
        collected_forwords = extract_forword(rest)

        # Remove all (See ...) blocks and markdown links from rest to get remedies
        remedies_text = rest
        remedies_text = re.sub(r'\(See [^)]*\)', '', remedies_text)
        remedies_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', '', remedies_text)
        remedies_text = remedies_text.strip()
        main_remedies = []
        if remedies_text:
            main_remedies = parse_remedies(clean_remedy_text(remedies_text))

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
with open("kent_cleaned_final.csv", "w", newline='', encoding='utf-8') as f:
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

print("✅ All done. Saved as 'kent_cleaned_final.csv'")
