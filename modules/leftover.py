import pandas as pd
from typing import List, Optional, Dict, Tuple
import os
import google.generativeai as genai
import logging
import random
import json
from datetime import datetime, date

from firebase_admin import firestore
from firebase_init import init_firebase
from modules.firebase_data import (
    search_recipes_by_ingredients, search_menu_by_ingredients,
    format_recipe_for_display, format_menu_item_for_display,
    get_popular_recipes, fetch_recipe_archive, fetch_menu_items
)
from modules.xp_utils import calculate_level_from_xp

logger = logging.getLogger('leftover_combined')

def load_leftovers(csv_path: str) -> List[str]:
    try:
        df = pd.read_csv(csv_path)
        if 'ingredient' not in df.columns:
            raise ValueError("CSV file must have an 'ingredient' column")
        ingredients = df['ingredient'].tolist()
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)]
        return ingredients
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file unavailable at: {csv_path}")
    except Exception as e:
        raise Exception(f"Error loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]:
    ingredients = input_text.split(',')
    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
    return ingredients

def parse_expiry_date(expiry_string: str) -> datetime:
    try:
        if "Expiry date:" in expiry_string:
            date_part = expiry_string.replace("Expiry date:", "").strip()
        else:
            date_part = expiry_string.strip()
        
        return datetime.strptime(date_part, "%d/%m/%Y")
    except Exception as e:
        logger.warning(f"Could not parse expiry date '{expiry_string}': {str(e)}")
        return None

def is_ingredient_valid(expiry_string: str) -> bool:
    expiry_date = parse_expiry_date(expiry_string)
    if expiry_date is None:
        return False
    
    current_date = datetime.now()
    return expiry_date.date() >= current_date.date()

def filter_valid_ingredients(ingredients: List[Dict]) -> List[Dict]:
    valid_ingredients = []
    expired_count = 0
    
    for ingredient in ingredients:
        expiry_date_str = ingredient.get('Expiry Date', '')
        if is_ingredient_valid(expiry_date_str):
            valid_ingredients.append(ingredient)
        else:
            expired_count += 1
    
    logger.info(f"Filtered out {expired_count} expired ingredients")
    return valid_ingredients

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
        
        all_ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            all_ingredients.append(item)
        
        valid_ingredients = filter_valid_ingredients(all_ingredients)
        valid_ingredients.sort(key=lambda x: parse_expiry_date(x.get('Expiry Date', '')) or datetime.max)
        
        return valid_ingredients
        
    except Exception as e:
        logger.error(f"Error fetching ingredients from Firebase: {str(e)}")
        raise Exception(f"Error fetching ingredients from Firebase: {str(e)}")

def get_ingredients_by_expiry_priority(firebase_ingredients: List[Dict], max_ingredients: int = 10) -> Tuple[List[str], List[Dict]]:
    if not firebase_ingredients:
        return [], []
    
    valid_ingredients = [ing for ing in firebase_ingredients if is_ingredient_valid(ing.get('Expiry Date', ''))]
    
    if not valid_ingredients:
        return [], []
    
    priority_ingredients = valid_ingredients[:max_ingredients]
    
    ingredient_names = []
    detailed_info = []
    
    for item in priority_ingredients:
        if 'Ingredient' in item and item['Ingredient']:
            ingredient_names.append(item['Ingredient'])
            days_until_expiry = calculate_days_until_expiry(item.get('Expiry Date', ''))
            detailed_info.append({
                'name': item['Ingredient'],
                'expiry_date': item.get('Expiry Date', 'No expiry date'),
                'type': item.get('Type', 'No type'),
                'days_until_expiry': days_until_expiry
            })
    
    return ingredient_names, detailed_info

def calculate_days_until_expiry(expiry_string: str) -> int:
    try:
        expiry_date = parse_expiry_date(expiry_string)
        if expiry_date is None:
            return -999
        
        current_date = datetime.now()
        delta = expiry_date.date() - current_date.date()
        return delta.days
    except:
        return -999

def parse_firebase_ingredients(firebase_ingredients: List[Dict]) -> List[str]:
    ingredients = []
    for item in firebase_ingredients:
        if 'Ingredient' in item and item['Ingredient']:
            if is_ingredient_valid(item.get('Expiry Date', '')):
                ingredients.append(item['Ingredient'])
    return ingredients

def get_restaurant_context() -> str:
    try:
        recipes = fetch_recipe_archive()
        menu_items = fetch_menu_items()
        
        context_info = []
        
        cooking_styles = set()
        common_spices = set()
        
        for recipe in recipes[:10]:
            name = recipe.get('name', '').lower()
            description = recipe.get('description', '').lower()
            ingredients = recipe.get('ingredients', [])
            
            if any(style in name or style in description for style in ['curry', 'masala', 'biryani', 'dal']):
                cooking_styles.add('Indian')
            if any(style in name or style in description for style in ['pasta', 'pizza', 'risotto']):
                cooking_styles.add('Italian')
            if any(style in name or style in description for style in ['stir fry', 'fried rice', 'noodles']):
                cooking_styles.add('Asian')
            
            if isinstance(ingredients, list):
                for ing in ingredients:
                    ing_str = str(ing).lower()
                    if any(spice in ing_str for spice in ['cumin', 'turmeric', 'garam masala', 'coriander']):
                        common_spices.add(ing_str)
        
        if cooking_styles:
            context_info.append(f"Restaurant specializes in: {', '.join(cooking_styles)} cuisine")
        
        if common_spices:
            context_info.append(f"Commonly used spices: {', '.join(list(common_spices)[:5])}")
        
        dish_types = set()
        for item in menu_items[:5]:
            name = item.get('name', '').lower()
            if 'curry' in name:
                dish_types.add('curries')
            elif 'rice' in name:
                dish_types.add('rice dishes')
            elif 'bread' in name or 'naan' in name or 'roti' in name:
                dish_types.add('breads')
        
        if dish_types:
            context_info.append(f"Restaurant serves: {', '.join(dish_types)}")
        
        return " | ".join(context_info) if context_info else "General restaurant kitchen"
        
    except Exception as e:
        logger.error(f"Error getting restaurant context: {str(e)}")
        return "General restaurant kitchen"

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3, notes: str = "", priority_ingredients: List[Dict] = None) -> List[str]:
    if not leftovers:
        return []

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ["GEMINI_API_KEY not found - cannot generate new recipes"]
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        restaurant_context = get_restaurant_context()
        
        ingredients_list = ", ".join(leftovers)
        
        notes_text = f"\nSpecial requirements: {notes}" if notes else ""
        
        priority_text = ""
        if priority_ingredients:
            urgent_ingredients = [ing for ing in priority_ingredients if 0 <= ing['days_until_expiry'] <= 7]
            if urgent_ingredients:
                urgent_details = [f"{ing['name']} (expires in {ing['days_until_expiry']} days)" for ing in urgent_ingredients]
                priority_text = f"\nURGENT: Must use these ingredients first: {', '.join(urgent_details)}"
        
        prompt = f'''You are a creative chef tasked with creating NEW, ORIGINAL recipes using leftover ingredients. 

LEFTOVER INGREDIENTS TO USE: {ingredients_list}

RESTAURANT CONTEXT (for style reference only): {restaurant_context}

TASK: Create {max_suggestions} completely NEW and CREATIVE recipe names that:
1. Use the leftover ingredients as main components
2. Are practical for a restaurant kitchen
3. Match the restaurant's cooking style
4. Are different from existing menu items
5. Help reduce food waste by using leftovers creatively

{notes_text}{priority_text}

IMPORTANT RULES:
- Create ORIGINAL recipes, not existing ones
- Focus on creative combinations of the leftover ingredients
- Make them sound appetizing and restaurant-quality
- Each recipe should be a complete dish name
- Consider fusion approaches if appropriate

Format: Return only the recipe names, one per line, numbered 1-{max_suggestions}.

Example format:
1. Spiced Leftover Vegetable Biryani Bowl
2. Fusion Leftover Curry Pasta
3. Crispy Leftover Vegetable Fritters with Mint Chutney'''

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        recipe_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        new_recipes = []
        
        for line in recipe_lines:
            if line and line[0].isdigit() and line[1:3] in ['. ', '- ', ') ']:
                line = line[3:].strip()
            
            line = line.strip('"\'')
            
            if line and len(new_recipes) < max_suggestions:
                new_recipes.append(line)
        
        if not new_recipes:
            return []
        
        logger.info(f"Generated {len(new_recipes)} new creative recipes using leftovers")
        return new_recipes[:max_suggestions]

    except Exception as e:
        logger.error(f"Error generating new recipes: {str(e)}")
        return []

