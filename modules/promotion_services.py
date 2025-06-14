"""
Promotion Campaign Services module for the Smart Restaurant Menu Management App.
Handles campaign generation, submission, and AI scoring using event_firebase configuration.
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

def save_campaign(db, staff_name, campaign_data):
    """Save campaign to database"""
    try:
        current_month = datetime.now().strftime("%Y-%m")
        campaign_doc_id = f"{staff_name}_{current_month}"
        
        campaign_data.update({
            "timestamp": firestore.SERVER_TIMESTAMP,
            "month": current_month
        })
        
        db.collection("staff_campaigns").document(campaign_doc_id).set(campaign_data)
        logger.info(f"Saved campaign for {staff_name} to database")
        return True
        
    except Exception as e:
        logger.error(f"Error saving campaign: {str(e)}")
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

def award_promotion_xp(user_id, campaign_quality="good"):
    """Award XP for creating a promotion campaign"""
    try:
        from modules.leftover import award_recipe_xp
        
        # Award different XP based on campaign quality
        xp_amounts = {
            "excellent": 50,
            "good": 30,
            "basic": 20
        }
        
        xp_to_award = xp_amounts.get(campaign_quality, 30)
        award_recipe_xp(user_id, xp_to_award, "promotion_campaign")
        
        logger.info(f"Awarded {xp_to_award} XP to user {user_id} for promotion campaign")
        return xp_to_award
        
    except Exception as e:
        logger.error(f"Error awarding promotion XP: {str(e)}")
        return 0
