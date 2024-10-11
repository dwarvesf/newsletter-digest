import subprocess
import sys

def run_migrations():
    try:
        # Check current revision
        result = subprocess.run(['alembic', 'current'], capture_output=True, text=True)
        print("Current database revision:")
        print(result.stdout)

        # Check for pending migrations
        result = subprocess.run(['alembic', 'heads'], capture_output=True, text=True)
        latest_revision = result.stdout.strip()

        result = subprocess.run(['alembic', 'current'], capture_output=True, text=True)
        current_revision = result.stdout.strip().split(' ')[0]

        if latest_revision != current_revision:
            print("Pending migrations found. Applying migrations...")
            result = subprocess.run(['alembic', 'upgrade', 'head'], check=True)
            print("Migrations applied successfully.")
        else:
            print("Database is up to date. No migrations to apply.")

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while running migrations: {e}")
        return False

if __name__ == "__main__":
    success = run_migrations()
    if not success:
        print("Migration script failed. Please check the logs and try again.")
        sys.exit(1)
    else:
        print("Migration script completed successfully.")
