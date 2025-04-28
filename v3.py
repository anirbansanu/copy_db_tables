from datetime import datetime
import mysql.connector
import os
import logging
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
        # Filter tables_to_copy to only include parent table name and child table names
        filtered_tables = []
        for table in tables_to_copy:
            parent_table = table.get('parent_table')
            child_tables = table.get('child_tables', [])
            # filtered_entry = {
            #     'parent_table': parent_table,
            #     # 'child_tables': [child.get('child_table') for child in child_tables]
            # }
            filtered_tables.append(parent_table)
            for child in child_tables:
                child_table = child.get('child_table')
                # print(f"Child table: {child}")
                filtered_tables.append(child_table)
             # Print the filtered tables
        print()
        print(f"All tables name : {filtered_tables}")

class TableCopier:
    def __init__(self, config, source_db, target_db, tables_to_copy):
        self.config = config
        self.source_db = source_db
        self.target_db = target_db
        self.tables_to_copy = tables_to_copy
        self.BATCH_SIZE = 1000
        self.setup_logging()

    def setup_logging(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join(os.getcwd(), 'logs', timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        self.success_log_path = os.path.join(self.log_dir, 'successful_tables.log')
        self.failure_log_path = os.path.join(self.log_dir, 'failed_tables.log')
        self.mismatch_log_path = os.path.join(self.log_dir, 'column_mismatches.log')

        self.success_log = open(self.success_log_path, 'w')
        self.failure_log = open(self.failure_log_path, 'w')
        self.mismatch_log = open(self.mismatch_log_path, 'w')

    def log_file(self, file, message):
        file.write(message + '\n')
        file.flush()

    def get_table_columns(self, cursor, db, table_name):
        cursor.execute(f"""
            SELECT COLUMN_NAME FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ORDINAL_POSITION
        """, (db, table_name))
        return [row[0] for row in cursor.fetchall()]

    def get_table_row_count(self, cursor, db, table_name, filter_condition=''):
        """Retrieve the row count for a table with an optional filter."""
        try:
            # Ensure filter_condition is properly formatted
            checkWhereIsInString = filter_condition.find('WHERE')
            if filter_condition.strip():
                if checkWhereIsInString == -1:
                    filter_condition = f"WHERE {filter_condition}"
                elif checkWhereIsInString == 0:
                    filter_condition = f"{filter_condition}"
                else:
                    filter_condition = f"WHERE {filter_condition}"
            else:
                filter_condition = ""

            # Construct and execute the query
            query = f"SELECT COUNT(*) FROM `{db}`.`{table_name}` {filter_condition}"
            # print(f"Executing query: {query}")  # Debugging output
            cursor.execute(query)
            return cursor.fetchone()[0]

        except mysql.connector.Error as err:
            # Log the error details
            error_message = (
                f"Error while retrieving row count for table '{table_name}' in database '{db}':\n"
                f"Error Code: {err.errno}\n"
                f"SQL State: {err.sqlstate}\n"
                f"Message: {err.msg}\n"
                f"Full Error: {str(err)}"
            )
            print(error_message)
            self.log_file(self.failure_log, error_message)
            return 0  # Return 0 as a fallback in case of an error

        except Exception as e:
            # Handle any other unexpected exceptions
            error_message = f"Unexpected error while retrieving row count for table '{table_name}': {str(e)}"
            print(error_message)
            self.log_file(self.failure_log, error_message)
            return 0  # Return 0 as a fallback in case of an error

    def check_column_match(self, cursor, table_info):
        parent_table = table_info['parent_table']
        match_columns = table_info.get('match_columns', False)

        if match_columns:
            source_cols = self.get_table_columns(cursor, self.source_db, parent_table)
            target_cols = self.get_table_columns(cursor, self.target_db, parent_table)

            if set(source_cols) != set(target_cols):
                if set(source_cols).issubset(set(target_cols)):
                    self.log_file(
                        self.mismatch_log,
                        f"Table: {parent_table} - Target table has extra columns.\n"
                        f"Source Columns: {source_cols}\nTarget Columns: {target_cols}"
                    )
                    return True
                else:
                    self.log_file(
                        self.mismatch_log,
                        f"Table: {parent_table} - Source table has extra columns. Skipping copy.\n"
                        f"Source Columns: {source_cols}\nTarget Columns: {target_cols}"
                    )
                    return False
        return True

    def copy_parent_and_child(self, cursor, table_info):
        parent_table = table_info['parent_table']
        child_tables = table_info.get('child_tables', [])
        parent_key = table_info['parent_key']
        filter_for_parent = table_info.get('filter_for_parent', '')

        # Display table name and row count
        parent_row_count = self.get_table_row_count(cursor, self.source_db, parent_table, filter_for_parent)
        print(f"Table: {parent_table}, Rows: {parent_row_count}")
        user_input = input(f"Do you want to copy the table '{parent_table}'? (y/n): ").strip().lower()
        if user_input != 'y':
            print(f"Skipping table '{parent_table}'.")
            self.log_file(self.failure_log, f"Table '{parent_table}' skipped by user.")
            return

        # Copy parent table
        cursor.execute(f"TRUNCATE TABLE `{self.target_db}`.`{parent_table}`")
        cursor.execute(f"""
            SELECT * FROM `{self.source_db}`.`{parent_table}` {filter_for_parent}
        """)
        parent_rows = cursor.fetchall()
        parent_columns = [f"`{desc[0]}`" for desc in cursor.description]

        placeholders = ', '.join(['%s'] * len(parent_columns))
        insert_query = f"""
            INSERT INTO `{self.target_db}`.`{parent_table}` ({', '.join(parent_columns)}) VALUES ({placeholders})
        """
        cursor.executemany(insert_query, parent_rows)
        self.log_file(self.success_log, f"Parent table '{parent_table}' copied successfully.")

        # Map old IDs to new IDs
        old_to_new_id_map = {}
        for old_row in parent_rows:
            old_id = old_row[parent_columns.index(f"`{parent_key}`")]
            cursor.execute(f"SELECT LAST_INSERT_ID()")
            new_id = cursor.fetchone()[0]
            old_to_new_id_map[old_id] = new_id

        # Copy child tables
        for child_info in child_tables:
            child_table = child_info['child_table']
            child_foreign_key = child_info['child_foreign_key']
            filter_for_child = child_info.get('filter_for_child', '')

            child_row_count = self.get_table_row_count(cursor, self.source_db, child_table, filter_for_child)
            print(f"Child Table: {child_table}, Rows: {child_row_count}")
            user_input = input(f"Do you want to copy the child table '{child_table}'? (y/n): ").strip().lower()
            if user_input != 'y':
                print(f"Skipping child table '{child_table}'.")
                self.log_file(self.failure_log, f"Child table '{child_table}' skipped by user.")
                continue

            cursor.execute(f"TRUNCATE TABLE `{self.target_db}`.`{child_table}`")
            for old_id, new_id in old_to_new_id_map.items():
                if filter_for_child:
                    query = f"""
                        SELECT * FROM `{self.source_db}`.`{child_table}` WHERE `{child_foreign_key}` = %s AND ({filter_for_child})
                    """
                else:
                    query = f"""
                        SELECT * FROM `{self.source_db}`.`{child_table}` WHERE `{child_foreign_key}` = %s
                    """
                cursor.execute(query, (old_id,))
                child_rows = cursor.fetchall()
                if not child_rows:
                    continue

                child_columns = [f"`{desc[0]}`" for desc in cursor.description]
                placeholders = ', '.join(['%s'] * len(child_columns))
                insert_query = f"""
                    INSERT INTO `{self.target_db}`.`{child_table}` ({', '.join(child_columns)}) VALUES ({placeholders})
                """
                updated_child_rows = []
                for row in child_rows:
                    row = list(row)
                    # row[child_columns.index(f"`{child_foreign_key}`")] = new_id
                    updated_child_rows.append(row)

                cursor.executemany(insert_query, updated_child_rows)
            self.log_file(self.success_log, f"Child table '{child_table}' copied successfully.")

    def copy_tables(self):
        query = ""
        try:
            conn = mysql.connector.connect(**self.config)
            cursor = conn.cursor()
            print("Connected to the database.")
            print(f"Source Database: {self.source_db}")

            for table_info in self.tables_to_copy:
                if not self.check_column_match(cursor, table_info):
                    continue

                if table_info.get('children', False):
                    self.copy_parent_and_child(cursor, table_info)
                else:
                    parent_table = table_info['parent_table']
                    filter_for_parent = table_info.get('filter_for_parent', '')

                    # Display table name and row count
                    source_row_count = self.get_table_row_count(cursor, self.source_db, parent_table, filter_for_parent)
                    print(f"Table: {parent_table}, Rows: {source_row_count}")
                    user_input = input(f"Do you want to copy the table '{parent_table}'? (y/n/t/ft): ").strip().lower()

                    if user_input == 't':
                        print("\nUser Terminated the process.")
                        self.log_file(self.success_log, f"User Terminated the process.")
                        break
                    elif user_input == 'ft':
                        print("\nUser Fully Terminated the process without saving data.")
                        self.log_file(self.success_log, f"User Fully Terminated the process without saving data.")
                        exit()

                    if user_input != 'y':
                        print(f"Skipping table '{parent_table}'.")
                        self.log_file(self.failure_log, f"Table '{parent_table}' skipped by user.")
                        continue
                    

                    if filter_for_parent.strip():
                        query = f"SELECT * FROM `{self.source_db}`.`{parent_table}` {filter_for_parent}"
                    else:
                        query = f"SELECT * FROM `{self.source_db}`.`{parent_table}`"
                    
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    columns = [f"`{desc[0]}`" for desc in cursor.description]
                    placeholders = ', '.join(['%s'] * len(columns))
                    cursor.execute(f"TRUNCATE TABLE `{self.target_db}`.`{parent_table}`")
                    insert_query = f"""
                        INSERT INTO `{self.target_db}`.`{parent_table}` ({', '.join(columns)}) VALUES ({placeholders})
                    """
                    cursor.executemany(insert_query, rows)

                    target_row_count = self.get_table_row_count(cursor, self.target_db, parent_table, filter_for_parent)

                    if source_row_count == target_row_count:
                        success_message = (
                            f"Standalone table '{parent_table}' copied successfully. "
                            f"Rows copied: {target_row_count}."
                        )
                        self.log_file(self.success_log, success_message)
                        print(success_message)
                        
                    else:
                        error_message = (
                            f"Error: Row count mismatch for table '{parent_table}'. "
                            f"Source rows: {source_row_count}, Target rows: {target_row_count}."
                        )
                        self.log_file(self.failure_log, error_message)
                        print(error_message)

            conn.commit()

        except mysql.connector.Error as err:
            error_message = (
                f"Error Code: {err.errno}\n"
                f"SQL State: {err.sqlstate}\n"
                f"Message: {err.msg}\n"
                f"Full Error: {str(err)}\n"
                f"Query: {query}"
            )
            self.log_file(self.failure_log, error_message)
            print(f"Connection error:\n{error_message}")

        finally:
            cursor.close()
            conn.close()
            self.success_log.close()
            self.failure_log.close()
            self.mismatch_log.close()


if __name__ == "__main__":
    config = {
        'user': 'root',
        'password': 'root',
        'host': 'localhost',
        'database': 'orbite_db'
    }

    source_db = 'orbite_db'
    target_db = 'srihari_db'

    # tables_to_copy = [
    #     {
    #         'parent_table': 'grc',
    #         'children': True,
    #         'child_tables': [
    #             {
    #                 'child_table': 'grc_items',
    #                 'child_foreign_key': 'grc_id',
    #                 'filter_for_child': 'grc_id IN (SELECT id FROM grc WHERE business_id IN (43, 44))'
    #             },
    #             {
    #                 'child_table': 'grc_calculated_values',
    #                 'child_foreign_key': 'grc_id',
    #                 'filter_for_child': 'grc_id IN (SELECT id FROM grc WHERE business_id IN (43, 44))'
    #             }
    #         ],
    #         'parent_key': 'id',
    #         'filter_for_parent': 'WHERE business_id IN (43, 44)',
    #         'match_columns': True
    #     },
    #     {
    #         'parent_table': 'items',
    #         'children': False,
    #         'parent_key': 'id',
    #         'filter_for_parent': 'WHERE business_id IN (43, 44)',
    #         'match_columns': True
    #     }
    # ]

    # Load data from tables_to_copy.json
    file_manager = FileManager(r"tables_to_copy.json")
    tables_to_copy = file_manager.load_json()
        
    file_manager.show_filtered_tables(tables_to_copy)
    
    copier = TableCopier(config, source_db, target_db, tables_to_copy)
    copier.copy_tables()