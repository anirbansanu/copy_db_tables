import mysql.connector
from mysql.connector import errorcode
import os
from datetime import datetime
import pprint
import logging
import json

class MySQLSchemaComparator:
    """
    Compares schemas between a source and target MySQL database,
    identifies parent-child relationships, checks for business_id,
    and builds a structure for tables to copy.
    """
    def __init__(self, host, user, password, source_db, target_db):
        self.source_config = {
            'host': host,
            'user': user,
            'password': password,
            'database': source_db
        }
        self.target_config = {
            'host': host,
            'user': user,
            'password': password,
            'database': target_db
        }
        self.source_conn = None
        self.target_conn = None
        self.source_cursor = None
        self.target_cursor = None

        # Set up logging
        self.setup_logging()

    def setup_logging(self):
        """Set up logging directories and files."""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.log_dir = os.path.join(os.getcwd(), 'analyzer_log', timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        self.success_log_path = os.path.join(self.log_dir, 'success.log')
        self.failed_log_path = os.path.join(self.log_dir, 'failed.log')

    def log_success(self, message):
        """Log a success message to success.log."""
        with open(self.success_log_path, 'a') as log_file:
            log_file.write(message + '\n')

    def log_failure(self, message):
        """Log a failure message to failed.log."""
        with open(self.failed_log_path, 'a') as log_file:
            log_file.write(message + '\n')

    def save_results_to_json(self, results):
        """Save the results to a JSON file in the timestamped log directory."""
        json_file_path = os.path.join(self.log_dir, 'tables_to_copy.json')
        try:
            with open(json_file_path, 'w') as json_file:
                json.dump(results, json_file, indent=4)
            self.log_success(f"Results successfully saved to {json_file_path}")
        except Exception as e:
            self.log_failure(f"Failed to save results to JSON: {e}")

    def connect(self):
        """Establish connections to both source and target databases."""
        try:
            self.source_conn = mysql.connector.connect(**self.source_config)
            self.target_conn = mysql.connector.connect(**self.target_config)
            self.source_cursor = self.source_conn.cursor(dictionary=True)
            self.target_cursor = self.target_conn.cursor(dictionary=True)
            success_message = f"Connected to {self.source_config['database']} and {self.target_config['database']}"
            print(success_message)
            self.log_success(success_message)
        except mysql.connector.Error as err:
            error_message = f"Database connection error: {err}"
            print(error_message)
            self.log_failure(error_message)
            raise

    def get_tables(self, cursor, db_name):
        """Retrieve all table names in the given database."""
        try:
            cursor.execute(f"SHOW TABLES FROM `{db_name}`")
            key = f'Tables_in_{db_name}'
            tables = [row[key] for row in cursor.fetchall()]
            self.log_success(f"Retrieved tables from {db_name}: {tables}")
            return tables
        except mysql.connector.Error as err:
            error_message = f"Failed to retrieve tables from {db_name}: {err}"
            # print(error_message)
            self.log_failure(error_message)
            return []

    def get_foreign_keys(self):
        """Retrieve foreign key constraints from source database."""
        try:
            query = """
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
            """
            self.source_cursor.execute(query, (self.source_config['database'],))
            fks = self.source_cursor.fetchall()
            relations = {}
            for row in fks:
                parent = row['REFERENCED_TABLE_NAME']
                child = row['TABLE_NAME']
                relations.setdefault(parent, []).append({
                    'child_table': child,
                    'child_foreign_key': row['COLUMN_NAME']
                })
            self.log_success(f"Retrieved foreign key relationships: {relations}")
            return relations
        except mysql.connector.Error as err:
            error_message = f"Failed to retrieve foreign keys: {err}"
            # print(error_message)
            self.log_failure(error_message)
            return {}

    def has_column(self, cursor, db_name, table, column):
        """Check if a column exists in a table."""
        try:
            query = """
                SELECT 1
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
                LIMIT 1
            """
            cursor.execute(query, (db_name, table, column))
            exists = cursor.fetchone() is not None
            self.log_success(f"Checked column '{column}' in table '{table}': Exists = {exists}")
            return exists
        except mysql.connector.Error as err:
            error_message = f"Failed to check column '{column}' in table '{table}': {err}"
            print(error_message)
            self.log_failure(error_message)
            return False

    def get_columns(self, cursor, db_name, table):
        """Retrieve column names for a table."""
        try:
            query = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """
            cursor.execute(query, (db_name, table))
            columns = {row['COLUMN_NAME'] for row in cursor.fetchall()}  # Fetch all rows
            self.log_success(f"Retrieved columns for table '{table}': {columns}")
            return columns
        except mysql.connector.Error as err:
            error_message = f"Failed to retrieve columns for table '{db_name}'.'{table}': {err}"
            print(error_message)
            self.log_failure(error_message)
            return set()
        finally:
            # Clear any unread results
            while cursor.nextset():
                pass

    def get_primary_key(self, cursor, db_name, table):
        """Retrieve primary key column for a table, or empty string if none."""
        try:
            query = """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY'
            """
            cursor.execute(query, (db_name, table))
            result = cursor.fetchone()
            primary_key = result['COLUMN_NAME'] if result else ''
            self.log_success(f"Retrieved primary key for table '{table}': {primary_key}")
            return primary_key
        except mysql.connector.Error as err:
            error_message = f"Failed to retrieve primary key for table '{table}': {err}"
            # print(error_message)
            self.log_failure(error_message)
            return ''

    def compare_columns(self, table):
        """Compare columns of the same-named table in source and target DB."""
        src_cols = self.get_columns(self.source_cursor, self.source_config['database'], table)
        tgt_cols = self.get_columns(self.target_cursor, self.target_config['database'], table)
        match = src_cols == tgt_cols
        self.log_success(f"Compared columns for table '{table}': Match = {match}")
        return match

    def build_tables_to_copy(self):
        """Main method to assemble the tables_to_copy structure."""
        self.connect()
        source_db = self.source_config['database']
        tables = self.get_tables(self.source_cursor, source_db)
        relations = self.get_foreign_keys()

        tables_to_copy = []
        for table in tables:
            parent_key = self.get_primary_key(self.source_cursor, source_db, table)
            has_biz = self.has_column(self.source_cursor, source_db, table, 'business_id')
            filter_parent = f"WHERE business_id IN (43, 44)" if has_biz else ''
            match_cols = self.compare_columns(table)

            children_list = []
            for rel in relations.get(table, []):
                fk = rel['child_foreign_key']
                if has_biz:
                    child_filter = f"{fk} IN (SELECT id FROM {table} {filter_parent})"
                else:
                    child_filter = ''
                children_list.append({
                    'child_table': rel['child_table'],
                    'child_foreign_key': fk,
                    'filter_for_child': child_filter
                })

            tables_to_copy.append({
                'parent_table': table,
                'children': bool(children_list),
                'child_tables': children_list,
                'parent_key': parent_key,
                'has_business_id': has_biz,
                'filter_for_parent': filter_parent,
                'match_columns': match_cols
            })

        return tables_to_copy


if __name__ == '__main__':
    # Configuration: adjust host, user, password as needed
    comparator = MySQLSchemaComparator(
        host='localhost',
        user='root',
        password='root',
        source_db='orbite_db',
        target_db='srihari_db_new'
    )
    result = comparator.build_tables_to_copy()
    # pprint.pprint(result)
    comparator.save_results_to_json(result)