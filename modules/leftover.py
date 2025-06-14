'''
FINAL VERSION: Enhanced leftover management with DD/MM/YYYY date format support
Minimalistic approach with priority shown only during recipe generation.
'''

import pandas as pd
from typing import List, Optional, Dict, Tuple
import os
import google.generativeai as genai
import logging
import random
import json
from datetime import datetime, timedelta

# Gamification-specific imports
from firebase_admin import firestore
from firebase_init import init_firebase

# Logger setup
logger = logging.getLogger('leftover_combined')

# ------------------ Enhanced Leftover Management Functions ------------------

def load_leftovers(csv_path: str) -> List[str]:
    try:
        df = pd.read_csv(csv_path)
        if 'ingredient' not in df.columns:
            raise ValueError("CSV file must have an 'ingredient' column")
        ingredients = df['ingredient'].tolist()
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)]
        return ingredients
    except FileNotFoundError:
        raise FileNotFoundError(f" CSV file unavailable at: {csv_path}")
    except Exception as e:
        raise Exception(f"Faced error in loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]:
    ingredients = input_text.split(',')
    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
    return ingredients

def fetch_ingredients_from_firebase() -> List[Dict]:
    try:
        from firebase_admin import firestore
        import firebase_admin
        
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            db = firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from app_integration import check_event_firebase_config
            check_event_firebase_config()
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            db = firestore.client(app=firebase_admin.get_app(name='event_app'))
        
        inventory_ref = db.collection('ingredient_inventory')
        inventory_docs = inventory_ref.get()
        
        ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            ingredients.append(item)
            
        return ingredients
    except Exception as e:
        logger.error(f"Error fetching ingredients from Firebase: {str(e)}")
        raise Exception(f"Error fetching ingredients from Firebase: {str(e)}")

def parse_expiry_date(expiry_str: str) -> Optional[datetime]:
    '''Parse expiry date string with DD/MM/YYYY format support'''
    if not expiry_str or expiry_str.lower() in ['none', 'null', '', 'n/a']:
        return None
    
    # Common date formats to try, prioritizing DD/MM/YYYY
    date_formats = [
        '%d/%m/%Y',      # 27/08/2025 (user's format)
        '%d-%m-%Y',      # 27-08-2025
        '%Y-%m-%d',      # 2025-08-27
        '%m/%d/%Y',      # 08/27/2025
        '%Y/%m/%d',      # 2025/08/27
        '%B %d, %Y',     # August 27, 2025
        '%d %B %Y',      # 27 August 2025
    ]
    
    for date_format in date_formats:
        try:
            return datetime.strptime(expiry_str.strip(), date_format)
        except ValueError:
            continue
    
    logger.warning(f"Could not parse expiry date: {expiry_str}")
    return None

def parse_quantity(quantity_str: str) -> float:
    if not quantity_str:
        return 0.0
    
    try:
        quantity_clean = str(quantity_str).lower().strip()
        units_to_remove = ['kg', 'g', 'lbs', 'oz', 'ml', 'l', 'cups', 'tbsp', 'tsp', 'pieces', 'pcs']
        for unit in units_to_remove:
            quantity_clean = quantity_clean.replace(unit, '').strip()
        
        import re
        numbers = re.findall(r'\d+\.?\d*', quantity_clean)
        if numbers:
            return float(numbers[0])
        
        return 0.0
    except:
        return 0.0

def calculate_days_until_expiry(expiry_date: Optional[datetime]) -> int:
    if not expiry_date:
        return 9999
    
    current_date = datetime.now()
    delta = expiry_date - current_date
    return delta.days

def prioritize_ingredients(firebase_ingredients: List[Dict]) -> List[Dict]:
    '''Prioritize ingredients based on expiry date and quantity'''
    processed_ingredients = []
    
    for item in firebase_ingredients:
        if not item.get('Ingredient'):
            continue
            
        # Parse expiry date and quantity
        expiry_date = parse_expiry_date(item.get('Expiry date', ''))
        quantity = parse_quantity(item.get('Quantity', '0'))
        days_until_expiry = calculate_days_until_expiry(expiry_date)
        
        # Determine priority
        is_expiring_soon = days_until_expiry <= 7 and days_until_expiry >= 0
        has_large_quantity = quantity >= 5
        
        if is_expiring_soon and has_large_quantity:
            priority = 1
        elif is_expiring_soon:
            priority = 2
        elif has_large_quantity:
            priority = 3
        else:
            priority = 4
        
        processed_item = {
            'ingredient': item['Ingredient'],
            'expiry_date': expiry_date,
            'quantity': quantity,
            'days_until_expiry': days_until_expiry,
            'priority': priority,
            'alternatives': item.get('Alternatives', ''),
            'original_data': item
        }
        
        processed_ingredients.append(processed_item)
    
    # Sort by priority
    processed_ingredients.sort(key=lambda x: (x['priority'], x['days_until_expiry'], -x['quantity']))
    
    return processed_ingredients

def parse_firebase_ingredients(firebase_ingredients: List[Dict]) -> List[str]:
    prioritized_ingredients = prioritize_ingredients(firebase_ingredients)
    ingredients = [item['ingredient'] for item in prioritized_ingredients if item['ingredient']]
    return ingredients

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3, notes: str = "", prioritized_ingredients: List[Dict] = None) -> List[str]:
    if not leftovers:
        logger.warning("No ingredients provided for recipe suggestions")
        return []

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable was not found!")
            raise ValueError("GEMINI_API_KEY environment variable was not found!")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        ingredients_list = ", ".join(leftovers)
        
        # Enhanced prompt with priority information
        priority_info = ""
        if prioritized_ingredients:
            high_priority_items = [item for item in prioritized_ingredients if item['priority'] <= 2]
            if high_priority_items:
                priority_info = f"\n\nPRIORITY: Use these ingredients first as they expire soon: {', '.join([item['ingredient'] for item in high_priority_items])}"
        
        notes_text = f"\nRequirements: {notes}" if notes else ""
        
        prompt = f'''
        Ingredients: {ingredients_list}{priority_info}{notes_text}

        Generate {max_suggestions} recipe names that use these ingredients to reduce food waste.
        Focus on using priority ingredients first.
        
        Format: Just the recipe name, one per line.
        ''' 

        response = model.generate_content(prompt)
        response_text = response.text
        
        recipe_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        recipes = []
        for line in recipe_lines:
            if line and line[0].isdigit() and line[1:3] in ['. ', '- ', ') ']:
                line = line[3:].strip()
            line = line.strip('"\'')
            if line and len(recipes) < max_suggestions:
                recipes.append(line)
        
        recipes = recipes[:max_suggestions]
        
        if not recipes:
            logger.warning(f"Got no recipes for the ingredients: {ingredients_list}!!")
            return []
        return recipes

    except Exception as e:
        logger.error(f"Error using Gemini API: {str(e)}")
        raise Exception(f"Error generating recipes: {str(e)}")

