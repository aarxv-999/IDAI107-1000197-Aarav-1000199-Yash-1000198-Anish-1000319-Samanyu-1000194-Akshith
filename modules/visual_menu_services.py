"""
Enhanced Visual Menu Services - Updated to remove cv2 dependency and add improved filtering.
"""

import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import re
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from dataclasses import dataclass
import difflib

logger = logging.getLogger(__name__)

@dataclass
class FilterCriteria:
    """Enhanced filter criteria with scoring"""
    dietary_preferences: List[str]
    cuisine_types: List[str]
    spice_levels: List[str]
    price_ranges: List[str]
    cooking_methods: List[str]
    meal_types: List[str]
    allergen_free: List[str]
    nutritional_focus: List[str]
    ingredient_preferences: List[str]
    texture_preferences: List[str]

class EnhancedVisualSearchEngine:
    """Enhanced visual search engine with improved filtering accuracy"""
    
    def __init__(self):
        self.cuisine_keywords = {
            'indian': ['curry', 'masala', 'biryani', 'dal', 'roti', 'naan', 'tandoor', 'samosa', 'dosa', 'idli'],
            'chinese': ['noodles', 'fried rice', 'dumpling', 'wonton', 'chow mein', 'spring roll', 'szechuan'],
            'italian': ['pasta', 'pizza', 'risotto', 'lasagna', 'spaghetti', 'marinara', 'pesto', 'carbonara'],
            'mexican': ['taco', 'burrito', 'quesadilla', 'salsa', 'guacamole', 'enchilada', 'fajita'],
            'thai': ['pad thai', 'tom yum', 'green curry', 'red curry', 'coconut', 'lemongrass'],
            'japanese': ['sushi', 'ramen', 'tempura', 'miso', 'teriyaki', 'udon', 'soba'],
            'mediterranean': ['hummus', 'falafel', 'olive', 'tzatziki', 'pita', 'kebab']
        }
        
        self.spice_indicators = {
            'mild': ['mild', 'gentle', 'light', 'subtle', 'delicate'],
            'medium': ['medium', 'moderate', 'balanced', 'flavorful'],
            'hot': ['spicy', 'hot', 'fiery', 'chili', 'pepper', 'jalapeño'],
            'very_hot': ['very hot', 'extremely spicy', 'ghost pepper', 'habanero', 'carolina reaper']
        }
        
        self.dietary_indicators = {
            'vegetarian': ['vegetarian', 'veggie', 'no meat', 'plant-based'],
            'vegan': ['vegan', 'dairy-free', 'no animal products', 'plant-only'],
            'gluten-free': ['gluten-free', 'no gluten', 'celiac-friendly'],
            'keto': ['keto', 'low-carb', 'ketogenic', 'high-fat'],
            'halal': ['halal', 'islamic', 'no pork', 'halal-certified'],
            'jain': ['jain', 'no onion', 'no garlic', 'jain-friendly']
        }
        
        self.cooking_method_keywords = {
            'grilled': ['grilled', 'barbecue', 'bbq', 'charcoal', 'flame-grilled'],
            'fried': ['fried', 'deep-fried', 'crispy', 'battered'],
            'steamed': ['steamed', 'steam-cooked', 'healthy cooking'],
            'baked': ['baked', 'oven-cooked', 'roasted'],
            'sautéed': ['sautéed', 'pan-fried', 'stir-fried'],
            'boiled': ['boiled', 'poached', 'simmered']
        }

def get_visual_firebase_db():
    """Get Firestore client for visual search"""
    try:
        # Try to get existing app first
        try:
            app = firebase_admin.get_app()
            return firestore.client(app=app)
        except ValueError:
            # If no default app exists, try to get event_app
            try:
                app = firebase_admin.get_app(name='event_app')
                return firestore.client(app=app)
            except ValueError:
                # Initialize default app if none exists
                if not firebase_admin._apps:
                    cred = firebase_admin.credentials.Certificate({
                        "type": st.secrets["firebase"]["type"],
                        "project_id": st.secrets["firebase"]["project_id"],
                        "private_key_id": st.secrets["firebase"]["private_key_id"],
                        "private_key": st.secrets["firebase"]["private_key"].replace('\\n', '\n'),
                        "client_email": st.secrets["firebase"]["client_email"],
                        "client_id": st.secrets["firebase"]["client_id"],
                        "auth_uri": st.secrets["firebase"]["auth_uri"],
                        "token_uri": st.secrets["firebase"]["token_uri"],
                        "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
                        "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
                    })
                    firebase_admin.initialize_app(cred)
                return firestore.client()
    except Exception as e:
        logger.error(f"Error getting visual Firebase DB: {str(e)}")
        return None

