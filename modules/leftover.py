'''
UPDATED VERSION: Enhanced leftover management with Firebase ingredient prioritization
MADE BY: Aarav Agarwal, IBCP CRS: AI, WACP ID: 1000197

This file combines leftover management and gamification features with enhanced Firebase integration
that prioritizes ingredients based on expiry dates and quantities.
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
    '''
    ARGUMENT - loading all leftover ingredients from a csv file (if it exists)
    csv_path (str) is the path to the csv file containing the ingredients & should have a column named "ingredients"

    RETURN -  List[str]: a list of names of all leftover ingredients

    RAISES -  if FileNotFoundError occurs then it means that the csv file does not exist. if "ValueError" occurs then that means thtat the CSV file doesnt have ingredients column
    '''
    try:
        df = pd.read_csv(csv_path) # reading the Csv file
        if 'ingredient' not in df.columns: # checking if ingredient column is present in the csv
            raise ValueError("CSV file must have an 'ingredient' column")
        ingredients = df['ingredient'].tolist() # getting all values in the "ingredient" column in list format if it is there 
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)] # strip whitespace
        return ingredients
    except FileNotFoundError:
        raise FileNotFoundError(f" CSV file unavailable at: {csv_path}")
    except Exception as e:
        raise Exception(f"Faced error in loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]:
    '''
    parses the manually entered list

    ARGUMENT - input_text (str), which is the manually entered ingredients with each being separated by a , 
    RETURN - List[str], a list of leftover ingredient names where it is properly organized 
    '''
    ingredients = input_text.split(',')
    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
    return ingredients

def fetch_ingredients_from_firebase() -> List[Dict]:
    '''
    Fetches ingredients from Firebase ingredient_inventory collection using the event Firebase configuration
    
    RETURN - List[Dict]: a list of ingredient dictionaries with their details including expiry dates and quantities
    '''
    try:
        from firebase_admin import firestore
        import firebase_admin
        
        # Use the event Firebase app instead of the default one
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            db = firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            # If event_app is not initialized, initialize it
            from app_integration import check_event_firebase_config
            check_event_firebase_config()
            from modules.event_planner import init_event_firebase  # Updated import path
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
    '''
    Parse expiry date string into datetime object
    
    ARGUMENT - expiry_str (str): The expiry date string from Firebase
    RETURN - Optional[datetime]: Parsed datetime object or None if parsing fails
    '''
    if not expiry_str or expiry_str.lower() in ['none', 'null', '', 'n/a']:
        return None
    
    # Common date formats to try
    date_formats = [
        '%Y-%m-%d',      # 2024-12-31
        '%d/%m/%Y',      # 31/12/2024
        '%m/%d/%Y',      # 12/31/2024
        '%d-%m-%Y',      # 31-12-2024
        '%Y/%m/%d',      # 2024/12/31
        '%B %d, %Y',     # December 31, 2024
        '%d %B %Y',      # 31 December 2024
    ]
    
    for date_format in date_formats:
        try:
            return datetime.strptime(expiry_str.strip(), date_format)
        except ValueError:
            continue
    
    logger.warning(f"Could not parse expiry date: {expiry_str}")
    return None

def parse_quantity(quantity_str: str) -> float:
    '''
    Parse quantity string into float value
    
    ARGUMENT - quantity_str (str): The quantity string from Firebase
    RETURN - float: Parsed quantity value, defaults to 0 if parsing fails
    '''
    if not quantity_str:
        return 0.0
    
    try:
        # Remove common units and extract numeric value
        quantity_clean = str(quantity_str).lower().strip()
        
        # Remove common units
        units_to_remove = ['kg', 'g', 'lbs', 'oz', 'ml', 'l', 'cups', 'tbsp', 'tsp', 'pieces', 'pcs']
        for unit in units_to_remove:
            quantity_clean = quantity_clean.replace(unit, '').strip()
        
        # Extract first number found
        import re
        numbers = re.findall(r'\d+\.?\d*', quantity_clean)
        if numbers:
            return float(numbers[0])
        
        return 0.0
    except:
        return 0.0

def calculate_days_until_expiry(expiry_date: Optional[datetime]) -> int:
    '''
    Calculate days until expiry from current date
    
    ARGUMENT - expiry_date (Optional[datetime]): The expiry date
    RETURN - int: Days until expiry (negative if expired, large positive if no expiry date)
    '''
    if not expiry_date:
        return 9999  # No expiry date, treat as very far future
    
    current_date = datetime.now()
    delta = expiry_date - current_date
    return delta.days

def prioritize_ingredients(firebase_ingredients: List[Dict]) -> List[Dict]:
    '''
    Prioritize ingredients based on expiry date and quantity
    Priority order:
    1. About to expire soon (≤7 days) and large quantity (≥5 units)
    2. About to expire soon (≤7 days) regardless of quantity
    3. Large quantity (≥5 units) regardless of expiry date
    4. Everything else
    
    ARGUMENT - firebase_ingredients (List[Dict]): Raw ingredients from Firebase
    RETURN - List[Dict]: Prioritized and sorted ingredients
    '''
    processed_ingredients = []
    
    for item in firebase_ingredients:
        if not item.get('Ingredient'):
            continue
            
        # Parse expiry date and quantity
        expiry_date = parse_expiry_date(item.get('Expiry date', ''))
        quantity = parse_quantity(item.get('Quantity', '0'))
        days_until_expiry = calculate_days_until_expiry(expiry_date)
        
        # Determine priority
        is_expiring_soon = days_until_expiry <= 7 and days_until_expiry >= 0  # Within 7 days, not expired
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
    
    # Sort by priority (1 = highest priority), then by days until expiry (ascending), then by quantity (descending)
    processed_ingredients.sort(key=lambda x: (x['priority'], x['days_until_expiry'], -x['quantity']))
    
    logger.info(f"Prioritized {len(processed_ingredients)} ingredients")
    for item in processed_ingredients[:5]:  # Log top 5 for debugging
        logger.info(f"Priority {item['priority']}: {item['ingredient']} - "
                   f"Expires in {item['days_until_expiry']} days, Quantity: {item['quantity']}")
    
    return processed_ingredients

def parse_firebase_ingredients(firebase_ingredients: List[Dict]) -> List[str]:
    '''
    Parses prioritized ingredients from Firebase into a simple list of ingredient names
    
    ARGUMENT - firebase_ingredients (List[Dict]): List of prioritized ingredient dictionaries from Firebase
    RETURN - List[str]: a list of ingredient names in priority order
    '''
    # First prioritize the ingredients
    prioritized_ingredients = prioritize_ingredients(firebase_ingredients)
    
    # Extract ingredient names in priority order
    ingredients = [item['ingredient'] for item in prioritized_ingredients if item['ingredient']]
    
    return ingredients

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3, notes: str = "", prioritized_ingredients: List[Dict] = None) -> List[str]:
    '''
    Suggest recipes based on the leftover ingredients with priority consideration.

    ARGUMENT - 
    leftovers (List[str]), list of the leftover ingredients (whether via the csv file or manually entered)
    max_suggestions (int, optional): maximum number of recipe suggestions to output
    notes (str, optional): additional notes or requirements for the recipes
    prioritized_ingredients (List[Dict], optional): prioritized ingredient data for enhanced prompting

    RETURN - List[str] of all recipes
    '''
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
        logger.info(f"Generating recipes for ingredients: {ingredients_list}")
        
        # Enhanced prompt with priority information
        priority_info = ""
        if prioritized_ingredients:
            high_priority_items = [item for item in prioritized_ingredients if item['priority'] <= 2]
            if high_priority_items:
                priority_info = "\n\nIMPORTANT: Please prioritize using these ingredients as they are expiring soon:\n"
                for item in high_priority_items:
                    expiry_info = f"expires in {item['days_until_expiry']} days" if item['days_until_expiry'] < 9999 else "no expiry date"
                    priority_info += f"- {item['ingredient']} (quantity: {item['quantity']}, {expiry_info})\n"
        
        # Add notes to the prompt if provided
        notes_text = f"\nAdditional requirements: {notes}" if notes else ""
        logger.info(f"Additional notes: {notes_text}")
        
        prompt = f'''
        Here are the leftover ingredients I have: {ingredients_list}.{priority_info}{notes_text}

        I need you to suggest {max_suggestions} creative and unique recipe ideas that use these ingredients to avoid any food waste.

        Please focus on using the high-priority ingredients (those expiring soon) as main components of the recipes.

        For each recipe, provide just the recipe name. Don't include ingredients list or instructions, just keep it very simple and minimalistic in the output
        Format each recipe as "Recipe Name"
        Keep the recipes simple and focused on using the leftover ingredients, especially those that are expiring soon.
        ''' 

        logger.info("Sending request to Gemini API")
        response = model.generate_content(prompt)
        response_text = response.text
        logger.info(f"Received response from Gemini API: {response_text[:100]}...")
        
        recipe_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        recipes = []
        for line in recipe_lines:
            if line and line[0].isdigit() and line[1:3] in ['. ', '- ', ') ']:
                line = line[3:].strip()
            line = line.strip('"\'')
            if line and len(recipes) < max_suggestions:
                recipes.append(line)
        
        recipes = recipes[:max_suggestions]
        logger.info(f"Processed recipes: {recipes}")
        
        if not recipes:
            logger.warning(f"Got no recipes for the ingredients: {ingredients_list}!!")
            return []
        return recipes

    except Exception as e:
        logger.error(f"Error using Gemini API: {str(e)}")
        logger.exception("Full exception details:")
        raise Exception(f"Error generating recipes: {str(e)}")

# ------------------ Gamification Functions (unchanged) ------------------

def get_firestore_db():
    """Get a Firestore client instance."""
    init_firebase()
    return firestore.client()

def generate_dynamic_quiz_questions(ingredients: List[str], num_questions: int = 5) -> List[Dict]:
    """
    Generate unique quiz questions based on the leftover ingredients using Gemini API.

    Args:
        ingredients (List[str]): List of leftover ingredients
        num_questions (int): Number of questions to generate

    Returns:
        List[Dict]: List of generated quiz questions
    """
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found, falling back to basic questions")
            return generate_fallback_questions(num_questions)
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        ingredients_list = ", ".join(ingredients)
        prompt = f"""
        Generate {num_questions} unique cooking quiz questions based on these ingredients: {ingredients_list}

        The questions should be:
        1. Related to cooking techniques, food safety, or culinary knowledge involving these ingredients
        2. Multiple choice with 4 options each
        3. Varied in difficulty (easy, medium, hard)
        4. Educational and fun

        Format your response as a JSON array with this exact structure:
        [
            {{
                "question": "Question text here?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 0,
                "difficulty": "easy",
                "xp_reward": 10,
                "explanation": "Brief explanation of the correct answer"
            }}
        ]

        Difficulty and XP mapping:
        - easy: 10 XP
        - medium: 15 XP  
        - hard: 20 XP

        Make sure the JSON is properly formatted and valid. Include interesting facts about the ingredients.
        """

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up the response to extract JSON
        if "\`\`\`json" in response_text:
            response_text = response_text.split("\`\`\`json")[1].split("\`\`\`")[0]
        elif "\`\`\`" in response_text:
            response_text = response_text.split("\`\`\`")[1].split("\`\`\`")[0]

        try:
            questions = json.loads(response_text)
            if isinstance(questions, list) and len(questions) > 0:
                logger.info(f"Successfully generated {len(questions)} dynamic questions")
                return questions
            else:
                logger.warning("Invalid question format from Gemini, using fallback")
                return generate_fallback_questions(num_questions)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response text: {response_text}")
            return generate_fallback_questions(num_questions)

    except Exception as e:
        logger.error(f"Error generating dynamic questions: {str(e)}")
        return generate_fallback_questions(num_questions)

def generate_fallback_questions(num_questions: int = 5) -> List[Dict]:
    """
    Generate fallback quiz questions when Gemini API is not available.

    Args:
        num_questions (int): Number of questions to return

    Returns:
        List[Dict]: List of fallback quiz questions
    """
    fallback_questions = [
        {
            "question": "What is the safe minimum internal temperature for cooking ground beef?",
            "options": ["145°F (63°C)", "160°F (71°C)", "165°F (74°C)", "180°F (82°C)"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Ground beef should be cooked to 160°F to eliminate harmful bacteria."
        },
        {
            "question": "Which cooking method uses dry heat and hot air circulation?",
            "options": ["Braising", "Steaming", "Roasting", "Poaching"],
            "correct": 2,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Roasting uses dry heat in an oven with hot air circulation."
        },
        {
            "question": "What does 'sauté' mean in cooking?",
            "options": ["To boil rapidly", "To cook quickly in a little fat", "To cook slowly in liquid", "To cook in the oven"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Sauté means to cook quickly in a small amount of fat over high heat."
        },
        {
            "question": "Which mother sauce is made with butter and egg yolks?",
            "options": ["Béchamel", "Velouté", "Hollandaise", "Espagnole"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Hollandaise is an emulsion of egg yolks, butter, and lemon juice."
        },
        {
            "question": "What is the purpose of blanching vegetables?",
            "options": ["To add flavor", "To partially cook and preserve color", "To remove moisture", "To add nutrients"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Blanching partially cooks vegetables and helps preserve their color and texture."
        },
        {
            "question": "Which technique involves slowly cooking tough cuts of meat in liquid?",
            "options": ["Grilling", "Braising", "Sautéing", "Broiling"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Braising slowly cooks tough meat in liquid to break down connective tissues."
        },
        {
            "question": "What is the Maillard reaction responsible for?",
            "options": ["Food spoilage", "Browning and flavor development", "Nutrient loss", "Texture changes only"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "The Maillard reaction creates browning and complex flavors when proteins and sugars are heated."
        },
        {
            "question": "Which knife cut produces long, thin strips?",
            "options": ["Brunoise", "Julienne", "Chiffonade", "Dice"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Julienne cut produces matchstick-like strips, typically 2mm x 2mm x 5cm."
        }
    ]
    return random.sample(fallback_questions, min(num_questions, len(fallback_questions)))

def calculate_quiz_score(answers: List[int], questions: List[Dict]) -> Tuple[int, int, int]:
    """
    Calculate quiz score and XP earned.

    Args:
        answers (List[int]): List of user's answers (indices)
        questions (List[Dict]): List of quiz questions

    Returns:
        Tuple[int, int, int]: (correct_answers, total_questions, xp_earned)
    """
    correct_answers = 0
    xp_earned = 0

    for i, question in enumerate(questions):
        if i < len(answers) and answers[i] == question["correct"]:
            correct_answers += 1
            xp_earned += question["xp_reward"]

    # Bonus XP for perfect score
    if correct_answers == len(questions):
        bonus_xp = len(questions) * 5
        xp_earned += bonus_xp
        logger.info(f"Perfect score bonus: +{bonus_xp} XP")

    return correct_answers, len(questions), xp_earned

def get_user_stats(user_id: str) -> Dict:
    """
    Get user's current gamification stats.

    Args:
        user_id (str): User's unique ID

    Returns:
        Dict: User's stats including XP, level, quizzes taken
    """
    try:
        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)
        doc = user_stats_ref.get()

        if doc.exists:
            return doc.to_dict()
        else:
            # Initialize new user stats
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
    """
    Update user's stats after completing a quiz.

    Args:
        user_id (str): User's unique ID
        xp_gained (int): XP earned from the quiz
        correct (int): Number of correct answers
        total (int): Total number of questions

    Returns:
        Dict: Updated user stats with new achievements
    """
    try:
        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)

        # Get current stats
        current_stats = get_user_stats(user_id)
        old_level = current_stats['level']

        # Calculate new stats
        new_total_xp = current_stats['total_xp'] + xp_gained
        new_level = calculate_level(new_total_xp)
        new_quizzes = current_stats['quizzes_taken'] + 1
        new_correct = current_stats['correct_answers'] + correct
        new_total_questions = current_stats['total_questions'] + total
        new_perfect_scores = current_stats['perfect_scores'] + (1 if correct == total else 0)

        # Check for new achievements
        current_achievements = current_stats.get('achievements', [])
        new_achievements = check_achievements(
            new_quizzes, new_perfect_scores, new_level, old_level, current_achievements
        )

        # Update stats
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
        logger.info(f"Updated stats for user {user_id}: +{xp_gained} XP, Level {new_level}")

        return updated_stats

    except Exception as e:
        logger.error(f"Error updating user stats: {str(e)}")
        return current_stats

def check_achievements(quizzes: int, perfect_scores: int, new_level: int, old_level: int, current_achievements: List[str]) -> List[str]:
    """
    Check and award new achievements based on user stats.

    Args:
        quizzes (int): Total quizzes taken
        perfect_scores (int): Number of perfect scores
        new_level (int): Current level
        old_level (int): Previous level
        current_achievements (List[str]): Current achievements

    Returns:
        List[str]: Updated achievements list
    """
    achievements = current_achievements.copy()

    # Quiz milestone achievements
    quiz_milestones = [
        (1, "First Quiz", "🏯"),
        (5, "Quiz Novice", "📚"),
        (10, "Quiz Enthusiast", "🔥"),
        (25, "Quiz Master", "👑"),
        (50, "Quiz Legend", "⭐")
    ]

    for milestone, title, emoji in quiz_milestones:
        achievement_key = f"{title}"
        if quizzes >= milestone and achievement_key not in achievements:
            achievements.append(achievement_key)
            logger.info(f"New achievement unlocked: {title}")

    # Perfect score achievements
    perfect_milestones = [
        (1, "Perfectionist", "💯"),
        (5, "Streak Master", "🏯"),
        (10, "Flawless Chef", "👨‍🍳")
    ]

    for milestone, title, emoji in perfect_milestones:
        achievement_key = f"{title}"
        if perfect_scores >= milestone and achievement_key not in achievements:
            achievements.append(achievement_key)
            logger.info(f"New achievement unlocked: {title}")

    # Level achievements
    level_milestones = [
        (5, "Rising Star", "🌟"),
        (10, "Kitchen Pro", "🔪"),
        (15, "Culinary Expert", "👨‍🍳"),
        (20, "Master Chef", "🏆")
    ]

    for milestone, title, emoji in level_milestones:
        achievement_key = f"{title}"
        if new_level >= milestone and achievement_key not in achievements:
            achievements.append(achievement_key)
            logger.info(f"New achievement unlocked: {title}")

    return achievements

def calculate_level(total_xp: int) -> int:
    """
    Calculate user level based on total XP.
    Level formula: Level = floor(sqrt(XP / 100)) + 1

    Args:
        total_xp (int): Total XP earned

    Returns:
        int: User's level
    """
    import math
    return max(1, int(math.sqrt(total_xp / 100)) + 1)

def get_xp_for_next_level(current_level: int) -> int:
    """
    Calculate XP needed for the next level.

    Args:
        current_level (int): Current user level

    Returns:
        int: XP needed for next level
    """
    return (current_level ** 2) * 100

def get_xp_progress(current_xp: int, current_level: int) -> Tuple[int, int]:
    """
    Calculate XP progress within current level.

    Args:
        current_xp (int): Current total XP
        current_level (int): Current level

    Returns:
        Tuple[int, int]: (current_level_xp, xp_needed_for_next_level)
    """
    previous_level_xp = ((current_level - 1) ** 2) * 100
    next_level_xp = (current_level ** 2) * 100
    current_level_xp = current_xp - previous_level_xp
    xp_needed = next_level_xp - current_xp

    return current_level_xp, xp_needed

def get_leaderboard(limit: int = 10) -> List[Dict]:
    """
    Get the top users leaderboard.

    Args:
        limit (int): Number of top users to return

    Returns:
        List[Dict]: Leaderboard data with user info
    """
    try:
        db = get_firestore_db()

        # Get user stats ordered by total XP
        stats_query = db.collection('user_stats').order_by('total_xp', direction=firestore.Query.DESCENDING).limit(limit)
        stats_docs = stats_query.get()

        # Get user details
        users_ref = db.collection('users')
        leaderboard = []

        for i, stat_doc in enumerate(stats_docs):
            stat_data = stat_doc.to_dict()
            user_id = stat_data['user_id']

            # Get username from users collection
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
    """
    Award XP for generating recipes (bonus gamification for main feature).

    Args:
        user_id (str): User's unique ID
        num_recipes (int): Number of recipes generated

    Returns:
        Dict: Updated user stats
    """
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
        logger.info(f"Awarded {total_xp} XP for generating {num_recipes} recipes")

        return updated_stats

    except Exception as e:
        logger.error(f"Error awarding recipe XP: {str(e)}")
        return get_user_stats(user_id)

# ------------------ End of Enhanced Module ------------------

print("Enhanced leftover management module loaded successfully!")
print("Key improvements:")
print("1. ✅ Ingredient prioritization based on expiry dates and quantities")
print("2. ✅ Enhanced recipe suggestions with priority consideration")
print("3. ✅ Better date and quantity parsing")
print("4. ✅ Detailed logging for debugging")
