# Domain Images Guide

This guide explains how to replace the placeholder domain images with your own high-quality images.

## Overview

The Time Series Commons website uses domain-specific images as backgrounds for dataset and model cards. Each of the 15 main domains has an associated image that displays in the card header area.

## Current Domain Categories

Your website uses these 15 domain categories, each with a placeholder gradient image:

1. **Energy** - Power grids, solar panels, electricity consumption
2. **Synthetic** - Computer-generated data, simulations, abstract patterns
3. **Image** - Computer vision, image analysis, visual data
4. **Sensor** - IoT devices, sensor networks, monitoring equipment
5. **Motion** - Human activity, movement tracking, gestures
6. **Corporate** - Business operations, web services, IT infrastructure
7. **Transportation** - Traffic, vehicles, urban mobility, logistics
8. **Nature** - Environment, climate, weather, landscapes
9. **Industry** - Manufacturing, industrial automation, factories
10. **Economics** - Markets, GDP, economic indicators, currency
11. **Demographics** - Population, social dynamics, people
12. **Retail** - Shopping, e-commerce, sales, stores
13. **Microeconomics** - Finance, banking, stocks, investments
14. **Health** - Medical equipment, healthcare, wellness
15. **Audio** - Sound waves, speech, acoustic signals

## Image Specifications

### Recommended Dimensions
- **Width**: 1200px
- **Height**: 800px
- **Aspect Ratio**: 3:2

### Supported Formats
- **JPEG (.jpg)** - Recommended for photographs (smaller file size)
- **PNG (.png)** - For images with transparency (larger file size)
- **WebP (.webp)** - Modern format with better compression (if browser support needed)

### File Size Guidelines
- Aim for **under 500KB** per image
- Optimize images before uploading (use tools like TinyPNG, ImageOptim, or Squoosh)
- Balance quality and file size for fast page loading

## Image Style Guidelines

### Visual Characteristics
✅ **Do:**
- Use high-quality, professional images
- Choose images that clearly represent the domain
- Ensure good contrast and visual clarity
- Consider how images look with dark overlays (cards have a gradient overlay)
- Use images with subject matter in the center/middle area
- Prefer images with some depth/dimension

❌ **Don't:**
- Use images with too much text
- Choose busy/cluttered images
- Use low-resolution or pixelated images
- Select images with critical details at edges (they may be cropped)

### Overlay Consideration
The card system adds a dark gradient overlay (40% to 20% black from top-left to bottom-right) to ensure text and icons remain visible. Choose images that:
- Have good contrast even when darkened
- Don't have important details that would be obscured by overlay
- Work well with white text/icons on top

## How to Replace Images

### Step 1: Prepare Your Images
1. Resize images to 1200x800px (or maintain 3:2 aspect ratio)
2. Optimize file size to under 500KB
3. Save as JPEG with appropriate quality (85-90%)
4. Name files according to domain (see naming below)

### Step 2: Replace Placeholder Files
Navigate to the images directory:
```
Time-Series-Commons/pics/domains/
```

Replace these files with your images (keep the exact filenames):
- `energy.jpg`
- `synthetic.jpg`
- `image.jpg`
- `sensor.jpg`
- `motion.jpg`
- `corporate.jpg`
- `transportation.jpg`
- `nature.jpg`
- `industry.jpg`
- `economics.jpg`
- `demographics.jpg`
- `retail.jpg`
- `microeconomics.jpg`
- `health.jpg`
- `audio.jpg`

### Step 3: Verify
1. Refresh your website (hard refresh: Ctrl+F5 or Cmd+Shift+R)
2. Navigate to the Models page
3. Check that images display correctly in card headers
4. Verify images work in both grid and list views
5. Test on different screen sizes (responsive)

## Finding Images

### Recommended Sources

