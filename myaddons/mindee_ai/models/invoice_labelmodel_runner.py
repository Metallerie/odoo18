# -*- coding: utf-8 -*-
# invoice_labelmodel_runner.py
#
# - OCR zones à partir d'un modèle Label Studio (JSON)
# - Déduplique les boîtes identiques (évite les doublons "NUL")
# - Numérotation par ligne : toutes les cases d'une même ligne partagent le même row_index
#   (tolérance verticale adaptative, robuste aux petites dérives d'alignement)

import json
import math
import tempfile
from statistics import median
from pdf2image import convert_from_path
import pytesseract


# --- Paramètres de regroupement (peuvent être ajustés si besoin) ---
# Facteur appliqué sur la "hauteur typique" / le pas vertical médian pour obtenir la tolérance
VERT_TOL_FACTOR = 0.45
# Tolérance verticale minimale (en % hauteur page, car y/h sont en %)
VERT_TOL_MIN = 0.6
# Tolérance verticale maximale (limite haute de sécurité)
VERT_TOL_MAX = 3.5

# Si présent, on essaie de borner les lignes entre "Table Header" et "Table End"
USE_TABLE_BOUNDS = True


def _bbox_key(z):
    """Clé de déduplication: bbox arrondie pour tolérer les micro-variations."""
    return (
        round(float(z["x"]), 3),
        round(float(z["y"]), 3),
        round(float(z["w"]), 3),
        round(float(z["h"]), 3),
    )


def _dedupe_boxes(zones):
    """
    Déduplique les zones avec la même bbox.
    Règles :
      - on préfère un label != "NUL" à un label "NUL"
      - on préfère le texte non vide / le plus long
    """
    kept = {}
    for z in zones:
        key = _bbox_key(z)
        if key not in kept:
            kept[key] = z
            continue
        a = kept[key]
        b = z
        # Choix du meilleur label
        a_label = (a.get("label") or "NUL")
        b_label = (b.get("label") or "NUL")
        a_text = (a.get("text") or "").strip()
        b_text = (b.get("text") or "").strip()

        def score(label, text):
            s = 0
            if label != "NUL":
                s += 10
            s += min(len(text), 50)  # plus de contenu est en général meilleur
            return s

        if score(b_label, b_text) > score(a_label, a_text):
            kept[key] = b

    return list(kept.values())


def _table_bounds(ocr_zones):
    """
    Facultatif: bornes verticales du tableau si on a des zones "Table Header" / "Table End".
    On retourne (top, bottom) en pourcentage (même unité que y/h).
    """
    header = next((z for z in ocr_zones if z.get("label") == "Table Header"), None)
    end = next((z for z in ocr_zones if z.get("label") in ("Table End", "Table Total")), None)

    if header:
        top = float(header["y"]) + float(header["h"]) * 0.8  # un peu sous l'entête
    else:
        top = min((float(z["y"]) for z in ocr_zones), default=0.0)

    if end:
        bottom = float(end["y"])  # juste au-dessus des totaux
    else:
        bottom = max((float(z["y"]) + float(z["h"]) for z in ocr_zones), default=100.0)

    return top, bottom


def _compute_vertical_tolerance(items):
    """
    Calcule une tolérance verticale adaptative basée sur :
    - la médiane des hauteurs de cases
    - la médiane des deltas y_center successifs
    On prend le max des deux signaux * VERT_TOL_FACTOR, borné entre VERT_TOL_MIN et VERT_TOL_MAX.
    """
    if not items:
        return VERT_TOL_MIN

    heights = [float(i["h"]) for i in items if float(i["h"]) > 0]
    med_h = median(heights) if heights else 1.0

    centers = [float(i["y"]) + float(i["h"]) / 2.0 for i in items]
    centers.sort()
    deltas = []
    for i in range(1, len(centers)):
        d = centers[i] - centers[i - 1]
        # on ignore les sauts trop gros (changement de bloc) et les zéros
        if 0.2 <= d <= 10.0:
            deltas.append(d)
    med_d = median(deltas) if deltas else med_h

    tol = max(med_h, med_d) * VERT_TOL_FACTOR
    tol = max(VERT_TOL_MIN, min(tol, VERT_TOL_MAX))
    return tol


