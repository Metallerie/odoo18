# parser_invoice_lines.py
# Entrée attendue : OCR output sous forme de liste de "words" :
# [{ "text": "Tube", "bbox": [ [x0,y0],[x1,y1] ] }, ...]
# ou liste de "lines" avec "words" inside (adaptable).
# Retour : liste de lignes produits détectées : {description, qty, unit, unit_price, total, tva, raw}

import re
from statistics import median
from collections import defaultdict

# Regex pour nombres en format FR (ex: 1 234,56 ou 1234,56 ou 100)
num_re = re.compile(r'[-+]?\d{1,3}(?:[ \u00A0]\d{3})*(?:,\d+)?|\d+(?:,\d+)?')

# Pattern heuristique pour trouver QTE / PU / MONTANT dans une phrase
line_pattern = re.compile(
    r'(?P<ref>[\w\-\/\.]{1,30})?.{0,30}?'
    r'(?P<qty>\d+(?:[ ,.]\d+)?)\s*(?P<unit>m|ml|kg|pcs|u|un|pc|L|l)?[^\d]{0,6}'
    r'(?P<unit_price>\d[\d \u00A0,]*\d(?:,\d+)?)?.{0,10}'
    r'(?P<total>\d[\d \u00A0,]*\d(?:,\d+)?)'
    , re.I)

def normalize_num(s):
    if s is None: return None
    s = s.replace('\u00A0', ' ').strip()
    s = s.replace(' ', '')
    s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return None

def bbox_center(bbox):
    (x0,y0),(x1,y1) = bbox
    return ((x0+x1)/2, (y0+y1)/2)

def group_words_into_lines(words, y_thresh=0.02):
    # words: list of dicts with text and bbox
    # y_thresh relative to page height (assume coords normalized 0-1 or consistent)
    words_sorted = sorted(words, key=lambda w: bbox_center(w['bbox'])[1])
    lines = []
    for w in words_sorted:
        cy = bbox_center(w['bbox'])[1]
        placed = False
        for line in lines:
            ly = median([bbox_center(x['bbox'])[1] for x in line])
            if abs(ly - cy) <= y_thresh:
                line.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])
    # sort words left->right inside each line
    line_texts = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: bbox_center(w['bbox'])[0])
        text = " ".join([w['text'] for w in line_sorted]).strip()
        xs = [bbox_center(w['bbox'])[0] for w in line_sorted]
        line_texts.append({'words': line_sorted, 'text': text, 'x_positions': xs})
    return line_texts

def detect_columns(lines, min_cols=2, max_cols=6, x_gap_thresh=0.03):
    # Build list of all x centers, cluster by gaps to find column separators
    xs_all = []
    for ln in lines:
        xs_all.extend(ln['x_positions'])
    if not xs_all:
        return []
    xs_sorted = sorted(xs_all)
    # compute gaps
    gaps = [(xs_sorted[i+1]-xs_sorted[i], i) for i in range(len(xs_sorted)-1)]
    # choose large gaps as separators
    gaps_sorted = sorted(gaps, key=lambda x: -x[0])
    separators = []
    # try up to max_cols-1 separators using threshold
    for gap, idx in gaps_sorted:
        if gap >= x_gap_thresh:
            separators.append((gap, xs_sorted[idx], xs_sorted[idx+1]))
    # create column x centers by grouping
    separators_x = sorted([s[1] for s in separators])
    # build column boundaries
    cols = []
    prev = -1.0
    for sep in separators_x:
        cols.append((prev, sep))
        prev = sep
    cols.append((prev, 2.0))
    # compute column centers
    centers = [ (a+b)/2 for a,b in cols ]
    return centers

def assign_to_columns(line, centers):
    # assign each word to nearest center
    cells = defaultdict(list)
    for w in line['words']:
        x = bbox_center(w['bbox'])[0]
        # find nearest center
        best_i = min(range(len(centers)), key=lambda i: abs(centers[i]-x))
        cells[best_i].append(w['text'])
    # join
    return {i: " ".join(cells[i]).strip() for i in range(len(centers))}

