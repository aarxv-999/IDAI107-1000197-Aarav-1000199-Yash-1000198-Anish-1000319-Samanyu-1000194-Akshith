"""
Promotion Campaign Services module for the Smart Restaurant Menu Management App.
Handles campaign generation, submission, and AI scoring using event_firebase configuration.
Updated with likes/dislikes functionality and user_id integration.
"""

import streamlit as st
import google.generativeai as genai
import re
import json
import pandas as pd
from datetime import datetime
from dateutil import parser
import firebase_admin
from firebase_admin import firestore
import logging
import time

logger = logging.getLogger(__name__)

def get_promotion_firebase_db():
    """Get Firestore client for promotion services using event_firebase configuration"""
    try:
        # Use the event Firebase app
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            # Initialize event Firebase if not already done
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting promotion Firebase DB: {str(e)}")
        st.error("Failed to connect to database. Please check your Firebase configuration.")
        return None

def get_main_firebase_db():
    """Get Firestore client for main Firebase (for gamification stats)"""
    try:
        # Use the main Firebase app (default)
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            # Initialize main Firebase if not already done
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting main Firebase DB: {str(e)}")
        st.error("Failed to connect to main database. Please check your Firebase configuration.")
        return None

def configure_promotion_gemini_ai():
    """Configure Gemini AI using Streamlit secrets"""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in Streamlit secrets")
        
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.error(f"Error configuring Gemini AI for promotions: {str(e)}")
        st.error("Failed to configure AI service. Please check your API key configuration.")
        return None

def parse_quantity(qty_string):
    """Parse quantity like '2 kg' or '500 ml'"""
    match = re.match(r"([\d\.]+)\s*(\w+)", str(qty_string).lower())
    return (float(match.group(1)), match.group(2)) if match else (None, None)

def standardize_quantity(quantity, unit):
    """Standardize to grams/ml or pieces"""
    if unit == 'kg': 
        return quantity * 1000
    if unit == 'g': 
        return quantity
    if unit == 'l': 
        return quantity * 1000
    if unit == 'ml': 
        return quantity
    if unit in ['pcs', 'piece', 'pieces']: 
        return quantity
    return None

def filter_valid_ingredients(db):
    """Process and filter inventory data to get available ingredients"""
    try:
        inventory_data = [doc.to_dict() for doc in db.collection('ingredient_inventory').stream()]
        if not inventory_data:
            logger.warning("No inventory data found")
            return []
            
        inventory_df = pd.DataFrame(inventory_data)
        today = datetime.now()
        
        # Parse expiry dates
        inventory_df['Expiry Date'] = pd.to_datetime(inventory_df['Expiry Date'], dayfirst=True, errors='coerce')
        
        # Parse quantities
        parsed = inventory_df['Quantity'].apply(parse_quantity)
        inventory_df['value'] = parsed.apply(lambda x: x[0] if x else None)
        inventory_df['unit'] = parsed.apply(lambda x: x[1] if x else None)
        inventory_df['standardized_quantity'] = inventory_df.apply(
            lambda row: standardize_quantity(row['value'], row['unit']) if row['value'] and row['unit'] else None, 
            axis=1
        )
        
        # Filter valid ingredients
        valid_df = inventory_df[
            (inventory_df['Expiry Date'] > today) & 
            (inventory_df['standardized_quantity'] > 0)
        ]
        
        available_ingredients = valid_df['Ingredient'].str.lower().tolist()
        logger.info(f"Found {len(available_ingredients)} valid ingredients")
        return available_ingredients
        
    except Exception as e:
        logger.error(f"Error filtering ingredients: {str(e)}")
        return []

def find_possible_dishes(db, available_ingredients):
    """Find dishes that can be made from valid ingredients"""
    try:
        menu_data = [doc.to_dict() for doc in db.collection('menu').stream()]
        if not menu_data:
            logger.warning("No menu data found")
            return []
            
        possible_dishes = []
        for dish in menu_data:
            if 'ingredients' in dish and dish['ingredients']:
                # Handle both string and list formats
                if isinstance(dish['ingredients'], str):
                    required = [i.strip().lower() for i in dish['ingredients'].split(',')]
                elif isinstance(dish['ingredients'], list):
                    required = [str(i).strip().lower() for i in dish['ingredients']]
                else:
                    continue
                    
                # Check if all required ingredients are available
                if all(ingredient in available_ingredients for ingredient in required):
                    possible_dishes.append(dish.get('name', 'Unknown Dish'))
        
        logger.info(f"Found {len(possible_dishes)} possible dishes")
        return possible_dishes
        
    except Exception as e:
        logger.error(f"Error finding possible dishes: {str(e)}")
        return []