def _assign_row_index_by_lines(ocr_zones):
    """
    Regroupe toutes les cases en lignes visuelles (buckets verticaux).
    Toutes les cases d'une même ligne reçoivent le même row_index (1,2,3,...).
    """
    if not ocr_zones:
        return ocr_zones

    # Optionnel: borner au "vrai" tableau si on a ces zones
    if USE_TABLE_BOUNDS:
        top, bottom = _table_bounds(ocr_zones)
    else:
        top = min(float(z["y"]) for z in ocr_zones)
        bottom = max(float(z["y"]) + float(z["h"]) for z in ocr_zones)

    # Liste de travail avec centres verticaux
    items = []
    for z in ocr_zones:
        y = float(z["y"])
        h = float(z["h"])
        y_center = y + h / 2.0
        # garde tout (on veut aussi commentaires, totaux, etc.), mais ça reste borné
        if y_center < top - 1.0 or y_center > bottom + 1.0:
            # hors du bloc principal -> on les inclut quand même, mais ils formeront leurs propres lignes
            pass
        items.append({
            "ref": z,
            "y": y,
            "h": h,
            "y_center": y_center,
            "x": float(z["x"]),
        })

    # Tri du haut vers le bas
    items.sort(key=lambda t: (t["y_center"], t["x"]))

    # Tolérance adaptative
    tol = _compute_vertical_tolerance(items)

    # Bucketing
    buckets = []  # chaque bucket: dict { "centers":[], "members":[items], "y_mean":float }
    for it in items:
        if not buckets:
            buckets.append({"centers": [it["y_center"]], "members": [it], "y_mean": it["y_center"]})
            continue
        b = buckets[-1]
        if abs(it["y_center"] - b["y_mean"]) <= tol:
            b["members"].append(it)
            b["centers"].append(it["y_center"])
            b["y_mean"] = sum(b["centers"]) / len(b["centers"])
        else:
            buckets.append({"centers": [it["y_center"]], "members": [it], "y_mean": it["y_center"]})

    # Attribution des row_index, 1..N
    row_idx = 1
    for b in buckets:
        for m in b["members"]:
            m["ref"]["row_index"] = row_idx
        row_idx += 1

    return ocr_zones


def run_invoice_labelmodel(pdf_file, json_model):
    """
    Exécute l'OCR sur un PDF avec un modèle LabelStudio
    et renvoie :
      - ocr_raw : texte brut complet de la page
      - ocr_zones : liste des zones labellisées avec valeurs OCR (+ row_index par ligne)
    """
    # Charger le modèle (JSON simple attendu)
    with open(json_model, "r", encoding="utf-8") as f:
        model = json.load(f)

    # PDF -> image (1ère page)
    pages = convert_from_path(pdf_file, dpi=300)
    page = pages[0]
    img_w, img_h = page.size

    # OCR brut
    ocr_raw = pytesseract.image_to_string(page, lang="fra")

    # OCR par zones
    ocr_zones = []
    for entry in model:
        for key, zones in entry.items():
            if not isinstance(zones, list):
                continue
            for zone in zones:
                if not isinstance(zone, dict):
                    continue

                label_list = zone.get("rectanglelabels", [])
                label = (label_list[0] if label_list else "NUL") or "NUL"

                # Certains exports mettent les coords à la racine, d'autres dans "value"
                v = zone.get("value") or {}
                x = zone.get("x", v.get("x"))
                y = zone.get("y", v.get("y"))
                w = zone.get("width", v.get("width"))
                h = zone.get("height", v.get("height"))
                if x is None or y is None or w is None or h is None:
                    continue

                # OCR de la zone (coords en % -> pixels)
                left = int((float(x) / 100.0) * img_w)
                top = int((float(y) / 100.0) * img_h)
                right = int(((float(x) + float(w)) / 100.0) * img_w)
                bottom = int(((float(y) + float(h)) / 100.0) * img_h)

                crop = page.crop((left, top, right, bottom))
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                    crop.save(tmp_img.name)

                text = pytesseract.image_to_string(crop, lang="fra").strip() or "NUL"

                ocr_zones.append({
                    "label": label,
                    "row_index": None,     # attribué ensuite
                    "x": float(x), "y": float(y), "w": float(w), "h": float(h),
                    "text": text
                })

    # 1) Déduplique les boîtes en double (souvent une version "NUL" et une version labellisée)
    ocr_zones = _dedupe_boxes(ocr_zones)

    # 2) Regroupe par lignes (toutes les cases d'une ligne -> même row_index)
    ocr_zones = _assign_row_index_by_lines(ocr_zones)

    return {"ocr_raw": ocr_raw, "ocr_zones": ocr_zones}


if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) != 3:
            print(json.dumps({"ocr_raw": "", "ocr_zones": [], "error": "Bad arguments"}))
            sys.exit(1)

        pdf_file = sys.argv[1]
        json_file = sys.argv[2]
        data = run_invoice_labelmodel(pdf_file, json_file)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ocr_raw": "", "ocr_zones": [], "error": str(e)}))
        sys.exit(1)