def get_firestore_db():
    init_firebase()
    return firestore.client()

def generate_dynamic_quiz_questions(ingredients: List[str], num_questions: int = 5) -> List[Dict]:
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found")
            return []
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        import random
        import time
        random_seed = int(time.time() * 1000) % 10000
        
        all_cooking_topics = [
            "food safety and temperatures",
            "knife skills and cutting techniques", 
            "baking and pastry fundamentals",
            "sauce making and emulsions",
            "meat cooking and doneness",
            "vegetable preparation methods",
            "spice and herb knowledge",
            "cooking equipment and tools",
            "food storage and preservation",
            "international cuisine techniques",
            "fermentation and pickling",
            "grilling and barbecue methods",
            "soup and stock preparation",
            "bread making techniques",
            "egg cooking methods",
            "dairy and cheese knowledge",
            "seafood preparation",
            "nutrition and dietary needs",
            "kitchen safety protocols",
            "food presentation and plating",
            "wine and beverage pairing",
            "molecular gastronomy basics",
            "smoking and curing techniques",
            "pasta and noodle preparation",
            "dessert and confection making"
        ]
        
        random.shuffle(all_cooking_topics)
        selected_topics = all_cooking_topics[:num_questions]
        
        prompt = f'''Generate {num_questions} COMPLETELY DIFFERENT and RANDOM cooking quiz questions. 

IMPORTANT: Each question must be about a COMPLETELY DIFFERENT cooking topic. No similar or related questions.

Random seed: {random_seed}
Topics to cover (one question per topic): {", ".join(selected_topics)}

Requirements:
1. Generate exactly {num_questions} questions
2. Each question must be about a COMPLETELY different cooking concept
3. Make questions random and unpredictable
4. Mix difficulty levels randomly
5. Cover diverse cooking knowledge areas
6. No repeated or similar question types

Return as valid JSON array:
[
    {{
        "question": "Completely unique cooking question here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct": 0,
        "difficulty": "easy",
        "xp_reward": 10,
        "explanation": "Brief explanation"
    }}
]

XP Rewards: easy=10, medium=15, hard=20

Make each question completely unique and random - no patterns or similarities!'''

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        try:
            questions = json.loads(response_text)
            
            if isinstance(questions, list) and len(questions) >= num_questions:
                selected_questions = questions[:num_questions]
                
                valid_questions = []
                for q in selected_questions:
                    if (isinstance(q, dict) and 
                        'question' in q and 
                        'options' in q and 
                        'correct' in q and
                        isinstance(q['options'], list) and 
                        len(q['options']) == 4):
                        valid_questions.append(q)
                
                if len(valid_questions) >= num_questions:
                    logger.info(f"Generated {len(valid_questions)} completely random quiz questions")
                    return valid_questions[:num_questions]
                else:
                    logger.warning(f"Only {len(valid_questions)} valid questions generated")
                    return []
            else:
                logger.warning(f"Expected {num_questions} questions, got {len(questions) if isinstance(questions, list) else 0}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return []

    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")
        return []

def calculate_quiz_score(answers: List[int], questions: List[Dict]) -> Tuple[int, int, int]:
    correct_answers = 0
    xp_earned = 0

    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question["correct"]:
            correct_answers += 1
            xp_earned += question["xp_reward"]

    if correct_answers == len(questions):
        bonus_xp = len(questions) * 5
        xp_earned += bonus_xp

    return correct_answers, len(questions), xp_earned

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

def update_user_stats(user_id, xp_gained, recipes_generated=0, quizzes_completed=0):
    try:
        db = get_firestore_db()
        if not db:
            return False
        
        user_stats_ref = db.collection('user_stats').document(user_id)
        user_stats_doc = user_stats_ref.get()
        
        if user_stats_doc.exists:
            current_stats = user_stats_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            current_recipes = current_stats.get('recipes_generated', 0)
            current_quizzes = current_stats.get('quizzes_completed', 0)
        else:
            current_xp = 0
            current_recipes = 0
            current_quizzes = 0
        
        new_total_xp = current_xp + xp_gained
        new_recipes = current_recipes + recipes_generated
        new_quizzes = current_quizzes + quizzes_completed
        
        new_level = calculate_level_from_xp(new_total_xp)
        
        updated_stats = {
            'total_xp': new_total_xp,
            'level': new_level,
            'recipes_generated': new_recipes,
            'quizzes_completed': new_quizzes,
            'last_activity': firestore.SERVER_TIMESTAMP
        }
        
        user_stats_ref.set(updated_stats, merge=True)
        
        logger.info(f"Updated user {user_id} stats: +{xp_gained} XP, Level {new_level}, Total XP: {new_total_xp}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating user stats: {str(e)}")
        return False

def check_achievements(quizzes: int, perfect_scores: int, new_level: int, old_level: int, current_achievements: List[str]) -> List[str]:
    achievements = current_achievements.copy()

    quiz_milestones = [
        (1, "First Quiz"),
        (5, "Quiz Novice"),
        (10, "Quiz Enthusiast"),
        (25, "Quiz Master"),
        (50, "Quiz Legend")
    ]

    for milestone, title in quiz_milestones:
        if quizzes >= milestone and title not in achievements:
            achievements.append(title)

    perfect_milestones = [
        (1, "Perfectionist"),
        (5, "Streak Master"),
        (10, "Flawless Chef")
    ]

    for milestone, title in perfect_milestones:
        if perfect_scores >= milestone and title not in achievements:
            achievements.append(title)

    level_milestones = [
        (5, "Rising Star"),
        (10, "Kitchen Pro"),
        (15, "Culinary Expert"),
        (20, "Master Chef")
    ]

    for milestone, title in level_milestones:
        if new_level >= milestone and title not in achievements:
            achievements.append(title)

    return achievements

def calculate_level(total_xp: int) -> int:
    import math
    return max(1, int(math.sqrt(total_xp / 100)) + 1)

def get_xp_progress(current_xp: int, current_level: int) -> Tuple[int, int]:
    previous_level_xp = ((current_level - 1) ** 2) * 100
    next_level_xp = (current_level ** 2) * 100
    current_level_xp = current_xp - previous_level_xp
    xp_needed = next_level_xp - current_xp

    return current_level_xp, xp_needed

def get_leaderboard(limit: int = 10) -> List[Dict]:
    try:
        db = get_firestore_db()

        stats_query = db.collection('user_stats').order_by('total_xp', direction=firestore.Query.DESCENDING).limit(limit)
        stats_docs = stats_query.get()

        users_ref = db.collection('users')
        leaderboard = []

        for i, stat_doc in enumerate(stats_docs):
            stat_data = stat_doc.to_dict()
            user_id = stat_data['user_id']

            try:
                user_doc = users_ref.document(user_id).get()
                username = user_doc.to_dict().get('username', 'Unknown') if user_doc.exists else 'Unknown'
            except:
                username = 'Unknown'

            leaderboard.append({
                'rank': i + 1,
                'username': username,
                'total_xp': stat_data.get('total_xp', 0),
                'level': stat_data.get('level', 1),
                'quizzes_taken': stat_data.get('quizzes_taken', 0),
                'perfect_scores': stat_data.get('perfect_scores', 0),
                'achievements': len(stat_data.get('achievements', []))
            })

        return leaderboard

    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        return []

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
