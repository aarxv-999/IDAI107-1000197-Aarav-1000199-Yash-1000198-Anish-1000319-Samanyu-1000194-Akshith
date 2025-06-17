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

REQUIRED_MENU_FIELDS = [
    "name", "description", "ingredients", "cook_time", "cuisine", "diet", 
    "category", "types", "source", "timestamp"
]

OPTIONAL_MENU_FIELDS = ["rating", "rating_comment"]

DIET_TYPES = [
    "Vegan", "Vegetarian", "Keto", "Gluten-Free", "Nut-Free",
    "Dairy-Free", "Low-Sugar", "Pescatarian", "Halal", "Jain", "Non-Veg"
]

MENU_CATEGORIES = [
    "Starter", "Main Course", "Dessert", "Beverage", 
    "Special Items", "Seasonal Items", "Chef Special Items"
]

def get_chef_firebase_db():
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting chef Firebase DB: {str(e)}")
        st.error("Failed to connect to database. Please check your Firebase configuration.")
        return None

def configure_gemini_ai():
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
    try:
        model = configure_gemini_ai()
        if not model:
            return None
            
        response = model.generate_content(prompt)
        logger.info(f"Raw Gemini response: {response.text[:200]}...")
        
        match = re.search(r"\[.*\]", response.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            logger.warning("No JSON array found in Gemini response")
            return None
    except Exception as e:
        logger.error(f"Gemini Error: {str(e)}")
        return None

def validate_and_fix_dish(dish):
    missing_required = [f for f in REQUIRED_MENU_FIELDS if f not in dish]
    if missing_required:
        logger.warning(f"Missing required fields: {missing_required}")
        for field in missing_required:
            if field == "timestamp":
                dish[field] = datetime.now().isoformat()
            elif field == "source":
                dish[field] = "AI Generated"
            else:
                dish[field] = "Not specified"
    
    if "diet" in dish and isinstance(dish["diet"], str):
        dish["diet"] = [dish["diet"]]
    
    if "types" in dish and isinstance(dish["types"], str):
        dish["types"] = [dish["types"]]
    
    if "ingredients" in dish and isinstance(dish["ingredients"], str):
        dish["ingredients"] = [ing.strip() for ing in dish["ingredients"].split(",")]
    
    return dish

def save_dish_to_firebase(dish, collection_name="menu"):
    try:
        db = get_chef_firebase_db()
        if not db:
            return False, "Database connection failed"
        
        dish = validate_and_fix_dish(dish)
        
        doc_ref = db.collection(collection_name).add(dish)
        logger.info(f"Saved dish '{dish.get('name', 'Unknown')}' to {collection_name} with ID: {doc_ref[1].id}")
        return True, f"Dish saved successfully with ID: {doc_ref[1].id}"
    except Exception as e:
        logger.error(f"Error saving dish to Firebase: {str(e)}")
        return False, f"Error saving dish: {str(e)}"

def get_existing_dishes(collection_name="menu"):
    try:
        db = get_chef_firebase_db()
        if not db:
            return []
        
        docs = db.collection(collection_name).stream()
        dishes = []
        for doc in docs:
            dish_data = doc.to_dict()
            dish_data['id'] = doc.id
            dishes.append(dish_data)
        
        logger.info(f"Retrieved {len(dishes)} dishes from {collection_name}")
        return dishes
    except Exception as e:
        logger.error(f"Error retrieving dishes: {str(e)}")
        return []

def delete_dish_from_firebase(dish_id, collection_name="menu"):
    try:
        db = get_chef_firebase_db()
        if not db:
            return False, "Database connection failed"
        
        db.collection(collection_name).document(dish_id).delete()
        logger.info(f"Deleted dish with ID: {dish_id} from {collection_name}")
        return True, "Dish deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting dish: {str(e)}")
        return False, f"Error deleting dish: {str(e)}"

def update_dish_in_firebase(dish_id, updated_dish, collection_name="menu"):
    try:
        db = get_chef_firebase_db()
        if not db:
            return False, "Database connection failed"
        
        updated_dish = validate_and_fix_dish(updated_dish)
        
        db.collection(collection_name).document(dish_id).set(updated_dish)
        logger.info(f"Updated dish with ID: {dish_id} in {collection_name}")
        return True, "Dish updated successfully"
    except Exception as e:
        logger.error(f"Error updating dish: {str(e)}")
        return False, f"Error updating dish: {str(e)}"

