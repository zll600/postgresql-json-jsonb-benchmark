#!/usr/bin/env python3
"""
Compare benchmark results between PostgreSQL (JSON/JSONB) and MySQL (JSON)
"""

import json
import os
import sys
from datetime import datetime


def load_results(file_path: str) -> dict:
    """Load benchmark results from JSON file"""
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r') as f:
        return json.load(f)


def format_number(n: float, decimals: int = 2) -> str:
    """Format number with thousands separator"""
    if isinstance(n, int) or n == int(n):
        return f"{int(n):,}"
    return f"{n:,.{decimals}f}"


def format_ratio(value: float, baseline: float, lower_is_better: bool = True) -> str:
    """Format ratio compared to baseline (MySQL). Returns 'N/A' if baseline is 0 or missing."""
    if not baseline or baseline == 0 or value == 'N/A' or baseline == 'N/A':
        return "N/A"
    ratio = value / baseline
    # For metrics where lower is better (time), ratio < 1 means better
    # For metrics where higher is better (records/sec), ratio > 1 means better
    return f"{ratio:.2f}x"


def print_separator(char: str = "=", width: int = 80):
    print(char * width)


def compare_benchmarks(pg_file: str, mysql_file: str, output_file: str = None):
    """Compare PostgreSQL and MySQL benchmark results"""

    pg_results = load_results(pg_file)
    mysql_results = load_results(mysql_file)

    if not pg_results and not mysql_results:
        print("No benchmark results found!")
        print(f"  PostgreSQL: {pg_file} - NOT FOUND")
        print(f"  MySQL: {mysql_file} - NOT FOUND")
        print("\nRun benchmarks first:")
        print("  make run        # PostgreSQL benchmark")
        print("  make mysql-run  # MySQL benchmark")
        return 1

    comparison = {
        'generated_at': datetime.now().isoformat(),
        'sources': {
            'postgresql': pg_file if pg_results else None,
            'mysql': mysql_file if mysql_results else None
        },
        'comparison': {}
    }

    print_separator()
    print("DATABASE JSON BENCHMARK COMPARISON")
    print_separator()
    print()

    # Test Info
    print("TEST INFORMATION")
    print("-" * 40)
    if pg_results:
        print(f"PostgreSQL: {pg_results['test_info'].get('postgresql_version', 'N/A')}")
    if mysql_results:
        print(f"MySQL: {mysql_results['test_info'].get('mysql_version', 'N/A')}")
    print()

    # INSERT Performance
    print("INSERT PERFORMANCE")
    print("-" * 40)

    insert_data = {}

    # Get MySQL baseline first
    mysql_time = 0
    mysql_rps = 0
    if mysql_results and 'insert_performance' in mysql_results:
        mysql_insert = mysql_results['insert_performance']
        mysql_time = mysql_insert.get('json_time_seconds', 0)
        mysql_rps = mysql_insert.get('json_records_per_second', 0)
        insert_data['mysql_json'] = {'time': mysql_time, 'rps': mysql_rps}

    # Determine record count
    record_count = 0
    if pg_results and 'insert_performance' in pg_results:
        record_count = pg_results['insert_performance'].get('record_count', 0)
    elif mysql_results and 'insert_performance' in mysql_results:
        record_count = mysql_results['insert_performance'].get('record_count', 0)

    if record_count:
        print(f"Record count: {format_number(record_count)}")
        print()

    print(f"{'Database':<20} {'Time (s)':<12} {'Records/sec':<15} {'Ratio':<10}")
    print("-" * 57)

    if pg_results and 'insert_performance' in pg_results:
        pg_insert = pg_results['insert_performance']
        pg_json_time = pg_insert.get('json_time_seconds', 0)
        pg_jsonb_time = pg_insert.get('jsonb_time_seconds', 0)
        pg_json_rps = pg_insert.get('json_records_per_second', 0)
        pg_jsonb_rps = pg_insert.get('jsonb_records_per_second', 0)

        pg_json_ratio = format_ratio(pg_json_time, mysql_time, lower_is_better=True)
        pg_jsonb_ratio = format_ratio(pg_jsonb_time, mysql_time, lower_is_better=True)

        print(f"{'PostgreSQL JSON':<20} {pg_json_time:<12} {format_number(pg_json_rps):<15} {pg_json_ratio:<10}")
        print(f"{'PostgreSQL JSONB':<20} {pg_jsonb_time:<12} {format_number(pg_jsonb_rps):<15} {pg_jsonb_ratio:<10}")

        insert_data['postgresql_json'] = {'time': pg_json_time, 'rps': pg_json_rps, 'ratio': pg_json_ratio}
        insert_data['postgresql_jsonb'] = {'time': pg_jsonb_time, 'rps': pg_jsonb_rps, 'ratio': pg_jsonb_ratio}

    if mysql_results and 'insert_performance' in mysql_results:
        print(f"{'MySQL JSON':<20} {mysql_time:<12} {format_number(mysql_rps):<15} {'1.00x':<10}")

    # Find winner
    if insert_data:
        fastest = min(insert_data.items(), key=lambda x: x[1]['time'])
        print()
        print(f"Fastest INSERT: {fastest[0].replace('_', ' ').title()} ({fastest[1]['time']}s)")

    comparison['comparison']['insert_performance'] = insert_data
    print()

    # Storage Size
    print("STORAGE SIZE")
    print("-" * 40)

    storage_data = {}

    # Get MySQL baseline first
    mysql_mb = 0
    if mysql_results and 'storage_sizes' in mysql_results:
        mysql_storage = mysql_results['storage_sizes']
        if 'json' in mysql_storage:
            mysql_mb = mysql_storage['json'].get('total_size_mb', 0)
            storage_data['mysql_json'] = {'size_mb': mysql_mb}

    print(f"{'Database':<20} {'Size (MB)':<15} {'Ratio':<10}")
    print("-" * 45)

    if pg_results and 'storage_sizes' in pg_results:
        pg_storage = pg_results['storage_sizes']
        if 'json' in pg_storage:
            pg_json_mb = pg_storage['json'].get('total_size_mb', 0)
            pg_json_ratio = format_ratio(pg_json_mb, mysql_mb, lower_is_better=True)
            print(f"{'PostgreSQL JSON':<20} {pg_json_mb:<15} {pg_json_ratio:<10}")
            storage_data['postgresql_json'] = {'size_mb': pg_json_mb, 'ratio': pg_json_ratio}
        if 'jsonb' in pg_storage:
            pg_jsonb_mb = pg_storage['jsonb'].get('total_size_mb', 0)
            pg_jsonb_ratio = format_ratio(pg_jsonb_mb, mysql_mb, lower_is_better=True)
            print(f"{'PostgreSQL JSONB':<20} {pg_jsonb_mb:<15} {pg_jsonb_ratio:<10}")
            storage_data['postgresql_jsonb'] = {'size_mb': pg_jsonb_mb, 'ratio': pg_jsonb_ratio}

    if mysql_results and 'storage_sizes' in mysql_results and mysql_mb:
        print(f"{'MySQL JSON':<20} {mysql_mb:<15} {'1.00x':<10}")

    if storage_data:
        smallest = min(storage_data.items(), key=lambda x: x[1]['size_mb'] if isinstance(x[1], dict) else x[1])
        size_val = smallest[1]['size_mb'] if isinstance(smallest[1], dict) else smallest[1]
        print()
        print(f"Smallest storage: {smallest[0].replace('_', ' ').title()} ({size_val} MB)")

    comparison['comparison']['storage_sizes'] = storage_data
    print()

    # Query Performance
    print("QUERY PERFORMANCE (ms) - Ratio based on MySQL")
    print("-" * 40)

    query_types = [
        'simple_key_extraction',
        'nested_field_access',
        'array_operations',
        'complex_conditions',
        'path_queries'
    ]

    query_data = {}

    # Build MySQL baseline lookup
    mysql_query_baseline = {}
    if mysql_results and 'query_performance' in mysql_results:
        for query_type in query_types:
            mysql_query = mysql_results['query_performance'].get(query_type, {})
            mysql_query_baseline[query_type] = mysql_query.get('json_time_ms', 0)

    # Header
    header = f"{'Query Type':<25}"
    if pg_results:
        header += f"{'PG JSON':<10}{'Ratio':<8}{'PG JSONB':<10}{'Ratio':<8}"
    if mysql_results:
        header += f"{'MySQL':<10}"
    print(header)
    print("-" * len(header))

    for query_type in query_types:
        row = f"{query_type:<25}"
        query_data[query_type] = {}

        mysql_baseline = mysql_query_baseline.get(query_type, 0)

        if pg_results and 'query_performance' in pg_results:
            pg_query = pg_results['query_performance'].get(query_type, {})
            pg_json_ms = pg_query.get('json_time_ms', 'N/A')
            pg_jsonb_ms = pg_query.get('jsonb_time_ms', 'N/A')
            pg_json_ratio = format_ratio(pg_json_ms, mysql_baseline, lower_is_better=True)
            pg_jsonb_ratio = format_ratio(pg_jsonb_ms, mysql_baseline, lower_is_better=True)
            row += f"{pg_json_ms:<10}{pg_json_ratio:<8}{pg_jsonb_ms:<10}{pg_jsonb_ratio:<8}"
            query_data[query_type]['postgresql_json'] = {'time_ms': pg_json_ms, 'ratio': pg_json_ratio}
            query_data[query_type]['postgresql_jsonb'] = {'time_ms': pg_jsonb_ms, 'ratio': pg_jsonb_ratio}

        if mysql_results and 'query_performance' in mysql_results:
            mysql_query = mysql_results['query_performance'].get(query_type, {})
            mysql_ms = mysql_query.get('json_time_ms', 'N/A')
            row += f"{mysql_ms:<10}"
            query_data[query_type]['mysql_json'] = {'time_ms': mysql_ms, 'ratio': '1.00x'}

        print(row)

    comparison['comparison']['query_performance'] = query_data
    print()

    # Update Performance
    print("UPDATE PERFORMANCE")
    print("-" * 40)

    update_data = {}

    # Get MySQL baseline first
    mysql_update_ms = 0
    if mysql_results and 'update_performance' in mysql_results:
        mysql_update = mysql_results['update_performance']
        mysql_update_ms = mysql_update.get('json_time_ms', 0)
        update_data['mysql_json'] = {'time_ms': mysql_update_ms}

    print(f"{'Database':<20} {'Time (ms)':<15} {'Ratio':<10}")
    print("-" * 45)

    if pg_results and 'update_performance' in pg_results:
        pg_update = pg_results['update_performance']
        pg_json_ms = pg_update.get('json_time_ms', 0)
        pg_jsonb_ms = pg_update.get('jsonb_time_ms', 0)
        pg_json_ratio = format_ratio(pg_json_ms, mysql_update_ms, lower_is_better=True)
        pg_jsonb_ratio = format_ratio(pg_jsonb_ms, mysql_update_ms, lower_is_better=True)
        print(f"{'PostgreSQL JSON':<20} {pg_json_ms:<15} {pg_json_ratio:<10}")
        print(f"{'PostgreSQL JSONB':<20} {pg_jsonb_ms:<15} {pg_jsonb_ratio:<10}")
        update_data['postgresql_json'] = {'time_ms': pg_json_ms, 'ratio': pg_json_ratio}
        update_data['postgresql_jsonb'] = {'time_ms': pg_jsonb_ms, 'ratio': pg_jsonb_ratio}

    if mysql_results and 'update_performance' in mysql_results and mysql_update_ms:
        print(f"{'MySQL JSON':<20} {mysql_update_ms:<15} {'1.00x':<10}")

    if update_data:
        fastest = min(update_data.items(), key=lambda x: x[1]['time_ms'] if isinstance(x[1], dict) else x[1])
        time_val = fastest[1]['time_ms'] if isinstance(fastest[1], dict) else fastest[1]
        print()
        print(f"Fastest UPDATE: {fastest[0].replace('_', ' ').title()} ({time_val} ms)")

    comparison['comparison']['update_performance'] = update_data
    print()

    print_separator()
    print("SUMMARY")
    print_separator()

    print("""
Ratio Interpretation (MySQL as baseline = 1.00x):
- Ratio < 1.00x = faster/smaller than MySQL (better)
- Ratio > 1.00x = slower/larger than MySQL (worse)
- Ratio = 1.00x = same as MySQL
""")

    # Save comparison results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(comparison, f, indent=2)
        print(f"Comparison saved to: {output_file}")

    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Compare PostgreSQL and MySQL JSON benchmark results')
    parser.add_argument('--pg-results', default='./results/benchmark_results.json',
                        help='PostgreSQL benchmark results file')
    parser.add_argument('--mysql-results', default='./results/mysql_benchmark_results.json',
                        help='MySQL benchmark results file')
    parser.add_argument('--output', default='./results/comparison_results.json',
                        help='Output file for comparison results')
    args = parser.parse_args()

    return compare_benchmarks(args.pg_results, args.mysql_results, args.output)


if __name__ == '__main__':
    sys.exit(main())
