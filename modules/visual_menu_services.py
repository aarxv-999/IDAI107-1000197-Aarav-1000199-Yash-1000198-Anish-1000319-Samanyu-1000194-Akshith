import streamlit as st
import google.generativeai as genai
from google.cloud import vision
from google.oauth2 import service_account
import firebase_admin
from firebase_admin import firestore
from PIL import Image, ImageEnhance
import io
import time
import logging
from datetime import datetime, timedelta
from fuzzywuzzy import fuzz
import pandas as pd

logger = logging.getLogger(__name__)

def get_visual_menu_firebase_db():
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting visual menu Firebase DB: {str(e)}")
        st.error("Failed to connect to database. Please check your Firebase configuration.")
        return None

def get_main_firebase_db():
    try:
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting main Firebase DB: {str(e)}")
        return None

def configure_vision_api():
    try:
        if "GOOGLE_CLOUD_VISION_CREDENTIALS" not in st.secrets:
            logger.warning("Google Cloud Vision API credentials not found in secrets")
            return None
            
        vision_credentials_dict = dict(st.secrets["GOOGLE_CLOUD_VISION_CREDENTIALS"])
        vision_credentials = service_account.Credentials.from_service_account_info(vision_credentials_dict)
        return vision.ImageAnnotatorClient(credentials=vision_credentials)
    except Exception as e:
        logger.error(f"Error configuring Vision API: {str(e)}")
        return None

def configure_visual_gemini_ai():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in Streamlit secrets")
        
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.error(f"Error configuring Gemini AI for visual menu: {str(e)}")
        st.error("Failed to configure AI service. Please check your API key configuration.")
        return None

ALLERGY_MAPPING = {
    "Nut-Free": ["peanuts", "almonds", "walnuts", "cashews", "hazelnuts", "peanut butter", "almond milk", "almond extract", "nut"],
    "Shellfish-Free": ["shrimp", "crab", "lobster", "mussels", "clams", "prawns", "shellfish"],
    "Soy-Free": ["soy", "tofu", "soybean", "edamame", "soy sauce", "soy milk", "tamari"],
    "Dairy-Free": ["milk", "cheese", "yogurt", "butter", "cream", "whey", "casein", "lactose"],
    "Veg": ["chicken", "beef", "pork", "lamb", "fish", "turkey", "duck", "venison", "meat"],
    "Non-Veg": [],
    "Gluten-Free": ["wheat", "barley", "rye", "malt", "flour", "bread", "pasta"],
    "Vegan": ["milk", "cheese", "yogurt", "butter", "cream", "egg", "honey", "gelatin", "meat", "fish", "chicken", "beef", "pork"]
}

@st.cache_data(ttl=300)
def fetch_menu_items(_db):
    try:
        if not _db:
            return []
        menu_docs = _db.collection("menu").stream()
        return [doc.to_dict() | {"id": doc.id} for doc in menu_docs]
    except Exception as e:
        logger.error(f"Error fetching menu items: {str(e)}")
        return []

@st.cache_data(ttl=300)
def fetch_order_history(_db, user_id):
    try:
        if not _db or not user_id:
            return []
        orders = _db.collection("orders").where("user_id", "==", user_id).stream()
        return [order.to_dict() | {"id": order.id} for order in orders]
    except Exception as e:
        logger.error(f"Error fetching order history: {str(e)}")
        return []

@st.cache_data(ttl=60)
def fetch_challenge_entries(_db):
    try:
        if not _db:
            return []
        challenges = _db.collection("visual_challenges").stream()
        return [doc.to_dict() | {"id": doc.id} for doc in challenges]
    except Exception as e:
        logger.error(f"Error fetching challenge entries: {str(e)}")
        return []

def calculate_challenge_score(entry):
    base_score = entry.get("views", 0) + entry.get("likes", 0) * 2 + entry.get("orders", 0) * 3
    if entry.get("trendy"): 
        base_score += 5
    if entry.get("diet_match"): 
        base_score += 3
    return base_score

def preprocess_image(uploaded_file):
    try:
        image = Image.open(uploaded_file).convert("RGB")
        
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)
        
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG")
        content = img_bytes.getvalue()
        
        return image, content
    except Exception as e:
        logger.error(f"Error preprocessing image: {str(e)}")
        return None, None

