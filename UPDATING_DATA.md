# Updating Website Data from CSV

This guide explains how to update the datasets and models on your website using the CSV file.

## Quick Update Process

When you update the CSV file with new datasets or model evaluations, follow these steps:

### 1. Edit the CSV File
Open and edit: `Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv`

Add or update:
- Dataset names and metadata
- Model evaluations (Y = evaluated, X = considered but not included)

### 2. Run the Update Script

**Option A: Using the shell script (recommended)**
```bash
./scripts/update_data.sh
```

**Option B: Using Python directly**
```bash
python3 scripts/csv_to_json.py
```

**Option C: Using Python (if python3 not available)**
```bash
python scripts/csv_to_json.py
```

### 3. Refresh Your Website
The changes will appear immediately when you refresh the page!

## What Gets Updated

The script automatically updates:
- ✅ All datasets in the Models page
- ✅ Dataset metadata (domain, time points, intervals, etc.)
- ✅ Model evaluation status (benchmarks)
- ✅ Dataset descriptions and links
- ✅ Featured datasets selection (first 4 datasets)

## CSV Format

### Required Columns
- **Dataset Name** - Name of the dataset
- **Domain** - Domain/category (e.g., "Health", "Finance", "Energy")
- **Number of Variables at each time point** - Variable count or description
- **Number of Time Points** - Total time points in dataset
- **Time interval between points** - Sampling frequency (e.g., "Hourly", "Daily")
- **Link to Data** - URL to access the dataset
- **Detailed Description** - Full dataset description

### Model Columns
All columns after the metadata columns represent models:
- **Y** = Model was evaluated on this dataset (appears as evaluated)
- **X** = Model was considered but not included (appears as not evaluated)
- **(empty)** = Not tracked (omitted from benchmarks)

## Examples

### Adding a New Dataset
1. Add a new row in the CSV file
2. Fill in all metadata columns
3. Mark relevant models with Y or X
4. Run: `./scripts/update_data.sh`
5. Refresh website

### Adding a New Model
1. Add a new column with the model name as header
2. Mark datasets where this model is evaluated with Y
3. Run: `./scripts/update_data.sh`
4. Refresh website

### Updating Model Evaluations
1. Find the dataset row
2. Change Y/X values in model columns
3. Run: `./scripts/update_data.sh`
4. Refresh website

## Technical Details

### Script Behavior
- Completely regenerates `data/models.json` from CSV
- Preserves all data (idempotent - safe to run multiple times)
- Automatically generates dataset IDs from names
- Handles Unicode and special characters properly
- No manual JSON editing needed!

### Output Location
Generated file: `data/models.json`

### Backup Recommendation
Before major updates, backup your current JSON:
```bash
cp data/models.json data/models.json.backup
```

## Troubleshooting

### "CSV file not found"
Make sure the CSV file is in the project root with the exact name:
`Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv`

### "Python not found"
Install Python 3.6 or higher from python.org

### Changes not appearing
1. Hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)
2. Clear browser cache
3. Check browser console for errors
4. Verify `data/models.json` was updated (check timestamp)

### Script errors
Check the error message and ensure:
- CSV file is not open in another program
- CSV file is properly formatted (no extra commas in descriptions)
- File permissions allow reading/writing

## Summary Statistics

After running the script, you'll see:
- Total datasets converted
- Number of unique models
- Number of unique domains

Example output:
```
✅ Successfully converted 815 datasets
📝 JSON saved to: data/models.json

📊 Summary:
   - Total datasets: 815
   - Unique models: 78
   - Unique domains: 244
```

## Need Help?

See `scripts/README.md` for more detailed documentation about the conversion script.
