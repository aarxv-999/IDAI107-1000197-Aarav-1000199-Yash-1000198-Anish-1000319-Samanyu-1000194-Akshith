"""
Event Planning Chatbot for Smart Restaurant Management App
Created by: v0

This module provides:
1. AI-powered event planning chatbot using Gemini API
2. Integration with Firestore for recipe and ingredient data (read-only)
3. Role-based access control for different user types
4. User-friendly display of event plans
5. PDF export functionality
6. Budget estimation in INR
7. **NEW: Gamification system with XP rewards for different user roles**
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import firebase_admin
from firebase_admin import firestore, credentials
import logging
import pandas as pd
from fpdf import FPDF
import base64
import io

# **NEW: Import gamification functions**
from modules.leftover import (
    get_user_stats, update_user_stats, award_recipe_xp, 
    generate_dynamic_quiz_questions, calculate_quiz_score,
    get_firestore_db
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Initialize Firebase for event data (read-only)
def init_event_firebase():
    """Initialize the Firebase Admin SDK for event data (read-only)"""
    if not firebase_admin._apps or 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
        try:
            # Use environment variables with EVENT_ prefix
            cred = credentials.Certificate({
                "type": st.secrets["event_firebase_type"],
                "project_id": st.secrets["event_firebase_project_id"],
                "private_key_id": st.secrets["event_firebase_private_key_id"],
                "private_key": st.secrets["event_firebase_private_key"].replace("\\n", "\n"),
                "client_email": st.secrets["event_firebase_client_email"],
                "client_id": st.secrets["event_firebase_client_id"],
                "auth_uri": st.secrets["event_firebase_auth_uri"],
                "token_uri": st.secrets["event_firebase_token_uri"],
                "auth_provider_x509_cert_url": st.secrets["event_firebase_auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["event_firebase_client_x509_cert_url"],
            })
            firebase_admin.initialize_app(cred, name='event_app')
            logger.info("Event Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            # Fallback to display error in UI
            st.error(f"Failed to initialize Event Firebase. Please check your credentials.")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

# **NEW: Gamification Functions for Event Planning**

def award_event_planning_xp(user_id: str, user_role: str, activity_type: str = "chatbot_use") -> Dict:
    """
    Award XP for event planning activities based on user role.
    
    Args:
        user_id (str): User's unique ID
        user_role (str): User's role (admin, staff, chef, user)
        activity_type (str): Type of activity performed
    
    Returns:
        Dict: Updated user stats
    """
    try:
        # XP rewards based on role and activity
        xp_rewards = {
            'admin': {
                'chatbot_use': 15,  # Higher XP for admin using chatbot
                'event_plan_generated': 25,
                'event_quiz_correct': 10
            },
            'staff': {
                'chatbot_use': 12,  # Good XP for staff using chatbot
                'event_plan_generated': 20,
                'event_quiz_correct': 10
            },
            'chef': {
                'chatbot_use': 12,  # Same as staff
                'event_plan_generated': 20,
                'event_quiz_correct': 10
            },
            'user': {
                'event_quiz_correct': 15,  # Users get XP from quizzes only
                'event_knowledge_bonus': 20,  # Bonus for learning about events
                'event_suggestion': 10  # XP for providing event suggestions
            }
        }
        
        xp_to_award = xp_rewards.get(user_role, {}).get(activity_type, 0)
        
        if xp_to_award > 0:
            # Use existing gamification system
            current_stats = get_user_stats(user_id)
            
            db = get_firestore_db()
            user_stats_ref = db.collection('user_stats').document(user_id)
            
            new_total_xp = current_stats['total_xp'] + xp_to_award
            new_level = calculate_level(new_total_xp)
            
            # Update event-specific stats
            event_activities = current_stats.get('event_activities', 0) + 1
            
            updated_stats = current_stats.copy()
            updated_stats.update({
                'total_xp': new_total_xp,
                'level': new_level,
                'event_activities': event_activities
            })
            
            user_stats_ref.set(updated_stats)
            logger.info(f"Awarded {xp_to_award} XP to {user_role} for {activity_type}")
            
            # Store XP notification in session state
            if 'xp_notifications' not in st.session_state:
                st.session_state.xp_notifications = []
            
            st.session_state.xp_notifications.append({
                'xp': xp_to_award,
                'activity': activity_type,
                'timestamp': datetime.now()
            })
            
            return updated_stats
        else:
            logger.info(f"No XP awarded for {user_role} doing {activity_type}")
            return get_user_stats(user_id)
            
    except Exception as e:
        logger.error(f"Error awarding event planning XP: {str(e)}")
        return get_user_stats(user_id)

def calculate_level(total_xp: int) -> int:
    """Calculate user level based on total XP."""
    import math
    return max(1, int(math.sqrt(total_xp / 100)) + 1)

def show_xp_notification():
    """Display XP notifications to the user."""
    if 'xp_notifications' in st.session_state and st.session_state.xp_notifications:
        for notification in st.session_state.xp_notifications:
            activity_messages = {
                'chatbot_use': 'using the Event Planning ChatBot',
                'event_plan_generated': 'generating an event plan',
                'event_quiz_correct': 'answering event quiz correctly',
                'event_knowledge_bonus': 'learning about event planning',
                'event_suggestion': 'providing event suggestions'
            }
            
            activity_msg = activity_messages.get(notification['activity'], 'event planning activity')
            st.success(f"🎉 +{notification['xp']} XP earned for {activity_msg}!")
        
        # Clear notifications after showing
        st.session_state.xp_notifications = []

def render_event_quiz_for_users(user_id: str):
    """
    Render event planning quiz for regular users to earn XP.
    This is the improvised method for users who can't organize events themselves.
    """
    st.markdown("### 🧠 Event Planning Knowledge Quiz")
    st.markdown("*Learn about event planning and earn XP!*")
    
    # Event planning focused ingredients/topics for quiz generation
    event_topics = [
        "catering", "banquet", "buffet", "appetizers", "main course", 
        "desserts", "beverages", "party planning", "wedding catering",
        "corporate events", "birthday parties", "seasonal events"
    ]
    
    if 'event_quiz_questions' not in st.session_state:
        st.session_state.event_quiz_questions = None
    if 'event_quiz_answers' not in st.session_state:
        st.session_state.event_quiz_answers = []
    if 'event_quiz_submitted' not in st.session_state:
        st.session_state.event_quiz_submitted = False
    if 'event_quiz_results' not in st.session_state:
        st.session_state.event_quiz_results = None

    col1, col2 = st.columns([1, 2])
    with col1:
        num_questions = st.selectbox("Questions:", [3, 5, 7], index=1, key="event_quiz_num")
    with col2:
        if st.button("Start Event Quiz", type="primary", use_container_width=True, key="start_event_quiz"):
            with st.spinner("Loading event planning questions..."):
                # Generate event-focused quiz questions
                st.session_state.event_quiz_questions = generate_event_quiz_questions(event_topics, num_questions)
                st.session_state.event_quiz_answers = []
                st.session_state.event_quiz_submitted = False
                st.session_state.event_quiz_results = None
                st.rerun()

    if st.session_state.event_quiz_questions and not st.session_state.event_quiz_submitted:
        st.divider()
        answers = []
        for i, question in enumerate(st.session_state.event_quiz_questions):
            with st.container():
                st.write(f"**{i+1}.** {question['question']}")
                st.caption(f"Event Planning • {question['xp_reward']} XP")
                answer = st.radio("Select answer:", options=question['options'], key=f"event_q_{i}", index=None, label_visibility="collapsed")
                if answer:
                    answers.append(question['options'].index(answer))
                else:
                    answers.append(-1)
            if i < len(st.session_state.event_quiz_questions) - 1:
                st.divider()
        
        st.write("")
        if st.button("Submit Event Quiz", type="primary", use_container_width=True, key="submit_event_quiz"):
            if -1 in answers:
                st.error("Please answer all questions before submitting.")
            else:
                st.session_state.event_quiz_answers = answers
                st.session_state.event_quiz_submitted = True
                correct, total, xp_earned = calculate_quiz_score(answers, st.session_state.event_quiz_questions)
                st.session_state.event_quiz_results = {
                    'correct': correct,
                    'total': total,
                    'xp_earned': xp_earned,
                    'percentage': (correct / total) * 100
                }
                
                # Award XP for each correct answer
                for i, answer in enumerate(answers):
                    if answer == st.session_state.event_quiz_questions[i]['correct']:
                        award_event_planning_xp(user_id, 'user', 'event_quiz_correct')
                
                # Bonus XP for learning
                if correct > 0:
                    award_event_planning_xp(user_id, 'user', 'event_knowledge_bonus')
                
                st.rerun()

    if st.session_state.event_quiz_submitted and st.session_state.event_quiz_results:
        display_event_quiz_results(st.session_state.event_quiz_results, st.session_state.event_quiz_questions, st.session_state.event_quiz_answers)

def generate_event_quiz_questions(topics: List[str], num_questions: int = 5) -> List[Dict]:
    """Generate event planning focused quiz questions."""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found, using fallback event questions")
            return generate_fallback_event_questions(num_questions)
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        topics_list = ", ".join(topics)
        
        prompt = f'''
        Generate {num_questions} unique quiz questions about event planning and catering.
        Focus on these topics: {topics_list}
        
        Include questions about:
        - Event planning basics and best practices
        - Catering and food service for events
        - Party planning and organization
        - Budget planning for events
        - Menu planning for different event types
        - Event logistics and coordination
        
        Format as JSON array:
        [
            {{
                "question": "Event planning question?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 0,
                "difficulty": "easy",
                "xp_reward": 15,
                "explanation": "Helpful explanation about event planning"
            }}
        ]

        XP Rewards: easy=15, medium=20, hard=25 (higher than cooking quiz since this is educational)
        '''

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up the response to extract JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        try:
            questions = json.loads(response_text)
            if isinstance(questions, list) and len(questions) > 0:
                return questions[:num_questions]
            else:
                return generate_fallback_event_questions(num_questions)
        except json.JSONDecodeError:
            return generate_fallback_event_questions(num_questions)

    except Exception as e:
        logger.error(f"Error generating event quiz questions: {str(e)}")
        return generate_fallback_event_questions(num_questions)

def generate_fallback_event_questions(num_questions: int = 5) -> List[Dict]:
    """Generate fallback event planning quiz questions."""
    event_questions = [
        {
            "question": "What is the recommended food quantity per person for a buffet-style event?",
            "options": ["0.5-0.75 lbs", "1-1.5 lbs", "2-2.5 lbs", "3-4 lbs"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "For buffet events, plan for 1-1.5 lbs of food per person to ensure adequate portions."
        },
        {
            "question": "How far in advance should you typically book a venue for a large event?",
            "options": ["1-2 weeks", "1 month", "3-6 months", "1 year"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 20,
            "explanation": "Popular venues book up quickly, so 3-6 months advance booking is recommended for large events."
        },
        {
            "question": "What percentage of the total event budget is typically allocated to catering?",
            "options": ["20-30%", "40-50%", "60-70%", "80-90%"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 20,
            "explanation": "Catering usually represents 40-50% of the total event budget, being one of the largest expenses."
        },
        {
            "question": "Which seating arrangement is best for encouraging interaction at corporate events?",
            "options": ["Theater style", "Classroom style", "Round tables", "U-shape"],
            "correct": 2,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "Round tables promote conversation and networking, making them ideal for corporate events."
        },
        {
            "question": "What is the ideal room temperature for most indoor events?",
            "options": ["65-68°F", "68-72°F", "72-76°F", "76-80°F"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "68-72°F is comfortable for most people and accounts for body heat from crowds."
        },
        {
            "question": "How many appetizer pieces per person should you plan for a cocktail reception?",
            "options": ["3-4 pieces", "6-8 pieces", "10-12 pieces", "15-20 pieces"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 20,
            "explanation": "Plan for 10-12 appetizer pieces per person for a cocktail reception without a full meal."
        },
        {
            "question": "What is the standard ratio of servers to guests for a plated dinner event?",
            "options": ["1:5", "1:10", "1:15", "1:20"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 25,
            "explanation": "One server per 10 guests ensures efficient service for plated dinner events."
        },
        {
            "question": "Which factor is most important when planning an outdoor event menu?",
            "options": ["Cost", "Weather conditions", "Guest preferences", "Venue restrictions"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 20,
            "explanation": "Weather affects food safety, presentation, and guest comfort, making it the top priority for outdoor events."
        }
    ]
    
    import random
    random.shuffle(event_questions)
    return event_questions[:num_questions]

def display_event_quiz_results(results: Dict, questions: List[Dict], user_answers: List[int]):
    """Display event quiz results with XP earned."""
    st.divider()
    st.subheader("🎉 Event Quiz Results")
    score = results['correct']
    total = results['total']
    percentage = results['percentage']
    xp_earned = results['xp_earned']

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Score", f"{score}/{total}")
    with col2:
        st.metric("Accuracy", f"{percentage:.1f}%")
    with col3:
        st.metric("XP Earned", f"+{xp_earned}")
    with col4:
        if percentage == 100:
            st.metric("Grade", "Perfect")
        elif percentage >= 80:
            st.metric("Grade", "Excellent")
        elif percentage >= 60:
            st.metric("Grade", "Good")
        else:
            st.metric("Grade", "Keep Learning")

    if percentage == 100:
        st.success("🎉 Perfect score! You're an event planning expert!")
    elif percentage >= 80:
        st.success("🌟 Excellent work! Your event planning knowledge is impressive.")
    elif percentage >= 60:
        st.info("👍 Good job! Keep learning about event planning.")
    else:
        st.warning("📚 Keep studying! Event planning has many aspects to master.")

    # Show XP notifications
    show_xp_notification()

    if st.button("Take Another Event Quiz", use_container_width=True, key="another_event_quiz"):
        st.session_state.event_quiz_questions = None
        st.session_state.event_quiz_answers = []
        st.session_state.event_quiz_submitted = False
        st.session_state.event_quiz_results = None
        st.rerun()

# AI Model Configuration
def configure_ai_model():
    """Configure and return the Gemini AI model"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            api_key = st.secrets.get("GEMINI_API_KEY")
            
        if not api_key:
            st.error("GEMINI_API_KEY not found in environment variables or secrets!")
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        logger.error(f"Error configuring AI model: {str(e)}")
        st.error(f"Failed to configure AI model: {str(e)}")
        return None