def analyze_image_with_vision(vision_client, content):
    try:
        if not vision_client:
            return [], [], [], []
            
        vision_image = vision.Image(content=content)
        
        label_response = vision_client.label_detection(image=vision_image)
        labels = [(label.description, label.score) for label in label_response.label_annotations if label.score > 0.7]
        
        obj_response = vision_client.object_localization(image=vision_image)
        objects = [(obj.name, obj.score) for obj in obj_response.localized_object_annotations]
        
        text_response = vision_client.text_detection(image=vision_image)
        texts = [text.description.lower().strip() for text in text_response.text_annotations[1:] if text.description.strip()]
        
        properties_response = vision_client.image_properties(image=vision_image)
        dominant_colors = properties_response.image_properties_annotation.dominant_colors.colors
        style_indicators = [label[0].lower() for label in labels if "style" in label[0].lower() or "plating" in label[0].lower()]
        
        if not style_indicators:
            style_indicators.append("modern" if any(color.color.red > 200 or color.color.green > 200 for color in dominant_colors) else "classic")
        
        return labels, objects, texts, style_indicators
        
    except Exception as e:
        logger.error(f"Error analyzing image with Vision API: {str(e)}")
        return [], [], [], []

def find_matching_dishes(menu_items, combined_labels):
    try:
        matching_dishes = []
        
        for item in menu_items:
            item_text = ' '.join([
                item.get('name', '').lower(),
                item.get('description', '').lower(),
                ' '.join(item.get('ingredients', [])).lower(),
                ' '.join(item.get('diet', [])).lower() if isinstance(item.get('diet'), list) else str(item.get('diet', '')).lower()
            ])
            
            score = max(fuzz.partial_ratio(label, item_text) for label in combined_labels) if combined_labels else 0
            
            if score > 60:
                matching_dishes.append({
                    "name": item.get('name', 'Unknown'),
                    "score": score,
                    "description": item.get('description', ''),
                    "ingredients": item.get('ingredients', []),
                    "dietary_tags": item.get('diet', []) if isinstance(item.get('diet'), list) else [item.get('diet', '')] if item.get('diet') else [],
                    "id": item.get('id', '')
                })
        
        return sorted(matching_dishes, key=lambda x: x['score'], reverse=True)[:5]
        
    except Exception as e:
        logger.error(f"Error finding matching dishes: {str(e)}")
        return []

def generate_ai_dish_analysis(model, labels, objects, texts, style_indicators, user_allergies, menu_text):
    try:
        if not model:
            return "AI analysis unavailable - Gemini API not configured"
            
        user_profile = f"Restrictions & Allergies: {', '.join(user_allergies) if user_allergies else 'None'}"
        
        prompt = f"""
        Analyze the following food image data:
        - Image labels and objects: {labels + objects}
        - Detected text: {texts if texts else 'None'}
        - Plating style: {', '.join(style_indicators) if style_indicators else 'Not identified'}
        - User profile: {user_profile}
        - Available menu items: {menu_text}
        - Event context: Current season with focus on fresh, seasonal dishes.

        Tasks:
        1. Predict the most likely dish from the menu that matches the image
        2. If no exact match, suggest the closest dish and explain why
        3. Recommend 3 additional relevant dishes that align with detected characteristics and user restrictions
        4. For pasta dishes, suggest variations like alternative noodles or sauces
        5. For desserts, suggest healthier alternatives

        Format the response as:
        **Predicted Dish**: [Dish Name]
        **Explanation**: [Reasoning]
        **Related Menu Items**:
        - [Dish Name]: [Description]
        **Additional Recommendations**:
        - [Dish Name]: [Reason]
        **Variations (if applicable)**:
        - [Variation]: [Description]
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error generating AI dish analysis: {str(e)}")
        return f"AI analysis error: {str(e)}"

def generate_personalized_recommendations(model, user_allergies, order_history, menu_text):
    try:
        if not model:
            return "AI recommendations unavailable - Gemini API not configured"
            
        user_profile = f"Restrictions & Allergies: {', '.join(user_allergies) if user_allergies else 'None'}"
        order_summary = "\n".join([f"- {order['dish_name']} (Ordered: {order.get('timestamp', 'Unknown')})" for order in order_history]) if order_history else "No order history available."
        popular_trends = "Current popular trends include plant-based proteins, fermented foods, and low-carb options."

        prompt = f"""
        Given the following information:
        - User profile: {user_profile}
        - Order history: {order_summary}
        - Popular trends: {popular_trends}
        - Available menu: {menu_text}

        Tasks:
        1. Recommend 5 dishes that align with user's restrictions, past orders, and current trends
        2. For pasta dishes, suggest variations with alternative noodles or sauces
        3. For desserts, suggest healthier alternatives
        4. Explain why each recommendation fits the user's profile

        Format the response as:
        **Recommended Dishes**:
        - [Dish Name]: [Reason for recommendation]
        **Pasta Variations (if applicable)**:
        - [Variation]: [Description]
        **Dessert Alternatives (if applicable)**:
        - [Alternative]: [Description]
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error generating personalized recommendations: {str(e)}")
        return f"Recommendation error: {str(e)}"

