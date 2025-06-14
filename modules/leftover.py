'''
Simplified leftover management and gamification module
'''

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

logger = logging.getLogger('leftover_combined')

def load_leftovers(csv_path: str) -> List[str]:
    '''Load leftover ingredients from CSV file'''
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
    '''Parse manually entered ingredients'''
    ingredients = input_text.split(',')
    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
    return ingredients

def parse_expiry_date(expiry_string: str) -> datetime:
    '''Parse expiry date from Firebase format'''
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
    '''Check if ingredient is still valid (not expired)'''
    expiry_date = parse_expiry_date(expiry_string)
    if expiry_date is None:
        return False
    
    current_date = datetime.now()
    return expiry_date.date() >= current_date.date()

def filter_valid_ingredients(ingredients: List[Dict]) -> List[Dict]:
    '''Filter out expired ingredients'''
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
    '''Fetch valid ingredients from Firebase'''
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
    '''Get ingredients prioritized by expiry date'''
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
    '''Calculate days until expiry'''
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
    '''Parse Firebase ingredients into simple list'''
    ingredients = []
    for item in firebase_ingredients:
        if 'Ingredient' in item and item['Ingredient']:
            if is_ingredient_valid(item.get('Expiry Date', '')):
                ingredients.append(item['Ingredient'])
    return ingredients

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3, notes: str = "", priority_ingredients: List[Dict] = None) -> List[str]:
    '''Suggest recipes based on leftover ingredients'''
    if not leftovers:
        return []

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found!")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        ingredients_list = ", ".join(leftovers)
        
        notes_text = f"\nRequirements: {notes}" if notes else ""
        
        priority_text = ""
        if priority_ingredients:
            urgent_ingredients = [ing for ing in priority_ingredients if 0 <= ing['days_until_expiry'] <= 7]
            if urgent_ingredients:
                urgent_details = [f"{ing['name']} (expires in {ing['days_until_expiry']} days)" for ing in urgent_ingredients]
                priority_text = f"\nPRIORITY: Use these ingredients first: {', '.join(urgent_details)}"
        
        prompt = f'''
        Ingredients: {ingredients_list}.{notes_text}{priority_text}

        Suggest {max_suggestions} simple recipe names using these ingredients.

        Format each recipe as just the name.
        Keep recipes simple and focused on using the ingredients.
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
            return []
        return recipes

    except Exception as e:
        logger.error(f"Error using Gemini API: {str(e)}")
        raise Exception(f"Error generating recipes: {str(e)}")

# Gamification functions
def get_firestore_db():
    """Get Firestore client"""
    init_firebase()
    return firestore.client()

def generate_dynamic_quiz_questions(ingredients: List[str], num_questions: int = 5) -> List[Dict]:
    """Generate quiz questions"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return generate_fallback_questions(num_questions)
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt = f'''
        Generate {num_questions} cooking quiz questions.
        
        Format as JSON array:
        [
            {{
                "question": "Question text?",
                "options": ["A", "B", "C", "D"],
                "correct": 0,
                "difficulty": "easy",
                "xp_reward": 10,
                "explanation": "Explanation"
            }}
        ]

        XP: easy=10, medium=15, hard=20
        '''

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        if "\`\`\`json" in response_text:
            response_text = response_text.split("\`\`\`json")[1].split("\`\`\`")[0]

        try:
            questions = json.loads(response_text)
            if isinstance(questions, list) and len(questions) > 0:
                return questions[:num_questions]
            else:
                return generate_fallback_questions(num_questions)
        except json.JSONDecodeError:
            return generate_fallback_questions(num_questions)

    except Exception as e:
        return generate_fallback_questions(num_questions)

def generate_fallback_questions(num_questions: int = 5) -> List[Dict]:
    """Generate fallback quiz questions"""
    all_questions = [
        {
            "question": "What is the safe minimum temperature for cooking ground beef?",
            "options": ["145°F", "160°F", "165°F", "180°F"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Ground beef should be cooked to 160°F to eliminate bacteria."
        },
        {
            "question": "Which cooking method uses dry heat?",
            "options": ["Braising", "Steaming", "Roasting", "Poaching"],
            "correct": 2,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Roasting uses dry heat in an oven."
        },
        {
            "question": "What does 'sauté' mean?",
            "options": ["Boil rapidly", "Cook quickly in fat", "Cook slowly", "Bake"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Sauté means to cook quickly in fat over high heat."
        }
    ]
    
    random.shuffle(all_questions)
    return all_questions[:num_questions]

def calculate_quiz_score(answers: List[int], questions: List[Dict]) -> Tuple[int, int, int]:
    """Calculate quiz score and XP"""
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
    """Get user's gamification stats"""
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

def update_user_stats(user_id: str, xp_gained: int, correct: int, total: int) -> Dict:
    """Update user stats after quiz"""
    try:
        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)

        current_stats = get_user_stats(user_id)
        old_level = current_stats['level']

        new_total_xp = current_stats['total_xp'] + xp_gained
        new_level = calculate_level(new_total_xp)
        new_quizzes = current_stats['quizzes_taken'] + 1
        new_correct = current_stats['correct_answers'] + correct
        new_total_questions = current_stats['total_questions'] + total
        new_perfect_scores = current_stats['perfect_scores'] + (1 if correct == total else 0)

        current_achievements = current_stats.get('achievements', [])
        new_achievements = check_achievements(
            new_quizzes, new_perfect_scores, new_level, old_level, current_achievements
        )

        updated_stats = {
            'user_id': user_id,
            'total_xp': new_total_xp,
            'level': new_level,
            'quizzes_taken': new_quizzes,
            'correct_answers': new_correct,
            'total_questions': new_total_questions,
            'recipes_generated': current_stats.get('recipes_generated', 0),
            'perfect_scores': new_perfect_scores,
            'last_quiz_date': firestore.SERVER_TIMESTAMP,
            'achievements': new_achievements
        }

        user_stats_ref.set(updated_stats)
        return updated_stats

    except Exception as e:
        logger.error(f"Error updating user stats: {str(e)}")
        return current_stats

def check_achievements(quizzes: int, perfect_scores: int, new_level: int, old_level: int, current_achievements: List[str]) -> List[str]:
    """Check for new achievements"""
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
    """Calculate user level based on XP"""
    import math
    return max(1, int(math.sqrt(total_xp / 100)) + 1)

def get_xp_progress(current_xp: int, current_level: int) -> Tuple[int, int]:
    """Calculate XP progress within current level"""
    previous_level_xp = ((current_level - 1) ** 2) * 100
    next_level_xp = (current_level ** 2) * 100
    current_level_xp = current_xp - previous_level_xp
    xp_needed = next_level_xp - current_xp

    return current_level_xp, xp_needed

def get_leaderboard(limit: int = 10) -> List[Dict]:
    """Get top users leaderboard"""
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
    """Award XP for generating recipes"""
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
