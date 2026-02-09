import os
import google.generativeai as genai
import json

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in env")
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')

    def select_best_photos(self, image_paths, max_count=5):
        """
        Uploads images to Gemini and asks for the best ones.
        Returns a list of indices.
        """
        # In a real scenario, we'd upload bytes. here we mock or assume local paths.
        # Since LINE sends bytes, we might need to save them temp or send bytes directly.
        # For this prototype, we'll assume we saved them to tmp/ and have paths.
        
        # Cost optimization: If < max_count, return all.
        if len(image_paths) <= max_count:
            return list(range(len(image_paths)))

        # TODO: Implement actual Gemini Vision call
        # For now, return the first n images to save tokens/complexity in this step
        return list(range(max_count))

    def generate_captions(self, location, date, image_descriptions=[]):
        """
        Generates a Gyaru-style title and caption.
        """
        prompt = f"""
        You are a high-energy, trendy Japanese Gyaru (Gal) from Shibuya.
        Current Year: 2024 (or {date})
        
        Task: Create a title and a short comment for a travel memory album.
        
        Location: {location}
        Date: {date}
        
        Output Format (JSON):
        {{
            "title": "Short punchy title (max 10 chars) with emojis",
            "location_romaji": "Location name in cool Romaji (e.g. 'Shibuya', 'Okinawa')",
            "comment": "1-2 sentences in heavy Gyaru-go (uses terms like わかりみ, きゃわ, あげぽよ, etc.)"
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            # Clean up json markdown
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            return json.loads(text)
        except Exception as e:
            print(f"Error generating caption: {e}")
            return {"title": "Travel Memoz", "location_romaji": location, "comment": "超楽しかったー！マジ最高！"}

