#!/usr/bin/env python3
"""
CSV to JSON Converter for Time Series Commons
Converts the CSV dataset file to models.json format for the website.

Usage:
    python scripts/csv_to_json.py
    
This will read the CSV file and generate/update data/models.json
"""

import csv
import json
import os
import sys
from pathlib import Path

def clean_value(value):
    """Clean and normalize CSV values"""
    if not value or value.strip() == '':
        return None
    return value.strip()

def parse_csv_to_json(csv_path):
    """
    Parse the CSV file and convert to JSON format
    
    Returns:
        dict: JSON structure with models array
    """
    datasets = []
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Get all column names to identify model columns
        fieldnames = reader.fieldnames
        
        # Identify model columns (those that come after the metadata columns)
        metadata_columns = [
            'Dataset Name', 'Domain', 'Number of Variables at each time point',
            'Number of Time Points', 'Time interval between points',
            'Primary Source Repository', 'Link to Data', 'Detailed Description',
            'Comments', 'Original Row #', 'Number of Versions', 'Reconciler Version',
            'Reconciler Status', 'Reconciliation Notes'
        ]
        
        # All columns after metadata are model evaluation columns
        model_columns = [col for col in fieldnames if col not in metadata_columns]
        
        for row in reader:
            dataset_name = clean_value(row.get('Dataset Name'))
            
            # Skip empty rows
            if not dataset_name:
                continue
            
            # Extract metadata
            domain = clean_value(row.get('Domain', ''))
            variables = clean_value(row.get('Number of Variables at each time point', ''))
            time_points = clean_value(row.get('Number of Time Points', ''))
            interval = clean_value(row.get('Time interval between points', 'Not specified'))
            data_link = clean_value(row.get('Link to Data', ''))
            description = clean_value(row.get('Detailed Description', ''))
            
            # Create dataset ID (lowercase, replace spaces with dashes)
            dataset_id = dataset_name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace(',', '')
            
            # Parse benchmarks (models)
            benchmarks = {}
            for model_col in model_columns:
                model_name = model_col.strip()
                if not model_name:
                    continue
                    
                # Get the value (Y, X, or empty)
                value = clean_value(row.get(model_col, ''))
                
                # Y means evaluated, X means considered but not included, empty means not evaluated
                if value == 'Y':
                    benchmarks[model_name] = True
                elif value == 'X':
                    benchmarks[model_name] = False
                # Don't include empty values
            
            # Determine dimensions based on variables
            dimensions = None
            if variables:
                if 'univariate' in variables.lower() or variables == '1' or variables.lower().startswith('1 '):
                    dimensions = '1'
                else:
                    # Try to extract number
                    try:
                        # Try to find a number in the string
                        import re
                        numbers = re.findall(r'\d+', variables)
                        if numbers:
                            dimensions = numbers[0]
                    except:
                        dimensions = variables
            
            # Build dataset object
            dataset = {
                'id': dataset_id,
                'name': dataset_name,
                'domain': domain if domain else 'General',
                'timePoints': time_points if time_points else 'Not specified',
                'interval': interval if interval else 'Not specified',
                'variables': variables if variables else 'Not specified',
                'dimensions': dimensions if dimensions else 'Not specified',
                'description': description if description else 'No description available.',
                'dataLink': data_link if data_link else '',
                'paperLink': '',  # Not in CSV, can be added manually if needed
                'benchmarks': benchmarks
            }
            
            datasets.append(dataset)
    
    return {'models': datasets}

def main():
    """Main function to convert CSV to JSON"""
    # Determine paths relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    csv_path = project_root / 'Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv'
    json_path = project_root / 'data' / 'models.json'
    
    # Check if CSV exists
    if not csv_path.exists():
        print(f"❌ Error: CSV file not found at {csv_path}")
        print(f"   Please ensure the CSV file is in the project root directory.")
        sys.exit(1)
    
    print(f"📖 Reading CSV from: {csv_path}")
    
    try:
        # Parse CSV
        data = parse_csv_to_json(csv_path)
        
        # Create data directory if it doesn't exist
        json_path.parent.mkdir(exist_ok=True)
        
        # Write JSON
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully converted {len(data['models'])} datasets")
        print(f"📝 JSON saved to: {json_path}")
        print(f"\n📊 Summary:")
        print(f"   - Total datasets: {len(data['models'])}")
        
        # Count unique models
        all_models = set()
        for dataset in data['models']:
            all_models.update(dataset['benchmarks'].keys())
        print(f"   - Unique models: {len(all_models)}")
        
        # Count domains
        domains = set(d['domain'] for d in data['models'])
        print(f"   - Unique domains: {len(domains)}")
        
        print(f"\n🎉 Done! You can now refresh your website to see the updated data.")
        
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
