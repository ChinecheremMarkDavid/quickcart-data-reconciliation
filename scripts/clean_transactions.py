
"""
QuickCart Transaction Cleaner
Reads raw_data.jsonl, cleans and normalizes transaction data,
outputs cleaned_transactions.csv for reconciliation.
"""

import json
import csv
import re
from pathlib import Path
from typing import Dict, Optional, List
from tqdm import tqdm


class TransactionCleaner:
    """Cleans and normalizes QuickCart transaction logs."""
    
    def __init__(self, input_file: str, output_file: str):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.stats = {
            'total_records': 0,
            'valid_records': 0,
            'test_filtered': 0,
            'invalid_amount': 0,
            'missing_data': 0,
            'noise_events': 0
        }
    
    def normalize_amount(self, amount) -> Optional[float]:
        """
        Normalize various amount formats to float (USD).
        
        Handles:
        - "$10.00" -> 10.00
        - "10.00" -> 10.00
        - 1000 (cents) -> 10.00
        - None/empty -> None
        """
        if amount is None or amount == "":
            return None
        
        # If it's already a number (int or float)
        if isinstance(amount, (int, float)):
            # Assume it's in cents if > 100 (heuristic)
            if amount >= 100:
                return round(amount / 100, 2)
            return float(amount)
        
        # If it's a string, clean it
        if isinstance(amount, str):
            # Remove currency symbols, spaces, commas
            cleaned = re.sub(r'[$USD\s,]', '', amount).strip()
            
            if not cleaned:
                return None
            
            try:
                value = float(cleaned)
                # If value is large, it's likely in cents
                if value >= 100:
                    return round(value / 100, 2)
                return round(value, 2)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def is_test_transaction(self, event_data: Dict) -> bool:
        """
        Identify test/sandbox transactions.
        
        Checks:
        - flags contain "test"
        - email contains "test"
        - event type is "heartbeat" or internal
        """
        # Check flags
        flags = event_data.get('payload', {}).get('flags', [])
        if flags and 'test' in flags:
            return True
        
        # Check email
        email = event_data.get('entity', {}).get('customer', {}).get('email', '')
        if email and 'test' in email.lower():
            return True
        
        # Check event type
        event_type = event_data.get('event', {}).get('type', '')
        if event_type in ['heartbeat', 'internal_ping']:
            return True
        
        return False
    
    def extract_transaction_data(self, event_data: Dict) -> Optional[Dict]:
        """
        Extract relevant fields from nested JSON.
        
        Returns None if record is invalid or should be filtered.
        """
        try:
            # Extract nested fields
            event = event_data.get('event', {})
            entity = event_data.get('entity', {})
            payload = event_data.get('payload', {})
            
            # Get required fields
            event_id = event.get('id')
            event_type = event.get('type')
            timestamp = event.get('ts')
            
            order_id = entity.get('order', {}).get('id')
            payment_id = entity.get('payment', {}).get('id')
            provider_ref = entity.get('payment', {}).get('provider_ref')
            provider = entity.get('payment', {}).get('provider')
            
            amount_raw = payload.get('Amount')
            status = payload.get('status')
            
            # Normalize amount
            amount_usd = self.normalize_amount(amount_raw)
            
            # Validation: Must have critical fields
            if not event_id or not payment_id:
                return None
            
            # Must have valid amount for financial transactions
            if amount_usd is None or amount_usd <= 0:
                return None
            
            # Must have status
            if not status:
                return None
            
            return {
                'event_id': event_id,
                'event_type': event_type,
                'timestamp': timestamp,
                'order_id': order_id if order_id else 'NULL',
                'payment_id': payment_id,
                'provider_ref': provider_ref if provider_ref else 'NULL',
                'provider': provider if provider else 'UNKNOWN',
                'amount_usd': amount_usd,
                'status': status,
            }
            
        except (KeyError, TypeError, AttributeError) as e:
            # Malformed JSON structure
            return None
    
    def process_file(self):
        """
        Main processing logic.
        Read JSONL, clean, filter, write CSV.
        """
        print(f"🔍 Reading from: {self.input_file}")
        print(f"📝 Writing to: {self.output_file}")
        
        # Ensure output directory exists
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        cleaned_records = []
        
        # Read and process each line
        with open(self.input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"📊 Processing {len(lines):,} records...")
        
        for line in tqdm(lines, desc="Cleaning"):
            self.stats['total_records'] += 1
            
            try:
                event_data = json.loads(line.strip())
            except json.JSONDecodeError:
                self.stats['missing_data'] += 1
                continue
            
            # Filter test transactions
            if self.is_test_transaction(event_data):
                self.stats['test_filtered'] += 1
                continue
            
            # Check for noise events
            event_type = event_data.get('event', {}).get('type', '')
            if event_type in ['heartbeat', 'ping']:
                self.stats['noise_events'] += 1
                continue
            
            # Extract and validate
            cleaned = self.extract_transaction_data(event_data)
            
            if cleaned is None:
                self.stats['invalid_amount'] += 1
                continue
            
            cleaned_records.append(cleaned)
            self.stats['valid_records'] += 1
        
        # Write to CSV
        if cleaned_records:
            fieldnames = cleaned_records[0].keys()
            
            with open(self.output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(cleaned_records)
            
            print(f"\n✅ Wrote {len(cleaned_records):,} cleaned records to {self.output_file}")
        else:
            print("\n❌ No valid records to write!")
        
        # Print statistics
        self.print_stats()
    
    def print_stats(self):
        """Print cleaning statistics."""
        print("\n" + "="*60)
        print("📊 CLEANING STATISTICS")
        print("="*60)
        print(f"Total records processed:     {self.stats['total_records']:>10,}")
        print(f"Valid records output:        {self.stats['valid_records']:>10,}")
        print(f"Test transactions filtered:  {self.stats['test_filtered']:>10,}")
        print(f"Invalid/missing amounts:     {self.stats['invalid_amount']:>10,}")
        print(f"Noise events filtered:       {self.stats['noise_events']:>10,}")
        print(f"Missing/malformed data:      {self.stats['missing_data']:>10,}")
        
        if self.stats['total_records'] > 0:
            success_rate = (self.stats['valid_records'] / self.stats['total_records']) * 100
            print(f"\nSuccess rate: {success_rate:.2f}%")
        print("="*60)


def main():
    """Main execution function."""
    # File paths
    input_file = "quickcart_data/raw_data.jsonl"
    output_file = "output/cleaned_transactions.csv"
    
    print("\n" + "="*60)
    print("QuickCart Transaction Data Cleaner")
    print("="*60 + "\n")
    
    # Initialize cleaner
    cleaner = TransactionCleaner(input_file, output_file)
    
    # Process
    cleaner.process_file()
    
    print("\n✅ Cleaning complete!")
    print(f"📁 Output saved to: {output_file}\n")


if __name__ == "__main__":
    main()