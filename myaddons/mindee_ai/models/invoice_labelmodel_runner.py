# -*- coding: utf-8 -*-
import sys
import json

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def round_coords(z):
    for key in ["x", "y", "w", "h"]:
        if key in z:
            z[key] = round(z[key], 2)
    return z

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 invoice_labelmodel_runner.py input.json output.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    data = load_json(input_file)

    if "ocr_zones_all" in data:
        data["ocr_zones_all"] = [round_coords(z) for z in data["ocr_zones_all"]]

    save_json(data, output_file)
    print(f"✅ JSON arrondi sauvegardé dans {output_file}")

if __name__ == "__main__":
    main()
