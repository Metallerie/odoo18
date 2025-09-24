ccl_regex = {
    "meta": {
        "update_count": 0,
        "last_update": None
    },
    "fields": {
        "invoice_number": {
            "patterns": [
                {"id": "1", "regex": r"(?:FACTURE|Facture)\s*(?:N°|No|Numéro)?\s*[:\-]?\s*([A-Z0-9\-\/]+)", "validated": True}
            ]
        },
        "invoice_date": {
            "patterns": [
                {"id": "1", "regex": r"(?:Date facture|Date)\s*[:\-]?\s*(\d{2}[\/\-]\d{2}[\/\-]\d{4})", "validated": True}
            ]
        },
        "siren": {
            "patterns": [
                {"id": "1", "regex": r"\b\d{9}\b", "validated": True}
            ]
        },
        "siret": {
            "patterns": [
                {"id": "1", "regex": r"\b\d{14}\b", "validated": True}
            ]
        },
        "tva_intracom": {
            "patterns": [
                {"id": "1", "regex": r"\bFR[0-9]{2}\s?\d{9}\b", "validated": True}
            ]
        },
        "iban": {
            "patterns": [
                {"id": "1", "regex": r"\bFR\d{2}(?:\s?\d{4}){5}(?:\s?[A-Z0-9]{2,})?\b", "validated": True}
            ]
        },
        "bic": {
            "patterns": [
                {"id": "1", "regex": r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", "validated": True}
            ]
        },
        "total_ht": {
            "patterns": [
                {"id": "1", "regex": r"(?:TOTAL\s+BRUT\s+H\.T\.|TOTAL\s+HT|Net\s+HT)\s*[:\-]?\s*([0-9.,]+)", "validated": True}
            ]
        },
        "total_tva": {
            "patterns": [
                {"id": "1", "regex": r"(?:TOTAL\s+T\.V\.A\.|TVA\s+TOTAL)\s*[:\-]?\s*([0-9.,]+)", "validated": True}
            ]
        },
        "total_ttc": {
            "patterns": [
                {"id": "1", "regex": r"(?:TOTAL\s+TTC|Net\s+à\s+payer|NET\s+À\s+PAYER)\s*[:\-]?\s*([0-9.,]+)", "validated": True}
            ]
        },
        "line_item": {
            "patterns": [
                {"id": "1", "regex": r"(\d{5,})\s+([A-Z0-9\s]+?)\s+([\d.,]+)\s+([A-Z]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d]+)?", "validated": True}
            ]
        }
    }
}
