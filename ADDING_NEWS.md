# Adding News Items - Quick Guide

This guide explains how to add new news items to the homepage Recent Updates section.

## Quick Start

1. Open `data/news.json`
2. Add your new item at the **top** of the `news` array
3. Save the file
4. Refresh the homepage to see your changes

## News Item Structure

```json
{
  "id": "unique-identifier",
  "date": "YYYY-MM-DD",
  "type": "paper|release|talk|award",
  "title": "Your News Title",
  "description": "Brief description of the news item",
  "image": "path/to/image.png",
  "link": "url-or-page.html"
}
```

## Field Descriptions

- **id**: Unique identifier (e.g., "kdd2026-submission")
- **date**: Date in YYYY-MM-DD format (e.g., "2026-01-23")
- **type**: Category - use one of:
  - `paper` - Paper submissions, acceptances, publications
  - `release` - Dataset or model releases
  - `talk` - Conference talks, presentations
  - `award` - Awards, grants, recognitions
- **title**: Short, descriptive title
- **description**: 1-2 sentence description
- **image**: Path to image (e.g., "pics/img/yourimage.png")
- **link**: URL or page to link to when clicked

## Example - Adding a Paper Submission

```json
{
  "news": [
    {
      "id": "neurips2026-submission",
      "date": "2026-05-15",
      "type": "paper",
      "title": "New Paper Submitted to NeurIPS 2026",
      "description": "Our latest research on time series forecasting has been submitted to NeurIPS 2026.",
      "image": "pics/img/neurips-paper.png",
      "link": "publications.html"
    },
    ... existing items ...
  ]
}
```

## Badge Colors

News items are automatically color-coded:
- **Paper** (Blue): #2E86AB
- **Release** (Green): #27ae60
- **Talk** (Purple): #9b59b6
- **Award** (Gold): #f39c12

## Display Rules

- Only the **3 most recent** items are shown on the homepage
- Items are automatically sorted by date (newest first)
- Older items remain in the JSON file but won't display unless they're in the top 3

## Tips

1. **Always add new items at the top** of the array
2. **Use consistent date format** (YYYY-MM-DD) for proper sorting
3. **Keep titles short** - aim for 5-8 words
4. **Keep descriptions concise** - 1-2 sentences max
5. **Use descriptive IDs** - helps with tracking and updates
6. **Test images** - ensure image paths are correct

## Common News Types

### Paper Milestones
- Submission: "Paper Submitted to [Conference]"
- Acceptance: "Paper Accepted to [Conference]"
- Publication: "Paper Published in [Journal]"
- ArXiv: "New Preprint Available on ArXiv"

### Releases
- "New Dataset Released: [Name]"
- "Model [Name] v2.0 Released"
- "Code Repository Now Public"

### Talks & Presentations
- "Presenting at [Conference] [Year]"
- "Invited Talk at [Institution]"
- "Webinar: [Topic]"

### Awards
- "Awarded [Grant Name]"
- "Best Paper Award at [Conference]"
- "[Student Name] Receives [Award]"

## File Locations

- **News Data**: `data/news.json`
- **News JavaScript**: `js/news.js`
- **CSS Styles**: `css/styles.css` (section 5.5)
- **HTML Section**: `index.html` (after Mission Statement)

## Troubleshooting

**News not showing?**
- Check browser console for errors
- Verify JSON syntax (use a JSON validator)
- Ensure image paths are correct
- Clear browser cache and refresh

**Wrong order?**
- Check date format (must be YYYY-MM-DD)
- Dates should be in quotes
- Verify dates are accurate

**Image not displaying?**
- Check image path is correct
- Ensure image file exists
- Try with a different image first

## Need Help?

If you encounter issues:
1. Check the browser console (F12 → Console tab)
2. Validate your JSON at https://jsonlint.com
3. Ensure all required fields are present
4. Check image paths are relative to the root directory
