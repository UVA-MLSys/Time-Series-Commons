# Time Series Commons - Models Catalog Management Guide

This guide explains how to manage the time series models catalog on the Time Series Commons website.

## Overview

The models catalog is powered by a single JSON data file (`data/models.json`) that contains information about all time series datasets. This architecture makes it easy to add, remove, or modify model information without touching the HTML or JavaScript code.

## File Structure

```
Time-Series-Commons/
├── data/
│   └── models.json          # Single source of truth for all model data
├── js/
│   └── models.js            # JavaScript that renders the catalog
├── css/
│   └── styles.css           # Styling for the catalog
└── index.html               # Main website with models section
```

## Data Format

The `models.json` file follows this structure:

```json
{
  "models": [
    {
      "id": "unique-identifier",
      "name": "Dataset Name",
      "domain": "Primary Domain (e.g., Healthcare, Finance)",
      "variables": "Number or description of variables",
      "timePoints": "Number of time points",
      "interval": "Time interval (e.g., Hourly, Daily, Monthly)",
      "repository": "Primary data source or repository",
      "dataLink": "Direct link to access the data",
      "description": "Detailed description of the dataset",
      "comments": "Additional comments or notes",
      "benchmarks": {
        "Informer": true,
        "Prophet": true,
        "TimeGPT": true
        // ... other benchmarks (true/false or other values)
      }
    }
  ]
}
```

## Adding a New Model

To add a new model to the catalog:

1. Open `data/models.json` in a text editor
2. Add a new entry to the `models` array
3. Follow the schema format shown above
4. Save the file
5. Refresh the website

### Example: Adding a New Dataset

```json
{
  "id": "my-new-dataset",
  "name": "My New Time Series Dataset",
  "domain": "Environmental Science",
  "variables": "15 (temperature, humidity, pressure, etc.)",
  "timePoints": "1000",
  "interval": "Hourly",
  "repository": "UCI Machine Learning Repository",
  "dataLink": "https://example.com/my-dataset",
  "description": "This dataset contains hourly measurements of environmental variables collected over 41 days in a research facility.",
  "comments": "Data has been preprocessed and normalized. Missing values have been interpolated.",
  "benchmarks": {
    "Informer": true,
    "Prophet": true,
    "TimeGPT": false,
    "AutoGluon": true
  }
}
```

### Important Notes

- **ID**: Must be unique. Use lowercase letters, numbers, and hyphens only
- **Name**: Display name shown in the catalog
- **Domain**: Can include multiple domains separated by commas (e.g., "Healthcare, Time Series")
- **Benchmarks**: Only include benchmarks where the model has been evaluated. Set to `true` if evaluated, `false` or omit if not

## Removing a Model

To remove a model from the catalog:

1. Open `data/models.json`
2. Find the model entry you want to remove
3. Delete the entire JSON object (including curly braces)
4. Ensure the JSON remains valid (proper commas between entries)
5. Save the file

## Updating Model Information

To update existing model information:

1. Open `data/models.json`
2. Find the model you want to update
3. Modify the relevant fields
4. Save the file
5. Refresh the website to see changes

### Common Updates

#### Updating Description
```json
{
  "id": "existing-dataset",
  "description": "Updated description with new information..."
}
```

#### Adding New Benchmark Results
```json
{
  "id": "existing-dataset",
  "benchmarks": {
    "Informer": true,
    "Prophet": true,
    "NewBenchmark": true  // Add new benchmark
  }
}
```

#### Updating Data Link
```json
{
  "id": "existing-dataset",
  "dataLink": "https://new-link.com/dataset"
}
```

## Supported Benchmarks

The catalog tracks evaluation across these popular time series benchmarks:

### Foundation Models
- TimeGPT
- Chronos (Pre, Eval1, Eval2)
- ChronosBolt (Pre, Eval1, Eval2)
- ChronosX (Pre, Eval1, Eval2, Synth)
- Tempo
- Timer-XL

### Classical & ML Models
- Informer
- Prophet
- AutoGluon
- Darts
- NeuralForecast
- TimesNet
- TimesFM

