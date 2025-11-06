"""
Script to clean duplicate events from the CSV file
Run this once to remove existing duplicates
"""
import pandas as pd
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.vector_store_service import VectorStoreService

def clean_duplicates():
    """Remove duplicate events from CSV based on URL or title+date"""
    csv_path = "./backend/data/events_with_metadata.csv"

    try:
        # Load CSV
        df = pd.read_csv(csv_path)
        initial_count = len(df)
        print(f"Initial events count: {initial_count}")

        # Create unique key for each event (URL if available, otherwise title+date)
        def create_key(row):
            url = str(row.get('url', '')).strip().lower()
            if url and url != 'nan':
                return url
            title = str(row.get('title', '')).strip().lower()
            date = str(row.get('event_date', ''))
            return f"{title}|{date}"

        df['_key'] = df.apply(create_key, axis=1)

        # Keep first occurrence of each unique key
        df_clean = df.drop_duplicates(subset=['_key'], keep='first')

        # Remove the temporary key column
        df_clean = df_clean.drop(columns=['_key'])

        # Save cleaned CSV
        df_clean.to_csv(csv_path, index=False)

        duplicates_removed = initial_count - len(df_clean)
        print(f"Removed {duplicates_removed} duplicate events")
        print(f"Final events count: {len(df_clean)}")

        if duplicates_removed > 0:
            print("\nRebuilding vector store with cleaned data...")
            # Rebuild vector store
            vector_store = VectorStoreService(csv_path=csv_path)
            print("Vector store rebuilt successfully")

    except Exception as e:
        print(f"Error cleaning duplicates: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    clean_duplicates()
