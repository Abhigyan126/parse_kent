import numpy as np
import requests
from tqdm import tqdm
import time
import os

# --- Configuration ---
DATA_FILE = "kent_subsymptoms_combined.npy"
ENDPOINT = "http://127.0.0.1:8080/insert"
TREE_NAME = "veckent"

# --- Helper Function ---
def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# --- Load Data ---
if not os.path.exists(DATA_FILE):
    log(f"Error: Data file '{DATA_FILE}' not found.")
    exit()

log(f"Loading data from {DATA_FILE}")
data = np.load(DATA_FILE, allow_pickle=True)
log(f"Loaded {len(data)} records")

# --- Preview First 3 Entries ---
log("Preview of first 3 entries:")
for i, item in enumerate(data[:3]):
    print(f"  {i + 1}. data: {item['data']}, embedding (len={len(item['embedding'])})")

# --- Upload individual points ---
log(f"Uploading individual points to tree: '{TREE_NAME}'")

for i, item in enumerate(tqdm(data, desc="Uploading Points")):
    # Prepare the payload for a single point
    payload = {
        "embedding": item["embedding"],
        "data": item["data"]
    }
    
    # Construct the full URL with the query parameter
    full_endpoint = f"{ENDPOINT}?tree_name={TREE_NAME}"

    try:
        response = requests.post(full_endpoint, json=payload)
        
        # Check for success, and log any failures
        if response.status_code != 200:
            log(f"❌ Failed to insert point {i + 1}: {response.status_code} - {response.text}")

    except Exception as e:
        log(f"❌ Exception during upload of point {i + 1}: {str(e)}")

log("✅ Upload process finished.")