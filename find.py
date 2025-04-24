from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.engine import reflection
import os
import logging
import pprint
from datetime import datetime


class DatabaseInspector:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        self.inspector = inspect(self.engine) 

    def get_all_tables(self):
        """Retrieve all table names from the database."""
        return self.inspector.get_table_names()

    def get_foreign_keys(self, table_name):
        """Retrieve foreign key constraints for a given table."""
        return self.inspector.get_foreign_keys(table_name)

    def get_primary_key(self, table_name):
        """Retrieve the primary key column for a given table."""
        pk_constraint = self.inspector.get_pk_constraint(table_name)
        constrained_columns = pk_constraint.get('constrained_columns', [])
        return constrained_columns[0] if constrained_columns else None


class TableRelationshipBuilder:
    def __init__(self, database_inspector, business_ids, log_dir):
        self.database_inspector = database_inspector
        self.business_ids = business_ids
        self.id_list_str = ", ".join(str(i) for i in business_ids)
        self.warning_log_path = os.path.join(log_dir, "warnings.log")
        self.setup_logging()

    def setup_logging(self):
        """Set up logging for warnings."""
        self.warning_log = open(self.warning_log_path, "w")

    def log_warning(self, message):
        """Log a warning message to the warning log file."""
        self.warning_log.write(message + "\n")
        self.warning_log.flush()

    def build_parent_child_mapping(self):
        """Build a mapping of parent tables to their child relationships."""
        all_tables = self.database_inspector.get_all_tables()
        parent_children = {table: [] for table in all_tables}

        for child_table in all_tables:
            foreign_keys = self.database_inspector.get_foreign_keys(child_table)
            for fk in foreign_keys:
                parent_table = fk.get('referred_table')
                if parent_table in parent_children:
                    parent_children[parent_table].append({
                        'child_table': child_table,
                        'foreign_key_column': fk.get('constrained_columns', [None])[0]
                    })

        return parent_children

    def construct_tables_to_copy(self):
        """Construct the list of dictionaries for tables to copy."""
        parent_children = self.build_parent_child_mapping()
        all_tables = self.database_inspector.get_all_tables()
        tables_to_copy = []

        for parent_table in all_tables:
            parent_key = self.database_inspector.get_primary_key(parent_table)
            if not parent_key:
                warning_message = f"Warning: Table '{parent_table}' does not have a primary key. Skipping."
                print(warning_message)
                self.log_warning(warning_message)
                continue

            children_info = parent_children.get(parent_table, [])
            entry = {
                'parent_table': parent_table,
                'children': bool(children_info),
                'parent_key': parent_key,
                'filter_for_parent': f"WHERE business_id IN ({self.id_list_str})",
                'match_columns': True
            }

            if children_info:
                child_entries = []
                for child in children_info:
                    child_entries.append({
                        'child_table': child['child_table'],
                        'child_foreign_key': child['foreign_key_column'],
                        'filter_for_child': (
                            f"{child['foreign_key_column']} IN (SELECT "
                            f"{entry['parent_key']} FROM {parent_table} "
                            f"WHERE business_id IN ({self.id_list_str}))"
                        )
                    })
                entry['child_tables'] = child_entries

            tables_to_copy.append(entry)

        return tables_to_copy


class TableCopyManager:
    def __init__(self, database_url, business_ids, log_dir):
        self.database_inspector = DatabaseInspector(database_url)
        self.relationship_builder = TableRelationshipBuilder(self.database_inspector, business_ids, log_dir)
        self.log_dir = log_dir
        self.tables_to_copy_path = os.path.join(log_dir, "tables_to_copy.txt")
        self.error_log_path = os.path.join(log_dir, "errors.log")
        self.setup_logging()

    def setup_logging(self):
        """Set up logging for errors."""
        self.error_log = open(self.error_log_path, "w")

    def log_error(self, message):
        """Log an error message to the error log file."""
        self.error_log.write(message + "\n")
        self.error_log.flush()

    def write_tables_to_copy(self, tables_to_copy):
        """Write the tables_to_copy list to a file."""
        with open(self.tables_to_copy_path, "w") as file:
            file.write(pprint.pformat(tables_to_copy))

    def get_tables_to_copy(self):
        """Get the list of tables to copy."""
        try:
            tables_to_copy = self.relationship_builder.construct_tables_to_copy()
            self.write_tables_to_copy(tables_to_copy)
            return tables_to_copy
        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(error_message)
            self.log_error(error_message)
            raise


if __name__ == '__main__':
    # Configuration: update with your database connection string and filter values
    DATABASE_URL = "mysql+pymysql://root:root@localhost/orbite_db"
    BUSINESS_IDS = [43, 44]

    # Create a directory for logs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = os.path.join(os.getcwd(), 'find_logs', timestamp)

    os.makedirs(log_dir, exist_ok=True)

    # Initialize the TableCopyManager
    table_copy_manager = TableCopyManager(DATABASE_URL, BUSINESS_IDS, log_dir)

    # Get the tables to copy
    try:
        tables_to_copy = table_copy_manager.get_tables_to_copy()
        print("Tables to copy have been written to 'tables_to_copy.txt'.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")