# Firestore Data Functions (Read-Only)
def get_recipe_items(dietary_restrictions: Optional[str] = None) -> List[Dict]:
    """
    Fetch recipe items from Firestore, optionally filtered by dietary restrictions

    Args:
        dietary_restrictions: Optional filter for dietary needs (e.g., "vegan", "gluten-free")
        
    Returns:
        List of recipe items as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            return []
            
        recipe_ref = db.collection('recipe_archive')
        
        # Apply dietary filter if provided
        if dietary_restrictions and dietary_restrictions.lower() != "none":
            query = recipe_ref.where('diet', 'array_contains', dietary_restrictions.lower())
            recipe_docs = query.get()
        else:
            recipe_docs = recipe_ref.get()
            
        recipe_items = []
        for doc in recipe_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            recipe_items.append(item)
            
        return recipe_items
    except Exception as e:
        logger.error(f"Error fetching recipe items: {str(e)}")
        return []

def get_available_ingredients() -> List[Dict]:
    """
    Fetch available ingredients from Firestore inventory

    Returns:
        List of ingredients as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            return []
            
        inventory_ref = db.collection('ingredients_inventory')
        inventory_docs = inventory_ref.get()
        
        ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            ingredients.append(item)
            
        return ingredients
    except Exception as e:
        logger.error(f"Error fetching ingredients: {str(e)}")
        return []