### Evaluation Archives
- UCR (UCR Time Series Classification Archive)
- UEA (UEA Time Series Classification Archive)
- Monash (Monash Time Series Forecasting Archive)
- M1, M2, M3, M4, M5, M6 (M-Competitions)

### Specialized Benchmarks
- TSB-UAD (Time Series Benchmark for Anomaly Detection)
- TSFM (Time Series Foundation Models)
- LLM-Time, LLM-Mixer, LLM-Prompt variants
- TSMamba (ZS, FullShot)
- And many more...

## Validation Tips

### JSON Validation
Before saving changes, validate your JSON:
- Use an online JSON validator (e.g., jsonlint.com)
- Use a code editor with JSON validation (VS Code, Sublime Text)
- Check for common errors:
  - Missing or extra commas
  - Unclosed brackets or braces
  - Unescaped quotes in strings

### Testing Changes Locally
1. Make changes to `models.json`
2. Open `index.html` in a web browser
3. Navigate to the Models section
4. Verify your changes appear correctly
5. Test filtering and search with your new/modified data

## Troubleshooting

### Models Don't Appear
- Check browser console for JavaScript errors
- Validate JSON syntax in `models.json`
- Ensure the file is in the correct location (`data/models.json`)
- Clear browser cache and refresh

### Search/Filter Not Working
- Verify the model has the correct field values
- Check that domain and interval values match expected formats
- Ensure benchmark names match exactly (case-sensitive)

### Modal Not Opening
- Check browser console for errors
- Verify the model has an `id` field
- Ensure JavaScript file is loaded (`js/models.js`)

## Best Practices

1. **Consistent Formatting**: Keep formatting consistent across all entries
2. **Complete Information**: Fill in all available fields for each model
3. **Accurate Benchmarks**: Only mark benchmarks as true if actually evaluated
4. **Descriptive Names**: Use clear, descriptive names for datasets
5. **URL Validation**: Test all links before adding them
6. **Regular Backups**: Keep backups of `models.json` before major changes

## Advanced: Regenerating from CSV

If you have an updated CSV file, you can regenerate the `models.json` file:

```bash
cd /path/to/Time-Series-Commons
python3 << 'EOF'
import csv
import json
import re

def clean_string(s):
    if s is None or s == '':
        return ''
    return str(s).strip()

def parse_csv_to_json():
    models = []
    
    with open('Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Extract benchmark columns
            benchmark_cols = [
                'Informer', 'Prophet', 'TimeGPT', 'Chronos-Pre', 'AutoGluon',
                # ... add all benchmark column names
            ]
            
            benchmarks = {}
            for col in benchmark_cols:
                val = clean_string(row.get(col, ''))
                if val in ['Y', 'X', 'y', 'x']:
                    benchmarks[col] = True
                elif val:
                    benchmarks[col] = val
            
            dataset_name = clean_string(row.get('Dataset Name', ''))
            if not dataset_name:
                continue
                
            model_id = re.sub(r'[^a-z0-9]+', '-', dataset_name.lower()).strip('-')
            
            model = {
                'id': model_id,
                'name': dataset_name,
                'domain': clean_string(row.get('Domain', '')),
                'variables': clean_string(row.get('Number of Variables at each time point', '')),
                'timePoints': clean_string(row.get('Number of Time Points', '')),
                'interval': clean_string(row.get('Time interval between points', '')),
                'repository': clean_string(row.get('Primary Source Repository', '')),
                'dataLink': clean_string(row.get('Link to Data', '')),
                'description': clean_string(row.get('Detailed Description', '')),
                'comments': clean_string(row.get('Comments', '')),
                'benchmarks': benchmarks
            }
            
            models.append(model)
    
    with open('data/models.json', 'w', encoding='utf-8') as f:
        json.dump({'models': models}, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully created models.json with {len(models)} models")

parse_csv_to_json()
EOF
```

## Support

For questions or issues with the models catalog:
- Check the browser console for error messages
- Review this documentation
- Validate your JSON syntax
- Test in a local environment first

## Version History

- **v1.0** (2025-01): Initial catalog system with 815+ models
  - JSON-based data management
  - Advanced filtering and search
  - Modal-based detail views
  - Responsive design

---

**Remember**: Always backup `models.json` before making significant changes!
