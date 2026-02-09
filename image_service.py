import random
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import math
import os

class ImageService:
    def __init__(self):
        self.font_path = "static/fonts/Yomogi-Regular.ttf"
        # Fallback if download failed
        if not os.path.exists(self.font_path):
            self.font_path = "static/fonts/default.ttf" 
            
        self.bg_color = (245, 245, 220) # Beige/Cream
        self.tape_colors = [
            (255, 182, 193, 200), # Pink semi-transparent
            (173, 216, 230, 200), # Light Blue
            (144, 238, 144, 200), # Light Green
            (255, 255, 153, 200), # Light Yellow
            (221, 160, 221, 200)  # Plum
        ]

import random
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import math
import os
import imagehash

class ImageService:
    def __init__(self):
        self.font_path = "static/fonts/Yomogi-Regular.ttf"
        if not os.path.exists(self.font_path):
            self.font_path = "static/fonts/default.ttf" 
            
        self.bg_color = (248, 245, 240) # Warm Off-white
        self.tape_colors = [
            (255, 182, 193, 220), # Pink
            (173, 216, 230, 220), # Blue
            (152, 251, 152, 220), # Green
            (255, 218, 185, 220), # Peach
            (230, 230, 250, 220)  # Lavender
        ]

    def load_image(self, image_path):
        return Image.open(image_path)

    def _deduplicate_images(self, image_paths, cutoff=10):
        """
        Removes similar images using ImageHash.
        Returns a filtered list of paths (preserving best ones - currently just first).
        """
        if not image_paths:
            return []
            
        hashes = {}
        unique_paths = []
        
        for p in image_paths:
            try:
                img = Image.open(p)
                h = imagehash.phash(img)
                duplicate = False
                for existing_h in hashes:
                    if h - existing_h < cutoff: # Hamming distance
                        duplicate = True
                        break
                if not duplicate:
                    hashes[h] = p
                    unique_paths.append(p)
            except Exception as e:
                print(f"Error hashing {p}: {e}")
                # If error, keep it safe
                unique_paths.append(p)
                
        return unique_paths

    def create_album_pages(self, image_paths, title=None, date=None, location_romaji=None):
        """
        Creates a list of album images (pages).
        """
        # 1. Deduplicate
        unique_paths = self._deduplicate_images(image_paths)
        print(f"Deduplicated: {len(image_paths)} -> {len(unique_paths)}")
        
        images = [self.load_image(p) for p in unique_paths]
        pages = []
        
        # 2. Dynamic Chunking (3-5 per page)
        chunks = []
        remaining = images[:]
        while remaining:
            # Decide size for this page
            if len(remaining) <= 5:
                size = len(remaining)
            else:
                size = random.randint(3, 5)
                # Avoid leaving 1 or 2 images for last page if possible
                if len(remaining) - size < 3 and len(remaining) - size > 0:
                     size = len(remaining) # Just take all if only small remainder
                     if size > 6: size = 4 # Split if too big? logic simplification: just take 3-5
            
            chunk = remaining[:size]
            remaining = remaining[size:]
            chunks.append(chunk)

        for i, chunk in enumerate(chunks):
            # Page Title (Only first page gets big title)
            page_title = title if i == 0 else None
            page_loc = location_romaji if i == 0 else None
            
            canvas = self._create_single_page(chunk, page_title, page_loc, date)
            pages.append(canvas)
            
        return pages

    def _create_single_page(self, images, title, location_romaji, date):
        width, height = 1080, 1920
        canvas = Image.new('RGB', (width, height), self.bg_color)
        draw = ImageDraw.Draw(canvas)
        
        # Seasonal Background
        self._draw_seasonal_bg(canvas, draw, date)

        # Better Scatter Layout logic
        # Divide canvas into zones.
        # Top zones (y=300-800), Bottom zones (y=900-1400)
        # We have 3-5 images.
        count = len(images)
        centers = []
        
        if count == 3:
            centers = [(540, 500), (300, 1000), (780, 1100)]
        elif count == 4:
            centers = [(300, 500), (780, 550), (300, 1100), (780, 1050)]
        elif count >= 5:
            centers = [(250, 450), (830, 500), (540, 850), (300, 1250), (780, 1300)]
            
        pol_width = 480
        pol_height = 580

        for i, img in enumerate(images):
            # Process Image (Resize/Crop/Frame/Shadow)
            # ... (Reuse previous logic for aesthetics) ...
            
            # --- START COPIED LOGIC (Refactored for brevity) ---
            img_ratio = img.width / img.height
            target_side = pol_width - 40
            
            if img_ratio > 1:
                new_h = target_side; new_w = int(new_h * img_ratio)
            else:
                new_w = target_side; new_h = int(new_w / img_ratio)
            
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # Crop center
            left = (img.width - target_side)//2
            top = (img.height - target_side)//2
            img = img.crop((left, top, left+target_side, top+target_side))
            
            polaroid = Image.new('RGBA', (pol_width, pol_height), (255,255,255,255))
            polaroid.paste(img, (20, 20))
            
            # Shadow
            shadow = Image.new('RGBA', (pol_width+40, pol_height+40), (0,0,0,0))
            s_draw = ImageDraw.Draw(shadow)
            s_draw.rectangle((20,20,pol_width+10,pol_height+10), fill=(0,0,0,60))
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            
            combined = Image.new('RGBA', (pol_width+40, pol_height+40), (0,0,0,0))
            combined.paste(shadow, (0,0))
            combined.paste(polaroid, (10,10))
            
            angle = random.randint(-12, 12)
            combined = combined.rotate(angle, expand=True, resample=Image.BICUBIC)
            # --- END COPIED LOGIC ---

            # Position
            if i < len(centers):
                cx, cy = centers[i]
                # Add randomness
                cx += random.randint(-40, 40)
                cy += random.randint(-40, 40)
                
                # Center-anchor paste
                paste_x = cx - combined.width//2
                paste_y = cy - combined.height//2
                
                canvas.paste(combined, (paste_x, paste_y), combined)
                
                # Tape - adjusted calculation
                # Tape should be at the "top" of the rotated photo
                # Simplified: just paste tape at top center of bounding box with same rotation + 90
                self._add_tape(canvas, cx, paste_y + 30, angle)

        # Titles & Text
        if title:
            # Main Title (Gyaru)
            self._draw_text(draw, title, (540, 150), font_size=100, color=(255, 105, 180), anchor="mm", shadow=True)
        
        if location_romaji:
            # Subtitle (Romaji - Stylized)
            self._draw_text(draw, location_romaji, (540, 260), font_size=70, color=(100, 150, 200), anchor="mm")
            
        if date:
             # Footer
             self._draw_text(draw, date, (900, 1800), font_size=50, color=(128, 128, 128), anchor="rb")

        return canvas

    def _draw_seasonal_bg(self, canvas, draw, date_str):
        """Draws simple seasonal motifs based on date string."""
        date_str = str(date_str)
        season = "spring" # default
        if "夏" in date_str or "8" in date_str or "7" in date_str: season = "summer"
        if "秋" in date_str or "9" in date_str or "10" in date_str or "11" in date_str: season = "autumn"
        if "冬" in date_str or "12" in date_str or "1" in date_str or "2" in date_str: season = "winter"
        
        # Draw motifs (simple circles/lines for now to keep it efficient)
        w, h = canvas.size
        
        if season == "summer":
            # Sun/Circles
            for _ in range(10):
                r = random.randint(30, 80)
                x = random.randint(0, w)
                y = random.randint(0, h)
                draw.ellipse((x, y, x+r, y+r), fill=(255, 255, 0, 40), outline=None)
        elif season == "autumn":
            # Orange/Brown leaves (ovals)
            for _ in range(15):
                r = random.randint(20, 60)
                x = random.randint(0, w)
                y = random.randint(0, h)
                draw.ellipse((x, y, x+r, y+r//2), fill=(210, 105, 30, 40), outline=None)
        elif season == "winter":
            # Blue icy circles
            for _ in range(12):
                r = random.randint(10, 50)
                x = random.randint(0, w)
                y = random.randint(0, h)
                draw.ellipse((x, y, x+r, y+r), fill=(173, 216, 230, 50), outline=None)
        else: # Spring (Pink petals)
            for _ in range(20):
                r = random.randint(10, 30)
                x = random.randint(0, w)
                y = random.randint(0, h)
                draw.ellipse((x, y, x+r, y+r), fill=(255, 192, 203, 60), outline=None)


    def _add_tape(self, canvas, center_x, top_y, angle):
        w, h = 180, 45
        color = random.choice(self.tape_colors)
        tape = Image.new('RGBA', (w, h), color)
        
        # Tape texture (transparency noise)
        # skipped for speed
        
        tape_angle = angle + random.randint(-5, 5) # Parallel to photo or slightly off
        tape = tape.rotate(tape_angle, expand=True, resample=Image.BICUBIC)
        
        canvas.paste(tape, (center_x - tape.width//2, top_y), tape)

    def _draw_text(self, draw, text, position, font_size=40, color=(0, 0, 0), shadow=False, anchor="lt"):
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except:
            font = ImageFont.load_default()
            
        if shadow:
            # Draw offsets
            x, y = position
            draw.text((x+5, y+5), text, font=font, fill=(50,50,50,50), anchor=anchor)
        
        draw.text(position, text, font=font, fill=color, anchor=anchor)


if __name__ == "__main__":
    svc = ImageService()
    print("Service init")
