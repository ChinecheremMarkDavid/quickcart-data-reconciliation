"""
QuickCart MongoDB Archival Script
Loads raw JSON transaction logs into MongoDB for archival purposes.
"""

import json
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, ConnectionFailure
from tqdm import tqdm
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MongoDBArchiver:
    """Archives raw transaction logs to MongoDB."""
    
    def __init__(self, mongo_uri: str, database_name: str = "quickcart"):
        """
        Initialize MongoDB connection.
        
        Args:
            mongo_uri: MongoDB connection string
            database_name: Name of the database
        """
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        self.client = None
        self.db = None
        self.collection = None
        
        self.stats = {
            'total_processed': 0,
            'successfully_inserted': 0,
            'duplicates_skipped': 0,
            'errors': 0
        }
    
    def connect(self):
        """Establish connection to MongoDB."""
        try:
            print("🔌 Connecting to MongoDB...")
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            
            # Test connection
            self.client.server_info()
            
            self.db = self.client[self.database_name]
            self.collection = self.db['raw_transaction_logs']
            
            # Create index on event_id for faster lookups and prevent duplicates
            self.collection.create_index('event.id', unique=True)
            
            print(f"✅ Connected to MongoDB database: {self.database_name}")
            print(f"📁 Using collection: raw_transaction_logs")
            
        except ConnectionFailure as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    def load_jsonl_file(self, file_path: str):
        """
        Load and parse JSONL file.
        
        Args:
            file_path: Path to raw_data.jsonl
        
        Returns:
            List of parsed JSON documents
        """
        documents = []
        
        print(f"\n📂 Reading file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"📊 Found {len(lines):,} records")
        
        for line in tqdm(lines, desc="Parsing JSON"):
            self.stats['total_processed'] += 1
            
            try:
                doc = json.loads(line.strip())
                
                # Add metadata for archival tracking
                doc['_archived_at'] = datetime.utcnow()
                doc['_source_file'] = Path(file_path).name
                
                documents.append(doc)
                
            except json.JSONDecodeError as e:
                print(f"\n⚠️  Skipping malformed JSON at line {self.stats['total_processed']}: {e}")
                self.stats['errors'] += 1
                continue
        
        return documents
    
    def batch_insert(self, documents: list, batch_size: int = 1000):
        """
        Insert documents in batches to MongoDB.
        
        Args:
            documents: List of documents to insert
            batch_size: Number of documents per batch
        """
        print(f"\n💾 Inserting {len(documents):,} documents to MongoDB...")
        print(f"📦 Batch size: {batch_size}")
        
        total_batches = (len(documents) + batch_size - 1) // batch_size
        
        for i in tqdm(range(0, len(documents), batch_size), 
                     total=total_batches, 
                     desc="Uploading"):
            
            batch = documents[i:i + batch_size]
            
            try:
                result = self.collection.insert_many(
                    batch, 
                    ordered=False  # Continue on duplicate key errors
                )
                self.stats['successfully_inserted'] += len(result.inserted_ids)
                
            except BulkWriteError as e:
                # Count duplicates
                duplicate_errors = sum(
                    1 for error in e.details.get('writeErrors', [])
                    if error.get('code') == 11000  # Duplicate key error
                )
                self.stats['duplicates_skipped'] += duplicate_errors
                
                # Count actual inserts from this batch
                inserted_count = e.details.get('nInserted', 0)
                self.stats['successfully_inserted'] += inserted_count
                
                # Count other errors
                other_errors = len(e.details.get('writeErrors', [])) - duplicate_errors
                self.stats['errors'] += other_errors
                
            except Exception as e:
                print(f"\n❌ Unexpected error in batch: {e}")
                self.stats['errors'] += len(batch)
    
    def verify_data(self):
        """Verify data was inserted correctly."""
        print("\n🔍 Verifying data integrity...")
        
        # Count documents
        doc_count = self.collection.count_documents({})
        print(f"✅ Total documents in MongoDB: {doc_count:,}")
        
        # Sample document
        sample = self.collection.find_one()
        if sample:
            print("\n📄 Sample document structure:")
            print(json.dumps({
                'event_id': sample.get('event', {}).get('id'),
                'event_type': sample.get('event', {}).get('type'),
                'payment_id': sample.get('entity', {}).get('payment', {}).get('id'),
                'archived_at': str(sample.get('_archived_at')),
            }, indent=2))
    
    def print_stats(self):
        """Print archival statistics."""
        print("\n" + "="*60)
        print("📊 MONGODB ARCHIVAL STATISTICS")
        print("="*60)
        print(f"Total records processed:     {self.stats['total_processed']:>10,}")
        print(f"Successfully inserted:       {self.stats['successfully_inserted']:>10,}")
        print(f"Duplicates skipped:          {self.stats['duplicates_skipped']:>10,}")
        print(f"Errors encountered:          {self.stats['errors']:>10,}")
        
        if self.stats['total_processed'] > 0:
            success_rate = (self.stats['successfully_inserted'] / self.stats['total_processed']) * 100
            print(f"\nSuccess rate: {success_rate:.2f}%")
        print("="*60)
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("\n🔌 MongoDB connection closed")


def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("QuickCart MongoDB Archival Tool")
    print("="*60 + "\n")
    
    # Configuration
    input_file = "quickcart_data/raw_data.jsonl"
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    database_name = "quickcart"
    
    # Check if input file exists
    if not Path(input_file).exists():
        print(f"❌ Error: Input file not found: {input_file}")
        print("Please run generate_quickcart_data.py first!")
        return
    
    # Initialize archiver
    archiver = MongoDBArchiver(mongo_uri, database_name)
    
    try:
        # Connect to MongoDB
        archiver.connect()
        
        # Load JSONL file
        documents = archiver.load_jsonl_file(input_file)
        
        if not documents:
            print("❌ No documents to insert!")
            return
        
        # Insert to MongoDB
        archiver.batch_insert(documents)
        
        # Verify
        archiver.verify_data()
        
        # Print stats
        archiver.print_stats()
        
        print("\n✅ Archival complete!")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
    
    finally:
        archiver.close()


if __name__ == "__main__":
    main()