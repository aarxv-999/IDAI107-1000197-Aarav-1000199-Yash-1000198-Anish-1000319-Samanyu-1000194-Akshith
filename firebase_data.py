import logging
from typing import List, Dict, Optional, Tuple
import firebase_admin
from firebase_admin import firestore
from firebase_init import init_firebase

logger = logging.getLogger(__name__)

def get_main_firestore_db():
    init_firebase()
    return firestore.client()

def get_event_firestore_db():
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

def fetch_recipe_archive() -> List[Dict]:
    try:
        db = get_event_firestore_db()
        if not db:
            logger.warning("Event Firebase not available, using main Firebase")
            db = get_main_firestore_db()
        
        recipes_ref = db.collection('recipe_archive')
        recipes_docs = recipes_ref.get()
        
        recipes = []
        for doc in recipes_docs:
            recipe_data = doc.to_dict()
            recipe_data['id'] = doc.id
            recipes.append(recipe_data)
        
        logger.info(f"Fetched {len(recipes)} recipes from archive")
        return recipes
        
    except Exception as e:
        logger.error(f"Error fetching recipe archive: {str(e)}")
        return []

def fetch_menu_items() -> List[Dict]:
    try:
        db = get_event_firestore_db()
        if not db:
            logger.warning("Event Firebase not available, using main Firebase")
            db = get_main_firestore_db()
        
        menu_ref = db.collection('menu')
        menu_docs = menu_ref.get()
        
        menu_items = []
        for doc in menu_docs:
            menu_data = doc.to_dict()
            menu_data['id'] = doc.id
            menu_items.append(menu_data)
        
        logger.info(f"Fetched {len(menu_items)} menu items")
        return menu_items
        
    except Exception as e:
        logger.error(f"Error fetching menu items: {str(e)}")
        return []

def search_recipes_by_ingredients(ingredients: List[str], limit: int = 10) -> List[Dict]:
    try:
        recipes = fetch_recipe_archive()
        if not recipes:
            return []
        
        matching_recipes = []
        ingredients_lower = [ing.lower().strip() for ing in ingredients]
        
        for recipe in recipes:
            recipe_ingredients = recipe.get('ingredients', [])
            recipe_name = recipe.get('name', '').lower()
            recipe_description = recipe.get('description', '').lower()
            
            if isinstance(recipe_ingredients, list):
                recipe_ingredients_lower = [str(ing).lower() for ing in recipe_ingredients]
            else:
                recipe_ingredients_lower = [str(recipe_ingredients).lower()]
            
            ingredient_match = any(
                any(search_ing in recipe_ing for recipe_ing in recipe_ingredients_lower)
                for search_ing in ingredients_lower
            )
            
            name_match = any(ing in recipe_name for ing in ingredients_lower)
            desc_match = any(ing in recipe_description for ing in ingredients_lower)
            
            if ingredient_match or name_match or desc_match:
                match_score = 0
                for ing in ingredients_lower:
                    if any(ing in recipe_ing for recipe_ing in recipe_ingredients_lower):
                        match_score += 2
                    if ing in recipe_name:
                        match_score += 1
                    if ing in recipe_description:
                        match_score += 0.5
                
                recipe['match_score'] = match_score
                matching_recipes.append(recipe)
        
        matching_recipes.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return matching_recipes[:limit]
        
    except Exception as e:
        logger.error(f"Error searching recipes by ingredients: {str(e)}")
        return []

def search_menu_by_ingredients(ingredients: List[str], limit: int = 10) -> List[Dict]:
    try:
        menu_items = fetch_menu_items()
        if not menu_items:
            return []
        
        matching_items = []
        ingredients_lower = [ing.lower().strip() for ing in ingredients]
        
        for item in menu_items:
            item_name = item.get('name', '').lower()
            item_description = item.get('description', '').lower()
            item_ingredients = item.get('ingredients', [])
            
            if isinstance(item_ingredients, list):
                item_ingredients_lower = [str(ing).lower() for ing in item_ingredients]
            else:
                item_ingredients_lower = [str(item_ingredients).lower()]
            
            ingredient_match = any(
                any(search_ing in item_ing for item_ing in item_ingredients_lower)
                for search_ing in ingredients_lower
            )
            
            name_match = any(ing in item_name for ing in ingredients_lower)
            desc_match = any(ing in item_description for ing in ingredients_lower)
            
            if ingredient_match or name_match or desc_match:
                match_score = 0
                for ing in ingredients_lower:
                    if any(ing in item_ing for item_ing in item_ingredients_lower):
                        match_score += 2
                    if ing in item_name:
                        match_score += 1
                    if ing in item_description:
                        match_score += 0.5
                
                item['match_score'] = match_score
                matching_items.append(item)
        
        matching_items.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        
        return matching_items[:limit]
        
    except Exception as e:
        logger.error(f"Error searching menu by ingredients: {str(e)}")
        return []

def get_popular_recipes(limit: int = 20) -> List[Dict]:
    try:
        recipes = fetch_recipe_archive()
        if not recipes:
            return []
        
        popular_recipes = sorted(recipes, key=lambda x: len(x.get('name', '')), reverse=True)
        
        return popular_recipes[:limit]
        
    except Exception as e:
        logger.error(f"Error getting popular recipes: {str(e)}")
        return []

def get_menu_categories() -> List[str]:
    try:
        menu_items = fetch_menu_items()
        if not menu_items:
            return []
        
        categories = set()
        for item in menu_items:
            category = item.get('category', '').strip()
            if category:
                categories.add(category)
        
        return sorted(list(categories))
        
    except Exception as e:
        logger.error(f"Error getting menu categories: {str(e)}")
        return []

def get_recipes_by_category(category: str, limit: int = 10) -> List[Dict]:
    try:
        recipes = fetch_recipe_archive()
        if not recipes:
            return []
        
        category_recipes = []
        for recipe in recipes:
            recipe_category = recipe.get('category', '').lower()
            if category.lower() in recipe_category:
                category_recipes.append(recipe)
        
        return category_recipes[:limit]
        
    except Exception as e:
        logger.error(f"Error getting recipes by category: {str(e)}")
        return []

def format_recipe_for_display(recipe: Dict) -> str:
    try:
        name = recipe.get('name', 'Unnamed Recipe')
        description = recipe.get('description', '')
        ingredients = recipe.get('ingredients', [])
        
        if description:
            return f"{name} - {description}"
        elif ingredients:
            if isinstance(ingredients, list) and len(ingredients) > 0:
                ing_preview = ', '.join(str(ing) for ing in ingredients[:3])
                if len(ingredients) > 3:
                    ing_preview += f" (and {len(ingredients) - 3} more)"
                return f"{name} (with {ing_preview})"
        
        return name
        
    except Exception as e:
        logger.error(f"Error formatting recipe: {str(e)}")
        return recipe.get('name', 'Recipe')

def format_menu_item_for_display(item: Dict) -> str:
    try:
        name = item.get('name', 'Unnamed Item')
        description = item.get('description', '')
        price = item.get('price', '')
        
        display_text = name
        if description:
            display_text += f" - {description}"
        if price:
            display_text += f" (₹{price})"
        
        return display_text
        
    except Exception as e:
        logger.error(f"Error formatting menu item: {str(e)}")
        return item.get('name', 'Menu Item')
