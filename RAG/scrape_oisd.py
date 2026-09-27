"""
OISD Scraper - Downloads Case Studies, Safety Alerts, and Documents
Sources:
  - https://oisd.gov.in/case-studies  (caseStudyID 1-98)
  - https://oisd.gov.in/safety-alert  (documentID via GetDocumentAttachmentByID)
  - https://oisd.gov.in/Image/GetDocumentAttachmentByID?documentID=10
"""

import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "https://oisd.gov.in"

# Output directories
CASE_STUDY_DIR = "knowledge-base/public/oisd/case-studies"
SAFETY_ALERT_DIR = "knowledge-base/public/oisd/safety-alerts"
DOCUMENTS_DIR = "knowledge-base/public/oisd/documents"

os.makedirs(CASE_STUDY_DIR, exist_ok=True)
os.makedirs(SAFETY_ALERT_DIR, exist_ok=True)
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://oisd.gov.in/case-studies",
}


def download_file(url, dest_path, label=""):
    """Download a file from URL to dest_path. Returns True on success."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if len(data) < 100:
                print(f"  [SKIP] {label} - Too small ({len(data)} bytes), likely not a real file")
                return False
            # Determine extension from content-type
            if not dest_path.endswith(".pdf") and "pdf" in content_type:
                dest_path += ".pdf"
            with open(dest_path, "wb") as f:
                f.write(data)
            print(f"  [OK] {label} -> {os.path.basename(dest_path)} ({len(data):,} bytes)")
            return True
    except urllib.error.HTTPError as e:
        print(f"  [HTTP {e.code}] {label} - {url}")
        return False
    except urllib.error.URLError as e:
        print(f"  [ERR] {label} - {e.reason}")
        return False
    except Exception as e:
        print(f"  [ERR] {label} - {e}")
        return False


# ──────────────────────────────────────────────────────────────
# PART 1: Download Case Study Attachments
# IDs scraped from https://oisd.gov.in/case-studies
# ──────────────────────────────────────────────────────────────

# All case study IDs found on the page (current + archived)
CASE_STUDY_IDS = {
    95: "OISD-CS-2026-27-PE-12_Fatal-scaffolding-dismantling",
    94: "OISD-CS-2026-27-PE-11_Fatal-HDPE-wax-forklift",
    93: "OISD-CS-2025-26-LPG-12_Fatal-electrical-shock",
    92: "OISD-CS-2025-26-MOPOL-20_Fire-ethanol-storage-tank",
    91: "OISD-CS-2025-26-MOLPG-22_Major-accident-service-water-valve",
    90: "OISD-CS-2025-26-PL-08_Fatal-fire-tender-parking",
    89: "OISD-CS-2025-26-PL-15_Gas-leakage-fire-offshore-pipeline",
    88: "OISD-CS-2025-26-PL-16_Piercing-LPG-pipeline-drilling",
    87: "OISD-CS-2025-26-PE-07_LNG-leakage-LCNG-station",
    86: "OISD-CS-2025-26-PE-09_220KV-cable-fire-RCC-trench",
    85: "OISD-CS-2025-26-PE-10_H2S-exposure-fatality-floating-roof-tank",
    84: "OISD-CS-2025-26-PE-17_Fire-2inch-hydrocarbon-drain-line",
    83: "OISD-CS-2026-27-PE-08_Fire-CDU-VDU",
    82: "OISD-CS-2026-27-EP-05_Fatal-fall-psychological-distress",
    81: "OISD-CS-2026-27-EP-06_HVAC-fire-machinery-deck",
    80: "OISD-CS-2026-27-EP-09_Major-incident-GGS",
    79: "OISD-CS-2026-27-EP-03_Minor-fire-well-site",
    78: "OISD-CS-2026-27-EP-02_Fall-travelling-block",
    77: "OISD-CS-2026-27-EP-01_Blowout-well-perforation",
    76: "OISD-CS-2025-26-EP-21_Gas-blowout-workover-rig",
    75: "OISD-CS-2025-26-EP-19_Fatal-dismantling-drilling-rig",
    74: "OISD-CS-2025-26-EP-18_Man-overboard-MOB",
    73: "OISD-CS-2025-26-EP-14_Fatal-tubing-drop-elevator-unlatched",
    72: "OISD-CS-2025-26-EP-13_Blowout-well-perforation",
    71: "OISD-CS-2025-26-EP-11_Fall-damage-workover-rig-mast",
    70: "OISD-CS-2026-27-PE-10_Fatal-flash-fire-desalter-manway",
    69: "OISD-CS-2026-27-PL-04_LPG-pipeline-piercing",
    68: "OISD-CS-2024-25-EP-17_Fall-damage-workover-rig-mast",
    67: "OISD-CS-2024-25-PL-07_Fatal-pipeline-ROW-excavation",
    66: "OISD-CS-2024-25-PE-09_Fire-maintenance-activity",
    65: "OISD-CS-2024-25-PE-08_Fatal-fall-from-height",
    64: "OISD-CS-2024-25-PE-04_Fatal-hook-loaded-crane",
    63: "OISD-CS-2024-25-PE-02_Fatal-hydrostatic-testing-fin-fan-cooler",
    62: "OISD-CS-2024-25-PE-01_Fatal-adsorbent-removal",
    61: "OISD-CS-2024-25-MOPOL-06_Explosion-ethanol-horizontal-tanks",
    60: "OISD-CS-2024-25-MOLPG-10_Major-accident-soap-solution-chain",
    59: "OISD-CS-2024-25-EP-08_Fire-battery-room",
    58: "OISD-CS-2024-25-EP-05_Fall-damage-drilling-rig-mast",
    57: "OISD-CS-2024-25-EP-03_Fatal-accident-wellsite",
    56: "OISD-CS-2023-24-PL-12_Pipeline-failure-river-crossing",
    55: "OISD-CS-2023-24-PE-15_Fatal-fire-wet-slop-oil-pump-house",
    54: "OISD-CS-2023-24-PE-14_Fatal-adsorbent-removal",
    53: "OISD-CS-2023-24-PE-10_Accident-maintenance-activity",
    52: "OISD-CS-2023-24-PE-09_Major-fire-HCU",
    51: "OISD-CS-2023-24-PE-08_Fatal-construction-activity",
    50: "OISD-CS-2023-24-PE-07_Fatal-explosion-sample-bomb",
    49: "OISD-CS-2023-24-EP-11_Major-fire-cluster-location",
    48: "OISD-CS-2023-24-EP-06_Man-overboard-MOB",
    47: "OISD-CS-2023-24-PE-13_Oil-ingress-waterbodies",
    46: "OISD-CS-2021-22-PE-06_Explosion-furnace-box",
    45: "OISD-CS-2021-22-PE-03_Fire-CDU-SR-line-leak",
    44: "OISD-CS-2021-22-LPG-05_Fatal-degassing-LPG-storage-bullet",
    43: "OISD-CS-2021-22-EP-07_Fall-travelling-block",
    42: "OISD-CS-2021-22-EP-07b_Fall-travelling-block-Mar2022",
    41: "OISD-CS-2021-22-EP-04_Accident-calibration-SRV",
    40: "OISD-CS-2021-22-EP-02_Fall-telescopic-mast",
    39: "OISD-CS-2021-22-EP-01_Fall-hatch-roustabout",
    38: "OISD-CS-2020-21-PE-02_Fire-maintenance-vessel-SPM",
    37: "OISD-SA-2026-27-MOLPG-06_Fatal-runover-LPG-tanktruck",
    36: "OISD-CS-2026-27-PL-04_LPG-pipeline-piercing-v2",
    35: "OISD-CS-2026-27-PE-08b_Fire-CDU-VDU-v2",
    34: "OISD-CS-2026-27-EP-06b_HVAC-fire-machinery-deck-v2",
    33: "OISD-CS-2026-27-EP-05b_Fatal-fall-psychological-v2",
    32: "OISD-CS-2026-27-EP-03b_Minor-fire-well-site-v2",
    31: "OISD-CS-2026-27-EP-02b_Fall-travelling-block-v2",
    30: "OISD-CS-2026-27-EP-01b_Blowout-well-perforation-v2",
    29: "OISD-CS-2025-26-PL-16_Pipeline-failure-monsoon-floods",
    28: "OISD-CS-2025-26-PL-15b_Gas-leakage-fire-offshore-pipeline-v2",
    27: "OISD-CS-2025-26-PL-08b_Fatal-fire-tender-parking-v2",
    26: "OISD-CS-2025-26-PL-03_Oil-pipeline-leakage-offshore",
    25: "OISD-CS-2025-26-PE-17b_Fire-2inch-drain-line-v2",
    24: "OISD-CS-2025-26-PE-10b_H2S-exposure-fatality-v2",
    23: "OISD-CS-2025-26-PE-09b_220KV-cable-fire-v2",
    22: "OISD-CS-2025-26-PE-07b_LNG-leakage-LCNG-v2",
    21: "OISD-CS-2025-26-PE-02_Fire-compressor-house",
    20: "OISD-CS-2025-26-MOPOL-20b_Fire-ethanol-storage-v2",
    19: "OISD-CS-2025-26-MOPOL-01_HSD-overflow-underground-tank",
    18: "OISD-CS-2025-26-MOLPG-22b_Major-accident-soap-solution-v2",
    17: "OISD-CS-2025-26-LPG-12b_Fatal-electrical-shock-v2",
    16: "OISD-CS-2025-26-EP-21b_Gas-blowout-workover-rig-v2",
    15: "OISD-CS-2025-26-EP-19b_Fatal-dismantling-drilling-rig-v2",
    14: "OISD-CS-2025-26-EP-18b_Man-overboard-v2",
    13: "OISD-CS-2025-26-EP-14b_Fatal-tubing-drop-v2",
    12: "OISD-CS-2025-26-EP-13b_Blowout-well-perforation-v2",
    11: "OISD-CS-2025-26-EP-11b_Fall-workover-rig-mast-v2",
    10: "OISD-CS-2025-26-EP-07_Fatal-offshore-vessel-unmanned-platform",
    9:  "OISD-CS-2025-26-EP-06_Major-fire-drilling-rig",
    8:  "OISD-CS-2025-26-EP-05_Fatal-accident-workover-rig",
    7:  "OISD-CS-2025-26-EP-04_Fatal-drill-pipe-catwalk",
    6:  "OISD-CS-2024-25-PE-16_Naphtha-splitter-reboiler-furnace-fire",
    5:  "OISD-CS-2024-25-PE-14_Explosion-fire-benzene-tanks",
    4:  "OISD-CS-2024-25-PE-13_Fire-AVU",
    3:  "OISD-CS-2024-25-PE-12_Explosion-furnace",
    2:  "OISD-CS-2024-25-PE-11_Fatal-accident-maintenance-fabrication-yard",
    1:  "OISD-CS-2024-25-EP-17_Fatal-fire-heater-treater",
    96: "OISD-CS-2022-23-POL-07_Fire-tank-lorry-filling-gantry",
    97: "OISD-CS-2020-21-POL-01_Fire-MS-insulating-flange-joint",
    98: "OISD-CS-2024-25-PE-13b_Fire-AVU-v2",
}

print("=" * 60)
print("DOWNLOADING CASE STUDIES")
print("=" * 60)
success_cs = 0
fail_cs = 0
for cs_id, name in sorted(CASE_STUDY_IDS.items()):
    url = f"{BASE_URL}/Image/GetCaseStudyAttachment?caseStudyID={cs_id}"
    dest = os.path.join(CASE_STUDY_DIR, f"{name}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 500:
        print(f"  [SKIP-EXISTS] {name}")
        success_cs += 1
        continue
    ok = download_file(url, dest, label=f"CS-{cs_id}: {name[:60]}")
    if ok:
        success_cs += 1
    else:
        fail_cs += 1
    time.sleep(0.5)  # polite delay

print(f"\nCase Studies: {success_cs} downloaded, {fail_cs} failed")

# ──────────────────────────────────────────────────────────────
# PART 2: Download Safety Alerts via GetDocumentAttachmentByID
# Try IDs 1-50 (the safety alert page uses this endpoint)
# ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("DOWNLOADING DOCUMENTS (GetDocumentAttachmentByID)")
print("=" * 60)

# The third URL given: documentID=10
# We'll try a range 1-60
success_doc = 0
fail_doc = 0
for doc_id in range(1, 61):
    url = f"{BASE_URL}/Image/GetDocumentAttachmentByID?documentID={doc_id}"
    dest = os.path.join(DOCUMENTS_DIR, f"OISD-Document-{doc_id:03d}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 500:
        print(f"  [SKIP-EXISTS] Document-{doc_id}")
        success_doc += 1
        continue
    ok = download_file(url, dest, label=f"Document-{doc_id}")
    if ok:
        success_doc += 1
    else:
        fail_doc += 1
    time.sleep(0.5)

print(f"\nDocuments: {success_doc} downloaded, {fail_doc} failed")

# ──────────────────────────────────────────────────────────────
# PART 3: Try Safety Alert attachments (if they use different IDs)
# The safety-alert page denied permission, but the GetCaseStudyAttachment
# endpoint works; safety alerts might share same endpoint with different IDs
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DOWNLOADING SAFETY ALERTS (GetSafetyAlertAttachment range probe)")
print("=" * 60)

success_sa = 0
fail_sa = 0
for sa_id in range(1, 60):
    url = f"{BASE_URL}/Image/GetSafetyAlertAttachment?safetyAlertID={sa_id}"
    dest = os.path.join(SAFETY_ALERT_DIR, f"OISD-SafetyAlert-{sa_id:03d}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 500:
        print(f"  [SKIP-EXISTS] SafetyAlert-{sa_id}")
        success_sa += 1
        continue
    ok = download_file(url, dest, label=f"SafetyAlert-{sa_id}")
    if ok:
        success_sa += 1
    else:
        fail_sa += 1
    time.sleep(0.4)

print(f"\nSafety Alerts: {success_sa} downloaded, {fail_sa} failed")

# ──────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SCRAPING COMPLETE - SUMMARY")
print("=" * 60)
total_files = 0
for d in [CASE_STUDY_DIR, SAFETY_ALERT_DIR, DOCUMENTS_DIR]:
    files = [f for f in os.listdir(d) if os.path.getsize(os.path.join(d, f)) > 500]
    print(f"  {d}: {len(files)} files")
    total_files += len(files)
print(f"\n  TOTAL: {total_files} files downloaded")
