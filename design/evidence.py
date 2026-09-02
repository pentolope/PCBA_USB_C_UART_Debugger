from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(REPO_ROOT, "evidence", "index.json")
DATASHEET_DIR = os.path.join(REPO_ROOT, "evidence", "datasheets")

#: Every document a claim in this repository rests on. `url` is where the file
#: came from; `document_id` is the revision the file itself states, which is
#: what a later reader has to match to know they are reading the same thing.
SOURCES = {
    "usb_20": {
        "file": "datasheets/usb_20_spec.pdf",
        "url": "https://www.usb.org/sites/default/files/usb_20_20250603.zip",
        "retrieved": "2026-09-02",
        "document_id": "Universal Serial Bus Specification Revision 2.0, "
                       "April 27, 2000 (usb_20.pdf, from the 2025-06-03 "
                       "release package)",
        "applies_to": ["USB 2.0 full-speed device", "VBUS limits",
                       "unit loads", "inrush", "differential impedance"],
    },
    "usb_20_suspend_current_ecn": {
        "file": "datasheets/usb_20_suspend_current_ecn.pdf",
        "url": "https://www.usb.org/sites/default/files/usb_20_20250603.zip",
        "retrieved": "2026-09-02",
        "document_id": "USB ECN: 2.5 mA Suspend Current for All Devices "
                       "Except ICUSB",
        "applies_to": ["suspend current limit"],
    },
    "usb_20_device_capacitance_ecn": {
        "file": "datasheets/usb_20_device_capacitance_ecn.pdf",
        "url": "https://www.usb.org/sites/default/files/usb_20_20250603.zip",
        "retrieved": "2026-09-02",
        "document_id": "USB Engineering Change Notice: Device Capacitance",
        "applies_to": ["upstream-facing-port bypass capacitance"],
    },
    "usb_20_vbus_max_limit_ecn": {
        "file": "datasheets/usb_20_vbus_max_limit_ecn.pdf",
        "url": "https://www.usb.org/sites/default/files/usb_20_20250603.zip",
        "retrieved": "2026-09-02",
        "document_id": "USB 2.0 ECN: VBUS Max Limit",
        "applies_to": ["VBUS maximum supplied voltage"],
    },
    "usb_type_c": {
        "file": "datasheets/usb_type_c_spec.pdf",
        "url": "https://www.usb.org/sites/default/files/"
               "USB%20Type-C%202.5%20Release%20202603.zip",
        "retrieved": "2026-09-02",
        "document_id": "USB Type-C Cable and Connector Specification, "
                       "Release 2.5, March 2026",
        "applies_to": ["sink CC termination"],
    },
    "cp2102n_silabs": {
        "file": "datasheets/cp2102n_silabs.pdf",
        "url": "https://www.silabs.com/documents/public/data-sheets/"
               "cp2102n-datasheet.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Silicon Labs CP2102N Data Sheet, Rev. 1.5",
        "applies_to": ["CP2102N-A02-GQFN28R"],
    },
    "xc6206_torex": {
        "file": "datasheets/xc6206_torex.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_Torex-Semicon-XC6206P332MR-G_C5446.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Torex XC6206 Series, ETR0305_004b",
        "applies_to": ["XC6206P332PR-G"],
    },
    "usblc6_2sc6_st": {
        "file": "datasheets/usblc6_2sc6_st.pdf",
        "url": "https://www.st.com/resource/en/datasheet/usblc6-2sc6.pdf",
        "retrieved": "2026-09-02",
        "document_id": "STMicroelectronics USBLC6-2, Doc ID 11265 Rev 5, "
                       "October 2011",
        "applies_to": ["USBLC6-2SC6"],
    },
    "usbc_typec31m12_hro": {
        "file": "datasheets/usbc_typec31m12_hro.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2205251630_Korean-Hroparts-Elec-TYPE-C-31-M-12_C165948.pdf",
        "retrieved": "2026-09-02",
        "document_id": "HRO Electronics TYPE-C-31-M-12 drawing, rev A, "
                       "2020-12-08",
        "applies_to": ["TYPE-C-31-M-12"],
    },
    "header1x6_kinghelm": {
        "file": "datasheets/header1x6_kinghelm.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2110191530_Shenzhen-Kinghelm-Elec-"
               "KH-2-54PH180-1X6P-L11-5_C2905486.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Shenzhen Kinghelm KH-2.54PH180-1X6P-L11.5 drawing",
        "applies_to": ["KH-2.54PH180-1X6P-L11.5"],
    },
    "ao3401a_aos": {
        "file": "datasheets/ao3401a_aos.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2412061733_Alpha---Omega-Semicon-AO3401A_C15127.pdf",
        "retrieved": "2026-09-02",
        "document_id": "AO3401A Rev 3.1, December 2023",
        "applies_to": ["AO3401A"],
    },
    "ao3400a_aos": {
        "file": "datasheets/ao3400a_aos.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "1811081213_Alpha---Omega-Semicon-AO3400A_C20917.pdf",
        "retrieved": "2026-09-02",
        "document_id": "AO3400A Rev 3, December 2011",
        "applies_to": ["AO3400A"],
    },
    "res_0603_uniroyal": {
        "file": "datasheets/res_0603_uniroyal.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2206010045_UNI-ROYAL-Uniroyal-Elec-0603WAF1003T5E_C25803.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Uniroyal 0603W chip resistor series specification",
        "applies_to": ["0603WAF4700T5E", "0603WAF1001T5E", "0603WAF5101T5E",
                       "0603WAF1002T5E", "0603WAF1003T5E",
                       "0603WAF2203T5E"],
    },
    "mlcc_yageo_cc0603": {
        "file": "datasheets/mlcc_yageo_cc0603.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2211101700_YAGEO-CC0603KRX7R9BB104_C14663.pdf",
        "retrieved": "2026-09-02",
        "document_id": "YAGEO CC series 0603 MLCC specification",
        "applies_to": ["CC0603KRX7R9BB104"],
    },
    "mlcc_4u7_samsung": {
        "file": "datasheets/mlcc_4u7_samsung.pdf",
        "url": "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/"
               "2304140030_Samsung-Electro-Mechanics-"
               "CL10A475KO8NNNC_C19666.pdf",
        "retrieved": "2026-09-02",
        "document_id": "Samsung Electro-Mechanics CL10A475KO8NNNC "
                       "specification",
        "applies_to": ["CL10A475KO8NNNC"],
    },
}


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_index():
    entries = {}
    for name in sorted(SOURCES):
        source = SOURCES[name]
        path = os.path.join(REPO_ROOT, "evidence", source["file"])
        entry = dict(source)
        entry["sha256"] = digest(path)
        entry["bytes"] = os.path.getsize(path)
        entries[name] = entry
    return {"schema_version": 1, "documents": entries}


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_index():
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(compute_index(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return INDEX_PATH


def verify():
    """Every recorded document present and unchanged, and nothing unrecorded."""
    recorded = load_index()["documents"]
    present = {name for name in os.listdir(DATASHEET_DIR)
               if name.endswith((".pdf", ".json"))}
    referenced = {os.path.basename(entry["file"])
                  for entry in recorded.values()}
    problems = []
    for name in sorted(referenced - present):
        problems.append(("missing_file", name))
    for name in sorted(present - referenced):
        problems.append(("unreferenced_file", name))
    for name in sorted(recorded):
        entry = recorded[name]
        path = os.path.join(REPO_ROOT, "evidence", entry["file"])
        if not os.path.isfile(path):
            continue
        if digest(path) != entry["sha256"]:
            problems.append(("digest_mismatch", name))
    return problems


if __name__ == "__main__":
    sys.stdout.write(write_index() + "\n")
