import os
import argparse
from storage import StorageUtil
import pandas as pd
from pathlib import Path
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 100)
pd.set_option('display.width', 1000)


def print_storage_data(date: str = None, last_days: int = None, show_raw: bool = False, export_path: str = None):
    """
    Print data from storage with optional date filtering and export capability
    
    Args:
        date: Specific date in YYYY-MM-DD format
        last_days: Number of last days to show
        show_raw: Show raw data instead of summary
        export_path: Local directory path to export files
    """
    storage = StorageUtil()
    # storage.delete_data(filepath='newsletter-digest/2024-04-10.parquet')
    # Create export directory if needed
    if export_path:
        export_dir = Path(export_path)
        export_dir.mkdir(parents=True, exist_ok=True)
    
    # List all files in storage
    blobs = storage.list_blobs(prefix='newsletter-digest/')
    
    # Filter files by date if specified
    if date:
        blobs = [b for b in blobs if date in b['name']]
    elif last_days:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=last_days)
        blobs = [b for b in blobs if datetime.strptime(
            b['updated'], '%Y-%m-%d %H:%M:%S') >= cutoff
        ]

    if not blobs:
        print("No files found matching criteria")
        return

    # Print and export each file's content
    for blob in blobs:
        print(f"\n{'='*80}")
        print(f"File: {blob['name']}")
        print(f"Updated: {blob['updated']}")
        print(f"Size: {blob['size']}")
        print(f"{'='*80}\n")

        try:
            data = storage.read_data(blob['name'])
            
            if isinstance(data, pd.DataFrame):
                if show_raw:
                    print(data)
                else:
                    print("\nSummary:")
                    print(f"Total rows: {len(data)}")
                    print("\nColumn info:")
                    print(data.dtypes)
                    print("\nFirst 5 rows:")
                    print(data.head())
                    
                    if 'criteria' in data.columns:
                        print("\nUnique criteria:")
                        criteria = data['criteria'].explode().unique()
                        print(criteria)
                
                # Export DataFrame if path provided
                if export_path:
                    filename = os.path.basename(blob['name'])
                    export_file = export_dir / filename
                    data.to_parquet(export_file)
                    print(f"\nExported to: {export_file}")
                    
                    # Also export as CSV for easy viewing
                    csv_file = export_file.with_suffix('.csv')
                    data.to_csv(csv_file, index=False)
                    print(f"CSV exported to: {csv_file}")
            
            else:
                import json
                print(json.dumps(data, indent=2))
                
                # Export JSON if path provided
                if export_path:
                    filename = os.path.basename(blob['name'])
                    if not filename.endswith('.json'):
                        filename += '.json'
                    export_file = export_dir / filename
                    with open(export_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"\nExported to: {export_file}")
                
        except Exception as e:
            print(f"Error reading file: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Print and export storage data')
    parser.add_argument('--date', help='Filter by date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, help='Show last N days')
    parser.add_argument('--raw', action='store_true', help='Show raw data')
    parser.add_argument('--export', help='Export to local directory path')
    
    args = parser.parse_args()
    print_storage_data(args.date, args.days, args.raw, args.export)