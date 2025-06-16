"""
Enhanced Leftover Management with Centralized Gamification
Generates recipes from leftover ingredients with XP rewards
"""

import logging
from typing import List, Dict, Optional, Tuple
import google.generativeai as genai
import os
from datetime import datetime, date
import firebase_admin
from firebase_admin import firestore

# Import centralized gamification system
from modules.gamification_core import award_xp

logger = logging.getLogger(__name__)

def get_event_firestore_db():
    """Get the event Firestore client for ingredient data"""
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            if init_event_firebase():
                return firestore.client(app=firebase_admin.get_app(name='event_app'))
            return None
    except Exception as e:
        logger.error(f"Error getting event Firestore client: {str(e)}")
        return None

def fetch_ingredients_from_firebase() -> List[Dict]:
    """Fetch ingredients from Firebase inventory"""
    try:
        db = get_event_firestore_db()
        if not db:
            return []
        
        inventory_ref = db.collection('ingredient_inventory')
        docs = inventory_ref.get()
        
        ingredients = []
        for doc in docs:
            data = doc.to_dict()
            ingredients.append(data)
        
        return ingredients
        
    except Exception as e:
        logger.error(f"Error fetching ingredients from Firebase: {str(e)}")
        return []

def get_ingredients_by_expiry_priority(firebase_ingredients: List[Dict], max_count: int = 20) -> Tuple[List[str], List[Dict]]:
    """Get ingredients prioritized by expiry date"""
    try:
        current_date = date.today()
        detailed_info = []
        
        for ingredient in firebase_ingredients:
            expiry_str = ingredient.get('Expiry Date', '')
            ingredient_name = ingredient.get('Ingredient', '').lower()
            
            if not expiry_str or not ingredient_name:
                continue
            
            try:
                expiry_date = datetime.strptime(expiry_str, "%d/%m/%Y").date()
                days_until_expiry = (expiry_date - current_date).days
                
                detailed_info.append({
                    'name': ingredient_name,
                    'expiry_date': expiry_str,
                    'days_until_expiry': days_until_expiry,
                    'quantity': ingredient.get('Quantity', ''),
                    'type': ingredient.get('Type', '')
                })
            except ValueError:
                continue
        
        # Sort by expiry date (soonest first)
        detailed_info.sort(key=lambda x: x['days_until_expiry'])
        
        # Limit to max_count
        detailed_info = detailed_info[:max_count]
        
        # Extract ingredient names
        ingredient_names = [item['name'] for item in detailed_info]
        
        return ingredient_names, detailed_info
        
    except Exception as e:
        logger.error(f"Error processing ingredients by expiry: {str(e)}")
        return [], []

def suggest_recipes(ingredients: List[str], num_recipes: int = 3, notes: str = "", 
                   priority_ingredients: List[Dict] = None) -> List[str]:
    """Generate recipe suggestions using AI with priority ingredient handling"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ["AI recipe generation unavailable - API key not found"]
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Build ingredient list with priority information
        ingredient_text = ", ".join(ingredients)
        
        # Add priority ingredient information if available
        priority_text = ""
        if priority_ingredients:
            urgent_ingredients = [item['name'] for item in priority_ingredients if item['days_until_expiry'] <= 3]
            if urgent_ingredients:
                priority_text = f"\n\nPRIORITY: Please prioritize using these ingredients that expire soon: {', '.join(urgent_ingredients)}"
        
        # Build the prompt
        prompt = f'''Generate exactly {num_recipes} practical recipe suggestions using these leftover ingredients: {ingredient_text}

Requirements:
- Use as many of the provided ingredients as possible
- Create recipes that minimize food waste
- Make recipes suitable for restaurant preparation
- Keep recipe names concise and appetizing
- Consider the ingredients' compatibility and cooking methods{priority_text}

Additional requirements: {notes if notes else "None"}

Format your response as a numbered list of recipe names only, nothing else.

Example format:
1. Recipe Name One
2. Recipe Name Two
3. Recipe Name Three'''

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse the recipes
        recipes = []
        for line in response_text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # Remove numbering and clean up
                recipe = line.split('.', 1)[-1].strip()
                if recipe:
                    recipes.append(recipe)
        
        # Ensure we have the requested number of recipes
        if len(recipes) < num_recipes:
            # Add fallback recipes if needed
            fallback_recipes = [
                f"Mixed {ingredients[0].title()} Stir-fry",
                f"Leftover {ingredients[0].title()} Soup",
                f"Quick {ingredients[0].title()} Curry"
            ]
            
            for fallback in fallback_recipes:
                if len(recipes) >= num_recipes:
                    break
                if fallback not in recipes:
                    recipes.append(fallback)
        
        return recipes[:num_recipes]
        
    except Exception as e:
        logger.error(f"Error generating recipes: {str(e)}")
        return [f"Error generating recipes: {str(e)}"]

# Legacy functions for backward compatibility - now use centralized system
def award_recipe_xp(user_id: str, recipe_count: int):
    """Legacy function - redirects to centralized system"""
    try:
        xp_awarded, level_up, achievements = award_xp(
            user_id, 
            'recipe_generation',
            context={'feature': 'leftover_management', 'recipe_count': recipe_count}
        )
        return xp_awarded > 0
    except Exception as e:
        logger.error(f"Error in legacy recipe XP: {str(e)}")
        return False

def update_user_stats(user_id: str, xp_amount: int):
    """Legacy function - redirects to centralized system"""
    try:
        xp_awarded, level_up, achievements = award_xp(
            user_id, 
            'recipe_generation',
            amount=xp_amount,
            context={'feature': 'leftover_management'}
        )
        return xp_awarded > 0
    except Exception as e:
        logger.error(f"Error in legacy update_user_stats: {str(e)}")
        return False

def get_user_stats(user_id: str) -> Dict:
    """Legacy function - redirects to centralized system"""
    try:
        from modules.gamification_core import get_user_stats as get_centralized_stats
        return get_centralized_stats(user_id)
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0
        }