def get_customers() -> List[Dict]:
    """
    Fetch customer data from Firestore

    Returns:
        List of customers as dictionaries
    """
    try:
        # Use the main Firebase app for user data
        db = firestore.client()
        users_ref = db.collection('users')
        
        # Get users with role 'user' (customers)
        users_docs = users_ref.where('role', '==', 'user').get()
        
        customers = []
        for doc in users_docs:
            user = doc.to_dict()
            # Only include necessary fields
            customers.append({
                'user_id': user.get('user_id', ''),
                'username': user.get('username', ''),
                'email': user.get('email', '')
            })
            
        return customers
    except Exception as e:
        logger.error(f"Error fetching customers: {str(e)}")
        return []

# AI Event Planning Functions
def generate_event_plan(query: str, user_id: str, user_role: str) -> Dict:
    """
    Generate an event plan using AI based on user query
    **NEW: Now includes gamification - awards XP for using the chatbot**

    Args:
        query: User's natural language query about event planning
        user_id: User's unique ID for XP tracking
        user_role: User's role for XP calculation
        
    Returns:
        Dictionary containing generated event plan details
    """
    model = configure_ai_model()
    if not model:
        return {
            'error': 'AI model configuration failed',
            'success': False
        }

    # **NEW: Award XP for using the chatbot (staff/admin only)**
    if user_role in ['admin', 'staff', 'chef']:
        award_event_planning_xp(user_id, user_role, 'chatbot_use')

    # Get available recipe items and ingredients for context
    recipe_items = get_recipe_items()
    recipe_names = [item.get('name', '') for item in recipe_items]

    ingredients = get_available_ingredients()
    ingredient_names = [item.get('Ingredient', '') for item in ingredients]

    # Extract dietary restrictions from query
    dietary_keywords = ['vegan', 'vegetarian', 'gluten-free', 'dairy-free', 'nut-free']
    dietary_restrictions = []

    for keyword in dietary_keywords:
        if keyword in query.lower():
            dietary_restrictions.append(keyword)

    # Extract guest count from query
    guest_count = 20  # Default
    guest_matches = re.findall(r'(\d+)\s+(?:people|guests|persons)', query)
    if guest_matches:
        guest_count = int(guest_matches[0])

    # Prepare prompt for AI
    prompt = f'''
    You are an expert event planner for a restaurant in India. Plan an event based on this request:
    "{query}"

    Available recipes at our restaurant: {', '.join(recipe_names[:20])}
    Available ingredients: {', '.join(ingredient_names[:20])}

    Generate a complete event plan with the following sections:
    1. Theme: A creative name and description for the event theme
    2. Seating: A seating plan for {guest_count} guests (specify table arrangement)
    3. Decor: Decoration and ambiance suggestions
    4. Recipes: 5-7 recipe suggestions from our available recipes
    5. Budget: Detailed budget breakdown in Indian Rupees (INR)
    6. Invitation: A short invitation message template

    For the budget, provide realistic Indian pricing for:
    - Food cost per person (₹300-800 depending on menu complexity)
    - Decoration costs (₹2000-8000 total depending on event size)
    - Venue setup costs (₹1000-5000 total)
    - Service charges (10-15% of food cost)
    - Total estimated cost
    - Cost per person

    Format your response as a JSON object with these exact keys:
    {{
        "theme": {{
            "name": "Theme name",
            "description": "Theme description"
        }},
        "seating": {{
            "layout": "Layout description",
            "tables": [
                {{"table_number": 1, "shape": "round", "seats": 8, "location": "near window"}},
                {{"table_number": 2, "shape": "rectangular", "seats": 10, "location": "center"}}
            ]
        }},
        "decor": [List of decoration ideas],
        "recipe_suggestions": [List of recipe names],
        "budget": {{
            "food_cost_per_person": 500,
            "total_food_cost": 10000,
            "decoration_cost": 5000,
            "venue_setup_cost": 3000,
            "service_charges": 1500,
            "total_cost": 19500,
            "cost_per_person": 975,
            "breakdown": [
                {{"item": "Food & Beverages", "cost": 10000}},
                {{"item": "Decorations", "cost": 5000}},
                {{"item": "Venue Setup", "cost": 3000}},
                {{"item": "Service Charges", "cost": 1500}}
            ]
        }},
        "invitation": "Invitation text"
    }}

    Make sure the JSON is valid and properly formatted. For the tables, include table number, shape, number of seats, and location.
    All budget amounts should be in Indian Rupees (INR) and be realistic for Indian market pricing.
    '''

    try:
        # Generate response from AI
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response
        json_match = re.search(r'\`\`\`json\s*(.*?)\s*\`\`\`', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            # Try to find JSON without code blocks
            json_match = re.search(r'({.*})', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
        
        # Parse JSON response
        event_plan = json.loads(response_text)
        
        # Filter recipe suggestions based on dietary restrictions
        if dietary_restrictions:
            filtered_recipes = get_recipe_items(dietary_restrictions[0])
            filtered_names = [item.get('name', '') for item in filtered_recipes]
            
            # If we have filtered items, use them instead
            if filtered_names:
                event_plan['recipe_suggestions'] = filtered_names[:7]
        
        # Ensure budget exists and has proper structure
        if 'budget' not in event_plan:
            # Create default budget if not generated
            food_cost_per_person = 500
            total_food_cost = food_cost_per_person * guest_count
            decoration_cost = min(5000, guest_count * 200)
            venue_setup_cost = 3000
            service_charges = int(total_food_cost * 0.15)
            total_cost = total_food_cost + decoration_cost + venue_setup_cost + service_charges
            
            event_plan['budget'] = {
                "food_cost_per_person": food_cost_per_person,
                "total_food_cost": total_food_cost,
                "decoration_cost": decoration_cost,
                "venue_setup_cost": venue_setup_cost,
                "service_charges": service_charges,
                "total_cost": total_cost,
                "cost_per_person": int(total_cost / guest_count),
                "breakdown": [
                    {"item": "Food & Beverages", "cost": total_food_cost},
                    {"item": "Decorations", "cost": decoration_cost},
                    {"item": "Venue Setup", "cost": venue_setup_cost},
                    {"item": "Service Charges", "cost": service_charges}
                ]
            }
        
        # Add event date (current date) and guest count
        event_plan['date'] = datetime.now().strftime("%Y-%m-%d")
        event_plan['guest_count'] = guest_count
        
        # **NEW: Award additional XP for successfully generating an event plan**
        if user_role in ['admin', 'staff', 'chef']:
            award_event_planning_xp(user_id, user_role, 'event_plan_generated')
        
        return {
            'plan': event_plan,
            'success': True
        }
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        return {
            'error': str(e),
            'success': False
        }

# PDF Generation Functions (keeping existing functions)
def create_event_pdf(event_plan: Dict) -> bytes:
    """
    Create a PDF document of the event plan
    
    Args:
        event_plan: Dictionary containing event plan details
        
    Returns:
        PDF document as bytes
    """
    try:
        # Create PDF object
        pdf = FPDF()
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", "B", 16)
        
        # Title
        pdf.cell(0, 10, f"Event Plan: {event_plan['theme']['name']}", ln=True, align="C")
        pdf.ln(5)
        
        # Date and guest count
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.cell(0, 10, f"Expected Guests: {event_plan.get('guest_count', 'Not specified')}", ln=True)
        pdf.ln(5)
        
        # Theme description
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Theme", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['theme']['description'])
        pdf.ln(5)
        
        # Budget Section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Budget Estimate (INR)", ln=True)
        pdf.set_font("Arial", "", 12)
        
        budget = event_plan.get('budget', {})
        if budget:
            # Budget summary
            pdf.cell(0, 10, f"Total Event Cost: Rs. {budget.get('total_cost', 0):,}", ln=True)
            pdf.cell(0, 10, f"Cost per Person: Rs. {budget.get('cost_per_person', 0):,}", ln=True)
            pdf.ln(3)
            
            # Budget breakdown table
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "Cost Breakdown:", ln=True)
            
            pdf.set_font("Arial", "", 10)
            col_width_item = 120
            col_width_cost = 60
            row_height = 8
            
            # Table headers
            pdf.cell(col_width_item, row_height, "Item", border=1)
            pdf.cell(col_width_cost, row_height, "Cost (INR)", border=1)
            pdf.ln(row_height)
            
            # Budget breakdown data
            for item in budget.get('breakdown', []):
                pdf.cell(col_width_item, row_height, str(item.get('item', '')), border=1)
                pdf.cell(col_width_cost, row_height, f"Rs. {item.get('cost', 0):,}", border=1)
                pdf.ln(row_height)
            
            pdf.ln(5)
        
        # Seating arrangement
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Seating Arrangement", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['seating']['layout'])
        
        # Table details
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Tables:", ln=True)
        
        # Create table for seating
        pdf.set_font("Arial", "", 10)
        col_width = 45
        row_height = 10
        
        # Table headers
        pdf.cell(col_width, row_height, "Table Number", border=1)
        pdf.cell(col_width, row_height, "Shape", border=1)
        pdf.cell(col_width, row_height, "Seats", border=1)
        pdf.cell(col_width, row_height, "Location", border=1)
        pdf.ln(row_height)
        
        # Table data
        for table in event_plan['seating']['tables']:
            if isinstance(table, dict):
                # New format
                pdf.cell(col_width, row_height, str(table.get('table_number', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('shape', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('seats', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('location', '')), border=1)
            else:
                # Old format (string)
                pdf.cell(0, row_height, str(table), border=1, ln=True)
            pdf.ln(row_height)
        
        pdf.ln(5)
        
        # Decoration
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Decoration Ideas", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['decor']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Recipe suggestions
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Recipe Suggestions", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['recipe_suggestions']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Invitation
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Invitation Template", ln=True)
        pdf.set_font("Arial", "I", 12)
        pdf.multi_cell(0, 10, event_plan['invitation'])
        
        # Return PDF as bytes
        return pdf.output(dest="S").encode("latin1", errors="replace")
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        return b""

def create_unicode_pdf(event_plan: Dict) -> bytes:
    """
    Create a PDF document with Unicode support using BytesIO
    
    Args:
        event_plan: Dictionary containing event plan details
        
    Returns:
        PDF document as bytes
    """
    try:
        from fpdf import FPDF
        
        class UnicodePDF(FPDF):
            def __init__(self):
                super().__init__()
                self.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
                self.add_font('DejaVu', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)
                self.add_font('DejaVu', 'I', 'DejaVuSansCondensed-Oblique.ttf', uni=True)
        
        # If we can't use DejaVu fonts, fall back to standard method
        try:
            pdf = UnicodePDF()
            use_unicode = True
        except:
            pdf = FPDF()
            use_unicode = False
        
        pdf.add_page()
        
        # Set font based on availability
        if use_unicode:
            pdf.set_font("DejaVu", "B", 16)
        else:
            pdf.set_font("Arial", "B", 16)
        
        # Title
        pdf.cell(0, 10, f"Event Plan: {event_plan['theme']['name']}", ln=True, align="C")
        pdf.ln(5)
        
        # Date and guest count
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.cell(0, 10, f"Expected Guests: {event_plan.get('guest_count', 'Not specified')}", ln=True)
        pdf.ln(5)
        
        # Theme description
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Theme", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['theme']['description'])
        pdf.ln(5)
        
        # Budget Section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Budget Estimate (INR)", ln=True)
        pdf.set_font("Arial", "", 12)
        
        budget = event_plan.get('budget', {})
        if budget:
            # Budget summary
            pdf.cell(0, 10, f"Total Event Cost: Rs. {budget.get('total_cost', 0):,}", ln=True)
            pdf.cell(0, 10, f"Cost per Person: Rs. {budget.get('cost_per_person', 0):,}", ln=True)
            pdf.ln(3)
            
            # Budget breakdown table
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "Cost Breakdown:", ln=True)
            
            pdf.set_font("Arial", "", 10)
            col_width_item = 120
            col_width_cost = 60
            row_height = 8
            
            # Table headers
            pdf.cell(col_width_item, row_height, "Item", border=1)
            pdf.cell(col_width_cost, row_height, "Cost (INR)", border=1)
            pdf.ln(row_height)
            
            # Budget breakdown data
            for item in budget.get('breakdown', []):
                pdf.cell(col_width_item, row_height, str(item.get('item', '')), border=1)
                pdf.cell(col_width_cost, row_height, f"Rs. {item.get('cost', 0):,}", border=1)
                pdf.ln(row_height)
            
            pdf.ln(5)
        
        # Seating arrangement
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Seating Arrangement", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['seating']['layout'])
        
        # Table details
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Tables:", ln=True)
        
        # Create table for seating
        pdf.set_font("Arial", "", 10)
        col_width = 45
        row_height = 10
        
        # Table headers
        pdf.cell(col_width, row_height, "Table Number", border=1)
        pdf.cell(col_width, row_height, "Shape", border=1)
        pdf.cell(col_width, row_height, "Seats", border=1)
        pdf.cell(col_width, row_height, "Location", border=1)
        pdf.ln(row_height)
        
        # Table data
        for table in event_plan['seating']['tables']:
            if isinstance(table, dict):
                # New format
                pdf.cell(col_width, row_height, str(table.get('table_number', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('shape', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('seats', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('location', '')), border=1)
            else:
                # Old format (string)
                pdf.cell(0, row_height, str(table), border=1, ln=True)
            pdf.ln(row_height)
        
        pdf.ln(5)
        
        # Decoration
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Decoration Ideas", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['decor']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Recipe suggestions
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Recipe Suggestions", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['recipe_suggestions']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Invitation
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Invitation Template", ln=True)
        pdf.set_font("Arial", "I", 12)
        pdf.multi_cell(0, 10, event_plan['invitation'])
        
        # Use BytesIO to avoid encoding issues
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        return pdf_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error creating Unicode PDF: {str(e)}")
        # Fall back to standard method with character replacement
        return create_event_pdf(event_plan)

def get_pdf_download_link(pdf_bytes: bytes, filename: str) -> str:
    """
    Generate a download link for a PDF file
    
    Args:
        pdf_bytes: PDF document as bytes
        filename: Name of the file to download
        
    Returns:
        HTML string with download link
    """
    b64 = base64.b64encode(pdf_bytes).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download Event Plan PDF</a>'
    return href

# Streamlit UI Components
def render_seating_visualization(tables: List):
    """
    Render a visual representation of the seating arrangement
    
    Args:
        tables: List of table dictionaries or strings
    """
    # Convert tables to dataframe for better display
    table_data = []
    
    for i, table in enumerate(tables):
        if isinstance(table, dict):
            # New format
            table_data.append({
                "Table Number": table.get("table_number", i+1),
                "Shape": table.get("shape", "Round"),
                "Seats": table.get("seats", 0),
                "Location": table.get("location", "")
            })
        else:
            # Old format (string) - try to parse
            try:
                # Try to extract information from string format
                table_info = eval(table) if isinstance(table, str) else {"table_number": i+1, "guest_count": 0}
                table_data.append({
                    "Table Number": table_info.get("table_number", i+1),
                    "Shape": "Not specified",
                    "Seats": table_info.get("guest_count", 0),
                    "Location": "Not specified"
                })
            except:
                # Fallback if parsing fails
                table_data.append({
                    "Table Number": i+1,
                    "Shape": "Not specified",
                    "Seats": 0,
                    "Location": "Not specified"
                })
    
    # Create dataframe
    df = pd.DataFrame(table_data)
    
    # Display as a styled table
    st.dataframe(
        df,
        column_config={
            "Table Number": st.column_config.NumberColumn(
                "Table #",
                help="Table number",
                format="%d"
            ),
            "Seats": st.column_config.NumberColumn(
                "Seats",
                help="Number of seats at this table",
                format="%d"
            )
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Calculate total seats
    total_seats = sum(table.get("seats", 0) if isinstance(table, dict) else 0 for table in tables)
    st.caption(f"Total capacity: {total_seats} guests")

def render_budget_visualization(budget: Dict):
    """
    Render a visual representation of the budget breakdown
    
    Args:
        budget: Dictionary containing budget information
    """
    if not budget:
        st.warning("No budget information available")
        return
    
    # Budget summary cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Cost",
            value=f"₹{budget.get('total_cost', 0):,}",
            help="Total estimated cost for the event"
        )
    
    with col2:
        st.metric(
            label="Cost per Person",
            value=f"₹{budget.get('cost_per_person', 0):,}",
            help="Estimated cost per guest"
        )
    
    with col3:
        st.metric(
            label="Food Cost per Person",
            value=f"₹{budget.get('food_cost_per_person', 0):,}",
            help="Food and beverage cost per guest"
        )
    
    # Budget breakdown table
    st.subheader("Cost Breakdown")
    
    breakdown_data = []
    for item in budget.get('breakdown', []):
        breakdown_data.append({
            "Category": item.get('item', ''),
            "Cost (INR)": f"₹{item.get('cost', 0):,}",
            "Percentage": f"{(item.get('cost', 0) / budget.get('total_cost', 1) * 100):.1f}%"
        })
    
    if breakdown_data:
        df = pd.DataFrame(breakdown_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Create a simple bar chart for visualization
        chart_data = pd.DataFrame({
            'Category': [item['Category'] for item in breakdown_data],
            'Cost': [item.get('cost', 0) for item in budget.get('breakdown', [])]
        })
        
        if not chart_data.empty:
            st.bar_chart(chart_data.set_index('Category'))

def render_chatbot_ui():
    """
    Render the event planning chatbot UI
    **NEW: Now includes gamification integration**
    """
    st.markdown("### 🤖 Event Planning Assistant")
    
    # **NEW: Get user info for gamification**
    user = st.session_state.get('user', {})
    user_id = user.get('user_id', '')
    user_role = user.get('role', 'user')
    
    # **NEW: Show XP info for staff/admin**
    if user_role in ['admin', 'staff', 'chef']:
        user_stats = get_user_stats(user_id)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Level", user_stats['level'])
        with col2:
            st.metric("Total XP", user_stats['total_xp'])
        with col3:
            st.metric("Event Activities", user_stats.get('event_activities', 0))
        
        st.info("💡 **Earn XP by using the Event Planning ChatBot!** You get XP for each interaction and successful event plan generation.")

    # Initialize chat history
    if 'event_chat_history' not in st.session_state:
        st.session_state.event_chat_history = []
        
    # Initialize current plan
    if 'current_event_plan' not in st.session_state:
        st.session_state.current_event_plan = None

    # Display chat history
    for message in st.session_state.event_chat_history:
        if message['role'] == 'user':
            st.chat_message('user').write(message['content'])
        else:
            st.chat_message('assistant').write(message['content'])

    # Chat input
    user_query = st.chat_input("Describe the event you want to plan...", key="event_chat_input")

    if user_query:
        # Add user message to chat history
        st.session_state.event_chat_history.append({
            'role': 'user',
            'content': user_query
        })
        
        # Display user message
        st.chat_message('user').write(user_query)
        
        # Generate response
        with st.chat_message('assistant'):
            with st.spinner("Planning your event..."):
                # **NEW: Pass user info for gamification**
                response = generate_event_plan(user_query, user_id, user_role)
                
                if response['success']:
                    event_plan = response['plan']
                    st.session_state.current_event_plan = event_plan
                    
                    # **NEW: Show XP notifications**
                    show_xp_notification()
                    
                    # Display response in a user-friendly format
                    st.markdown(f"### 🎉 {event_plan['theme']['name']}")
                    st.markdown(event_plan['theme']['description'])
                    
                    # Create tabs for different aspects of the plan
                    tabs = st.tabs(["💺 Seating", "💰 Budget", "🎭 Decor", "🍽️ Recipes", "✉️ Invitation", "📄 Export"])
                    
                    with tabs[0]:
                        st.markdown("#### Seating Arrangement")
                        st.markdown(event_plan['seating']['layout'])
                        
                        # Display tables in a user-friendly format
                        st.markdown("##### Tables:")
                        render_seating_visualization(event_plan['seating']['tables'])
                    
                    with tabs[1]:
                        st.markdown("#### Budget Estimate")
                        render_budget_visualization(event_plan.get('budget', {}))
                    
                    with tabs[2]:
                        st.markdown("#### Decoration Ideas")
                        for item in event_plan['decor']:
                            st.markdown(f"- {item}")
                    
                    with tabs[3]:
                        st.markdown("#### Recipe Suggestions")
                        for item in event_plan['recipe_suggestions']:
                            st.markdown(f"- {item}")
                    
                    with tabs[4]:
                        st.markdown("#### Invitation Template")
                        st.info(event_plan['invitation'])
                    
                    with tabs[5]:
                        st.markdown("#### Export Event Plan")
                        
                        # Generate PDF
                        try:
                            # Try Unicode PDF first
                            pdf_bytes = create_unicode_pdf(event_plan)
                        except:
                            # Fall back to standard PDF with character replacement
                            pdf_bytes = create_event_pdf(event_plan)
                        
                        if pdf_bytes:
                            # Create download button
                            st.download_button(
                                label="Download Event Plan as PDF",
                                data=pdf_bytes,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="download_pdf"
                            )
                        else:
                            st.error("Failed to generate PDF. Please try again.")
                            
                            # Provide plain text alternative
                            st.markdown("### Plain Text Export")
                            text_export = f"""
                            # Event Plan: {event_plan['theme']['name']}
                            Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}
                            Expected Guests: {event_plan.get('guest_count', 'Not specified')}
                            
                            ## Theme
                            {event_plan['theme']['description']}
                            
                            ## Budget Estimate (INR)
                            Total Cost: Rs. {event_plan.get('budget', {}).get('total_cost', 0):,}
                            Cost per Person: Rs. {event_plan.get('budget', {}).get('cost_per_person', 0):,}
                            
                            ### Cost Breakdown:
                            """
                            
                            for item in event_plan.get('budget', {}).get('breakdown', []):
                                text_export += f"- {item.get('item', '')}: Rs. {item.get('cost', 0):,}\n"
                            
                            text_export += f"""
                            ## Seating Arrangement
                            {event_plan['seating']['layout']}
                            
                            ### Tables:
                            """
                            
                            for i, table in enumerate(event_plan['seating']['tables']):
                                if isinstance(table, dict):
                                    text_export += f"- Table {table.get('table_number', i+1)}: {table.get('shape', 'Round')} table with {table.get('seats', 0)} seats at {table.get('location', 'unspecified location')}\n"
                                else:
                                    text_export += f"- {table}\n"
                            
                            text_export += "\n## Decoration Ideas\n"
                            for item in event_plan['decor']:
                                text_export += f"- {item}\n"
                                
                            text_export += "\n## Recipe Suggestions\n"
                            for item in event_plan['recipe_suggestions']:
                                text_export += f"- {item}\n"
                                
                            text_export += f"\n## Invitation Template\n{event_plan['invitation']}\n"
                            
                            st.download_button(
                                label="Download as Text File",
                                data=text_export,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                key="download_txt"
                            )
                    
                    # Add assistant message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I've created an event plan for '{event_plan['theme']['name']}' with a budget estimate of ₹{event_plan.get('budget', {}).get('total_cost', 0):,}. You can view the details above and download it as a PDF."
                    })
                else:
                    st.error(f"Failed to generate event plan: {response.get('error', 'Unknown error')}")
                    
                    # Add error message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I'm sorry, I couldn't generate an event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_user_invites():
    """
    Render the user's event invites UI
    **NEW: Now includes event planning quiz for XP earning**
    """
    st.markdown("### 📬 My Event Experience")
    
    # **NEW: Get user info for gamification**
    user = st.session_state.get('user', {})
    user_id = user.get('user_id', '')
    
    # **NEW: Show user stats**
    user_stats = get_user_stats(user_id)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Level", user_stats['level'])
    with col2:
        st.metric("Total XP", user_stats['total_xp'])
    with col3:
        st.metric("Event Activities", user_stats.get('event_activities', 0))
    
    st.info("💡 **Earn XP by learning about event planning!** Take quizzes to gain knowledge and experience points.")
    
    # **NEW: Event planning quiz for users**
    st.divider()
    render_event_quiz_for_users(user_id)
    
    st.divider()
    st.markdown("### 🎉 Event Suggestions")
    st.markdown("Have ideas for restaurant events? Share them here and earn XP!")
    
    # **NEW: Event suggestion form for users to earn XP**
    with st.form("event_suggestion_form"):
        suggestion_title = st.text_input("Event Idea Title", placeholder="e.g., Wine Tasting Night")
        suggestion_description = st.text_area("Describe your event idea", placeholder="Tell us about your event concept...")
        
        if st.form_submit_button("Submit Suggestion", type="primary"):
            if suggestion_title and suggestion_description:
                # Award XP for providing suggestions
                award_event_planning_xp(user_id, 'user', 'event_suggestion')
                st.success("🎉 Thank you for your suggestion! You've earned XP for contributing ideas.")
                show_xp_notification()
            else:
                st.error("Please fill in both the title and description.")

# Main Event Planner Function
def event_planner():
    """
    Main function to render the event planner UI based on user role
    **NEW: Now includes gamification for all user types**
    """
    st.title("🎉 Event Planning System")

    # Check if user is logged in
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("Please log in to access the Event Planning System")
        return

    # Get user role
    user_role = st.session_state.user.get('role', 'user')

    # Different views based on role
    if user_role in ['admin', 'staff', 'chef']:
        # Staff view with chatbot and gamification
        render_chatbot_ui()
    else:
        # Customer view with quiz and suggestions for XP
        render_user_invites()

# For testing the module independently
if __name__ == "__main__":
    st.set_page_config(page_title="Event Planning System", layout="wide")

    # Mock session state for testing
    if 'user' not in st.session_state:
        st.session_state.user = {
            'user_id': 'test_user',
            'username': 'Test User',
            'role': 'admin'
        }

    event_planner()
