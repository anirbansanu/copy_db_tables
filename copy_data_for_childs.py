import json
import logging
from typing import List, Dict, Any
import mysql.connector
from mysql.connector import Error, connection

# Configure logging to file with human-readable timestamps
logging.basicConfig(
    filename='copy_data.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Database configuration - fill in your own credentials
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_username',
    'password': 'your_password',
    'database': 'your_database',
    'port': 3306
}

JSON_FILE = 'tables.json'
SOURCE_BUSINESS_ID = 43
TARGET_BUSINESS_IDS = [44, 45, 46]


class JSONConfigLoader:
    """
    Loads table configuration from a JSON file.
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def load_tables(self) -> List[str]:
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            tables = data.get('tables', [])
            logging.info(f"Loaded {len(tables)} tables from config.")
            return tables
        except Exception as e:
            logging.error(f"Failed to read JSON file {self.filepath}: {e}")
            raise


class DatabaseConnector:
    """
    Manages MySQL database connections.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.conn: connection.MySQLConnection = None

    def __enter__(self) -> connection.MySQLConnection:
        try:
            self.conn = mysql.connector.connect(**self.config)
            if self.conn.is_connected():
                logging.info("Successfully connected to the database.")
                return self.conn
        except Error as e:
            logging.error(f"Error connecting to database: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn and self.conn.is_connected():
            self.conn.close()
            logging.info("Database connection closed.")


class TableProcessor:
    """
    Processes each table: fetching rows and inserting copies.
    """
    def __init__(self, conn: connection.MySQLConnection):
        self.conn = conn
        self.cursor = conn.cursor(dictionary=True)

    def fetch_rows(self, table: str, business_id: int) -> List[Dict[str, Any]]:
        query = f"SELECT * FROM `{table}` WHERE business_id = %s"
        try:
            logging.info(f"Executing SELECT: {query} [{business_id}]")
            self.cursor.execute(query, (business_id,))
            rows = self.cursor.fetchall()
            logging.info(f"Fetched {len(rows)} rows from {table}.")
            return rows
        except Error as e:
            logging.error(f"Error fetching rows from {table}: {e}")
            raise

    def insert_copies(self, table: str, rows: List[Dict[str, Any]], target_ids: List[int]) -> None:
        if not rows:
            logging.info(f"No rows to copy in table {table}.")
            return

        for row in rows:
            base_data = dict(row)
            base_data.pop('id', None)

            for new_id in target_ids:
                base_data['business_id'] = new_id
                columns = ', '.join(f"`{col}`" for col in base_data.keys())
                placeholders = ', '.join(['%s'] * len(base_data))
                values = tuple(base_data.values())
                insert_query = f"INSERT INTO `{table}` ({columns}) VALUES ({placeholders})"

                try:
                    logging.info(f"Executing INSERT on {table}: {insert_query} {values}")
                    self.cursor.execute(insert_query, values)
                    self.conn.commit()
                    logging.info(f"Inserted row into {table} with business_id={new_id}.")
                except Error as e:
                    logging.error(f"Error inserting into {table}: {e}")
                    self.conn.rollback()

    def process_table(self, table: str, source_id: int, target_ids: List[int]) -> None:
        logging.info(f"Processing table: {table}")
        try:
            rows = self.fetch_rows(table, source_id)
            self.insert_copies(table, rows, target_ids)
            logging.info(f"Completed copying for table: {table}")
        except Exception as e:
            logging.error(f"Error processing table {table}: {e}")


def main():
    loader = JSONConfigLoader(JSON_FILE)
    tables = loader.load_tables()

    if not tables:
        logging.warning("No tables found in JSON configuration.")
        return

    with DatabaseConnector(DB_CONFIG) as conn:
        processor = TableProcessor(conn)
        for table in tables:
            processor.process_table(table, SOURCE_BUSINESS_ID, TARGET_BUSINESS_IDS)


if __name__ == '__main__':
    main()
