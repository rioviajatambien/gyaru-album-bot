from image_service import ImageService
from PIL import Image, ImageDraw
import os

def create_dummy_images():
    os.makedirs("test_images", exist_ok=True)
    paths = []
    colors = ['red', 'blue', 'green', 'yellow', 'purple']
    for i in range(5):
        img = Image.new('RGB', (800, 600), color=colors[i])
        d = ImageDraw.Draw(img)
        d.text((10,10), f"Test Image {i}", fill='white')
        path = f"test_images/img_{i}.jpg"
        img.save(path)
        paths.append(path)
    return paths

def main():
    print("Generating dummy images...")
    paths = create_dummy_images()
    
    svc = ImageService()
    print("Creating album...")
    try:
        album = svc.create_album(paths, title="Test Album", date="2024 Summer")
        album.save("test_album_output.jpg")
        print("Success! Saved to test_album_output.jpg")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
