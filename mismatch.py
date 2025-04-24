import mysql.connector
import os
from datetime import datetime
import json


class FileManager:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_json(self):
        """Load JSON data from the file."""
        try:
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"File '{self.file_path}' not found.")

            with open(self.file_path, 'r') as file:
                data = json.load(file)
                print(f"Successfully loaded data from '{self.file_path}'.")
                return data
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return []  # Default to an empty list if the file is missing
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON in '{self.file_path}': {e}")
            return []  # Default to an empty list if JSON is invalid
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []  # Default to an empty list for any other exceptions

    def show_filtered_tables(self, tables_to_copy):
        """Display filtered tables to copy."""
        filtered_tables = []
        for table in tables_to_copy:
            parent_table = table.get('parent_table')
            child_tables = table.get('child_tables', [])
            filtered_tables.append(parent_table)
            for child in child_tables:
                child_table = child.get('child_table')
                filtered_tables.append(child_table)
        print(f"All table names: {filtered_tables}")
        return filtered_tables


class DatabaseManager:
    def __init__(self, db_config, source_db, target_db):
        self.db_config = db_config
        self.source_db = source_db
        self.target_db = target_db
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish a database connection."""
        try:
            self.conn = mysql.connector.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            print("Database connection established.")
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            raise

    def close(self):
        """Close the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn and self.conn.is_connected():
            self.conn.close()
        print("Database connection closed.")

    def get_columns(self, db, table):
        """Retrieve column names for a table."""
        query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """
        self.cursor.execute(query, (db, table))
        return [row[0] for row in self.cursor.fetchall()]


class TableComparator:
    def __init__(self, db_manager, log_dir):
        self.db_manager = db_manager
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

    def log_to_file(self, filename, content):
        """Write content to a log file."""
        with open(os.path.join(self.log_dir, filename), "a") as f:
            f.write(content + "\n")

    def compare_tables(self, tables_to_compare):
        """Compare columns of tables between source and target databases."""
        for table_name in tables_to_compare:
            try:
                source_columns = self.db_manager.get_columns(self.db_manager.source_db, table_name)
                target_columns = self.db_manager.get_columns(self.db_manager.target_db, table_name)

                if source_columns != target_columns:
                    content = (
                        f"Table: {table_name}\n"
                        f"Source ({self.db_manager.source_db}.{table_name}) columns:\n{source_columns}\n\n"
                        f"Target ({self.db_manager.target_db}.{table_name}) columns:\n{target_columns}\n\n"
                        "----------------------------------------\n"
                    )
                    self.log_to_file("columns_mismatch.log", content)
                    print(f"Column mismatch detected for table '{table_name}'. Logged to columns_mismatch.log")
                else:
                    self.log_to_file("success.log", f"Success: Columns match exactly for table '{table_name}'.")
                    print(f"Success: Columns match for table '{table_name}'. Logged to success.log")
            except mysql.connector.Error as err:
                self.log_to_file("error.log", f"MySQL Error for table '{table_name}': {err}")
                print(f"MySQL Error for table '{table_name}': {err}")


if __name__ == "__main__":
    # Database connection configs
    db_config = {
        "user": "root",
        "password": "root",
        "host": "localhost",
    }

    source_db = "orbite_db"
    target_db = "srihari_db"

    # Load tables to compare from JSON file
    file_manager = FileManager("tables_to_copy.json")
    tables_to_copy = file_manager.load_json()
    tables_to_compare = file_manager.show_filtered_tables(tables_to_copy)

    # Timestamped directory for logs
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_dir = f"mismatch_logs/{timestamp}"

    # Initialize database manager and table comparator
    db_manager = DatabaseManager(db_config, source_db, target_db)
    table_comparator = TableComparator(db_manager, log_dir)

    try:
        db_manager.connect()
        table_comparator.compare_tables(tables_to_compare)
    finally:
        db_manager.close()