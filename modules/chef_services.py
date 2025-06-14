"""
Chef Recipe Services module for the Smart Restaurant Menu Management App.
Handles menu generation, chef submissions, and analytics using event_firebase configuration.
"""

import streamlit as st
import google.generativeai as genai
import re
import json
from datetime import datetime
from dateutil import parser
import firebase_admin
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)

# Constants
REQUIRED_MENU_FIELDS = [
    "name", "description", "ingredients", "cook_time", "cuisine", "diet", 
    "category", "types", "source", "rating", "rating_comment", "timestamp"
]

DIET_TYPES = [
    "Vegan", "Vegetarian", "Keto", "Gluten-Free", "Nut-Free",
    "Dairy-Free", "Low-Sugar", "Pescatarian", "Halal", "Jain", "Non-Veg"
]

MENU_CATEGORIES = [
    "Starter", "Main Course", "Dessert", "Beverage", 
    "Special Items", "Seasonal Items", "Chef Special Items"
]

def get_chef_firebase_db():
    """Get Firestore client for chef services using event_firebase configuration"""
    try:
        # Use the event Firebase app
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            # Initialize event Firebase if not already done
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting chef Firebase DB: {str(e)}")
        st.error("Failed to connect to database. Please check your Firebase configuration.")
        return None

def configure_gemini_ai():
    """Configure Gemini AI using Streamlit secrets"""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in Streamlit secrets")
        
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.error(f"Error configuring Gemini AI: {str(e)}")
        st.error("Failed to configure AI service. Please check your API key configuration.")
        return None

def generate_dish(prompt: str) -> dict:
    """Generate dish using Gemini AI"""
    try:
        model = configure_gemini_ai()
        if not model:
            return None
            
        response = model.generate_content(prompt)
        logger.info(f"Raw Gemini response: {response.text[:200]}...")
        
        # Extract JSON from response
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            logger.warning("No JSON array found in Gemini response")
            return None
    except Exception as e:
        logger.error(f"Gemini Error: {str(e)}")
        return None

def generate_dish_rating(dish_name, description, ingredients, cook_time, cuisine):
    """Generate AI rating for a chef's dish submission"""
    prompt = f"""
You are a professional food critic and culinary expert. Please evaluate the following dish submitted by a chef.

Dish Name: {dish_name}
Description: {description}
Ingredients: {ingredients}
Cook Time: {cook_time}
Cuisine: {cuisine}

Please rate this dish on a scale of 1 to 5 based on creativity, ingredient usage, and overall appeal.
Respond in the following JSON format:

{{
  "rating": integer between 1 and 5,
  "rating_comment": brief 1-line critique of the dish
}}
"""
    try:
        model = configure_gemini_ai()
        if not model:
            return {"rating": "NA", "rating_comment": "AI service unavailable"}
            
        response = model.generate_content(prompt)
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        
        if match:
            return json.loads(match.group(0))
        else:
            return {
                "rating": "NA",
                "rating_comment": "Could not parse AI response"
            }
    except Exception as e:
        logger.error(f"Error generating dish rating: {str(e)}")
        return {"rating": "NA", "rating_comment": str(e)}

def parse_ingredients(db):
    """Parse ingredients from Firebase inventory (READ-ONLY)"""
    if not db:
        return []
        
    try:
        ingredients_ref = db.collection("ingredient_inventory")
        ingredients = []

        for doc in ingredients_ref.stream():
            data = doc.to_dict()

            name = data.get("Ingredient", "").strip()
            expiry_str = data.get("Expiry Date", "").strip()
            quantity_raw = data.get("Quantity", "").strip()

            # Parse quantity: extract number from string like "4 kg"
            try:
                quantity = float("".join(c for c in quantity_raw if c.isdigit() or c == '.'))
            except:
                quantity = 0

            if not name or not expiry_str:
                continue

            try:
                expiry_date = parser.parse(expiry_str)
                days_to_expiry = (expiry_date - datetime.now()).days
            except Exception:
                continue

            ingredients.append({
                "name": name,
                "expiry_date": expiry_str,
                "quantity": quantity,
                "days_to_expiry": days_to_expiry
            })

        logger.info(f"Parsed {len(ingredients)} ingredients from inventory")
        return ingredients
        
    except Exception as e:
        logger.error(f"Error parsing ingredients: {str(e)}")
        return []

def create_chef_sub_ratings_collection(db):
    """Create chef_sub_ratings collection if it doesn't exist"""
    try:
        # Check if collection exists by trying to get a document
        test_query = db.collection("chef_sub_ratings").limit(1).get()
        logger.info("chef_sub_ratings collection already exists")
        return True
    except Exception as e:
        logger.info("chef_sub_ratings collection doesn't exist, will be created on first write")
        return True
