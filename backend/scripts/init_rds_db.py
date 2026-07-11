"""Execute SQL scripts (001-003) on the Aliyun RDS database.

Splits SQL by GO batches and executes them one by one.
Drops existing tables first to ensure clean state.
"""
import os
import pyodbc

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "sql")

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=rm-bp16606d541v6qslyoo.sqlserver.rds.aliyuncs.com,1432;"
    "DATABASE=3DPMS;"
    "UID=stdu_admin;"
    "PWD=xiguaAp6y3!;"
    "TrustServerCertificate=yes;"
    "Encrypt=yes;"
    "Connection Timeout=30;"
)


def split_batches(sql: str) -> list[str]:
    """Split SQL script into batches by GO statements."""
    batches = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.upper() == "GO":
            if current:
                batches.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        batches.append("\n".join(current))
    return batches


def execute_script(conn, filepath: str) -> None:
    """Execute a SQL file, splitting by GO batches."""
    with open(filepath, encoding="utf-8-sig") as f:
        sql = f.read()

    batches = split_batches(sql)
    print(f"\n{'='*60}")
    print(f"Executing: {os.path.basename(filepath)} ({len(batches)} batches)")
    print(f"{'='*60}")

    cursor = conn.cursor()
    success = 0
    failed = 0
    for i, batch in enumerate(batches, 1):
        batch = batch.strip()
        if not batch:
            continue
        try:
            cursor.execute(batch)
            conn.commit()
            success += 1
        except Exception as e:
            err_msg = str(e)[:200]
            # Skip "already exists" errors for idempotency
            if "already an object named" in err_msg or "already exists" in err_msg:
                print(f"  Batch {i}: SKIP (already exists)")
            else:
                print(f"  Batch {i}: ERROR - {err_msg}")
                failed += 1
            conn.rollback()

    print(f"  Result: {success} success, {failed} failed")


def main():
    print("Connecting to Aliyun RDS SQL Server...")
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.autocommit = True
    cursor = conn.cursor()

    # Check current tables
    cursor.execute("SELECT COUNT(*) FROM sys.tables")
    table_count = cursor.fetchone()[0]
    print(f"Current tables: {table_count}")

    if table_count > 0:
        print("\nDropping existing tables and sequences...")
        # Drop all foreign keys first
        cursor.execute(
            "SELECT 'ALTER TABLE [' + s.name + '].[' + t.name + '] DROP CONSTRAINT [' + c.name + ']'"
            " FROM sys.foreign_keys c "
            " JOIN sys.tables t ON c.parent_object_id = t.object_id"
            " JOIN sys.schemas s ON t.schema_id = s.schema_id"
        )
        fks = [r[0] for r in cursor.fetchall()]
        for fk in fks:
            try:
                cursor.execute(fk)
            except Exception:
                pass

        # Drop all tables
        cursor.execute(
            "SELECT 'DROP TABLE [' + s.name + '].[' + t.name + ']'"
            " FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id"
        )
        drops = [r[0] for r in cursor.fetchall()]
        for d in drops:
            try:
                cursor.execute(d)
                print(f"  Dropped: {d}")
            except Exception as e:
                print(f"  Drop failed: {e}")

        # Drop all sequences
        cursor.execute(
            "SELECT 'DROP SEQUENCE [' + s.name + '].[' + seq.name + ']'"
            " FROM sys.sequences seq JOIN sys.schemas s ON seq.schema_id = s.schema_id"
        )
        seqs = [r[0] for r in cursor.fetchall()]
        for sq in seqs:
            try:
                cursor.execute(sq)
            except Exception:
                pass

        print(f"Dropped {len(drops)} tables, {len(seqs)} sequences")

    conn.close()

    # Reconnect with autocommit for script execution
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.autocommit = True

    # Execute scripts
    scripts = [
        "001_create_tables.sql",
        "002_create_triggers.sql",
        "003_seed_dev.sql",
    ]

    for script in scripts:
        filepath = os.path.join(DB_DIR, script)
        if os.path.exists(filepath):
            execute_script(conn, filepath)
        else:
            print(f"WARNING: {script} not found at {filepath}")

    # Final verification
    print(f"\n{'='*60}")
    print("Verification")
    print(f"{'='*60}")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sys.tables")
    print(f"Total tables: {cursor.fetchone()[0]}")
    cursor.execute("SELECT name FROM sys.tables ORDER BY name")
    for row in cursor.fetchall():
        print(f"  {row[0]}")

    # Check admin user
    cursor.execute("SELECT username, display_name, role FROM staff_users")
    for row in cursor.fetchall():
        print(f"Admin user: {row[0]}, Name: {row[1]}, Role: {row[2]}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
