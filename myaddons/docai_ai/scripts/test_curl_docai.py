curl -X POST \
  -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d "{
        'rawDocument': {
          'content': '$(base64 /data/Documents/factures_archive/Facture_CCL_153880.pdf)',
          'mimeType': 'application/pdf'
        }
      }" \
  "https://eu-documentai.googleapis.com/v1/projects/889157590963/locations/eu/processors/a228740c1efe755d:process"