def generate_campaign(staff_name, promotion_type, promotion_goal, target_audience, campaign_duration, possible_dishes):
    """Generate marketing campaign using AI"""
    try:
        model = configure_promotion_gemini_ai()
        if not model:
            return None
            
        current_month = datetime.now().strftime("%B %Y")
        
        prompt_text = f"""
        You are a professional restaurant marketing expert creating a campaign for {current_month}.

        CAMPAIGN REQUIREMENTS:
        - Staff Member: {staff_name}
        - Promotion Type: {promotion_type}
        - Campaign Goal: {promotion_goal}
        - Target Audience: {target_audience}
        - Duration: {campaign_duration}

        AVAILABLE DISHES TODAY:
        {', '.join(possible_dishes)}

        INSTRUCTIONS:
        1. Create an attractive, specific campaign using ONLY the dishes listed above
        2. Make the offer compelling with clear value proposition
        3. Include specific pricing or discount details
        4. Focus on the campaign goal: {promotion_goal}
        5. Write in an engaging, marketing-friendly tone
        6. Keep it concise but impactful (2-3 paragraphs max)
        7. Include a clear call-to-action

        Create a professional marketing campaign now:
        """
        
        response = model.generate_content(prompt_text)
        campaign = response.text.strip()
        
        logger.info(f"Generated campaign for {staff_name}: {len(campaign)} characters")
        return campaign
        
    except Exception as e:
        logger.error(f"Error generating campaign: {str(e)}")
        return None

