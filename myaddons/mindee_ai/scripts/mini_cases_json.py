# mini_cases_json.py

import sys
import json

def main(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        model = json.load(f)

    print("=== Cases détectées dans le JSON ===")
    for entry in model:
        for section in ["Document", "header", "footer", "table", "table_header", "line_cells"]:
            zones = entry.get(section, [])
            for idx, zone in enumerate(zones, start=1):
                label_list = zone.get("rectanglelabels", [])
                label = label_list[0] if label_list else "NUL"

                x, y, w, h = zone["x"], zone["y"], zone["width"], zone["height"]

                print(f"[{section}] {label} → x={x}, y={y}, w={w}, h={h}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python mini_cases_json.py <modele.json>")
        sys.exit(1)

    main(sys.argv[1])
