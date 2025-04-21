class TableCopier:
    def __init__(self, config, source_db, target_db, tables_to_copy, filter_condition):
        self.config = config
        self.source_db = source_db
        self.target_db = target_db
        self.tables_to_copy = tables_to_copy
        self.filter_condition = filter_condition
        self.BATCH_SIZE = 1000
        self.setup_logging()

    def setup_logging(self):
        # Create a timestamped folder for logs
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join(os.getcwd(), 'logs', timestamp)
        os.makedirs(self.log_dir, exist_ok=True)

        # Define log file paths
        self.success_log_path = os.path.join(self.log_dir, 'successful_tables.log')
        self.failure_log_path = os.path.join(self.log_dir, 'failed_tables.log')
        self.mismatch_log_path = os.path.join(self.log_dir, 'column_mismatches.log')

        # Open log files
        self.success_log = open(self.success_log_path, 'w')
        self.failure_log = open(self.failure_log_path, 'w')
        self.mismatch_log = open(self.mismatch_log_path, 'w')

        logging.basicConfig(level=logging.INFO)
        logging.info(f"Logs will be saved in: {self.log_dir}")

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

    def copy_parent_and_child(self, cursor, parent_table, child_table, parent_key, child_foreign_key):
        """
        Copies parent records and their related child records while maintaining foreign key relationships.

        :param cursor: MySQL cursor object
        :param parent_table: Name of the parent table (e.g., 'grc')
        :param child_table: Name of the child table (e.g., 'grc_items')
        :param parent_key: Primary key column in the parent table (e.g., 'id')
        :param child_foreign_key: Foreign key column in the child table (e.g., 'grc_id')
        """
        # Step 1: Copy parent records and track ID mapping
        cursor.execute(f"""
            SELECT * FROM `{self.source_db}`.`{parent_table}` {self.filter_condition}
        """)
        parent_rows = cursor.fetchall()
        parent_columns = [desc[0] for desc in cursor.description]

        # Insert parent records into the target DB
        placeholders = ', '.join(['%s'] * len(parent_columns))
        insert_query = f"""
            INSERT INTO `{self.target_db}`.`{parent_table}` ({', '.join(parent_columns)}) VALUES ({placeholders})
        """
        cursor.executemany(insert_query, parent_rows)

        # Fetch the new IDs for the inserted parent records
        old_to_new_id_map = {}
        for old_row in parent_rows:
            old_id = old_row[parent_columns.index(parent_key)]
            cursor.execute(f"SELECT `{parent_key}` FROM `{self.target_db}`.`{parent_table}` WHERE `{parent_key}` = LAST_INSERT_ID()")
            new_id = cursor.fetchone()[0]
            old_to_new_id_map[old_id] = new_id

        # Step 2: Copy child records with updated foreign keys
        if child_table:
            for old_id, new_id in old_to_new_id_map.items():
                cursor.execute(f"""
                    SELECT * FROM `{self.source_db}`.`{child_table}` WHERE `{child_foreign_key}` = %s
                """, (old_id,))
                child_rows = cursor.fetchall()
                if not child_rows:
                    continue

                child_columns = [desc[0] for desc in cursor.description]
                placeholders = ', '.join(['%s'] * len(child_columns))
                insert_query = f"""
                    INSERT INTO `{self.target_db}`.`{child_table}` ({', '.join(child_columns)}) VALUES ({placeholders})
                """

                # Update the foreign key in child rows
                updated_child_rows = []
                for row in child_rows:
                    row = list(row)
                    row[child_columns.index(child_foreign_key)] = new_id
                    updated_child_rows.append(row)

                cursor.executemany(insert_query, updated_child_rows)

    def copy_tables(self):
        try:
            conn = mysql.connector.connect(**self.config)
            cursor = conn.cursor()

            for table_info in self.tables_to_copy:
                parent_table = table_info['parent_table']
                child_table = table_info.get('child_table')  # Optional
                parent_key = table_info['parent_key']
                child_foreign_key = table_info.get('child_foreign_key')  # Optional

                if child_table:
                    self.copy_parent_and_child(cursor, parent_table, child_table, parent_key, child_foreign_key)
                else:
                    # Copy standalone table
                    self.copy_table_data_in_batches(cursor, self.source_db, self.target_db, parent_table)

            conn.commit()

        except mysql.connector.Error as err:
            print(f"Connection error: {err}")

        finally:
            cursor.close()
            conn.close()
            self.success_log.close()
            self.failure_log.close()
            self.mismatch_log.close()


# ---------- Main Execution ----------
if __name__ == "__main__":
    # MySQL Connection Config
    config = {
        'user': 'root',
        'password': 'root',
        'host': 'localhost',
    }

    source_db = 'orbite_db'
    target_db = 'srihari_db'

    # Define tables to copy with parent-child relationships
    tables_to_copy = [
        {
            'parent_table': 'grc',
            'child_table': 'grc_items',
            'parent_key': 'id',
            'child_foreign_key': 'grc_id'
        },
        {
            'parent_table': 'item_name',  # Standalone table
            'parent_key': 'id'
        }
    ]

    filter_condition = "WHERE business_id IN (43, 44)"  # Change this filter as needed

    copier = TableCopier(config, source_db, target_db, tables_to_copy, filter_condition)
    copier.copy_tables()