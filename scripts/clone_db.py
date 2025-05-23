import os

# Configuration
source_db = "metal-prod-18"
target_db = "18-clone"
pg_user = "odoo"
pg_host = "localhost"
pg_port = "5432"

# Commandes
drop_cmd = f"dropdb -U {pg_user} -h {pg_host} -p {pg_port} --if-exists {target_db}"
dump_cmd = f"pg_dump -U {pg_user} -h {pg_host} -p {pg_port} -Fc {source_db} -f /tmp/{source_db}.dump"
create_cmd = f"createdb -U {pg_user} -h {pg_host} -p {pg_port} {target_db}"
restore_cmd = f"pg_restore -U {pg_user} -h {pg_host} -p {pg_port} -d {target_db} /tmp/{source_db}.dump"

# Exécution
print("🧨 Suppression de l'ancienne base clone (si elle existe)...")
os.system(drop_cmd)

print("📦 Dumping base source...")
os.system(dump_cmd)

print("📂 Création de la base cible...")
os.system(create_cmd)

print("📥 Restauration dans la base cible...")
os.system(restore_cmd)

print("✅ Base clonée avec succès :", target_db)