def configure_visual_gemini():
    """Configure Gemini AI for visual analysis"""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found")
        
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.error(f"Error configuring Gemini: {str(e)}")
        return None

def analyze_food_image_with_gemini(image: Image.Image) -> Dict[str, Any]:
    """Enhanced image analysis with detailed food recognition"""
    try:
        model = configure_visual_gemini()
        if not model:
            return {"error": "AI model not available"}
        
        prompt = """Analyze this food image in detail and return a JSON response with the following structure:

{
  "dish_name": "Primary dish name",
  "confidence": 0.95,
  "cuisine_type": "Indian/Chinese/Italian/etc",
  "dietary_info": ["Vegetarian", "Gluten-Free", "etc"],
  "spice_level": "Mild/Medium/Hot/Very Hot",
  "cooking_method": "Grilled/Fried/Steamed/etc",
  "main_ingredients": ["ingredient1", "ingredient2"],
  "allergens": ["nuts", "dairy", "gluten"],
  "meal_type": "Breakfast/Lunch/Dinner/Snack",
  "texture": "Crispy/Soft/Chewy/etc",
  "color_profile": ["red", "brown", "green"],
  "estimated_price_range": "Budget/Mid-range/Premium",
  "nutritional_focus": "High-protein/Low-carb/etc",
  "serving_style": "Individual/Family/Sharing",
  "garnish_elements": ["herbs", "sauce", "etc"],
  "presentation_style": "Casual/Fine-dining/Street-food"
}

Be very specific and accurate. If uncertain about any field, use "Unknown" or empty array."""

        response = model.generate_content([prompt, image])
        
        # Extract JSON from response
        response_text = response.text.strip()
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            analysis = json.loads(json_match.group())
            
            # Add timestamp and processing info
            analysis['timestamp'] = datetime.now().isoformat()
            analysis['processing_method'] = 'enhanced_gemini_analysis'
            
            return analysis
        else:
            logger.warning("No JSON found in Gemini response")
            return {"error": "Failed to parse AI response"}
            
    except Exception as e:
        logger.error(f"Error in image analysis: {str(e)}")
        return {"error": str(e)}

def calculate_filter_match_score(dish: Dict, filters: FilterCriteria, analysis: Dict) -> Tuple[float, Dict[str, float]]:
    """Calculate detailed match score for filters with breakdown"""
    scores = {}
    total_weight = 0
    weighted_score = 0
    
    # Dietary preferences (weight: 25%)
    if filters.dietary_preferences:
        dietary_score = calculate_dietary_match(dish, analysis, filters.dietary_preferences)
        scores['dietary'] = dietary_score
        weighted_score += dietary_score * 0.25
        total_weight += 0.25
    
    # Cuisine type (weight: 20%)
    if filters.cuisine_types:
        cuisine_score = calculate_cuisine_match(dish, analysis, filters.cuisine_types)
        scores['cuisine'] = cuisine_score
        weighted_score += cuisine_score * 0.20
        total_weight += 0.20
    
    # Spice level (weight: 15%)
    if filters.spice_levels:
        spice_score = calculate_spice_match(dish, analysis, filters.spice_levels)
        scores['spice'] = spice_score
        weighted_score += spice_score * 0.15
        total_weight += 0.15
    
    # Cooking method (weight: 10%)
    if filters.cooking_methods:
        cooking_score = calculate_cooking_method_match(dish, analysis, filters.cooking_methods)
        scores['cooking_method'] = cooking_score
        weighted_score += cooking_score * 0.10
        total_weight += 0.10
    
    # Ingredients (weight: 15%)
    if filters.ingredient_preferences:
        ingredient_score = calculate_ingredient_match(dish, analysis, filters.ingredient_preferences)
        scores['ingredients'] = ingredient_score
        weighted_score += ingredient_score * 0.15
        total_weight += 0.15
    
    # Allergen-free (weight: 10%)
    if filters.allergen_free:
        allergen_score = calculate_allergen_match(dish, analysis, filters.allergen_free)
        scores['allergen_free'] = allergen_score
        weighted_score += allergen_score * 0.10
        total_weight += 0.10
    
    # Meal type (weight: 5%)
    if filters.meal_types:
        meal_score = calculate_meal_type_match(dish, analysis, filters.meal_types)
        scores['meal_type'] = meal_score
        weighted_score += meal_score * 0.05
        total_weight += 0.05
    
    # Calculate final score
    final_score = weighted_score / total_weight if total_weight > 0 else 0
    
    return final_score, scores