def generate_menu_suggestions(cuisine_type, dietary_restrictions, num_dishes=5):
    try:
        model = configure_gemini_ai()
        if not model:
            return []
        
        prompt = f"""
        Generate {num_dishes} restaurant menu items for {cuisine_type} cuisine with {dietary_restrictions} dietary restrictions.
        
        Return as a JSON array with each dish having these exact fields:
        - name: string
        - description: string (detailed, appetizing description)
        - ingredients: array of strings
        - cook_time: string (e.g., "30 minutes")
        - cuisine: string
        - diet: array of strings (from: {', '.join(DIET_TYPES)})
        - category: string (from: {', '.join(MENU_CATEGORIES)})
        - types: array of strings (e.g., ["Spicy", "Popular"])
        - source: "AI Generated"
        - timestamp: current ISO timestamp
        
        Make dishes authentic, detailed, and restaurant-quality.
        """
        
        response = model.generate_content(prompt)
        
        try:
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                dishes = json.loads(json_match.group(0))
                
                for dish in dishes:
                    dish['timestamp'] = datetime.now().isoformat()
                    dish = validate_and_fix_dish(dish)
                
                return dishes
            else:
                logger.warning("No JSON array found in menu generation response")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in menu generation: {str(e)}")
            return []
            
    except Exception as e:
        logger.error(f"Error generating menu suggestions: {str(e)}")
        return []

def get_menu_analytics(collection_name="menu"):
    try:
        dishes = get_existing_dishes(collection_name)
        if not dishes:
            return {}
        
        analytics = {
            'total_dishes': len(dishes),
            'by_cuisine': {},
            'by_category': {},
            'by_diet': {},
            'by_source': {},
            'recent_additions': 0
        }
        
        from datetime import timedelta
        one_week_ago = datetime.now() - timedelta(days=7)
        
        for dish in dishes:
            cuisine = dish.get('cuisine', 'Unknown')
            analytics['by_cuisine'][cuisine] = analytics['by_cuisine'].get(cuisine, 0) + 1
            
            category = dish.get('category', 'Unknown')
            analytics['by_category'][category] = analytics['by_category'].get(category, 0) + 1
            
            diet_types = dish.get('diet', [])
            if isinstance(diet_types, list):
                for diet in diet_types:
                    analytics['by_diet'][diet] = analytics['by_diet'].get(diet, 0) + 1
            
            source = dish.get('source', 'Unknown')
            analytics['by_source'][source] = analytics['by_source'].get(source, 0) + 1
            
            timestamp_str = dish.get('timestamp', '')
            if timestamp_str:
                try:
                    dish_date = parser.parse(timestamp_str)
                    if dish_date.replace(tzinfo=None) > one_week_ago:
                        analytics['recent_additions'] += 1
                except:
                    pass
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error generating menu analytics: {str(e)}")
        return {}

def search_dishes(query, collection_name="menu"):
    try:
        dishes = get_existing_dishes(collection_name)
        if not dishes:
            return []
        
        query_lower = query.lower()
        matching_dishes = []
        
        for dish in dishes:
            score = 0
            
            name = dish.get('name', '').lower()
            if query_lower in name:
                score += 10
            
            description = dish.get('description', '').lower()
            if query_lower in description:
                score += 5
            
            ingredients = dish.get('ingredients', [])
            for ingredient in ingredients:
                if query_lower in str(ingredient).lower():
                    score += 3
            
            cuisine = dish.get('cuisine', '').lower()
            if query_lower in cuisine:
                score += 4
            
            if score > 0:
                dish['search_score'] = score
                matching_dishes.append(dish)
        
        matching_dishes.sort(key=lambda x: x['search_score'], reverse=True)
        return matching_dishes
        
    except Exception as e:
        logger.error(f"Error searching dishes: {str(e)}")
        return []

def export_menu_to_csv(collection_name="menu"):
    try:
        dishes = get_existing_dishes(collection_name)
        if not dishes:
            return None
        
        import pandas as pd
        
        export_data = []
        for dish in dishes:
            export_data.append({
                'Name': dish.get('name', ''),
                'Description': dish.get('description', ''),
                'Ingredients': ', '.join(dish.get('ingredients', [])),
                'Cook Time': dish.get('cook_time', ''),
                'Cuisine': dish.get('cuisine', ''),
                'Diet': ', '.join(dish.get('diet', [])),
                'Category': dish.get('category', ''),
                'Types': ', '.join(dish.get('types', [])),
                'Source': dish.get('source', ''),
                'Timestamp': dish.get('timestamp', '')
            })
        
        df = pd.DataFrame(export_data)
        return df.to_csv(index=False)
        
    except Exception as e:
        logger.error(f"Error exporting menu to CSV: {str(e)}")
        return None