**Free Stock Photos:**
- [Unsplash](https://unsplash.com/) - High-quality, free images
- [Pexels](https://pexels.com/) - Curated free stock photos
- [Pixabay](https://pixabay.com/) - Large collection of free images

**Icon/Abstract:**
- [Freepik](https://freepik.com/) - Icons and illustrations (check license)
- [Vecteezy](https://vecteezy.com/) - Vectors and photos

### Search Terms by Domain

**Energy**: "power plant", "solar panels", "electricity grid", "wind turbines", "energy infrastructure"

**Synthetic**: "abstract pattern", "computer simulation", "data visualization", "digital abstract", "algorithm visualization"

**Image**: "computer vision", "image processing", "digital photography", "visual analysis", "camera sensor"

**Sensor**: "IoT devices", "sensor network", "monitoring equipment", "smart sensors", "industrial sensors"

**Motion**: "human activity", "motion tracking", "gesture control", "movement sensors", "activity recognition"

**Corporate**: "business meeting", "office workspace", "corporate headquarters", "IT infrastructure", "data center"

**Transportation**: "city traffic", "urban mobility", "transportation network", "vehicles", "logistics"

**Nature**: "forest landscape", "mountains", "environmental monitoring", "climate", "weather patterns"

**Industry**: "manufacturing plant", "industrial automation", "factory floor", "assembly line", "industrial equipment"

**Economics**: "stock market", "financial district", "economy growth", "currency exchange", "market trends"

**Demographics**: "diverse people", "population", "community", "social dynamics", "demographic data"

**Retail**: "shopping mall", "e-commerce", "retail store", "consumer shopping", "sales"

**Microeconomics**: "banking", "financial analysis", "stock trading", "investment", "financial markets"

**Health**: "medical equipment", "healthcare", "hospital", "wellness", "medical technology"

**Audio**: "sound waves", "audio spectrum", "music production", "speech recognition", "acoustic waves"

## Advanced: Adjusting Domain Keywords

If you find that datasets are being assigned to the wrong domain categories, you can adjust the keyword matching in:

```
Time-Series-Commons/data/domain-config.json
```

Edit the `keywords` array for any domain to improve matching. For example:

```json
{
  "domains": {
    "Energy": {
      "image": "pics/domains/energy.jpg",
      "color": "#f39c12",
      "keywords": ["energy", "power", "electricity", ...]
    }
  }
}
```

## Testing Your Changes

After replacing images:

1. **Visual Check**: View cards on models page
2. **Domain Mapping**: Verify datasets show correct domain images
3. **Performance**: Check page load time (images should load quickly)
4. **Responsive**: Test on mobile, tablet, desktop
5. **Browser Compatibility**: Test in Chrome, Firefox, Safari

## Troubleshooting

### Images not appearing
- Check file names match exactly (case-sensitive)
- Verify files are in `pics/domains/` directory
- Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)
- Check browser console for 404 errors

### Images look wrong
- Images may need better composition for card format
- Consider the dark overlay when choosing images
- Ensure images have good contrast

### File size too large
- Use image optimization tools
- Convert to JPEG if using PNG
- Reduce dimensions if larger than 1200x800px
- Lower JPEG quality to 80-85%

## Color Scheme Reference

Each domain has an associated color (currently used for fallbacks). You can see these in `data/domain-config.json`:

- Energy: #f39c12 (orange)
- Synthetic: #9b59b6 (purple)
- Image: #1abc9c (teal)
- Sensor: #3498db (blue)
- Motion: #2ecc71 (green)
- Corporate: #34495e (navy)
- Transportation: #e74c3c (red)
- Nature: #27ae60 (forest green)
- Industry: #2c3e50 (dark blue)
- Economics: #f1c40f (gold)
- Demographics: #16a085 (cyan)
- Retail: #e91e63 (pink)
- Microeconomics: #8e44ad (purple)
- Health: #c0392b (dark red)
- Audio: #9b59b6 (purple)

Consider these colors when choosing images to maintain visual consistency.

## Need Help?

If you encounter issues or need assistance:
1. Check browser console for errors
2. Verify file paths are correct
3. Ensure images meet size/format requirements
4. Review `data/domain-config.json` for configuration issues

---

**Last Updated**: Implementation Date  
**Version**: 1.0
