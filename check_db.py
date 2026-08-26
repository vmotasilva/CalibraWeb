import sqlite3
import json

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print('Auditoria tables:', [t for t in tables if 'auditoria' in t.lower()])

for t in [t for t in tables if 'auditoria' in t.lower()]:
    if 'auditoriaiso' in t.lower() and 'escopo' not in t.lower() and 'auditores' not in t.lower() and 'itens' not in t.lower() and 'resposta' not in t.lower() and 'avaliacao' not in t.lower():
        print('=== Table:', t)
        cols = [col[1] for col in cursor.execute(f"PRAGMA table_info({t});").fetchall()]
        rows = cursor.execute(f"SELECT * FROM {t}").fetchall()
        for r in rows:
            d = dict(zip(cols, r))
            print(json.dumps({k: str(v) for k, v in d.items()}, indent=2, ensure_ascii=False))