# Gamification functions (keeping existing ones)
def get_firestore_db():
    init_firebase()
    return firestore.client()

def get_user_stats(user_id: str) -> Dict:
    try:
        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)
        doc = user_stats_ref.get()

        if doc.exists:
            return doc.to_dict()
        else:
            initial_stats = {
                'user_id': user_id,
                'total_xp': 0,
                'level': 1,
                'quizzes_taken': 0,
                'correct_answers': 0,
                'total_questions': 0,
                'recipes_generated': 0,
                'perfect_scores': 0,
                'last_quiz_date': None,
                'achievements': []
            }
            user_stats_ref.set(initial_stats)
            return initial_stats

    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'quizzes_taken': 0,
            'correct_answers': 0,
            'total_questions': 0,
            'recipes_generated': 0,
            'perfect_scores': 0,
            'last_quiz_date': None,
            'achievements': []
        }

def award_recipe_xp(user_id: str, num_recipes: int) -> Dict:
    try:
        xp_per_recipe = 5
        total_xp = num_recipes * xp_per_recipe

        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)
        current_stats = get_user_stats(user_id)

        new_total_xp = current_stats['total_xp'] + total_xp
        new_level = calculate_level(new_total_xp)
        new_recipes = current_stats.get('recipes_generated', 0) + num_recipes

        updated_stats = current_stats.copy()
        updated_stats.update({
            'total_xp': new_total_xp,
            'level': new_level,
            'recipes_generated': new_recipes
        })

        user_stats_ref.set(updated_stats)
        return updated_stats

    except Exception as e:
        logger.error(f"Error awarding recipe XP: {str(e)}")
        return get_user_stats(user_id)

def calculate_level(total_xp: int) -> int:
    import math
    return max(1, int(math.sqrt(total_xp / 100)) + 1)

print("✅ Final leftover management module loaded!")
