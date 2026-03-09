import psycopg2
conn_str = "postgresql://postgres:Al29minuto$@db.mlirsjgolmryywlfahuf.supabase.co:6543/postgres"
print("Connecting...")
try:
    conn = psycopg2.connect(conn_str)
    print("Success!")
    conn.close()
except Exception as e:
    print("Failed:", str(e))
