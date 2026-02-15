#!/usr/bin/env python3
"""
Generate placeholder gradient images for domain categories.
Creates simple gradient images that can be replaced with real photos later.

Usage:
    python scripts/generate_placeholder_images.py
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys

def create_gradient_image(width, height, color_hex, name, output_path):
    """
    Create a gradient image with a color overlay
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        color_hex: Primary color in hex format (e.g., "#f39c12")
        name: Domain name for labeling
        output_path: Path to save the image
    """
    # Convert hex to RGB
    color_hex = color_hex.lstrip('#')
    r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
    
    # Create image
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    
    # Create diagonal gradient
    for y in range(height):
        # Calculate gradient ratio (0.0 to 1.0)
        ratio = y / height
        
        # Darken the color as we go down
        new_r = int(r * (1.0 - ratio * 0.3))
        new_g = int(g * (1.0 - ratio * 0.3))
        new_b = int(b * (1.0 - ratio * 0.3))
        
        # Draw horizontal line
        draw.line([(0, y), (width, y)], fill=(new_r, new_g, new_b))
    
    # Add subtle pattern overlay
    for x in range(0, width, 40):
        for y in range(0, height, 40):
            # Add subtle dots for texture
            alpha = 0.1
            overlay_r = int(255 * alpha + r * (1 - alpha))
            overlay_g = int(255 * alpha + g * (1 - alpha))
            overlay_b = int(255 * alpha + b * (1 - alpha))
            draw.ellipse([x, y, x+3, y+3], fill=(overlay_r, overlay_g, overlay_b))
    
    # Try to add domain name text
    try:
        # Use a large font if available
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            except:
                font = ImageFont.load_default()
        
        # Add semi-transparent text
        text_img = Image.new('RGBA', (width, height), (255, 255, 255, 0))
        text_draw = ImageDraw.Draw(text_img)
        
        # Get text bounding box
        bbox = text_draw.textbbox((0, 0), name, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center the text
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Draw text with transparency
        text_draw.text((x, y), name, font=font, fill=(255, 255, 255, 100))
        
        # Composite the text onto the gradient
        img = Image.alpha_composite(img.convert('RGBA'), text_img).convert('RGB')
    except Exception as e:
        print(f"  Note: Could not add text to image: {e}")
    
    # Save image
    img.save(output_path, 'JPEG', quality=85, optimize=True)

def main():
    """Generate all placeholder images"""
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'pics', 'domains')
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Domain configurations
    domains = {
        'energy': {'color': '#f39c12', 'name': 'Energy'},
        'synthetic': {'color': '#9b59b6', 'name': 'Synthetic'},
        'image': {'color': '#1abc9c', 'name': 'Image'},
        'sensor': {'color': '#3498db', 'name': 'Sensor'},
        'motion': {'color': '#2ecc71', 'name': 'Motion'},
        'corporate': {'color': '#34495e', 'name': 'Corporate'},
        'transportation': {'color': '#e74c3c', 'name': 'Transportation'},
        'nature': {'color': '#27ae60', 'name': 'Nature'},
        'industry': {'color': '#2c3e50', 'name': 'Industry'},
        'economics': {'color': '#f1c40f', 'name': 'Economics'},
        'demographics': {'color': '#16a085', 'name': 'Demographics'},
        'retail': {'color': '#e91e63', 'name': 'Retail'},
        'microeconomics': {'color': '#8e44ad', 'name': 'Microeconomics'},
        'health': {'color': '#c0392b', 'name': 'Health'},
        'audio': {'color': '#9b59b6', 'name': 'Audio'}
    }
    
    # Image dimensions (optimized for card headers)
    width = 1200
    height = 800
    
    print("🎨 Generating placeholder domain images...")
    print(f"📁 Output directory: {output_dir}")
    print(f"📐 Image size: {width}x{height}px")
    print()
    
    # Generate each image
    for filename, config in domains.items():
        output_path = os.path.join(output_dir, f"{filename}.jpg")
        print(f"  Creating {filename}.jpg ({config['name']})...")
        
        try:
            create_gradient_image(
                width, 
                height, 
                config['color'], 
                config['name'], 
                output_path
            )
            print(f"    ✓ Saved to {output_path}")
        except Exception as e:
            print(f"    ✗ Error: {e}")
            sys.exit(1)
    
    print()
    print(f"✅ Successfully generated {len(domains)} placeholder images!")
    print()
    print("📝 Next steps:")
    print("  1. Review the images in pics/domains/")
    print("  2. Replace placeholders with high-quality images (1200x800px)")
    print("  3. Refresh your website to see domain images on cards")
    print()

if __name__ == '__main__':
    main()