def calculate_dietary_match(dish: Dict, analysis: Dict, preferences: List[str]) -> float:
    """Calculate dietary preference match with fuzzy matching"""
    dish_dietary = []
    
    # Extract from dish data
    if 'diet' in dish:
        if isinstance(dish['diet'], list):
            dish_dietary.extend([d.lower() for d in dish['diet']])
        else:
            dish_dietary.append(str(dish['diet']).lower())
    
    # Extract from analysis
    if 'dietary_info' in analysis:
        dish_dietary.extend([d.lower() for d in analysis['dietary_info']])
    
    # Check description for dietary keywords
    description = str(dish.get('description', '')).lower()
    name = str(dish.get('name', '')).lower()
    
    search_engine = EnhancedVisualSearchEngine()
    
    matches = 0
    total_preferences = len(preferences)
    
    for preference in preferences:
        pref_lower = preference.lower()
        
        # Direct match
        if pref_lower in dish_dietary:
            matches += 1
            continue
        
        # Keyword match in description/name
        keywords = search_engine.dietary_indicators.get(pref_lower, [pref_lower])
        if any(keyword in description or keyword in name for keyword in keywords):
            matches += 0.8  # Slightly lower score for keyword match
            continue
        
        # Fuzzy match
        for dish_diet in dish_dietary:
            similarity = difflib.SequenceMatcher(None, pref_lower, dish_diet).ratio()
            if similarity > 0.8:
                matches += similarity * 0.6  # Lower score for fuzzy match
                break
    
    return min(matches / total_preferences, 1.0) if total_preferences > 0 else 1.0

def calculate_cuisine_match(dish: Dict, analysis: Dict, cuisine_types: List[str]) -> float:
    """Calculate cuisine type match with enhanced accuracy"""
    dish_cuisine = str(dish.get('cuisine', '')).lower()
    analysis_cuisine = str(analysis.get('cuisine_type', '')).lower()
    
    description = str(dish.get('description', '')).lower()
    name = str(dish.get('name', '')).lower()
    ingredients = dish.get('ingredients', [])
    
    search_engine = EnhancedVisualSearchEngine()
    
    best_match = 0
    
    for cuisine_type in cuisine_types:
        cuisine_lower = cuisine_type.lower()
        score = 0
        
        # Direct match
        if cuisine_lower in dish_cuisine or cuisine_lower in analysis_cuisine:
            score = 1.0
        
        # Keyword-based matching
        elif cuisine_lower in search_engine.cuisine_keywords:
            keywords = search_engine.cuisine_keywords[cuisine_lower]
            keyword_matches = 0
            
            # Check in name, description, and ingredients
            for keyword in keywords:
                if keyword in name:
                    keyword_matches += 2  # Higher weight for name
                elif keyword in description:
                    keyword_matches += 1
                elif isinstance(ingredients, list):
                    for ingredient in ingredients:
                        if keyword in str(ingredient).lower():
                            keyword_matches += 0.5
            
            score = min(keyword_matches / len(keywords), 1.0)
        
        # Fuzzy matching
        else:
            similarity1 = difflib.SequenceMatcher(None, cuisine_lower, dish_cuisine).ratio()
            similarity2 = difflib.SequenceMatcher(None, cuisine_lower, analysis_cuisine).ratio()
            score = max(similarity1, similarity2) * 0.7  # Lower weight for fuzzy match
        
        best_match = max(best_match, score)
    
    return best_match

