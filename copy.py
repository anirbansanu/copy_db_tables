import mysql.connector
from mysql.connector import errorcode
import logging
import os
from datetime import datetime

# ---------- Logging Setup ----------
# Create a timestamped folder for logs
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_dir = os.path.join(os.getcwd(), 'logs', timestamp)
os.makedirs(log_dir, exist_ok=True)

# Define log file paths
success_log_path = os.path.join(log_dir, 'successful_tables.log')
failure_log_path = os.path.join(log_dir, 'failed_tables.log')
mismatch_log_path = os.path.join(log_dir, 'column_mismatches.log')

# Open log files
success_log = open(success_log_path, 'w')
failure_log = open(failure_log_path, 'w')
mismatch_log = open(mismatch_log_path, 'w')

logging.basicConfig(level=logging.INFO)
logging.info(f"Logs will be saved in: {log_dir}")

# ---------- MySQL Connection Config ----------
config = {
    'user': 'your_user',
    'password': 'your_password',
    'host': 'localhost',
}

source_db = 'orbite_db'
target_db = 'srihari_db'

# ---------- Helper Functions ----------
def log_file(file, message):
    file.write(message + '\n')
    file.flush()

def get_table_columns(cursor, db, table_name):
    cursor.execute(f"""
        SELECT COLUMN_NAME FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ORDINAL_POSITION
    """, (db, table_name))
    return [row[0] for row in cursor.fetchall()]

def table_has_column(columns, col_name):
    return col_name in columns

# ---------- Main Execution ----------
try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    # Get all tables in source DB
    cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (source_db,))
    source_tables = [row[0] for row in cursor.fetchall()]

    for table in source_tables:
        try:
            # Check if table exists in target DB
            cursor.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """, (target_db, table))
            if cursor.fetchone()[0] == 0:
                log_file(failure_log, f"{table} - Does not exist in target DB")
                continue

            # Get columns from both tables
            source_cols = get_table_columns(cursor, source_db, table)
            target_cols = get_table_columns(cursor, target_db, table)

            if source_cols != target_cols:
                log_file(mismatch_log, f"{table} - Column mismatch:\nSOURCE: {source_cols}\nTARGET: {target_cols}\n")
                continue

            if 'business_id' not in source_cols:
                log_file(failure_log, f"{table} - No 'business_id' column")
                continue

            # Truncate target table
            cursor.execute(f"TRUNCATE TABLE `{target_db}`.`{table}`")

            # Copy filtered data
            cursor.execute(f"""
                INSERT INTO `{target_db}`.`{table}`
                SELECT * FROM `{source_db}`.`{table}` WHERE business_id IN (43, 44)
            """)

            conn.commit()
            log_file(success_log, f"{table}")

        except Exception as e:
            conn.rollback()
            log_file(failure_log, f"{table} - {str(e)}")

except mysql.connector.Error as err:
    print(f"Connection error: {err}")

finally:
    cursor.close()
    conn.close()
    success_log.close()
    failure_log.close()
    mismatch_log.close()