def filter_menu_by_allergies(menu_items, selected_allergies):
    try:
        filtered_menu = []
        debug_info = []
        
        for item in menu_items:
            ingredients = [ing.lower() for ing in item.get("ingredients", [])]
            restriction_match = True
            
            for restriction in selected_allergies:
                if restriction == "Non-Veg":
                    non_veg_ingredients = ALLERGY_MAPPING["Veg"]
                    has_non_veg = any(
                        any(non_veg_ing.lower() in ing.split() for ing in ingredients)
                        for non_veg_ing in non_veg_ingredients
                    )
                    if not has_non_veg:
                        restriction_match = False
                        debug_info.append(f"Item '{item.get('name', 'Unknown')}' filtered out: Does not contain non-veg ingredients")
                    continue

                items_to_exclude = ALLERGY_MAPPING.get(restriction, [])
                for item_to_exclude in items_to_exclude:
                    for ing in ingredients:
                        words = ing.split()
                        if item_to_exclude.lower() in words:
                            restriction_match = False
                            debug_info.append(f"Item '{item.get('name', 'Unknown')}' filtered out: Contains '{item_to_exclude}' (from restriction '{restriction}')")
                            break
                    if not restriction_match:
                        break
                if not restriction_match:
                    break

            if restriction_match:
                filtered_menu.append(item)
        
        return filtered_menu, debug_info
        
    except Exception as e:
        logger.error(f"Error filtering menu by allergies: {str(e)}")
        return menu_items, [f"Filter error: {str(e)}"]

def save_challenge_entry(db, staff_name, dish_name, ingredients, plating_style, trendy, diet_match):
    try:
        if not db:
            return False, "Database connection failed"
            
        challenge_data = {
            "staff": staff_name,
            "dish": dish_name,
            "ingredients": [i.strip() for i in ingredients.split(",") if i.strip()],
            "style": plating_style,
            "trendy": trendy,
            "diet_match": diet_match,
            "timestamp": time.time(),
            "created_at": datetime.now().isoformat(),
            "views": 0,
            "likes": 0,
            "orders": 0
        }
        
        db.collection("visual_challenges").add(challenge_data)
        logger.info(f"Saved challenge entry for {staff_name}: {dish_name}")
        return True, "Challenge entry saved successfully"
        
    except Exception as e:
        logger.error(f"Error saving challenge entry: {str(e)}")
        return False, f"Error saving challenge: {str(e)}"

def update_challenge_interaction(db, challenge_id, interaction_type):
    try:
        if not db:
            return False
            
        doc_ref = db.collection("visual_challenges").document(challenge_id)
        doc = doc_ref.get()
        
        if doc.exists:
            current_data = doc.to_dict()
            current_count = current_data.get(interaction_type, 0)
            doc_ref.update({interaction_type: current_count + 1})
            
            logger.info(f"Updated {interaction_type} for challenge {challenge_id}")
            return True
        else:
            logger.warning(f"Challenge {challenge_id} not found")
            return False
            
    except Exception as e:
        logger.error(f"Error updating challenge interaction: {str(e)}")
        return False

def save_order(db, user_id, dish_name, price=0.0):
    try:
        if not db:
            return False
            
        order_data = {
            "user_id": user_id,
            "dish_name": dish_name,
            "price": price,
            "timestamp": time.time(),
            "created_at": datetime.now().isoformat(),
            "status": "completed"
        }
        
        db.collection("orders").add(order_data)
        logger.info(f"Saved order for user {user_id}: {dish_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving order: {str(e)}")
        return False

def award_visual_menu_xp(user_id, xp_amount, activity_type):
    try:
        main_db = get_main_firebase_db()
        if not main_db:
            logger.error("Could not connect to main Firebase for XP award")
            return 0
        
        user_ref = main_db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            current_stats = user_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            new_xp = current_xp + xp_amount
            new_level = (new_xp // 100) + 1
            
            user_ref.update({
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Awarded {xp_amount} XP to user {user_id} for {activity_type}")
        else:
            user_ref.set({
                'user_id': user_id,
                'total_xp': xp_amount,
                'level': 1,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Created new user stats for {user_id} with {xp_amount} XP")
        
        return xp_amount
        
    except Exception as e:
        logger.error(f"Error awarding visual menu XP: {str(e)}")
        return 0

def reset_weekly_leaderboard(db):
    try:
        if not db:
            return False
            
        current_week = datetime.now().strftime("%Y-W%U")
        challenges = db.collection("visual_challenges").stream()
        
        for challenge in challenges:
            challenge_data = challenge.to_dict()
            challenge_data['week'] = current_week
            challenge_data['archived_at'] = datetime.now().isoformat()
            
            db.collection("challenge_archive").add(challenge_data)
            
            challenge.reference.update({
                'views': 0,
                'likes': 0,
                'orders': 0
            })
        
        logger.info(f"Reset weekly leaderboard for week {current_week}")
        return True
        
    except Exception as e:
        logger.error(f"Error resetting weekly leaderboard: {str(e)}")
        return False
