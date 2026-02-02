# Quick Start - CSV to JSON Converter

## 🎯 Purpose
Automatically convert your CSV dataset file to the JSON format used by the website, so you can easily update datasets and models without manual JSON editing.

## 🚀 Quick Commands

### Update Data (Easiest Method)
```bash
./scripts/update_data.sh
```

### Or Using Python Directly
```bash
python3 scripts/csv_to_json.py
```

## 📝 What You'll See

```
📖 Reading CSV from: Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv
✅ Successfully converted 815 datasets
📝 JSON saved to: data/models.json

📊 Summary:
   - Total datasets: 815
   - Unique models: 78
   - Unique domains: 244

🎉 Done! You can now refresh your website to see the updated data.
```

## 📋 Typical Workflow

1. **Edit the CSV file**
   - Add new datasets
   - Update model evaluations (Y/X values)
   - Modify descriptions

2. **Run the update script**
   ```bash
   ./scripts/update_data.sh
   ```

3. **Refresh your website**
   - No server restart needed
   - Changes appear immediately

## 💡 Key Features

✅ **Automatic Conversion** - Handles all CSV → JSON conversion
✅ **Safe to Rerun** - Same input = same output (idempotent)
✅ **No Manual Editing** - Never touch JSON files directly
✅ **Preserves Data** - All information maintained
✅ **Error Checking** - Clear error messages if issues occur
✅ **Fast Updates** - Edit CSV, run script, refresh page. Done!

## 📊 CSV Structure

### Metadata Columns (Required)
- Dataset Name
- Domain
- Number of Variables at each time point
- Number of Time Points
- Time interval between points
- Link to Data
- Detailed Description

### Model Columns (All columns after metadata)
- **Y** → Model evaluated on this dataset ✅
- **X** → Model considered but not included ⚠️
- **Empty** → Not tracked (omitted)

## 🎓 Examples

### Example 1: Add a New Dataset
```csv
Dataset Name,Domain,...,Informer,Monash,...
My New Dataset,Finance,...,Y,Y,...
```
Run script → Refresh page → New dataset appears!

### Example 2: Update Model Evaluation
Change `X` to `Y` in CSV → Run script → Model now shows as evaluated!

### Example 3: Add New Model
Add new column "NewModel" → Mark datasets with Y → Run script → Model appears!

## 🆘 Common Issues

**"CSV file not found"**
→ Ensure CSV is in project root directory

**"Permission denied"**
→ Run: `chmod +x scripts/update_data.sh`

**Changes not showing**
→ Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)

**Python not found**
→ Install Python 3.6+ from python.org

## 📚 More Documentation

- **scripts/README.md** - Detailed technical documentation
- **UPDATING_DATA.md** - Complete guide with examples and troubleshooting

## ✨ That's It!

You now have a simple, reliable way to keep your website data up-to-date:

**Edit CSV → Run Script → Refresh Page** ✅

No complex processes, no manual JSON editing, no room for errors!
