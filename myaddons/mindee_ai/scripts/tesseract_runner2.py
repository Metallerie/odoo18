def get_column_bounds(header_words):
    """Définit les colonnes par leurs positions X"""
    columns = {}
    for w in header_words:
        txt = w['text'].lower()
        if "réf" in txt:
            columns["Réf."] = w['left']
        elif "désign" in txt:
            columns["Désignation"] = w['left']
        elif "qté" in txt or "quantité" in txt:
            columns["Qté"] = w['left']
        elif "unité" in txt:
            columns["Unité"] = w['left']
        elif "prix" in txt:
            columns["Prix Unitaire"] = w['left']
        elif "montant" in txt:
            columns["Montant"] = w['left']
        elif "tva" in txt:
            columns["TVA"] = w['left']

    # Trie les colonnes de gauche à droite
    sorted_cols = dict(sorted(columns.items(), key=lambda x: x[1]))
    return list(sorted_cols.keys()), list(sorted_cols.values())

def map_row_to_columns(words, headers, bounds):
    """Découpe une ligne en colonnes avec X"""
    row = {h: "" for h in headers}
    for w in words:
        x = w['left']
        for i, h in enumerate(headers):
            if i == len(bounds) - 1 or (x >= bounds[i] and x < bounds[i+1]):
                row[h] += " " + w['text']
                break
    # Nettoie
    row = {k: v.strip() for k, v in row.items()}
    return row
