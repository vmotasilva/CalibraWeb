import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get the schema for procedures_registrotreinamento table
cursor.execute("PRAGMA table_info(procedures_registrotreinamento)")
columns = cursor.fetchall()

print("Columns in procedures_registrotreinamento:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Check if ativo column exists
ativo_exists = any(col[1] == 'ativo' for col in columns)
print(f"\n✓ Column 'ativo' exists!" if ativo_exists else "\n✗ Column 'ativo' NOT found")

conn.close()
