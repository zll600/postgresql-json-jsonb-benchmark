#!/usr/bin/env python3
"""
MySQL JSON Benchmark Runner
Automates the benchmark execution and generates performance reports

Requirements:
- mysql-connector-python
- python-dotenv (optional, for .env file support)
"""

import mysql.connector
import time
import json
import sys
from datetime import datetime
from typing import Dict


class MySQLBenchmark:
    def __init__(self, connection_params: Dict[str, str]):
        """Initialize benchmark with database connection parameters"""
        self.conn_params = connection_params
        self.results = {
            'test_info': {
                'timestamp': datetime.now().isoformat(),
                'mysql_version': None,
                'server_info': 'Dell PowerEdge R450, 2x Intel Xeon Silver 4310 24/48 cores @ 2.1GHz'
            },
            'insert_performance': {},
            'storage_sizes': {},
            'query_performance': {},
            'update_performance': {}
        }

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = mysql.connector.connect(**self.conn_params)
            self.conn.autocommit = True
            self.cur = self.conn.cursor()

            # Get MySQL version
            self.cur.execute("SELECT VERSION()")
            self.results['test_info']['mysql_version'] = self.cur.fetchone()[0]
            print(f"Connected to: MySQL {self.results['test_info']['mysql_version']}")

        except Exception as e:
            print(f"Connection failed: {e}")
            sys.exit(1)

    def setup_tables(self):
        """Create test tables"""
        print("Setting up test tables...")

        # Drop existing tables
        self.cur.execute("DROP TABLE IF EXISTS json_test")

        # Create table with JSON column
        self.cur.execute("""
            CREATE TABLE json_test (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        print("Tables created successfully")

    def generate_test_json(self, i: int) -> str:
        """Generate test JSON data for a given index"""
        theme_options = ['dark', 'light', 'auto']
        notifications = 'true' if i % 2 == 0 else 'false'

        return json.dumps({
            "user_id": i,
            "username": f"user_{i}",
            "profile": {
                "name": f"User {i}",
                "age": (i % 50) + 18,
                "city": f"City_{(i % 100) + 1}",
                "preferences": {
                    "theme": theme_options[i % 3],
                    "language": "en",
                    "notifications": notifications == 'true'
                }
            },
            "orders": [
                {"id": i * 2, "amount": (i % 1000) + 10, "status": "completed"},
                {"id": (i * 2) + 1, "amount": (i % 500) + 5, "status": "pending"}
            ],
            "metadata": {
                "last_login": f"2024-12-{(i % 30) + 1:02d}",
                "ip_address": f"192.168.1.{(i % 254) + 1}",
                "user_agent": f"Browser_{(i % 10) + 1}"
            }
        })

    def benchmark_inserts(self, record_count: int = 1000000):
        """Benchmark INSERT performance"""
        print(f"Benchmarking INSERT performance with {record_count:,} records...")

        # Prepare batch insert
        batch_size = 10000

        start_time = time.time()

        for batch_start in range(1, record_count + 1, batch_size):
            batch_end = min(batch_start + batch_size, record_count + 1)
            values = []
            for i in range(batch_start, batch_end):
                values.append((self.generate_test_json(i),))

            self.cur.executemany(
                "INSERT INTO json_test (data) VALUES (%s)",
                values
            )

            if batch_start % 100000 == 1:
                elapsed = time.time() - start_time
                print(f"  Inserted {batch_end - 1:,} records ({elapsed:.1f}s)")

        json_insert_time = time.time() - start_time

        self.results['insert_performance'] = {
            'record_count': record_count,
            'json_time_seconds': round(json_insert_time, 2),
            'json_records_per_second': int(record_count / json_insert_time)
        }

        print(f"JSON INSERT: {json_insert_time:.2f}s ({self.results['insert_performance']['json_records_per_second']:,} records/sec)")

        # Create indexes after insert
        print("Creating indexes...")
        # MySQL 8.0+ supports functional indexes on JSON
        self.cur.execute("""
            CREATE INDEX idx_json_user_id ON json_test ((CAST(data->>'$.user_id' AS UNSIGNED)))
        """)
        self.cur.execute("""
            CREATE INDEX idx_json_city ON json_test ((CAST(data->>'$.profile.city' AS CHAR(50))))
        """)

        # Update statistics for query optimizer
        print("Running ANALYZE TABLE...")
        self.cur.execute("ANALYZE TABLE json_test")
        self.cur.fetchall()  # Consume result set

    def check_storage_sizes(self):
        """Check storage sizes"""
        print("Checking storage sizes...")

        self.cur.execute("""
            SELECT
                table_name,
                data_length + index_length AS total_size,
                data_length AS data_size
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            AND table_name = 'json_test'
        """)

        row = self.cur.fetchone()
        if row:
            table_name, total_size, data_size = row
            self.results['storage_sizes'] = {
                'json': {
                    'total_size_bytes': total_size,
                    'data_size_bytes': data_size,
                    'total_size_mb': round(total_size / (1024*1024), 2),
                    'data_size_mb': round(data_size / (1024*1024), 2)
                }
            }

            print(f"JSON total size: {self.results['storage_sizes']['json']['total_size_mb']} MB")

    def benchmark_queries(self):
        """Benchmark various query types"""
        print("Benchmarking query performance...")

        queries = {
            'simple_key_extraction': {
                'description': 'Simple key extraction (JSON_EXTRACT)',
                'query': "SELECT COUNT(*) FROM json_test WHERE JSON_EXTRACT(data, '$.user_id') = 12345"
            },
            'nested_field_access': {
                'description': 'Nested field access',
                'query': "SELECT COUNT(*) FROM json_test WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$.profile.city')) = 'City_50'"
            },
            'array_operations': {
                'description': 'Array operations',
                'query': "SELECT COUNT(*) FROM json_test WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$.orders[0].status')) = 'completed'"
            },
            'complex_conditions': {
                'description': 'Complex multi-field conditions',
                'query': """SELECT COUNT(*) FROM json_test
                    WHERE JSON_EXTRACT(data, '$.user_id') > 500000
                      AND JSON_EXTRACT(data, '$.profile.age') < 30
                      AND JSON_UNQUOTE(JSON_EXTRACT(data, '$.profile.preferences.theme')) = 'dark'"""
            },
            'path_queries': {
                'description': 'Path-based queries with LIKE',
                'query': "SELECT COUNT(*) FROM json_test WHERE JSON_UNQUOTE(JSON_EXTRACT(data, '$.profile.name')) LIKE 'User 1%'"
            }
        }

        self.results['query_performance'] = {}

        for query_name, query_info in queries.items():
            print(f"Testing: {query_info['description']}")

            # Warm up
            self.cur.execute("SELECT 1")
            self.cur.fetchone()

            # Run query
            start_time = time.time()
            self.cur.execute(query_info['query'])
            result = self.cur.fetchone()[0]
            query_time = time.time() - start_time

            self.results['query_performance'][query_name] = {
                'description': query_info['description'],
                'json_time_ms': round(query_time * 1000, 2),
                'json_result_count': result
            }

            print(f"  Time: {query_time*1000:.2f}ms | Results: {result}")

    def benchmark_updates(self):
        """Benchmark UPDATE performance"""
        print("Benchmarking UPDATE performance...")

        start_time = time.time()
        self.cur.execute("""
            UPDATE json_test
            SET data = JSON_SET(data, '$.profile.preferences.theme', 'updated')
            WHERE id BETWEEN 1 AND 1000
        """)
        json_update_time = time.time() - start_time

        self.results['update_performance'] = {
            'records_updated': 1000,
            'json_time_ms': round(json_update_time * 1000, 2)
        }

        print(f"JSON UPDATE: {json_update_time*1000:.2f}ms")

    def generate_report(self, output_file: str = 'mysql_benchmark_results.json'):
        """Generate detailed benchmark report"""
        print(f"Generating report: {output_file}")

        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        # Console summary
        print("\n" + "="*60)
        print("MYSQL JSON BENCHMARK SUMMARY")
        print("="*60)

        insert = self.results['insert_performance']
        print(f"INSERT Performance ({insert['record_count']:,} records):")
        print(f"  JSON: {insert['json_time_seconds']}s ({insert['json_records_per_second']:,} rec/s)")

        storage = self.results['storage_sizes']
        print("\nStorage Size:")
        print(f"  JSON: {storage['json']['total_size_mb']} MB")

        print("\nQuery Performance:")
        for name, data in self.results['query_performance'].items():
            print(f"  {data['description']}: {data['json_time_ms']}ms")

        update = self.results['update_performance']
        print("\nUpdate Performance:")
        print(f"  {update['records_updated']} records in {update['json_time_ms']}ms")

        print("\nDetailed results saved to:", output_file)

    def cleanup(self):
        """Clean up test data"""
        try:
            if hasattr(self, 'cur') and self.cur:
                print("Cleaning up...")
                self.cur.execute("DROP TABLE IF EXISTS json_test")
                print("Cleanup completed")
        except Exception as e:
            print(f"Cleanup failed (non-critical): {e}")

    def close(self):
        """Close database connection"""
        try:
            if hasattr(self, 'cur') and self.cur:
                self.cur.close()
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except Exception as e:
            print(f"Error closing connections: {e}")


def load_env_file(env_file='.env'):
    """Load environment variables from .env file"""
    import os
    if env_file == '/dev/null':
        return
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip()


def main():
    """Main benchmark execution"""
    import os
    import argparse

    parser = argparse.ArgumentParser(description='MySQL JSON Benchmark')
    parser.add_argument('--records', type=int, default=None,
                        help='Number of records to test (default from env or 1000000)')
    parser.add_argument('--env-file', default='.env',
                        help='Path to .env file (default: .env)')
    parser.add_argument('--output', default=None,
                        help='Output file for results')
    args = parser.parse_args()

    load_env_file(args.env_file)

    conn_params = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'database': os.getenv('MYSQL_DATABASE', 'json_benchmark_db'),
        'user': os.getenv('MYSQL_USER', 'benchmark_user'),
        'password': os.getenv('MYSQL_PASSWORD', 'benchmark_pass_2024'),
        'port': int(os.getenv('MYSQL_PORT', 3306))
    }

    record_count = args.records or int(os.getenv('BENCHMARK_RECORDS', 1000000))
    output_file = args.output or os.getenv('MYSQL_BENCHMARK_OUTPUT_FILE', 'mysql_benchmark_results.json')

    print(f"Connecting to: {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
    print(f"Testing with: {record_count:,} records")
    print(f"Output file: {output_file}")
    print("")

    benchmark = MySQLBenchmark(conn_params)

    try:
        benchmark.connect()
        benchmark.setup_tables()
        benchmark.benchmark_inserts(record_count)
        benchmark.check_storage_sizes()
        benchmark.benchmark_queries()
        benchmark.benchmark_updates()
        benchmark.generate_report(output_file)

        print("\nBenchmark completed successfully!")
        print(f"Results saved to: {output_file}")

    except Exception as e:
        print(f"Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        benchmark.cleanup()
        benchmark.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
