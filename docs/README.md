# Time Series Commons - Documentation

This directory contains documentation for the Time Series Commons website.

## Available Guides

### Domain Image System
- **[DOMAIN_IMAGES_QUICK_START.md](../DOMAIN_IMAGES_QUICK_START.md)** - Quick start guide in project root
- **[DOMAIN_IMAGES_GUIDE.md](DOMAIN_IMAGES_GUIDE.md)** - Complete guide for replacing placeholder images
- **[DOMAIN_SYSTEM_SUMMARY.md](DOMAIN_SYSTEM_SUMMARY.md)** - Implementation details and technical overview

### Data Management
- **[UPDATING_DATA.md](../UPDATING_DATA.md)** - How to update datasets/models from CSV (in project root)
- **[scripts/README.md](../scripts/README.md)** - Script documentation
- **[scripts/QUICK_START.md](../scripts/QUICK_START.md)** - CSV to JSON converter quick start

## Quick Links

### Update Your Data
```bash
./scripts/update_data.sh
```
Converts CSV → JSON, updates website data

### Replace Domain Images
1. Find images for each of 15 domains
2. Save as `pics/domains/[domain-name].jpg`
3. Refresh website

### Validate Domain Mappings
```bash
python3 scripts/validate_domain_mapping.py
```
Verifies all datasets are properly categorized

## Overview

The Time Series Commons website consists of:

1. **Homepage** (`index.html`) - Mission, team, partners
2. **Models Catalog** (`models.html`) - Browse datasets and models
3. **Projects** (`projects.html`) - Research projects
4. **Publications** (`publications.html`) - Papers and research
5. **Awards** (`awards.html`) - Recognition and achievements

## Data Flow

```
CSV File (source of truth)
    ↓
scripts/csv_to_json.py
    ↓
data/models.json (website data)
    ↓
js/models.js (renders catalog)
    +
data/domain-config.json (domain images)
    ↓
Models page with domain-specific images
```

## Key Features

- **Domain Image System**: 15 categories with background images
- **CSV-Driven Updates**: Easy data updates from spreadsheet
- **Automatic Categorization**: Smart keyword matching for domains
- **Responsive Design**: Works on all devices
- **Search & Filter**: Find datasets quickly
- **Modal Details**: Click any dataset for full information

## Development

### File Structure
```
Time-Series-Commons/
├── index.html              # Homepage
├── models.html             # Catalog page
├── css/
│   └── styles.css          # Main stylesheet
├── js/
│   └── models.js           # Catalog logic
├── data/
│   ├── models.json         # Datasets/models (generated)
│   └── domain-config.json  # Domain configuration
├── pics/
│   ├── img/               # Team photos, logos
│   └── domains/           # Domain category images
├── scripts/
│   ├── csv_to_json.py             # CSV converter
│   ├── generate_placeholder_images.py  # Image generator
│   └── validate_domain_mapping.py      # Validation
└── docs/
    └── (this directory)
```

### Making Changes

**Update Datasets:**
1. Edit CSV file
2. Run `./scripts/update_data.sh`
3. Refresh website

**Update Domain Images:**
1. Replace files in `pics/domains/`
2. Refresh website

**Adjust Domain Mappings:**
1. Edit `data/domain-config.json`
2. Refresh website

## Helpful Commands

```bash
# Update website data from CSV
./scripts/update_data.sh

# Generate placeholder images
python3 scripts/generate_placeholder_images.py

# Validate domain mappings
python3 scripts/validate_domain_mapping.py

# Start local web server (for testing)
python3 -m http.server 8000
```

## Support

For issues or questions:
1. Check relevant guide in this docs/ directory
2. Review script output for error messages
3. Check browser console for JavaScript errors
4. Verify file paths and permissions

---

**Project**: Time Series Commons  
**Documentation Version**: 1.0  
**Last Updated**: 2026-01-23
