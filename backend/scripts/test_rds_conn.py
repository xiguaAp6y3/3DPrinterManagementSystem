"""Fix 3DPMS database state: kill DBeaver session, set MULTI_USER, map user."""
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=rm-bp16606d541v6qslyoo.sqlserver.rds.aliyuncs.com,1432;"
    "DATABASE=master;"
    "UID=stdu_admin;"
    "PWD=xiguaAp6y3!;"
    "TrustServerCertificate=yes;"
    "Encrypt=yes;"
    "Connection Timeout=15;"
)

try:
    conn = pyodbc.connect(conn_str, timeout=15)
    conn.autocommit = True  # Required for ALTER DATABASE
    cursor = conn.cursor()

    # Check current state
    cursor.execute(
        "SELECT name, state_desc, user_access_desc "
        "FROM sys.databases WHERE name = '3DPMS'"
    )
    row = cursor.fetchone()
    print(f"Database: {row[0]}, State: {row[1]}, Access: {row[2]}")

    # Kill the session occupying 3DPMS
    cursor.execute(
        "SELECT session_id, login_name, host_name, program_name "
        "FROM sys.dm_exec_sessions WHERE database_id = DB_ID('3DPMS')"
    )
    sessions = cursor.fetchall()
    print(f"Active sessions: {len(sessions)}")
    for s in sessions:
        print(f"  SPID={s[0]}, Login={s[1]}, Host={s[2]}, Program={s[3]}")
        cursor.execute(f"KILL {s[0]}")
        print(f"  -> Killed SPID {s[0]}")

    # Set to MULTI_USER
    cursor.execute("ALTER DATABASE [3DPMS] SET MULTI_USER")
    print("Set MULTI_USER OK")

    # Verify
    cursor.execute(
        "SELECT user_access_desc FROM sys.databases WHERE name = '3DPMS'"
    )
    access = cursor.fetchone()[0]
    print(f"Access mode now: {access}")

    conn.close()

    # Now connect to 3DPMS and create user mapping
    print("\n--- Connecting to 3DPMS ---")
    conn2_str = conn_str.replace("DATABASE=master", "DATABASE=3DPMS")
    conn2 = pyodbc.connect(conn2_str, timeout=15)
    conn2.autocommit = True
    cursor2 = conn2.cursor()

    # Create user mapping
    cursor2.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'stdu_admin') "
        "CREATE USER stdu_admin FROM LOGIN stdu_admin"
    )
    print("User mapping created (or existed)")

    # Add to db_owner
    try:
        cursor2.execute("ALTER ROLE db_owner ADD MEMBER stdu_admin")
        print("Added to db_owner")
    except Exception as e:
        print(f"db_owner add: {e}")

    # List tables
    cursor2.execute("SELECT name FROM sys.tables ORDER BY name")
    tables = [r[0] for r in cursor2.fetchall()]
    print(f"\nTables in 3DPMS ({len(tables)}):")
    for t in tables:
        print(f"  {t}")

    conn2.close()

except Exception as e:
    print(f"FAILED: {type(e).__name__}")
    for item in e.args:
        print(repr(item)[:300])
