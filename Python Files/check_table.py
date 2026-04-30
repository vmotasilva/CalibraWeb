import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rh_colaborador_pacotes_treinamento'")
result = cursor.fetchone()
if result:
    print('✓ Table rh_colaborador_pacotes_treinamento exists!')
else:
    print('✗ Table rh_colaborador_pacotes_treinamento NOT found')
conn.close()
