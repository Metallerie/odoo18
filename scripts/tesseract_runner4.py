def parse_fields(text, data):
    """Extrait les champs via toutes les regex définies dans ccl_regex.json"""
    parsed = {}
    for key, patterns in regex_patterns.get("fields", {}).items():
        if not isinstance(patterns, list):
            patterns = [patterns]  # sécurité si jamais une seule regex

        value, y_coord, used_pattern = None, None, None
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                # ✅ Sécurité sur group()
                if match.lastindex and match.lastindex >= 1:
                    value = match.group(1).strip()
                else:
                    value = match.group(0).strip()

                # retrouver coord Y
                for i, word in enumerate(data["text"]):
                    if value in word:
                        y_coord = data["top"][i]
                        break

                used_pattern = pattern
                break  # on arrête au premier match

        if value:
            parsed[key] = {"value": value, "y": y_coord}
            print(f"[DEBUG] Champ '{key}' trouvé : {value} (regex: {used_pattern})")
        else:
            print(f"[DEBUG] Champ '{key}' introuvable")

    return parsed
