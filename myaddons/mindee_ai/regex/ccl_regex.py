{
  "CCL": {
    "invoice_number": {
      "label": "Numéro de facture",
      "pattern": "FACTURE\\s*(?:N°|No|Numéro)?\\s*[:\\-]?\\s*([A-Z0-9\\-\\/]+)"
    },
    "invoice_date": {
      "label": "Date de facture",
      "pattern": "Date\\s+facture\\s*[:\\-]?\\s*(\\d{2}[\\/\\-]\\d{2}[\\/\\-]\\d{4})"
    },
    "client_code": {
      "label": "Code client",
      "pattern": "Client\\s*:?\\s*(\\d+)"
    },
    "line_item": {
      "label": "Ligne produit",
      "pattern": "(\\d{5,})\\s+([A-Z0-9\\s]+?)\\s+([0-9.,]+)\\s+([A-Z]+)\\s+([0-9.,]+)\\s+([0-9.,]+)\\s+([0-9]+)?"
    },
    "total_ht": {
      "label": "Total HT",
      "pattern": "TOTAL\\s+BRUT\\s+H\\.T\\.?\\s*([0-9.,]+)"
    },
    "total_tva": {
      "label": "Total TVA",
      "pattern": "TOTAL\\s+T\\.V\\.A\\.?\\s*([0-9.,]+)"
    },
    "total_ttc": {
      "label": "Total TTC",
      "pattern": "(?:NET\\s+À\\s+PAYER|Net\\s+à\\s+payer)\\s*([0-9.,]+)"
    }
  }
}