def save_campaign(db, staff_name, campaign_data, user_id=None):
    """Save campaign to database with user_id"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        campaign_doc_id = f"{staff_name}_{current_month}"
        
        campaign_data.update({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "month": current_month,
            "created_at": datetime.now().isoformat(),
            "user_id": user_id,  # Add user_id to campaign
            "likes": 0,  # Initialize likes counter
            "dislikes": 0,  # Initialize dislikes counter
            "liked_by": [],  # List of user IDs who liked
            "disliked_by": []  # List of user IDs who disliked
        })
        
        db.collection("staff_campaigns").document(campaign_doc_id).set(campaign_data)
        logger.info(f"Saved campaign for {staff_name} to database with user_id: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving campaign: {str(e)}")
        return False

def delete_campaign(db, staff_name):
    """Delete existing campaign for current month"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        campaign_doc_id = f"{staff_name}_{current_month}"
        
        doc_ref = db.collection("staff_campaigns").document(campaign_doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            doc_ref.delete()
            logger.info(f"Deleted campaign for {staff_name} for month {current_month}")
            return True
        else:
            logger.warning(f"No campaign found to delete for {staff_name} for month {current_month}")
            return False
        
    except Exception as e:
        logger.error(f"Error deleting campaign: {str(e)}")
        return False

def get_existing_campaign(db, staff_name):
    """Check if user already has a campaign for current month"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        campaign_doc_id = f"{staff_name}_{current_month}"
        
        doc = db.collection('staff_campaigns').document(campaign_doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
        
    except Exception as e:
        logger.error(f"Error checking existing campaign: {str(e)}")
        return None

def get_campaigns_for_month(db, month=None):
    """Get all campaigns for a specific month"""
    try:
        if month is None:
            month = datetime.now().strftime("%Y-%m")
            
        docs = db.collection("staff_campaigns").where("month", "==", month).stream()
        campaigns = [doc.to_dict() for doc in docs]
        
        logger.info(f"Retrieved {len(campaigns)} campaigns for month {month}")
        return campaigns
        
    except Exception as e:
        logger.error(f"Error retrieving campaigns: {str(e)}")
        return []

def get_all_campaigns(db, limit=50):
    """Get all campaigns across all months with pagination"""
    try:
        docs = db.collection("staff_campaigns").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
        campaigns = []
        
        for doc in docs:
            campaign_data = doc.to_dict()
            campaign_data['doc_id'] = doc.id  # Add document ID for updates
            campaigns.append(campaign_data)
        
        logger.info(f"Retrieved {len(campaigns)} campaigns total")
        return campaigns
        
    except Exception as e:
        logger.error(f"Error retrieving all campaigns: {str(e)}")
        return []

def like_campaign(db, campaign_doc_id, user_id):
    """Like a campaign and award XP to campaign creator"""
    try:
        campaign_ref = db.collection("staff_campaigns").document(campaign_doc_id)
        campaign_doc = campaign_ref.get()
        
        if not campaign_doc.exists:
            return False, "Campaign not found"
        
        campaign_data = campaign_doc.to_dict()
        liked_by = campaign_data.get('liked_by', [])
        disliked_by = campaign_data.get('disliked_by', [])
        
        # Check if user already liked
        if user_id in liked_by:
            return False, "You already liked this campaign"
        
        # Remove from dislikes if present
        if user_id in disliked_by:
            disliked_by.remove(user_id)
        
        # Add to likes
        liked_by.append(user_id)
        
        # Update campaign
        campaign_ref.update({
            'likes': len(liked_by),
            'dislikes': len(disliked_by),
            'liked_by': liked_by,
            'disliked_by': disliked_by
        })
        
        # Award XP to campaign creator
        campaign_creator_id = campaign_data.get('user_id')
        if campaign_creator_id:
            award_like_xp(campaign_creator_id, is_like=True)
        
        logger.info(f"User {user_id} liked campaign {campaign_doc_id}")
        return True, "Campaign liked successfully"
        
    except Exception as e:
        logger.error(f"Error liking campaign: {str(e)}")
        return False, f"Error: {str(e)}"

def dislike_campaign(db, campaign_doc_id, user_id):
    """Dislike a campaign and award minimal XP to campaign creator"""
    try:
        campaign_ref = db.collection("staff_campaigns").document(campaign_doc_id)
        campaign_doc = campaign_ref.get()
        
        if not campaign_doc.exists:
            return False, "Campaign not found"
        
        campaign_data = campaign_doc.to_dict()
        liked_by = campaign_data.get('liked_by', [])
        disliked_by = campaign_data.get('disliked_by', [])
        
        # Check if user already disliked
        if user_id in disliked_by:
            return False, "You already disliked this campaign"
        
        # Remove from likes if present
        if user_id in liked_by:
            liked_by.remove(user_id)
        
        # Add to dislikes
        disliked_by.append(user_id)
        
        # Update campaign
        campaign_ref.update({
            'likes': len(liked_by),
            'dislikes': len(disliked_by),
            'liked_by': liked_by,
            'disliked_by': disliked_by
        })
        
        # Award minimal XP to campaign creator
        campaign_creator_id = campaign_data.get('user_id')
        if campaign_creator_id:
            award_like_xp(campaign_creator_id, is_like=False)
        
        logger.info(f"User {user_id} disliked campaign {campaign_doc_id}")
        return True, "Campaign disliked"
        
    except Exception as e:
        logger.error(f"Error disliking campaign: {str(e)}")
        return False, f"Error: {str(e)}"

def award_like_xp(campaign_creator_id, is_like=True):
    """Award XP to campaign creator for receiving likes/dislikes"""
    try:
        main_db = get_main_firebase_db()
        if not main_db:
            logger.error("Could not connect to main Firebase for like XP award")
            return 0
        
        # Award different XP for likes vs dislikes
        xp_to_award = 10 if is_like else 2
        
        # Update user stats in main Firebase
        user_ref = main_db.collection('user_stats').document(campaign_creator_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            current_stats = user_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            new_xp = current_xp + xp_to_award
            
            # Calculate new level
            new_level = (new_xp // 100) + 1
            
            # Update stats
            user_ref.update({
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            action = "like" if is_like else "dislike"
            logger.info(f"Awarded {xp_to_award} XP to user {campaign_creator_id} for campaign {action}. New total: {new_xp} XP")
        else:
            # Create new user stats
            user_ref.set({
                'user_id': campaign_creator_id,
                'total_xp': xp_to_award,
                'level': 1,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Created new user stats for {campaign_creator_id} with {xp_to_award} XP")
        
        return xp_to_award
        
    except Exception as e:
        logger.error(f"Error awarding like XP: {str(e)}")
        return 0

def award_promotion_xp(user_id, campaign_quality="good"):
    """Award XP for creating a promotion campaign using main Firebase"""
    try:
        # Get main Firebase database for gamification
        main_db = get_main_firebase_db()
        if not main_db:
            logger.error("Could not connect to main Firebase for XP award")
            return 0
        
        # Award different XP based on campaign quality
        xp_amounts = {
            "excellent": 50,
            "good": 30,
            "basic": 20
        }
        
        xp_to_award = xp_amounts.get(campaign_quality, 30)
        
        # Update user stats in main Firebase
        user_ref = main_db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            current_stats = user_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            new_xp = current_xp + xp_to_award
            
            # Calculate new level
            new_level = (new_xp // 100) + 1
            
            # Update stats
            user_ref.update({
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Awarded {xp_to_award} XP to user {user_id} for promotion campaign. New total: {new_xp} XP, Level: {new_level}")
        else:
            # Create new user stats
            user_ref.set({
                'user_id': user_id,
                'total_xp': xp_to_award,
                'level': 1,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Created new user stats for {user_id} with {xp_to_award} XP")
        
        # Clear any cached user stats to force refresh
        if hasattr(st, 'cache_data'):
            st.cache_data.clear()
        
        return xp_to_award
        
    except Exception as e:
        logger.error(f"Error awarding promotion XP: {str(e)}")
        return 0

def get_user_stats_promotion(user_id):
    """Get user stats from main Firebase"""
    try:
        main_db = get_main_firebase_db()
        if not main_db:
            return {'total_xp': 0, 'level': 1}
        
        user_ref = main_db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return user_doc.to_dict()
        else:
            return {'total_xp': 0, 'level': 1}
            
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {'total_xp': 0, 'level': 1}

def get_user_by_id(user_id):
    """Get user information by user_id from main Firebase"""
    try:
        main_db = get_main_firebase_db()
        if not main_db:
            return None
        
        user_ref = main_db.collection('users').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            return user_doc.to_dict()
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error getting user by ID: {str(e)}")
        return None
