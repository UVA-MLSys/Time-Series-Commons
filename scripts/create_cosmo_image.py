#!/usr/bin/env python3
"""
Create a placeholder image for Cosmo3DFlow publication
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Create output directory if needed
output_dir = "../pics/img"
os.makedirs(output_dir, exist_ok=True)

# Create image with cosmic colors
width, height = 800, 600
img = Image.new('RGB', (width, height), color='#0a0e27')
draw = ImageDraw.Draw(img)

# Create gradient background (dark blue to purple)
for y in range(height):
    r = int(10 + (138 - 10) * y / height)
    g = int(14 + (43 - 14) * y / height)
    b = int(39 + (226 - 39) * y / height)
    draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))

# Add some "stars" (small white dots)
import random
random.seed(42)
for _ in range(100):
    x = random.randint(0, width)
    y = random.randint(0, height)
    size = random.randint(1, 3)
    brightness = random.randint(200, 255)
    draw.ellipse([x, y, x+size, y+size], fill=(brightness, brightness, brightness))

# Add wavelet-like pattern (abstract representation)
center_x, center_y = width // 2, height // 2
for i in range(5):
    radius = 80 + i * 40
    thickness = 3 - i // 2
    alpha = 180 - i * 30
    # Draw concentric circles with varying opacity
    draw.ellipse(
        [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
        outline=(255, 255, 255, alpha),
        width=thickness
    )

# Add flowing lines (representing flow matching)
for i in range(8):
    angle = i * 45
    import math
    x1 = center_x + math.cos(math.radians(angle)) * 50
    y1 = center_y + math.sin(math.radians(angle)) * 50
    x2 = center_x + math.cos(math.radians(angle)) * 200
    y2 = center_y + math.sin(math.radians(angle)) * 200
    draw.line([(x1, y1), (x2, y2)], fill=(100, 150, 255), width=2)

# Add title text overlay
try:
    font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Add semi-transparent overlay for text
overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
overlay_draw = ImageDraw.Draw(overlay)
overlay_draw.rectangle([(0, height - 150), (width, height)], fill=(0, 0, 0, 180))
img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
draw = ImageDraw.Draw(img)

# Draw text
text1 = "Cosmo3DFlow"
text2 = "Wavelet Flow Matching"
draw.text((width // 2, height - 100), text1, fill=(255, 255, 255), anchor="mm", font=font_large)
draw.text((width // 2, height - 50), text2, fill=(200, 200, 255), anchor="mm", font=font_small)

# Save image
output_path = os.path.join(output_dir, "cosmo3dflow.png")
img.save(output_path, 'PNG', quality=95)
print(f"✅ Created: {output_path}")
print(f"   Size: {width}x{height}px")