def calculate_spice_match(dish: Dict, analysis: Dict, spice_levels: List[str]) -> float:
    """Calculate spice level match"""
    dish_spice = str(analysis.get('spice_level', '')).lower()
    description = str(dish.get('description', '')).lower()
    name = str(dish.get('name', '')).lower()
    
    search_engine = EnhancedVisualSearchEngine()
    
    best_match = 0
    
    for spice_level in spice_levels:
        spice_lower = spice_level.lower()
        score = 0
        
        # Direct match
        if spice_lower in dish_spice:
            score = 1.0
        
        # Keyword matching
        elif spice_lower in search_engine.spice_indicators:
            keywords = search_engine.spice_indicators[spice_lower]
            if any(keyword in description or keyword in name for keyword in keywords):
                score = 0.8
        
        # Fuzzy match
        else:
            similarity = difflib.SequenceMatcher(None, spice_lower, dish_spice).ratio()
            if similarity > 0.7:
                score = similarity * 0.6
        
        best_match = max(best_match, score)
    
    return best_match

def calculate_cooking_method_match(dish: Dict, analysis: Dict, cooking_methods: List[str]) -> float:
    """Calculate cooking method match"""
    analysis_method = str(analysis.get('cooking_method', '')).lower()
    description = str(dish.get('description', '')).lower()
    name = str(dish.get('name', '')).lower()
    
    search_engine = EnhancedVisualSearchEngine()
    
    best_match = 0
    
    for method in cooking_methods:
        method_lower = method.lower()
        score = 0
        
        # Direct match
        if method_lower in analysis_method:
            score = 1.0
        
        # Keyword matching
        elif method_lower in search_engine.cooking_method_keywords:
            keywords = search_engine.cooking_method_keywords[method_lower]
            if any(keyword in description or keyword in name for keyword in keywords):
                score = 0.8
        
        # Simple substring match
        elif method_lower in description or method_lower in name:
            score = 0.6
        
        best_match = max(best_match, score)
    
    return best_match

def calculate_ingredient_match(dish: Dict, analysis: Dict, ingredient_preferences: List[str]) -> float:
    """Calculate ingredient preference match"""
    dish_ingredients = dish.get('ingredients', [])
    analysis_ingredients = analysis.get('main_ingredients', [])
    
    all_ingredients = []
    
    if isinstance(dish_ingredients, list):
        all_ingredients.extend([str(ing).lower() for ing in dish_ingredients])
    elif isinstance(dish_ingredients, str):
        all_ingredients.extend([ing.strip().lower() for ing in dish_ingredients.split(',')])
    
    all_ingredients.extend([str(ing).lower() for ing in analysis_ingredients])
    
    description = str(dish.get('description', '')).lower()
    name = str(dish.get('name', '')).lower()
    
    matches = 0
    total_preferences = len(ingredient_preferences)
    
    for preference in ingredient_preferences:
        pref_lower = preference.lower()
        
        # Direct ingredient match
        if any(pref_lower in ingredient for ingredient in all_ingredients):
            matches += 1
            continue
        
        # Description/name match
        if pref_lower in description or pref_lower in name:
            matches += 0.7
            continue
        
        # Fuzzy match with ingredients
        for ingredient in all_ingredients:
            similarity = difflib.SequenceMatcher(None, pref_lower, ingredient).ratio()
            if similarity > 0.8:
                matches += similarity * 0.5
                break
    
    return min(matches / total_preferences, 1.0) if total_preferences > 0 else 1.0

def calculate_allergen_match(dish: Dict, analysis: Dict, allergen_free: List[str]) -> float:
    """Calculate allergen-free match (higher score = fewer allergens)"""
    analysis_allergens = [str(a).lower() for a in analysis.get('allergens', [])]
    description = str(dish.get('description', '')).lower()
    
    violations = 0
    total_allergens = len(allergen_free)
    
    for allergen in allergen_free:
        allergen_lower = allergen.lower()
        
        # Check if allergen is present
        if allergen_lower in analysis_allergens:
            violations += 1
        elif allergen_lower in description:
            violations += 0.5  # Partial violation for description mention
    
    # Return score (1.0 = no violations, 0.0 = all allergens present)
    return max(0, 1.0 - (violations / total_allergens)) if total_allergens > 0 else 1.0

def calculate_meal_type_match(dish: Dict, analysis: Dict, meal_types: List[str]) -> float:
    """Calculate meal type match"""
    analysis_meal = str(analysis.get('meal_type', '')).lower()
    category = str(dish.get('category', '')).lower()
    
    best_match = 0
    
    for meal_type in meal_types:
        meal_lower = meal_type.lower()
        
        if meal_lower in analysis_meal or meal_lower in category:
            best_match = max(best_match, 1.0)
        else:
            # Fuzzy match
            similarity1 = difflib.SequenceMatcher(None, meal_lower, analysis_meal).ratio()
            similarity2 = difflib.SequenceMatcher(None, meal_lower, category).ratio()
            best_match = max(best_match, max(similarity1, similarity2) * 0.7)
    
    return best_match

