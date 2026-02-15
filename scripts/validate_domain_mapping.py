#!/usr/bin/env python3
"""
Validate Domain Mapping - Verify all datasets are mapped to domain categories
Shows which category each dataset is assigned to and ensures 100% coverage.

Usage:
    python scripts/validate_domain_mapping.py
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

def match_domain_to_category(domain_name, domain_config):
    """
    Match a dataset domain to a category using the same logic as JavaScript
    
    Args:
        domain_name: Original domain name from dataset
        domain_config: Loaded domain configuration
        
    Returns:
        tuple: (category_name, match_type)
    """
    if not domain_name:
        domain_name = 'Sensor'
    
    domain_lower = domain_name.lower()
    
    # Try exact match first
    for category, config in domain_config['domains'].items():
        if category.lower() == domain_lower:
            return (category, 'exact')
    
    # Try keyword matching
    best_match = None
    max_match_count = 0
    
    for category, config in domain_config['domains'].items():
        match_count = 0
        matched_keywords = []
        
        for keyword in config['keywords']:
            if keyword.lower() in domain_lower:
                match_count += 1
                matched_keywords.append(keyword)
        
        if match_count > max_match_count:
            max_match_count = match_count
            best_match = (category, f'keyword: {", ".join(matched_keywords[:3])}')
    
    if best_match:
        return best_match
    
    # Fallback to Sensor
    return ('Sensor', 'fallback')

def main():
    """Validate domain mapping for all datasets"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    models_path = project_root / 'data' / 'models.json'
    config_path = project_root / 'data' / 'domain-config.json'
    
    # Load data
    print("📖 Loading data...")
    
    try:
        with open(models_path, 'r') as f:
            models_data = json.load(f)
        
        with open(config_path, 'r') as f:
            domain_config = json.load(f)
    except FileNotFoundError as e:
        print(f"❌ Error: Required file not found: {e}")
        sys.exit(1)
    
    datasets = models_data['models']
    
    print(f"✓ Loaded {len(datasets)} datasets")
    print(f"✓ Loaded {len(domain_config['domains'])} domain categories")
    print()
    
    # Validate each dataset
    print("🔍 Validating domain mappings...")
    print()
    
    category_counts = defaultdict(int)
    unmatched_domains = set()
    mapping_report = []
    
    for dataset in datasets:
        original_domain = dataset.get('domain', 'Unknown')
        category, match_type = match_domain_to_category(original_domain, domain_config)
        
        category_counts[category] += 1
        
        # Record mapping for detailed report
        mapping_report.append({
            'dataset': dataset['name'],
            'original_domain': original_domain,
            'category': category,
            'match_type': match_type
        })
        
        # Track fallbacks
        if match_type == 'fallback':
            unmatched_domains.add(original_domain)
    
    # Display summary
    print("📊 Domain Category Distribution:")
    print("=" * 70)
    
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    for category, count in sorted_categories:
        percentage = (count / len(datasets)) * 100
        bar_length = int(percentage / 2)
        bar = '█' * bar_length
        print(f"{category:20s} | {count:4d} datasets ({percentage:5.1f}%) {bar}")
    
    print("=" * 70)
    print(f"Total: {len(datasets)} datasets")
    print()
    
    # Check for unmatched domains
    if unmatched_domains:
        print("⚠️  Domains using fallback mapping (should be 0):")
        for domain in sorted(unmatched_domains):
            print(f"   - {domain}")
        print()
        print("💡 Consider adding keywords to domain-config.json to match these domains")
    else:
        print("✅ 100% Coverage - All datasets successfully mapped!")
    
    print()
    
    # Offer detailed report option
    print("📝 Detailed mapping report available.")
    print("   To see full mapping for each dataset, review mapping_report variable in script.")
    print()
    
    # Sample mappings
    print("📋 Sample Mappings (first 10 datasets):")
    print("-" * 70)
    for entry in mapping_report[:10]:
        print(f"Dataset: {entry['dataset']}")
        print(f"  Original: {entry['original_domain']}")
        print(f"  Category: {entry['category']} ({entry['match_type']})")
        print()
    
    # Save detailed report to file
    report_path = project_root / 'domain_mapping_report.json'
    with open(report_path, 'w') as f:
        json.dump({
            'summary': dict(category_counts),
            'total_datasets': len(datasets),
            'coverage_percent': 100 - (len(unmatched_domains) / len(datasets) * 100 if unmatched_domains else 0),
            'unmatched_domains': list(unmatched_domains),
            'detailed_mappings': mapping_report
        }, f, indent=2)
    
    print(f"📄 Full report saved to: {report_path}")
    print()
    
    if unmatched_domains:
        print("⚠️  Warning: Some domains are using fallback mapping")
        sys.exit(1)
    else:
        print("🎉 Success! All domains properly categorized.")
        sys.exit(0)

if __name__ == '__main__':
    main()
