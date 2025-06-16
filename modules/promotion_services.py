"""
Promotion Campaign Services module for the Smart Restaurant Menu Management App.
Handles campaign generation, submission, AI scoring, and voting system using event_firebase configuration.
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

def save_campaign(db, staff_name, user_id, campaign_data):
    """Save campaign to database with both name and user_id"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        campaign_doc_id = f"{staff_name}_{current_month}"
        
        campaign_data.update({
            "name": staff_name,
            "user_id": user_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "month": current_month,
            "created_at": datetime.now().isoformat(),
            "likes": 0,
            "dislikes": 0
        })
        
        db.collection("staff_campaigns").document(campaign_doc_id).set(campaign_data)
        logger.info(f"Saved campaign for {staff_name} (ID: {user_id}) to database")
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

def get_all_campaigns_sorted(db):
    """Get all campaigns sorted by timestamp (newest first)"""
    try:
        docs = db.collection("staff_campaigns").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        campaigns = []
        
        for doc in docs:
            campaign_data = doc.to_dict()
            campaign_data['campaign_id'] = doc.id
            campaigns.append(campaign_data)
        
        logger.info(f"Retrieved {len(campaigns)} total campaigns")
        return campaigns
        
    except Exception as e:
        logger.error(f"Error retrieving all campaigns: {str(e)}")
        return []

def has_user_voted(db, user_id, campaign_id):
    """Check if user has already voted on a campaign"""
    try:
        docs = db.collection("campaign_votes").where("user_id", "==", user_id).where("campaign_id", "==", campaign_id).limit(1).stream()
        votes = list(docs)
        return len(votes) > 0, votes[0].to_dict() if votes else None
        
    except Exception as e:
        logger.error(f"Error checking user vote: {str(e)}")
        return False, None

def vote_on_campaign(db, user_id, campaign_id, vote_type):
    """Vote on a campaign (like or dislike) and award XP to campaign creator"""
    try:
        # Check if user already voted
        has_voted, existing_vote = has_user_voted(db, user_id, campaign_id)
        if has_voted:
            return False, "You have already voted on this campaign"
        
        # Get campaign details to find creator
        campaign_doc = db.collection("staff_campaigns").document(campaign_id).get()
        if not campaign_doc.exists:
            return False, "Campaign not found"
        
        campaign_data = campaign_doc.to_dict()
        creator_user_id = campaign_data.get('user_id')
        
        if not creator_user_id:
            return False, "Campaign creator not found"
        
        # Don't allow voting on own campaigns
        if creator_user_id == user_id:
            return False, "You cannot vote on your own campaign"
        
        # Record the vote in event_firebase
        vote_data = {
            "user_id": user_id,
            "campaign_id": campaign_id,
            "vote_type": vote_type,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "created_at": datetime.now().isoformat()
        }
        
        db.collection("campaign_votes").add(vote_data)
        
        # Update campaign vote counts
        if vote_type == "like":
            db.collection("staff_campaigns").document(campaign_id).update({
                "likes": firestore.Increment(1)
            })
            xp_to_award = 10  # Award 10 XP for likes
        else:  # dislike
            db.collection("staff_campaigns").document(campaign_id).update({
                "dislikes": firestore.Increment(1)
            })
            xp_to_award = 2   # Award 2 XP for dislikes (feedback is still valuable)
        
        # Award XP to campaign creator in main_firebase
        success = award_vote_xp(creator_user_id, xp_to_award, vote_type)
        
        if success:
            logger.info(f"User {user_id} voted '{vote_type}' on campaign {campaign_id}, awarded {xp_to_award} XP to creator {creator_user_id}")
            return True, f"Vote recorded! Campaign creator earned {xp_to_award} XP"
        else:
            logger.warning(f"Vote recorded but XP award failed for creator {creator_user_id}")
            return True, "Vote recorded!"
        
    except Exception as e:
        logger.error(f"Error voting on campaign: {str(e)}")
        return False, f"Error recording vote: {str(e)}"

def award_vote_xp(creator_user_id, xp_amount, vote_type):
    """Award XP to campaign creator for receiving votes"""
    try:
        main_db = get_main_firebase_db()
        if not main_db:
            logger.error("Could not connect to main Firebase for vote XP award")
            return False
        
        # Update user stats in main Firebase
        user_ref = main_db.collection('user_stats').document(creator_user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            current_stats = user_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            new_xp = current_xp + xp_amount
            
            # Calculate new level using progressive system
            from modules.xp_utils import calculate_level_from_xp
            new_level = calculate_level_from_xp(new_xp)
            
            # Update stats
            user_ref.update({
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Awarded {xp_amount} XP to user {creator_user_id} for receiving {vote_type}. New total: {new_xp} XP, Level: {new_level}")
        else:
            # Create new user stats if they don't exist
            from modules.xp_utils import calculate_level_from_xp
            new_level = calculate_level_from_xp(xp_amount)
            
            user_ref.set({
                'user_id': creator_user_id,
                'total_xp': xp_amount,
                'level': new_level,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Created new user stats for {creator_user_id} with {xp_amount} XP")
        
        return True
        
    except Exception as e:
        logger.error(f"Error awarding vote XP: {str(e)}")
        return False

def get_campaign_votes_summary(db, campaign_id):
    """Get vote summary for a campaign"""
    try:
        campaign_doc = db.collection("staff_campaigns").document(campaign_id).get()
        if campaign_doc.exists:
            data = campaign_doc.to_dict()
            return {
                'likes': data.get('likes', 0),
                'dislikes': data.get('dislikes', 0)
            }
        return {'likes': 0, 'dislikes': 0}
        
    except Exception as e:
        logger.error(f"Error getting vote summary: {str(e)}")
        return {'likes': 0, 'dislikes': 0}

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
            
            # Calculate new level using progressive system
            from modules.xp_utils import calculate_level_from_xp
            new_level = calculate_level_from_xp(new_xp)
            
            # Update stats
            user_ref.update({
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Awarded {xp_to_award} XP to user {user_id} for promotion campaign. New total: {new_xp} XP, Level: {new_level}")
        else:
            # Create new user stats
            from modules.xp_utils import calculate_level_from_xp
            new_level = calculate_level_from_xp(xp_to_award)
            
            user_ref.set({
                'user_id': user_id,
                'total_xp': xp_to_award,
                'level': new_level,
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
