import sys

from sqlalchemy import create_engine, inspect

from app.utils.database import build_rls_statements, execute_ddl


def main():
    """
    Applies Row Level Security (RLS) directly to the PostgreSQL database tables.
    Usage: python apply_rls.py <DATABASE_URL>
    """
    if len(sys.argv) < 2:
        print("Usage: python apply_rls.py <DATABASE_URL>")
        sys.exit(1)

    db_url = sys.argv[1]
    # Standard replacement for older postgres URLs
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print("Connecting to database...")
    try:
        engine = create_engine(db_url)
        tables = set(inspect(engine).get_table_names())
        statements = build_rls_statements(engine, tables)

        if statements:
            print("Enabling Row Level Security (RLS) on public tables...")
            for statement in statements:
                print(f"Executing: {statement}")
            execute_ddl(engine, statements)

        print("\nSuccessfully updated Row Level Security configurations!")
    except Exception as e:
        print(f"\nError applying RLS: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
