# -*- coding: utf-8 -*-
"""
Répare un export Label Studio mal formé en JSON valide.
Usage:
  python3 repair_labelstudio_json.py <entree_ls.json> <sortie_propre.json>
"""
import sys, re, json

def _read_raw(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _preclean(raw: str) -> str:
    # 1) Supprime caractères de contrôle invisibles
    raw = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw)

    # 2) Corrige les flottants tronqués: "height":1.  -> "height":1.0
    raw = re.sub(r'(?P<num>\d+)\.(?P<tail>\s*[,}\]])', r'\g<num>.0\g<tail>', raw)

    # 3) Corrige les .] ou .} éventuels: 1.] -> 1.0]
    raw = re.sub(r'(?P<num>\d+)\.\s*\]', r'\g<num>.0]', raw)
    raw = re.sub(r'(?P<num>\d+)\.\s*\}', r'\g<num>.0}', raw)

    # 4) Remplace NaN/Infinity (non JSON) par null
    raw = re.sub(r'\bNaN\b', 'null', raw)
    raw = re.sub(r'\bInfinity\b', 'null', raw)
    raw = re.sub(r'\b-Infinity\b', 'null', raw)

    # 5) Supprime les virgules traînantes avant ] ou }
    raw = re.sub(r',(\s*[\]}])', r'\1', raw)

    return raw

def _try_json_parsers(raw: str):
    # A) json standard
    try:
        return json.loads(raw)
    except Exception:
        pass

    # B) demjson3 (très tolérant)
    try:
        import demjson3
        return demjson3.decode(raw, strict=False)
    except Exception:
        pass

    # C) json5 (tolérant aux trailing commas, etc.)
    try:
        import json5
        return json5.loads(raw)
    except Exception:
        pass

    # D) Dernière tentative: refermer top-level si c’est une liste/objet non terminé
    # Ajoute ']' ou '}' manquant dans quelques cas simples
    fixed = raw
    open_brackets = fixed.count('[') - fixed.count(']')
    open_braces = fixed.count('{') - fixed.count('}')
    if open_brackets > 0:
        fixed += ']' * open_brackets
    if open_braces > 0:
        fixed += '}' * open_braces
    try:
        return json.loads(fixed)
    except Exception:
        return None

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 repair_labelstudio_json.py <entree_ls.json> <sortie_propre.json>")
        sys.exit(1)

    src, dst = sys.argv[1], sys.argv[2]
    raw = _read_raw(src)
    raw = _preclean(raw)

    data = _try_json_parsers(raw)
    if data is None:
        print("❌ Impossible de réparer automatiquement ce JSON (trop endommagé).")
        sys.exit(2)

    # On réécrit en JSON propre et stable
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON réparé → {dst}")

if __name__ == "__main__":
    main()
