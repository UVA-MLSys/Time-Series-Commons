# CSV to JSON Conversion Script

This directory contains scripts for converting the CSV dataset file to the JSON format used by the website.

## Quick Start

### Option 1: Using Python directly
```bash
python scripts/csv_to_json.py
```

### Option 2: Using the shell script (Unix/Mac)
```bash
./scripts/update_data.sh
```

## What it does

The script reads `Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv` from the project root and:

1. **Parses dataset metadata:**
   - Dataset Name
   - Domain
   - Number of Variables
   - Number of Time Points
   - Time Interval
   - Links to data
   - Descriptions

2. **Identifies model evaluations:**
   - Reads all model columns (after metadata columns)
   - Converts Y → evaluated (true)
   - Converts X → considered but not included (false)
   - Omits empty values

3. **Generates `data/models.json`:**
   - Creates properly formatted JSON for the website
   - Automatically generates dataset IDs
   - Preserves all metadata and benchmarks

## Requirements

- Python 3.6 or higher (standard library only, no extra packages needed)

## Usage Workflow

1. **Update the CSV file** with new datasets or model evaluations
2. **Run the conversion script:**
   ```bash
   python scripts/csv_to_json.py
   ```
3. **Refresh your website** - the changes will appear immediately

## Output

The script generates `data/models.json` with this structure:

```json
{
  "models": [
    {
      "id": "dataset-name",
      "name": "Dataset Name",
      "domain": "Domain",
      "timePoints": "1000",
      "interval": "Daily",
      "variables": "Univariate",
      "dimensions": "1",
      "description": "Dataset description...",
      "dataLink": "https://...",
      "paperLink": "",
      "benchmarks": {
        "ModelName1": true,
        "ModelName2": false,
        ...
      }
    },
    ...
  ]
}
```

## Troubleshooting

### CSV file not found
Make sure the CSV file is in the project root directory with the exact name:
`Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv`

### Permission denied (Unix/Mac)
Make the scripts executable:
```bash
chmod +x scripts/csv_to_json.py
chmod +x scripts/update_data.sh
```

### Python not found
Ensure Python 3 is installed:
```bash
python3 --version
```

If needed, use `python3` instead of `python`:
```bash
python3 scripts/csv_to_json.py
```

## Notes

- The script preserves existing data by completely regenerating the JSON file
- Backup your `data/models.json` before running if you have manual changes
- The script is idempotent - running it multiple times produces the same result
- No data is lost during conversion (all CSV columns are mapped)