def import_menu_from_csv(csv_content, collection_name="menu"):
    try:
        import pandas as pd
        from io import StringIO
        
        df = pd.read_csv(StringIO(csv_content))
        
        required_columns = ['Name', 'Description', 'Ingredients', 'Cook Time', 'Cuisine', 'Diet', 'Category']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        imported_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                dish = {
                    'name': str(row['Name']),
                    'description': str(row['Description']),
                    'ingredients': [ing.strip() for ing in str(row['Ingredients']).split(',')],
                    'cook_time': str(row['Cook Time']),
                    'cuisine': str(row['Cuisine']),
                    'diet': [diet.strip() for diet in str(row['Diet']).split(',')],
                    'category': str(row['Category']),
                    'types': [t.strip() for t in str(row.get('Types', '')).split(',') if t.strip()],
                    'source': 'CSV Import',
                    'timestamp': datetime.now().isoformat()
                }
                
                success, message = save_dish_to_firebase(dish, collection_name)
                if success:
                    imported_count += 1
                else:
                    errors.append(f"Row {index + 1}: {message}")
                    
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        if errors:
            return True, f"Imported {imported_count} dishes with {len(errors)} errors: {'; '.join(errors[:3])}"
        else:
            return True, f"Successfully imported {imported_count} dishes"
            
    except Exception as e:
        logger.error(f"Error importing menu from CSV: {str(e)}")
        return False, f"Import error: {str(e)}"

def get_dish_by_id(dish_id, collection_name="menu"):
    try:
        db = get_chef_firebase_db()
        if not db:
            return None
        
        doc = db.collection(collection_name).document(dish_id).get()
        if doc.exists:
            dish_data = doc.to_dict()
            dish_data['id'] = doc.id
            return dish_data
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error getting dish by ID: {str(e)}")
        return None

def validate_dish_data(dish_data):
    errors = []
    
    if not dish_data.get('name', '').strip():
        errors.append("Dish name is required")
    
    if not dish_data.get('description', '').strip():
        errors.append("Description is required")
    
    if not dish_data.get('ingredients') or len(dish_data['ingredients']) == 0:
        errors.append("At least one ingredient is required")
    
    if not dish_data.get('cuisine', '').strip():
        errors.append("Cuisine is required")
    
    if not dish_data.get('category', '').strip():
        errors.append("Category is required")
    
    if dish_data.get('category') not in MENU_CATEGORIES:
        errors.append(f"Category must be one of: {', '.join(MENU_CATEGORIES)}")
    
    diet_types = dish_data.get('diet', [])
    if isinstance(diet_types, list):
        invalid_diets = [d for d in diet_types if d not in DIET_TYPES]
        if invalid_diets:
            errors.append(f"Invalid diet types: {', '.join(invalid_diets)}")
    
    return errors

def get_popular_dishes(collection_name="menu", limit=10):
    try:
        dishes = get_existing_dishes(collection_name)
        if not dishes:
            return []
        
        popular_dishes = []
        for dish in dishes:
            popularity_score = 0
            
            if 'Popular' in dish.get('types', []):
                popularity_score += 10
            
            if 'Chef Special' in dish.get('types', []):
                popularity_score += 8
            
            if dish.get('rating', 0) >= 4:
                popularity_score += 5
            
            if len(dish.get('ingredients', [])) <= 5:
                popularity_score += 2
            
            dish['popularity_score'] = popularity_score
            popular_dishes.append(dish)
        
        popular_dishes.sort(key=lambda x: x['popularity_score'], reverse=True)
        return popular_dishes[:limit]
        
    except Exception as e:
        logger.error(f"Error getting popular dishes: {str(e)}")
        return []

def generate_dish_rating(dish_name, description, ingredients, cook_time, cuisine):
    """Generate AI rating for a chef's dish submission using old logic"""
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
            return {"rating": 3, "rating_comment": "AI service unavailable"}
            
        response = model.generate_content(prompt)
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        
        if match:
            rating_data = json.loads(match.group(0))
            rating_data["rating"] = int(rating_data.get("rating", 3))
            return rating_data
        else:
            return {
                "rating": 3,
                "rating_comment": "Could not parse AI response"
            }
    except Exception as e:
        logger.error(f"Error generating dish rating: {str(e)}")
        return {"rating": 3, "rating_comment": f"Rating error: {str(e)}"}

def parse_ingredients(db):
    """Parse ingredients from Firebase inventory using old logic"""
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
