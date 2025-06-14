'''
MADE BY: Aarav Agarwal, IBCP CRS: AI, WACP ID: 1000197
This file combines leftover management and gamification features (originally in leftover.py and leftover_gamification.py).

Packages used:
- pandas: to read CSV files
- google.generativeai: to add Gemini API
- firebase_admin: for Firestore (gamification)
- logging, random, json, os: for utility
'''

import pandas as pd
from typing import List, Optional, Dict, Tuple
import os
import google.generativeai as genai
import logging
import random
import json
from datetime import datetime, date

# Gamification-specific imports
from firebase_admin import firestore
from firebase_init import init_firebase

# Logger setup
logger = logging.getLogger('leftover_combined')

# ------------------ Leftover Management Functions ------------------

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

def parse_expiry_date(expiry_string: str) -> datetime:
    '''
    Parse expiry date from Firebase format "Expiry date: DD/MM/YYYY"
    
    ARGUMENT - expiry_string (str): The expiry date string from Firebase
    RETURN - datetime: Parsed datetime object, or None if parsing fails
    '''
    try:
        # Remove "Expiry date:" prefix if present
        if "Expiry date:" in expiry_string:
            date_part = expiry_string.replace("Expiry date:", "").strip()
        else:
            date_part = expiry_string.strip()
        
        # Parse DD/MM/YYYY format
        return datetime.strptime(date_part, "%d/%m/%Y")
    except Exception as e:
        logger.warning(f"Could not parse expiry date '{expiry_string}': {str(e)}")
        return None

def is_ingredient_valid(expiry_string: str) -> bool:
    '''
    Check if an ingredient is still valid (not expired)
    
    ARGUMENT - expiry_string (str): The expiry date string from Firebase
    RETURN - bool: True if ingredient is still valid, False if expired or invalid date
    '''
    expiry_date = parse_expiry_date(expiry_string)
    if expiry_date is None:
        return False  # If we can't parse the date, consider it invalid
    
    current_date = datetime.now()
    return expiry_date.date() >= current_date.date()  # Valid if expiry is today or later

def filter_valid_ingredients(ingredients: List[Dict]) -> List[Dict]:
    '''
    Filter out expired ingredients from the list
    
    ARGUMENT - ingredients (List[Dict]): List of ingredient dictionaries from Firebase
    RETURN - List[Dict]: List of valid (non-expired) ingredients
    '''
    valid_ingredients = []
    expired_count = 0
    
    for ingredient in ingredients:
        expiry_date_str = ingredient.get('Expiry Date', '')
        if is_ingredient_valid(expiry_date_str):
            valid_ingredients.append(ingredient)
        else:
            expired_count += 1
            logger.info(f"Filtered out expired ingredient: {ingredient.get('Ingredient', 'Unknown')} - {expiry_date_str}")
    
    logger.info(f"Filtered out {expired_count} expired ingredients, {len(valid_ingredients)} valid ingredients remaining")
    return valid_ingredients

