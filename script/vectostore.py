import numpy as np
import requests
from tqdm import tqdm
import time

# --- Configuration ---
DATA_FILE = "kent_subsymptoms_combined.npy"
ENDPOINT = "http://localhost:8080/bulk_insert?tree_name=veckent"
BATCH_SIZE = 100  # Set to an integer like 1000 if batching is needed

# --- Helper Function ---
def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# --- Load Data ---
log(f"Loading data from {DATA_FILE}")
data = np.load(DATA_FILE, allow_pickle=True)
log(f"Loaded {len(data)} records")

# --- Preview First 3 Entries ---
log("Preview of first 3 entries:")
for i, item in enumerate(data[:3]):
    print(f"  {i + 1}. data: {item['data']}, embedding (len={len(item['embedding'])})")

# --- Prepare Payload ---
payload = [
    {
        "embedding": item["embedding"],
        "data": item["data"]
    }
    for item in data
]

# --- Upload ---
if BATCH_SIZE:
    log(f"Uploading in batches of {BATCH_SIZE}")
    for i in tqdm(range(0, len(payload), BATCH_SIZE), desc="Uploading Batches"):
        batch = payload[i:i + BATCH_SIZE]
        try:
            response = requests.post(ENDPOINT, json=batch)
            if response.status_code == 200:
                log(f"✅ Batch {i // BATCH_SIZE + 1}: Success")
            else:
                log(f"❌ Batch {i // BATCH_SIZE + 1} Failed: {response.status_code} - {response.text}")
        except Exception as e:
            log(f"❌ Batch {i // BATCH_SIZE + 1} Exception: {str(e)}")
else:
    log("Uploading full dataset in one request")
    try:
        response = requests.post(ENDPOINT, json=payload)
        if response.status_code == 200:
            log("✅ Bulk insert successful")
            print(response.text)
        else:
            log(f"❌ Bulk insert failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        log(f"❌ Exception during bulk insert: {str(e)}")
