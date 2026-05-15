import os

import psycopg2
conn_str = os.environ.get("DATABASE_URL")
if not conn_str:
    raise SystemExit("Missing DATABASE_URL.")

print("Connecting...")
try:
    conn = psycopg2.connect(conn_str)
    print("Success!")
    conn.close()
except Exception as e:
    print("Failed:", str(e))