def fetch_ingredients_from_firebase() -> List[Dict]:
    '''
    Fetches ingredients from Firebase ingredient_inventory collection using the event Firebase configuration
    Only returns ingredients that haven't expired yet
    
    RETURN - List[Dict]: a list of valid (non-expired) ingredient dictionaries with their details
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
        
        all_ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            all_ingredients.append(item)
        
        logger.info(f"Fetched {len(all_ingredients)} total ingredients from Firebase")
        
        # Filter out expired ingredients
        valid_ingredients = filter_valid_ingredients(all_ingredients)
        
        # Sort valid ingredients by expiry date (closest to expire first)
        valid_ingredients.sort(key=lambda x: parse_expiry_date(x.get('Expiry Date', '')) or datetime.max)
        
        logger.info(f"Returning {len(valid_ingredients)} valid ingredients, sorted by expiry date")
        return valid_ingredients
        
    except Exception as e:
        logger.error(f"Error fetching ingredients from Firebase: {str(e)}")
        raise Exception(f"Error fetching ingredients from Firebase: {str(e)}")

def get_ingredients_by_expiry_priority(firebase_ingredients: List[Dict], max_ingredients: int = 10) -> Tuple[List[str], List[Dict]]:
    '''
    Get valid ingredients prioritized by expiry date (closest to expire first)
    Only includes ingredients that haven't expired yet
    
    ARGUMENT - 
    firebase_ingredients (List[Dict]): List of ingredient dictionaries from Firebase (should already be filtered for valid ones)
    max_ingredients (int): Maximum number of ingredients to return
    
    RETURN - Tuple[List[str], List[Dict]]: (ingredient_names, detailed_ingredient_info)
    '''
    if not firebase_ingredients:
        return [], []
    
    # Double-check that all ingredients are still valid (in case filtering wasn't done earlier)
    valid_ingredients = [ing for ing in firebase_ingredients if is_ingredient_valid(ing.get('Expiry Date', ''))]
    
    if not valid_ingredients:
        logger.warning("No valid (non-expired) ingredients found")
        return [], []
    
    # Take the first max_ingredients (already sorted by expiry date)
    priority_ingredients = valid_ingredients[:max_ingredients]
    
    # Extract ingredient names
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
    
    logger.info(f"Selected {len(ingredient_names)} priority ingredients for recipe generation")
    return ingredient_names, detailed_info

def calculate_days_until_expiry(expiry_string: str) -> int:
    '''
    Calculate days until expiry from current date
    
    ARGUMENT - expiry_string (str): The expiry date string
    RETURN - int: Number of days until expiry (0 if expires today, negative if expired)
    '''
    try:
        expiry_date = parse_expiry_date(expiry_string)
        if expiry_date is None:
            return -999  # Return a very negative number for invalid dates
        
        current_date = datetime.now()
        delta = expiry_date.date() - current_date.date()
        return delta.days
    except:
        return -999  # Return a very negative number for invalid dates

def parse_firebase_ingredients(firebase_ingredients: List[Dict]) -> List[str]:
    '''
    Parses ingredients fetched from Firebase into a simple list of ingredient names
    Only includes valid (non-expired) ingredients
    
    ARGUMENT - firebase_ingredients (List[Dict]): List of ingredient dictionaries from Firebase
    RETURN - List[str]: a list of valid ingredient names
    '''
    ingredients = []
    for item in firebase_ingredients:
        if 'Ingredient' in item and item['Ingredient']:
            # Double-check that the ingredient is still valid
            if is_ingredient_valid(item.get('Expiry Date', '')):
                ingredients.append(item['Ingredient'])
    return ingredients

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3, notes: str = "", priority_ingredients: List[Dict] = None) -> List[str]:
    '''
    Suggest recipes based on the leftover ingredients, with priority for ingredients close to expiry.

    ARGUMENT - 
    leftovers (List[str]), list of the leftover ingredients (whether via the csv file or manually entered)
    max_suggestions (int, optional): maximum number of recipe suggestions to output
    notes (str, optional): additional notes or requirements for the recipes
    priority_ingredients (List[Dict], optional): detailed info about ingredients with expiry dates

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
        
        # Add notes to the prompt if provided
        notes_text = f"\nAdditional requirements: {notes}" if notes else ""
        
        # Add priority information if available
        priority_text = ""
        if priority_ingredients:
            # Only consider ingredients that expire within the next 7 days as urgent
            urgent_ingredients = [ing for ing in priority_ingredients if 0 <= ing['days_until_expiry'] <= 7]
            if urgent_ingredients:
                urgent_names = [ing['name'] for ing in urgent_ingredients]
                urgent_details = [f"{ing['name']} (expires in {ing['days_until_expiry']} days)" for ing in urgent_ingredients]
                priority_text = f"\nIMPORTANT: Please prioritize using these ingredients as they expire soon: {', '.join(urgent_details)}"
        
        logger.info(f"Additional notes: {notes_text}")
        logger.info(f"Priority ingredients: {priority_text}")
        
        prompt = f'''
        Here are the leftover ingredients I have: {ingredients_list}.{notes_text}{priority_text}

        I need you to suggest {max_suggestions} creative and unique recipe ideas that use these ingredients to avoid any food waste.

        IMPORTANT: All ingredients provided are still fresh and valid (not expired). Please create recipes that make good use of them.

        For each recipe, provide just the recipe name. Don't include ingredients list or instructions, just keep it very simple and minimalistic in the output.
        Format each recipe as "Recipe Name"
        Keep the recipes simple and focused on using the leftover ingredients.
        If there are ingredients that expire soon, make sure to prioritize those in the recipe suggestions.
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

# ------------------ Gamification Functions ------------------

def get_firestore_db():
    """Get a Firestore client instance."""
    init_firebase()
    return firestore.client()

def generate_dynamic_quiz_questions(ingredients: List[str], num_questions: int = 5) -> List[Dict]:
    """
    Generate unique quiz questions with maximum randomization to ensure different questions every time.
    Uses multiple layers of randomization for maximum variety.

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

        # LAYER 1: Time-based randomization with microseconds
        current_time = datetime.now()
        microsecond_seed = current_time.microsecond
        timestamp_seed = int(current_time.timestamp() * 1000000) % 999999
        
        # LAYER 2: Multiple random seeds
        primary_seed = random.randint(10000, 99999)
        secondary_seed = random.randint(100000, 999999)
        tertiary_seed = random.randint(1000000, 9999999)
        
        # LAYER 3: Complex session ID with multiple entropy sources
        session_entropy = f"{timestamp_seed}_{microsecond_seed}_{primary_seed}_{secondary_seed}_{tertiary_seed}"
        session_id = f"QUIZ_{current_time.strftime('%Y%m%d_%H%M%S_%f')}_{session_entropy}"
        
        # LAYER 4: Randomized ingredient combinations
        all_possible_ingredients = ingredients + [
            "garlic", "onion", "tomato", "chicken", "beef", "pork", "fish", "rice", "pasta", 
            "potatoes", "carrots", "broccoli", "spinach", "mushrooms", "bell peppers",
            "cheese", "eggs", "milk", "butter", "olive oil", "herbs", "spices"
        ]
        
        # Create multiple random ingredient combinations
        random.shuffle(all_possible_ingredients)
        combo1 = random.sample(all_possible_ingredients, min(6, len(all_possible_ingredients)))
        random.shuffle(all_possible_ingredients)
        combo2 = random.sample(all_possible_ingredients, min(8, len(all_possible_ingredients)))
        random.shuffle(all_possible_ingredients)
        combo3 = random.sample(all_possible_ingredients, min(5, len(all_possible_ingredients)))
        
        # Randomly select which combination to use
        selected_combo = random.choice([combo1, combo2, combo3, ingredients[:8]])
        random.shuffle(selected_combo)
        
        # LAYER 5: Expanded and randomized question topics
        all_question_topics = [
            "advanced cooking techniques and molecular gastronomy",
            "food safety protocols and temperature control",
            "nutritional science and dietary benefits", 
            "culinary history and cultural origins",
            "flavor chemistry and taste combinations",
            "precision cooking temperatures and timing",
            "creative ingredient substitutions and alternatives",
            "professional kitchen tools and equipment mastery",
            "fermentation and preservation methods",
            "baking science and pastry techniques",
            "international cuisine and regional specialties",
            "food presentation and plating artistry",
            "wine and beverage pairing principles",
            "sustainable cooking and zero-waste techniques",
            "food allergies and dietary restrictions",
            "seasonal cooking and ingredient selection",
            "smoking, grilling, and barbecue techniques",
            "soup, sauce, and stock fundamentals",
            "bread making and yeast science",
            "chocolate and confectionery arts"
        ]
        
        # Randomly select and weight topics differently each time
        num_topics = random.randint(4, 8)
        selected_topics = random.sample(all_question_topics, num_topics)
        random.shuffle(selected_topics)
        
        # LAYER 6: Randomized difficulty distribution patterns
        difficulty_patterns = [
            ['easy', 'easy', 'medium', 'medium', 'hard'],
            ['easy', 'medium', 'easy', 'hard', 'medium'],
            ['medium', 'easy', 'hard', 'easy', 'medium'],
            ['easy', 'medium', 'medium', 'hard', 'easy'],
            ['hard', 'easy', 'medium', 'easy', 'hard'],
            ['medium', 'medium', 'easy', 'hard', 'easy']
        ]
        
        if num_questions <= 5:
            difficulty_distribution = random.choice(difficulty_patterns)[:num_questions]
        else:
            # For more questions, create dynamic distribution
            base_pattern = random.choice(difficulty_patterns)
            difficulty_distribution = []
            while len(difficulty_distribution) < num_questions:
                difficulty_distribution.extend(base_pattern)
            difficulty_distribution = difficulty_distribution[:num_questions]
        
        random.shuffle(difficulty_distribution)
        
        # LAYER 7: Multiple prompt templates for variety
        prompt_templates = [
            {
                "style": "scientific_approach",
                "intro": "As a culinary scientist, create fascinating quiz questions that explore the science behind cooking",
                "focus": "Focus on the chemistry, physics, and biology of cooking processes"
            },
            {
                "style": "cultural_explorer", 
                "intro": "As a world cuisine expert, generate questions about diverse cooking traditions and cultural techniques",
                "focus": "Emphasize international cooking methods, traditional techniques, and cultural food practices"
            },
            {
                "style": "professional_chef",
                "intro": "As a master chef, create challenging questions about advanced culinary techniques and professional kitchen skills",
                "focus": "Focus on professional cooking methods, advanced techniques, and industry standards"
            },
            {
                "style": "food_historian",
                "intro": "As a culinary historian, develop questions about the origins, evolution, and stories behind cooking techniques",
                "focus": "Emphasize historical context, evolution of techniques, and fascinating food facts"
            },
            {
                "style": "nutrition_expert",
                "intro": "As a nutrition scientist, create questions that blend cooking knowledge with nutritional science",
                "focus": "Focus on nutritional benefits, healthy cooking methods, and food science"
            }
        ]
        
        selected_template = random.choice(prompt_templates)
        
        # LAYER 8: Randomized question formats
        question_formats = [
            "multiple choice with surprising facts",
            "scenario-based problem solving",
            "technique identification challenges", 
            "ingredient knowledge tests",
            "cooking science explanations",
            "cultural cooking traditions",
            "professional kitchen scenarios"
        ]
        
        selected_formats = random.sample(question_formats, min(3, len(question_formats)))
        
        # LAYER 9: Dynamic complexity modifiers
        complexity_modifiers = [
            "Include lesser-known culinary secrets and professional tips",
            "Add surprising historical facts and origin stories", 
            "Focus on advanced techniques used by master chefs",
            "Include scientific explanations and food chemistry",
            "Add international perspectives and cultural variations",
            "Include modern cooking innovations and trends"
        ]
        
        selected_modifiers = random.sample(complexity_modifiers, random.randint(2, 4))
        
        ingredients_list = ", ".join(selected_combo)
        topics_list = ", ".join(selected_topics)
        formats_list = ", ".join(selected_formats)
        modifiers_list = ". ".join(selected_modifiers)
        
        # LAYER 10: Completely randomized prompt construction
        prompt = f"""
        MAXIMUM RANDOMIZATION SESSION: {session_id}
        ENTROPY SEEDS: {primary_seed} | {secondary_seed} | {tertiary_seed}
        TIMESTAMP: {current_time.isoformat()}
        MICROSECOND_SEED: {microsecond_seed}
        
        {selected_template['intro']} with these specific ingredients as inspiration: {ingredients_list}
        
        UNIQUE GENERATION REQUIREMENTS:
        - Generate {num_questions} COMPLETELY UNIQUE questions that have NEVER been asked before
        - {selected_template['focus']}
        - Use these diverse topics: {topics_list}
        - Apply these question formats: {formats_list}
        - {modifiers_list}
        
        CRITICAL UNIQUENESS FACTORS:
        1. Each question must be 100% ORIGINAL and UNPRECEDENTED
        2. Use difficulty distribution: {difficulty_distribution}
        3. Incorporate unexpected angles and surprising perspectives
        4. Avoid ANY common or typical cooking quiz questions
        5. Make each question teach something genuinely new and interesting
        6. Use creative scenarios and unique contexts
        7. Include fascinating trivia that most people don't know
        
        RANDOMIZATION DIRECTIVE: 
        This session ID {session_id} must produce questions that are COMPLETELY DIFFERENT from any previous generation.
        Use maximum creativity and originality. NO REPETITION ALLOWED.
        
        Format as JSON array:
        [
            {{
                "question": "Completely unique question text?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 0,
                "difficulty": "easy",
                "xp_reward": 10,
                "explanation": "Fascinating explanation with new information"
            }}
        ]

        XP Rewards: easy=10, medium=15, hard=20
        
        GENERATE QUESTIONS THAT ARE:
        - Absolutely unique and never seen before
        - Educational and mind-blowing
        - Varied in style and approach
        - Surprising and memorable
        - Based on real culinary knowledge but presented uniquely
        
        SESSION UNIQUENESS GUARANTEE: Questions generated with session {session_id} must be 100% different from all previous sessions.
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
                # Ensure we have the right number of questions
                questions = questions[:num_questions]
                
                # Apply the randomized difficulty distribution
                for i, question in enumerate(questions):
                    if i < len(difficulty_distribution):
                        question['difficulty'] = difficulty_distribution[i]
                        # Update XP based on difficulty
                        xp_map = {'easy': 10, 'medium': 15, 'hard': 20}
                        question['xp_reward'] = xp_map.get(question['difficulty'], 10)
                
                # FINAL RANDOMIZATION: Shuffle the final questions
                random.shuffle(questions)
                
                logger.info(f"Generated {len(questions)} MAXIMUM RANDOMIZED questions with session: {session_id}")
                logger.info(f"Used template: {selected_template['style']}, Topics: {len(selected_topics)}, Entropy: {session_entropy}")
                
                return questions
            else:
                logger.warning("Invalid question format from Gemini, using randomized fallback")
                return generate_fallback_questions(num_questions)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response text: {response_text}")
            return generate_fallback_questions(num_questions)

    except Exception as e:
        logger.error(f"Error generating maximum randomized questions: {str(e)}")
        return generate_fallback_questions(num_questions)

def generate_fallback_questions(num_questions: int = 5) -> List[Dict]:
    """
    Generate highly randomized fallback quiz questions when Gemini API is not available.
    Now with maximum randomization and variety.

    Args:
        num_questions (int): Number of questions to return

    Returns:
        List[Dict]: List of fallback quiz questions
    """
    # Expanded question pool with more variety
    all_fallback_questions = [
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
        },
        {
            "question": "What temperature should a candy thermometer read for soft ball stage?",
            "options": ["235-240°F", "250-265°F", "300-310°F", "320-335°F"],
            "correct": 0,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Soft ball stage occurs at 235-240°F, perfect for fudge and fondant."
        },
        {
            "question": "Which spice is derived from the Crocus flower?",
            "options": ["Turmeric", "Saffron", "Paprika", "Cardamom"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Saffron comes from the stigmas of the Crocus sativus flower."
        },
        {
            "question": "What does 'mise en place' mean in professional cooking?",
            "options": ["Cooking method", "Everything in its place", "Final plating", "Sauce preparation"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Mise en place means having all ingredients prepared and organized before cooking."
        },
        {
            "question": "Which cooking fat has the highest smoke point?",
            "options": ["Butter", "Olive oil", "Avocado oil", "Coconut oil"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Avocado oil has a smoke point around 520°F, higher than most cooking fats."
        },
        {
            "question": "What is the ideal pH level for bread dough?",
            "options": ["4.5-5.0", "5.5-6.0", "6.0-6.5", "7.0-7.5"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Bread dough performs best at a slightly acidic pH of 5.5-6.0."
        },
        {
            "question": "Which country is credited with inventing tempura?",
            "options": ["Japan", "Portugal", "China", "Korea"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Tempura was actually introduced to Japan by Portuguese missionaries in the 16th century."
        },
        {
            "question": "What does 'al dente' literally translate to?",
            "options": ["To the tooth", "Perfectly cooked", "Italian style", "Firm texture"],
            "correct": 0,
            "difficulty": "easy",
            "xp_reward": 10,
            "explanation": "Al dente literally means 'to the tooth' in Italian, describing the ideal pasta texture."
        },
        {
            "question": "Which enzyme in pineapple breaks down proteins?",
            "options": ["Papain", "Bromelain", "Pepsin", "Trypsin"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Bromelain is the enzyme in pineapple that breaks down proteins and tenderizes meat."
        },
        {
            "question": "What is the traditional thickening agent in gumbo?",
            "options": ["Cornstarch", "Flour", "Okra or filé powder", "Arrowroot"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Traditional gumbo is thickened with either okra or filé powder (ground sassafras leaves)."
        },
        {
            "question": "Which cooking method was invented by Benjamin Thompson (Count Rumford)?",
            "options": ["Pressure cooking", "Sous vide", "Baking", "Modern oven design"],
            "correct": 3,
            "difficulty": "hard",
            "xp_reward": 20,
            "explanation": "Count Rumford revolutionized oven design and cooking efficiency in the late 1700s."
        },
        {
            "question": "What gives black garlic its distinctive color and flavor?",
            "options": ["Charcoal coating", "Maillard reaction", "Food coloring", "Fermentation"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Black garlic gets its color and sweet flavor from the Maillard reaction during slow heating."
        },
        {
            "question": "Which salt is traditionally used in Korean cuisine?",
            "options": ["Sea salt", "Rock salt", "Bamboo salt", "Table salt"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 15,
            "explanation": "Bamboo salt (죽염) is traditional Korean salt roasted in bamboo tubes, prized for its mineral content."
        }
    ]
    
    # MAXIMUM RANDOMIZATION for fallback questions
    current_time = datetime.now()
    time_seed = int(current_time.timestamp() * 1000000) % 999999
    random.seed(time_seed)
    
    # Multiple shuffles with different seeds
    for i in range(random.randint(3, 7)):
        random.shuffle(all_fallback_questions)
    
    # Create multiple random selections and combine them
    selection1 = random.sample(all_fallback_questions, min(num_questions, len(all_fallback_questions)))
    random.shuffle(all_fallback_questions)
    selection2 = random.sample(all_fallback_questions, min(num_questions, len(all_fallback_questions)))
    
    # Randomly choose which selection to use or combine them
    if random.choice([True, False]):
        final_selection = selection1
    else:
        final_selection = selection2
    
    # Final randomization
    random.shuffle(final_selection)
    
    # Randomize difficulty distribution
    difficulties = ['easy', 'medium', 'hard']
    for question in final_selection:
        if random.random() < 0.3:  # 30% chance to randomize difficulty
            question['difficulty'] = random.choice(difficulties)
            xp_map = {'easy': 10, 'medium': 15, 'hard': 20}
            question['xp_reward'] = xp_map[question['difficulty']]
    
    logger.info(f"Generated {len(final_selection)} maximum randomized fallback questions with time seed: {time_seed}")
    return final_selection[:num_questions]

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

# ------------------ End of Combined Module ------------------

'''
How to use this module:

1. Activate a Python virtual environment:
   - On Windows: venv\Scripts\activate
   - On macOS/Linux: source venv/bin/activate

2. Install required packages:
   pip install pandas google-generativeai firebase-admin

3. Set up your Gemini API key as an environment variable:
   - On Windows: set GEMINI_API_KEY=your_api_key_here
   - On macOS/Linux: export GEMINI_API_KEY=your_api_key_here

4. Import and use in your code:
   from modules.leftover_combined import load_leftovers, suggest_recipes, generate_dynamic_quiz_questions, ...
'''