def extract_lines_from_text_lines(lines):
    results = []
    # try to detect header that contains typical column titles to find indices
    header_idx = None
    for i,ln in enumerate(lines[:8]):
        t = ln['text'].lower()
        if 'désignation' in t or 'réf' in t or 'qté' in t or 'prix unitaire' in t or 'montant' in t:
            header_idx = i
            break
    # build column centers
    centers = detect_columns(lines)
    # fallback: try to create 4 columns if none found
    if not centers:
        # estimate by equal spacing using typical invoice width normalized [0..1]
        centers = [0.15, 0.55, 0.75, 0.9]

    for i, ln in enumerate(lines):
        if i == header_idx:
            continue
        text = ln['text']
        # first, try regex match
        m = line_pattern.search(text)
        if m:
            qty = normalize_num(m.group('qty'))
            unit = m.group('unit')
            unit_price = normalize_num(m.group('unit_price'))
            total = normalize_num(m.group('total'))
            descr = text[:m.start('qty')].strip()
            results.append({
                'description': descr or text,
                'qty': qty,
                'unit': unit,
                'unit_price': unit_price,
                'total': total,
                'raw': text
            })
            continue
        # else fallback: use column extraction
        cells = assign_to_columns(ln, centers)
        # heuristics: assume last cell contains total, second last unit price, first a ref/desc
        last = cells.get(len(centers)-1, '')
        second_last = cells.get(len(centers)-2, '')
        first_cells = " ".join([cells.get(i,'') for i in range(0, max(1, len(centers)-3))])
        total_num = None
        unit_price_num = None
        # extract numbers from last and second last
        nm = num_re.findall(last)
        if nm:
            total_num = normalize_num(nm[-1])
        nm2 = num_re.findall(second_last)
        if nm2:
            unit_price_num = normalize_num(nm2[-1])
        # try qty in remaining cells
        qty = None
        for i in range(len(centers)-3, len(centers)-1):
            c = cells.get(i, '')
            nmq = num_re.findall(c)
            if nmq:
                qty = normalize_num(nmq[0])
                break
        results.append({
            'description': first_cells.strip() or text,
            'qty': qty,
            'unit': None,
            'unit_price': unit_price_num,
            'total': total_num,
            'raw': text,
            'cells': cells
        })
    # filter vague results: keep those with a numeric total or a qty
    filtered = [r for r in results if (r.get('total') is not None) or (r.get('qty') is not None)]
    return filtered

# API function to call
def parse_invoice_lines_from_ocr_words(words, page_height_normalized=True):
    """
    words: list of dicts {text,bbox:[[x0,y0],[x1,y1]]}
    If bbox are in pixels, you should normalize Y/X by dividing by page height/width first.
    """
    # If coords are in pixels, detect and normalize (simple heuristic)
    max_x = max((bbox_center(w['bbox'])[0] for w in words), default=1.0)
    max_y = max((bbox_center(w['bbox'])[1] for w in words), default=1.0)
    # If the max coords >> 1 assume pixel coords and normalize
    if max_x > 2 or max_y > 2:
        # detect page width/height
        xs = [bbox_center(w['bbox'])[0] for w in words]
        ys = [bbox_center(w['bbox'])[1] for w in words]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        # normalize in-place
        for w in words:
            (x0,y0),(x1,y1) = w['bbox']
            w['bbox'] = [[(x0-minx)/(maxx-minx), (y0-miny)/(maxy-miny)],
                         [(x1-minx)/(maxx-minx), (y1-miny)/(maxy-miny)]]

    lines = group_words_into_lines(words, y_thresh=0.015)
    parsed = extract_lines_from_text_lines(lines)
    return parsed

# --- exemple d'utilisation ---
if __name__ == "__main__":
    # test minimal: construire words depuis ton OCR bbox runner
    sample = [
        {'text':'REF 123','bbox':[[50,100],[200,120]]},
        {'text':'Tube 40x40','bbox':[[210,100],[480,120]]},
        {'text':'2','bbox':[[490,100],[520,120]]},
        {'text':'m','bbox':[[525,100],[540,120]]},
        {'text':'10,00','bbox':[[700,100],[760,120]]},
        {'text':'20,00','bbox':[[820,100],[880,120]]},
    ]
    # normalize pixels -> le parse gère la normalisation
    out = parse_invoice_lines_from_ocr_words(sample)
    from pprint import pprint
    pprint(out)
