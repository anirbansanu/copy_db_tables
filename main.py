import mysql.connector
from mysql.connector import errorcode
import logging
import os
from datetime import datetime


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

    def get_table_row_count(self, cursor, db, table_name):
        cursor.execute(f"SELECT COUNT(*) FROM `{db}`.`{table_name}` {self.filter_condition}")
        return cursor.fetchone()[0]

    def copy_table_data_in_batches(self, cursor, source_db, target_db, table_name):
        offset = 0
        while True:
            cursor.execute(f"""
                SELECT * FROM `{source_db}`.`{table_name}` {self.filter_condition} LIMIT {self.BATCH_SIZE} OFFSET {offset}
            """)
            rows = cursor.fetchall()
            if not rows:
                break

            # Insert rows into the target table
            placeholders = ', '.join(['%s'] * len(rows[0]))
            insert_query = f"""
                INSERT INTO `{target_db}`.`{table_name}` VALUES ({placeholders})
            """
            cursor.executemany(insert_query, rows)
            offset += self.BATCH_SIZE

    def copy_tables(self):
        try:
            conn = mysql.connector.connect(**self.config)
            cursor = conn.cursor()

            for table in self.tables_to_copy:
                try:
                    # Check if table exists in source DB
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    """, (self.source_db, table))
                    if cursor.fetchone()[0] == 0:
                        self.log_file(self.failure_log, f"{table} - Does not exist in source DB")
                        continue

                    # Check if table exists in target DB
                    cursor.execute(f"""
                        SELECT COUNT(*) FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    """, (self.target_db, table))
                    if cursor.fetchone()[0] == 0:
                        self.log_file(self.failure_log, f"{table} - Does not exist in target DB")
                        continue

                    # Get row count and confirm with the user
                    row_count = self.get_table_row_count(cursor, self.source_db, table)
                    print(f"Table: {table}, Row Count: {row_count}")
                    confirm = input(f"Do you want to copy this table? (y/n): ").strip().lower()
                    if confirm != 'y':
                        self.log_file(self.failure_log, f"{table} - Skipped by user")
                        continue

                    # Get columns from both tables
                    source_cols = self.get_table_columns(cursor, self.source_db, table)
                    target_cols = self.get_table_columns(cursor, self.target_db, table)

                    if source_cols != target_cols:
                        self.log_file(self.mismatch_log, f"{table} - Column mismatch:\nSOURCE: {source_cols}\nTARGET: {target_cols}\n")
                        continue

                    if self.filter_condition.strip() and 'business_id' not in source_cols:
                        self.log_file(self.failure_log, f"{table} - No 'business_id' column")
                        continue

                    # Truncate target table
                    cursor.execute(f"TRUNCATE TABLE `{self.target_db}`.`{table}`")

                    # Copy data in batches
                    self.copy_table_data_in_batches(cursor, self.source_db, self.target_db, table)

                    conn.commit()
                    self.log_file(self.success_log, f"{table}")

                except Exception as e:
                    conn.rollback()
                    self.log_file(self.failure_log, f"{table} - {str(e)}")

        except mysql.connector.Error as err:
            print(f"Connection error: {err}")

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
    }

    source_db = 'orbite_db'
    target_db = 'srihari_db'
    tables_to_copy = ['customer_type']
    filter_condition = "WHERE business_id IN (43, 44)"  # WHERE business_id IN (43, 44)

    copier = TableCopier(config, source_db, target_db, tables_to_copy, filter_condition)
    copier.copy_tables()