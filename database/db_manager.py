import sqlite3
import os
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path='database/attendance.db'):
        self.db_path = db_path
        self._ensure_db_directory()
        self.conn = None
        self.cursor = None

    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def connect(self):
        """Connect to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self.conn

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def execute_script(self, script_path):
        """Execute an SQL script file"""
        with open(script_path, 'r') as f:
            script = f.read()
        self.cursor.executescript(script)
        self.conn.commit()

    def initialize_database(self):
        """Initialize or update the database schema"""
        try:
            self.connect()
            schema_path = Path('database/schemas/schema.sql')
            
            if not schema_path.exists():
                raise FileNotFoundError(f"Schema file not found at {schema_path}")
            
            print("Applying database schema...")
            self.execute_script(schema_path)
            print("Database schema applied successfully!")

        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self.close()

    def reset_database(self):
        """Reset the database by dropping all tables and reapplying schema"""
        try:
            self.connect()
            
            # Get all tables
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in self.cursor.fetchall()]

            # Drop all tables
            for table in tables:
                self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
            self.conn.commit()

            print("Database reset complete!")
            
            # Reapply schema
            self.initialize_database()

        except Exception as e:
            print(f"Error resetting database: {str(e)}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self.close()

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.initialize_database() 