def search_similar_dishes(image: Image.Image, custom_filters=None, limit: int = 10) -> List[Dict]:
    """Enhanced visual search with improved filtering accuracy"""
    try:
        # Convert custom_filters to FilterCriteria if needed
        if custom_filters is None:
            filters = FilterCriteria([], [], [], [], [], [], [], [], [], [])
        elif isinstance(custom_filters, dict):
            filters = FilterCriteria(
                dietary_preferences=custom_filters.get('dietary_preferences', []),
                cuisine_types=custom_filters.get('cuisine_types', []),
                spice_levels=custom_filters.get('spice_levels', []),
                price_ranges=custom_filters.get('price_ranges', []),
                cooking_methods=custom_filters.get('cooking_methods', []),
                meal_types=custom_filters.get('meal_types', []),
                allergen_free=custom_filters.get('allergen_free', []),
                nutritional_focus=custom_filters.get('nutritional_focus', []),
                ingredient_preferences=custom_filters.get('ingredient_preferences', []),
                texture_preferences=custom_filters.get('texture_preferences', [])
            )
        else:
            filters = custom_filters
        
        # Analyze the uploaded image
        analysis = analyze_food_image_with_gemini(image)
        
        if "error" in analysis:
            logger.error(f"Image analysis failed: {analysis['error']}")
            return []
        
        # Get menu items from database
        db = get_visual_firebase_db()
        if not db:
            logger.error("Database connection failed")
            return []
        
        menu_docs = db.collection('menu').stream()
        all_dishes = [doc.to_dict() for doc in menu_docs]
        
        if not all_dishes:
            logger.warning("No dishes found in database")
            return []
        
        # Calculate match scores for each dish
        scored_dishes = []
        
        for dish in all_dishes:
            match_score, score_breakdown = calculate_filter_match_score(dish, filters, analysis)
            
            if match_score > 0.1:  # Only include dishes with some relevance
                dish_with_score = dish.copy()
                dish_with_score['match_score'] = match_score
                dish_with_score['score_breakdown'] = score_breakdown
                dish_with_score['analysis_match'] = analysis
                scored_dishes.append(dish_with_score)
        
        # Sort by match score (highest first)
        scored_dishes.sort(key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"Found {len(scored_dishes)} matching dishes out of {len(all_dishes)} total")
        
        return scored_dishes[:limit]
        
    except Exception as e:
        logger.error(f"Error in visual search: {str(e)}")
        return []

def get_smart_filter_suggestions(analysis: Dict) -> Dict[str, List[str]]:
    """Generate smart filter suggestions based on image analysis"""
    suggestions = {
        'dietary_preferences': [],
        'cuisine_types': [],
        'spice_levels': [],
        'cooking_methods': [],
        'meal_types': [],
        'allergen_free': [],
        'ingredient_preferences': []
    }
    
    try:
        # Suggest based on analysis
        if 'dietary_info' in analysis:
            suggestions['dietary_preferences'] = analysis['dietary_info'][:3]
        
        if 'cuisine_type' in analysis and analysis['cuisine_type'] != 'Unknown':
            suggestions['cuisine_types'] = [analysis['cuisine_type']]
        
        if 'spice_level' in analysis and analysis['spice_level'] != 'Unknown':
            suggestions['spice_levels'] = [analysis['spice_level']]
        
        if 'cooking_method' in analysis and analysis['cooking_method'] != 'Unknown':
            suggestions['cooking_methods'] = [analysis['cooking_method']]
        
        if 'meal_type' in analysis and analysis['meal_type'] != 'Unknown':
            suggestions['meal_types'] = [analysis['meal_type']]
        
        if 'main_ingredients' in analysis:
            suggestions['ingredient_preferences'] = analysis['main_ingredients'][:4]
        
        # Suggest allergen-free options based on detected allergens
        if 'allergens' in analysis and analysis['allergens']:
            suggestions['allergen_free'] = analysis['allergens'][:3]
    
    except Exception as e:
        logger.error(f"Error generating smart suggestions: {str(e)}")
    
    return suggestions
