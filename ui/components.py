"""
UI Components for the Smart Restaurant Menu Management App.
Includes authentication, gamification, and utility components.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
import hashlib
import secrets
import logging
from typing import Dict, List, Optional, Tuple
import random

# Import XP utilities
from modules.xp_utils import (
    calculate_level_from_xp, get_xp_progress, get_level_title, 
    calculate_xp_reward, format_xp_display, get_next_milestone,
    XP_REWARDS, LEVEL_TITLES
)

logger = logging.getLogger(__name__)

# Authentication Functions
def initialize_session_state():
    """Initialize session state variables for authentication"""
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'auth_error' not in st.session_state:
        st.session_state.auth_error = None

def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
    """Hash password with salt"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    password_hash = hashlib.pbkdf2_hmac('sha256', 
                                       password.encode('utf-8'), 
                                       salt.encode('utf-8'), 
                                       100000)
    return password_hash.hex(), salt

def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """Verify password against hash"""
    password_hash, _ = hash_password(password, salt)
    return password_hash == hashed_password

def register_user(username: str, password: str, role: str = 'user') -> bool:
    """Register a new user"""
    try:
        db = firestore.client()
        
        # Check if username already exists
        users_ref = db.collection('users')
        existing_user = users_ref.where('username', '==', username).limit(1).get()
        
        if existing_user:
            st.session_state.auth_error = "Username already exists"
            return False
        
        # Hash password
        password_hash, salt = hash_password(password)
        
        # Generate user ID
        user_id = f"user_{secrets.token_hex(8)}"
        
        # Create user document
        user_data = {
            'user_id': user_id,
            'username': username,
            'password_hash': password_hash,
            'salt': salt,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
            'last_login': firestore.SERVER_TIMESTAMP
        }
        
        users_ref.document(user_id).set(user_data)
        
        # Initialize user stats
        stats_data = {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'campaigns_created': 0,
            'quizzes_completed': 0,
            'perfect_quizzes': 0,
            'current_streak': 0,
            'longest_streak': 0,
            'last_activity': firestore.SERVER_TIMESTAMP,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        db.collection('user_stats').document(user_id).set(stats_data)
        
        logger.info(f"User {username} registered successfully with ID {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        st.session_state.auth_error = f"Registration failed: {str(e)}"
        return False

def login_user(username: str, password: str) -> bool:
    """Login user"""
    try:
        db = firestore.client()
        
        # Find user by username
        users_ref = db.collection('users')
        user_docs = users_ref.where('username', '==', username).limit(1).get()
        
        if not user_docs:
            st.session_state.auth_error = "Invalid username or password"
            return False
        
        user_doc = user_docs[0]
        user_data = user_doc.to_dict()
        
        # Verify password
        if verify_password(password, user_data['password_hash'], user_data['salt']):
            # Update last login
            users_ref.document(user_doc.id).update({
                'last_login': firestore.SERVER_TIMESTAMP
            })
            
            # Set session state
            st.session_state.is_authenticated = True
            st.session_state.user = user_data
            st.session_state.auth_error = None
            
            logger.info(f"User {username} logged in successfully")
            return True
        else:
            st.session_state.auth_error = "Invalid username or password"
            return False
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        st.session_state.auth_error = f"Login failed: {str(e)}"
        return False

def logout_user():
    """Logout current user"""
    st.session_state.is_authenticated = False
    st.session_state.user = None
    st.session_state.auth_error = None
    logger.info("User logged out")

def get_current_user() -> Optional[Dict]:
    """Get current authenticated user"""
    return st.session_state.get('user')

def is_user_role(required_roles: List[str]) -> bool:
    """Check if current user has required role"""
    user = get_current_user()
    if not user:
        return False
    return user.get('role') in required_roles

def auth_required(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        if not st.session_state.get('is_authenticated', False):
            st.warning("Please log in to access this feature")
            return None
        return func(*args, **kwargs)
    return wrapper

def render_auth_ui():
    """Render authentication UI in sidebar"""
    if st.session_state.get('is_authenticated', False):
        user = st.session_state.get('user', {})
        st.sidebar.success(f"Welcome, {user.get('username', 'User')}!")
        st.sidebar.write(f"Role: {user.get('role', 'user').title()}")
        
        if st.sidebar.button("Logout", type="secondary"):
            logout_user()
            st.rerun()
    else:
        # Login/Register tabs
        auth_tab = st.sidebar.radio("Authentication", ["Login", "Register"])
        
        if auth_tab == "Login":
            with st.sidebar.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                if st.form_submit_button("Login", type="primary"):
                    if username and password:
                        if login_user(username, password):
                            st.rerun()
                    else:
                        st.session_state.auth_error = "Please enter username and password"
        
        else:  # Register
            with st.sidebar.form("register_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                role = st.selectbox("Role", ["user", "staff", "chef", "admin"])
                
                if st.form_submit_button("Register", type="primary"):
                    if not username or not password:
                        st.session_state.auth_error = "Please fill all fields"
                    elif password != confirm_password:
                        st.session_state.auth_error = "Passwords don't match"
                    elif len(password) < 6:
                        st.session_state.auth_error = "Password must be at least 6 characters"
                    else:
                        if register_user(username, password, role):
                            st.success("Registration successful! Please login.")
                            st.rerun()
        
        # Show auth error if any
        if st.session_state.get('auth_error'):
            st.sidebar.error(st.session_state.auth_error)
            st.session_state.auth_error = None

# Gamification Functions
def get_user_stats(user_id: str) -> Dict:
    """Get user gamification stats"""
    try:
        db = firestore.client()
        user_stats_ref = db.collection('user_stats').document(user_id)
        user_stats_doc = user_stats_ref.get()
        
        if user_stats_doc.exists:
            stats = user_stats_doc.to_dict()
            # Ensure all required fields exist
            default_stats = {
                'total_xp': 0,
                'level': 1,
                'recipes_generated': 0,
                'campaigns_created': 0,
                'quizzes_completed': 0,
                'perfect_quizzes': 0,
                'current_streak': 0,
                'longest_streak': 0
            }
            
            # Merge with defaults
            for key, default_value in default_stats.items():
                if key not in stats:
                    stats[key] = default_value
            
            # Recalculate level from XP to ensure consistency
            stats['level'] = calculate_level_from_xp(stats['total_xp'])
            
            return stats
        else:
            # Create default stats
            default_stats = {
                'user_id': user_id,
                'total_xp': 0,
                'level': 1,
                'recipes_generated': 0,
                'campaigns_created': 0,
                'quizzes_completed': 0,
                'perfect_quizzes': 0,
                'current_streak': 0,
                'longest_streak': 0,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            }
            
            user_stats_ref.set(default_stats)
            return default_stats
            
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'campaigns_created': 0,
            'quizzes_completed': 0,
            'perfect_quizzes': 0,
            'current_streak': 0,
            'longest_streak': 0
        }

def award_recipe_xp(user_id: str, recipe_count: int = 1) -> int:
    """Award XP for recipe generation"""
    try:
        xp_earned = calculate_xp_reward('recipe_generation', recipe_count=recipe_count)
        
        db = firestore.client()
        user_stats_ref = db.collection('user_stats').document(user_id)
        
        # Get current stats
        current_stats = get_user_stats(user_id)
        old_level = current_stats['level']
        
        # Update stats
        new_total_xp = current_stats['total_xp'] + xp_earned
        new_level = calculate_level_from_xp(new_total_xp)
        
        update_data = {
            'total_xp': new_total_xp,
            'level': new_level,
            'recipes_generated': current_stats['recipes_generated'] + recipe_count,
            'last_activity': firestore.SERVER_TIMESTAMP
        }
        
        user_stats_ref.update(update_data)
        
        # Check for level up
        if new_level > old_level:
            show_level_up_notification(old_level, new_level)
        
        logger.info(f"Awarded {xp_earned} XP to user {user_id} for {recipe_count} recipes")
        return xp_earned
        
    except Exception as e:
        logger.error(f"Error awarding recipe XP: {str(e)}")
        return 0

def award_recipe_generation_xp(user_id: str, recipe_count: int = 1):
    """Award XP for recipe generation with notification"""
    xp_earned = award_recipe_xp(user_id, recipe_count)
    if xp_earned > 0:
        show_xp_notification(xp_earned, f"Generating {recipe_count} recipe{'s' if recipe_count > 1 else ''}")

def display_user_stats_sidebar(user_id: str):
    """Display user stats in sidebar"""
    try:
        stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎮 Your Progress")
        
        # Level and XP
        level = stats['level']
        total_xp = stats['total_xp']
        title = get_level_title(level)
        
        st.sidebar.metric("Level", f"{level}")
        st.sidebar.caption(f"**{title}**")
        st.sidebar.metric("Total XP", format_xp_display(total_xp))
        
        # Progress to next level
        try:
            current_level_xp, xp_needed, progress_pct = get_xp_progress(total_xp, level)
            
            if xp_needed > 0:
                st.sidebar.progress(progress_pct / 100, text=f"Next Level: {progress_pct:.1f}%")
                st.sidebar.caption(f"Need {xp_needed:,} more XP")
            else:
                st.sidebar.success("🏆 Max Level Reached!")
                
        except Exception as e:
            logger.error(f"Error displaying progress: {str(e)}")
            st.sidebar.caption("Progress calculation error")
        
        # Quick stats
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Recipes", stats.get('recipes_generated', 0))
        with col2:
            st.metric("Streak", f"{stats.get('current_streak', 0)} days")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_earned: int, activity: str):
    """Show XP earned notification"""
    if xp_earned > 0:
        st.success(f"🎉 **+{xp_earned} XP** earned for {activity}!")

def show_level_up_notification(old_level: int, new_level: int):
    """Show level up notification"""
    new_title = get_level_title(new_level)
    st.balloons()
    st.success(f"🎉 **LEVEL UP!** You reached Level {new_level}: {new_title}")

def display_gamification_dashboard(user_id: str):
    """Display comprehensive gamification dashboard"""
    st.title("🎮 Gamification Hub")
    
    try:
        stats = get_user_stats(user_id)
        
        # Main stats
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Level", stats['level'])
            st.caption(get_level_title(stats['level']))
        
        with col2:
            st.metric("Total XP", format_xp_display(stats['total_xp']))
        
        with col3:
            st.metric("Recipes Generated", stats.get('recipes_generated', 0))
        
        with col4:
            st.metric("Current Streak", f"{stats.get('current_streak', 0)} days")
        
        # Progress chart
        st.markdown("### 📈 Level Progress")
        
        try:
            current_level_xp, xp_needed, progress_pct = get_xp_progress(stats['total_xp'], stats['level'])
            
            if xp_needed > 0:
                progress_data = {
                    'Category': ['Current XP', 'Needed XP'],
                    'XP': [current_level_xp, xp_needed],
                    'Color': ['#1f77b4', '#d62728']
                }
                
                fig = px.pie(progress_data, values='XP', names='Category', 
                           title=f"Progress to Level {stats['level'] + 1}",
                           color_discrete_sequence=['#1f77b4', '#d62728'])
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.success("🏆 Maximum level reached!")
                
        except Exception as e:
            logger.error(f"Error creating progress chart: {str(e)}")
            st.error("Error displaying progress chart")
        
        # Activity breakdown
        st.markdown("### 🏆 Activity Summary")
        
        activity_data = {
            'Activity': ['Recipes Generated', 'Campaigns Created', 'Quizzes Completed', 'Perfect Quizzes'],
            'Count': [
                stats.get('recipes_generated', 0),
                stats.get('campaigns_created', 0), 
                stats.get('quizzes_completed', 0),
                stats.get('perfect_quizzes', 0)
            ]
        }
        
        if sum(activity_data['Count']) > 0:
            fig = px.bar(activity_data, x='Activity', y='Count', 
                        title="Your Activities",
                        color='Count',
                        color_continuous_scale='viridis')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Start using the app to see your activity summary!")
        
        # Next milestone
        next_milestone = get_next_milestone(stats['level'])
        if next_milestone:
            st.markdown("### 🎯 Next Milestone")
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**Level {next_milestone['level']}:** {next_milestone['title']}")
            
            with col2:
                xp_needed_for_milestone = next_milestone['xp_required'] - stats['total_xp']
                st.info(f"**XP Needed:** {xp_needed_for_milestone:,}")
        
    except Exception as e:
        logger.error(f"Error displaying gamification dashboard: {str(e)}")
        st.error("Error loading gamification dashboard")

def render_cooking_quiz(ingredients: List[str], user_id: str):
    """Render cooking knowledge quiz"""
    st.markdown("### 🧠 Cooking Knowledge Quiz")
    st.markdown("Test your culinary knowledge and earn XP!")
    
    # Generate quiz questions
    questions = generate_quiz_questions(ingredients)
    
    if not questions:
        st.error("Unable to generate quiz questions")
        return
    
    # Quiz form
    with st.form("cooking_quiz"):
        user_answers = []
        
        for i, question in enumerate(questions):
            st.markdown(f"**Question {i+1}:** {question['question']}")
            answer = st.radio(
                f"Select your answer for question {i+1}:",
                question['options'],
                key=f"q_{i}",
                label_visibility="collapsed"
            )
            user_answers.append(answer)
        
        submitted = st.form_submit_button("Submit Quiz", type="primary")
        
        if submitted:
            score = calculate_quiz_score(questions, user_answers)
            total_questions = len(questions)
            
            # Display results
            st.markdown("### 📊 Quiz Results")
            
            if score == total_questions:
                st.success(f"🎉 Perfect Score! {score}/{total_questions}")
                xp_earned = calculate_xp_reward('cooking_quiz_perfect')
                award_quiz_xp(user_id, score, total_questions, perfect=True)
            elif score >= total_questions * 0.7:
                st.success(f"✅ Great job! {score}/{total_questions}")
                xp_earned = calculate_xp_reward('cooking_quiz_correct') * score
                award_quiz_xp(user_id, score, total_questions)
            else:
                st.warning(f"📚 Keep studying! {score}/{total_questions}")
                xp_earned = calculate_xp_reward('cooking_quiz_correct') * score
                award_quiz_xp(user_id, score, total_questions)
            
            # Show correct answers
            with st.expander("📖 Review Answers"):
                for i, question in enumerate(questions):
                    user_answer = user_answers[i]
                    correct_answer = question['correct_answer']
                    
                    if user_answer == correct_answer:
                        st.success(f"Q{i+1}: ✅ {user_answer}")
                    else:
                        st.error(f"Q{i+1}: ❌ Your answer: {user_answer}")
                        st.info(f"Correct answer: {correct_answer}")

def generate_quiz_questions(ingredients: List[str]) -> List[Dict]:
    """Generate cooking quiz questions"""
    # Sample quiz questions - in a real app, this could be more sophisticated
    all_questions = [
        {
            "question": "What is the ideal internal temperature for cooked chicken?",
            "options": ["145°F (63°C)", "165°F (74°C)", "180°F (82°C)", "200°F (93°C)"],
            "correct_answer": "165°F (74°C)"
        },
        {
            "question": "Which cooking method uses dry heat?",
            "options": ["Boiling", "Steaming", "Roasting", "Poaching"],
            "correct_answer": "Roasting"
        },
        {
            "question": "What does 'mise en place' mean in cooking?",
            "options": ["Cooking technique", "Everything in its place", "French sauce", "Knife skill"],
            "correct_answer": "Everything in its place"
        },
        {
            "question": "Which ingredient is used to thicken sauces?",
            "options": ["Salt", "Sugar", "Flour", "Vinegar"],
            "correct_answer": "Flour"
        },
        {
            "question": "What is the purpose of resting meat after cooking?",
            "options": ["Cool it down", "Redistribute juices", "Add flavor", "Tenderize"],
            "correct_answer": "Redistribute juices"
        }
    ]
    
    # Return random selection of questions
    import random
    return random.sample(all_questions, min(3, len(all_questions)))

def calculate_quiz_score(questions: List[Dict], user_answers: List[str]) -> int:
    """Calculate quiz score"""
    score = 0
    for question, user_answer in zip(questions, user_answers):
        if user_answer == question['correct_answer']:
            score += 1
    return score

def award_quiz_xp(user_id: str, score: int, total_questions: int, perfect: bool = False):
    """Award XP for quiz completion"""
    try:
        if perfect:
            xp_earned = calculate_xp_reward('cooking_quiz_perfect')
        else:
            xp_earned = calculate_xp_reward('cooking_quiz_correct') * score
        
        db = firestore.client()
        user_stats_ref = db.collection('user_stats').document(user_id)
        
        # Get current stats
        current_stats = get_user_stats(user_id)
        old_level = current_stats['level']
        
        # Update stats
        new_total_xp = current_stats['total_xp'] + xp_earned
        new_level = calculate_level_from_xp(new_total_xp)
        
        update_data = {
            'total_xp': new_total_xp,
            'level': new_level,
            'quizzes_completed': current_stats['quizzes_completed'] + 1,
            'last_activity': firestore.SERVER_TIMESTAMP
        }
        
        if perfect:
            update_data['perfect_quizzes'] = current_stats.get('perfect_quizzes', 0) + 1
        
        user_stats_ref.update(update_data)
        
        # Show notifications
        show_xp_notification(xp_earned, f"Quiz ({score}/{total_questions})")
        
        if new_level > old_level:
            show_level_up_notification(old_level, new_level)
        
        logger.info(f"Awarded {xp_earned} XP to user {user_id} for quiz score {score}/{total_questions}")
        
    except Exception as e:
        logger.error(f"Error awarding quiz XP: {str(e)}")

def display_daily_challenge(user_id: str):
    """Display daily cooking challenge"""
    st.markdown("### 🎯 Daily Challenge")
    
    # Generate daily challenge based on date
    today = datetime.now().date()
    challenge_seed = int(today.strftime("%Y%m%d"))
    random.seed(challenge_seed)
    
    challenges = [
        "Create a recipe using only 5 ingredients",
        "Design a vegetarian main course",
        "Plan a complete breakfast menu",
        "Suggest a recipe for food waste reduction",
        "Create a kid-friendly healthy snack"
    ]
    
    daily_challenge = random.choice(challenges)
    
    st.info(f"**Today's Challenge:** {daily_challenge}")
    
    if st.button("Complete Challenge", key="daily_challenge"):
        # Award challenge XP
        xp_earned = calculate_xp_reward('daily_challenge_complete')
        
        try:
            db = firestore.client()
            user_stats_ref = db.collection('user_stats').document(user_id)
            
            current_stats = get_user_stats(user_id)
            old_level = current_stats['level']
            
            new_total_xp = current_stats['total_xp'] + xp_earned
            new_level = calculate_level_from_xp(new_total_xp)
            
            user_stats_ref.update({
                'total_xp': new_total_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            })
            
            show_xp_notification(xp_earned, "Daily Challenge")
            
            if new_level > old_level:
                show_level_up_notification(old_level, new_level)
                
        except Exception as e:
            logger.error(f"Error awarding daily challenge XP: {str(e)}")

# CSV Input Functions
def leftover_input_csv():
    """Handle CSV file upload for leftover ingredients"""
    st.subheader("Upload CSV File")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Display the uploaded data
            st.write("Uploaded data:")
            st.dataframe(df)
            
            # Extract ingredients (assuming there's an 'ingredient' column)
            if 'ingredient' in df.columns:
                ingredients = df['ingredient'].dropna().tolist()
                return [ing.lower().strip() for ing in ingredients]
            else:
                st.error("CSV file must contain an 'ingredient' column")
                return []
                
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")
            return []
    
    return []

def leftover_input_manual():
    """Handle manual input of leftover ingredients"""
    st.subheader("Manual Input")
    
    ingredients_text = st.text_area(
        "Enter ingredients (one per line or comma-separated)",
        placeholder="tomatoes\nonions\ngarlic\nrice\n\nOr: tomatoes, onions, garlic, rice",
        height=150
    )
    
    if ingredients_text:
        # Handle both line-separated and comma-separated input
        if '\n' in ingredients_text:
            ingredients = [ing.strip().lower() for ing in ingredients_text.split('\n') if ing.strip()]
        else:
            ingredients = [ing.strip().lower() for ing in ingredients_text.split(',') if ing.strip()]
        
        return ingredients
    
    return []

def leftover_input_firebase():
    """Handle Firebase inventory input for leftover ingredients"""
    st.subheader("Firebase Inventory")
    
    max_ingredients = st.slider(
        "Maximum ingredients to fetch", 
        min_value=5, 
        max_value=50, 
        value=20,
        help="Limit the number of ingredients to prioritize those expiring soon"
    )
    
    if st.button("Fetch Priority Ingredients", type="primary"):
        try:
            # This would integrate with your Firebase inventory
            # For now, return sample data
            st.info("Firebase integration would fetch ingredients here")
            return []
            
        except Exception as e:
            st.error(f"Firebase error: {str(e)}")
            return []
    
    return []
