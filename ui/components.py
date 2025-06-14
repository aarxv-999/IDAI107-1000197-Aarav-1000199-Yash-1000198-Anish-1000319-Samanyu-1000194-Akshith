"""
UI Components for the Smart Restaurant Menu Management App.
Contains authentication, gamification, and other UI elements.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
import logging
import random

logger = logging.getLogger(__name__)

# Authentication Components
def initialize_session_state():
    """Initialize session state variables for authentication"""
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'auth_error' not in st.session_state:
        st.session_state.auth_error = None

def get_firestore_client():
    """Get Firestore client"""
    try:
        return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client: {str(e)}")
        return None

def authenticate_user(username, password):
    """Authenticate user against Firestore"""
    try:
        db = get_firestore_client()
        if not db:
            return None, "Database connection failed"
        
        # Query users collection
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).where('password', '==', password)
        docs = query.stream()
        
        user_doc = None
        for doc in docs:
            user_doc = doc
            break
        
        if user_doc:
            user_data = user_doc.to_dict()
            user_data['user_id'] = doc.id  # Add document ID as user_id
            return user_data, None
        else:
            return None, "Invalid username or password"
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None, f"Authentication error: {str(e)}"

def register_user(username, password, role='user'):
    """Register a new user"""
    try:
        db = get_firestore_client()
        if not db:
            return False, "Database connection failed"
        
        # Check if username already exists
        users_ref = db.collection('users')
        existing_query = users_ref.where('username', '==', username)
        existing_docs = list(existing_query.stream())
        
        if existing_docs:
            return False, "Username already exists"
        
        # Create new user
        user_data = {
            'username': username,
            'password': password,  # In production, hash this!
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        doc_ref = users_ref.add(user_data)
        user_data['user_id'] = doc_ref[1].id
        
        return True, "User registered successfully"
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"

def render_auth_ui():
    """Render authentication UI in sidebar"""
    if st.session_state.is_authenticated:
        user = st.session_state.user
        st.sidebar.success(f"Welcome, {user['username']}!")
        st.sidebar.write(f"Role: {user['role'].title()}")
        
        if st.sidebar.button("Logout"):
            st.session_state.is_authenticated = False
            st.session_state.user = None
            st.rerun()
        
        return True
    else:
        st.sidebar.subheader("Login / Register")
        
        # Toggle between login and register
        auth_mode = st.sidebar.radio("Mode", ["Login", "Register"])
        
        with st.sidebar.form("auth_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if auth_mode == "Register":
                role = st.selectbox("Role", ["user", "staff", "chef", "admin"])
            
            submit_button = st.form_submit_button(auth_mode)
            
            if submit_button:
                if not username or not password:
                    st.sidebar.error("Please fill in all fields")
                elif auth_mode == "Login":
                    user_data, error = authenticate_user(username, password)
                    if user_data:
                        st.session_state.is_authenticated = True
                        st.session_state.user = user_data
                        st.sidebar.success("Login successful!")
                        st.rerun()
                    else:
                        st.sidebar.error(error)
                else:  # Register
                    success, message = register_user(username, password, role)
                    if success:
                        st.sidebar.success(message)
                        # Auto-login after registration
                        user_data, _ = authenticate_user(username, password)
                        if user_data:
                            st.session_state.is_authenticated = True
                            st.session_state.user = user_data
                            st.rerun()
                    else:
                        st.sidebar.error(message)
        
        return False

def auth_required(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        if not st.session_state.is_authenticated:
            st.warning("Please log in to access this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper

def get_current_user():
    """Get current authenticated user"""
    return st.session_state.get('user')

def is_user_role(required_role):
    """Check if current user has required role"""
    user = get_current_user()
    if not user:
        return False
    return user.get('role') == required_role

# Gamification Components
def display_user_stats_sidebar(user_id):
    """Display user gamification stats in sidebar with fixed progress calculation"""
    try:
        from modules.leftover import get_user_stats
        
        # Get user stats
        user_stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎮 Your Stats")
        
        # Extract stats with safe defaults
        total_xp = max(0, user_stats.get('total_xp', 0))
        level = max(1, user_stats.get('level', 1))
        
        # Calculate current level XP and progress
        xp_for_current_level = (level - 1) * 100
        current_level_xp = total_xp - xp_for_current_level
        xp_needed = 100 - current_level_xp
        
        # Ensure current_level_xp is within bounds
        current_level_xp = max(0, min(100, current_level_xp))
        
        # Calculate progress as a value between 0.0 and 1.0
        progress = current_level_xp / 100.0
        progress = max(0.0, min(1.0, progress))  # Clamp between 0 and 1
        
        # Display metrics
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Level", level)
        with col2:
            st.metric("Total XP", f"{total_xp:,}")
        
        # Progress bar with safe values
        st.sidebar.progress(progress, text=f"{max(0, xp_needed)} XP to next level")
        
        # Additional stats
        recipes_generated = user_stats.get('recipes_generated', 0)
        quizzes_completed = user_stats.get('quizzes_completed', 0)
        
        if recipes_generated > 0 or quizzes_completed > 0:
            st.sidebar.markdown("**Activity:**")
            if recipes_generated > 0:
                st.sidebar.write(f"🍽️ Recipes: {recipes_generated}")
            if quizzes_completed > 0:
                st.sidebar.write(f"🧠 Quizzes: {quizzes_completed}")
        
        logger.info(f"Displayed stats for user {user_id}: Level {level}, XP {total_xp}, Progress {progress:.2f}")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_amount, activity_type):
    """Show XP notification"""
    st.success(f"🎉 +{xp_amount} XP earned for {activity_type}!")

def display_gamification_dashboard(user_id):
    """Display comprehensive gamification dashboard"""
    st.title("🎮 Gamification Hub")
    
    try:
        from modules.leftover import get_user_stats, get_leaderboard
        
        # Get user stats
        user_stats = get_user_stats(user_id)
        
        # Overview metrics
        st.subheader("📊 Your Progress")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Level", user_stats.get('level', 1))
        
        with col2:
            st.metric("Total XP", f"{user_stats.get('total_xp', 0):,}")
        
        with col3:
            st.metric("Recipes Generated", user_stats.get('recipes_generated', 0))
        
        with col4:
            st.metric("Quizzes Completed", user_stats.get('quizzes_completed', 0))
        
        # Progress visualization
        total_xp = user_stats.get('total_xp', 0)
        level = user_stats.get('level', 1)
        
        # Calculate progress for current level
        xp_for_current_level = (level - 1) * 100
        current_level_xp = total_xp - xp_for_current_level
        progress = min(current_level_xp / 100.0, 1.0)
        
        st.subheader("📈 Level Progress")
        st.progress(progress, text=f"Level {level} - {current_level_xp}/100 XP")
        
        # Achievements section
        st.subheader("🏆 Achievements")
        
        achievements = []
        if user_stats.get('recipes_generated', 0) >= 1:
            achievements.append("🍽️ Recipe Novice - Generated your first recipe")
        if user_stats.get('recipes_generated', 0) >= 10:
            achievements.append("🍽️ Recipe Expert - Generated 10+ recipes")
        if user_stats.get('quizzes_completed', 0) >= 1:
            achievements.append("🧠 Quiz Starter - Completed your first quiz")
        if user_stats.get('quizzes_completed', 0) >= 5:
            achievements.append("🧠 Quiz Master - Completed 5+ quizzes")
        if user_stats.get('level', 1) >= 5:
            achievements.append("⭐ Rising Star - Reached Level 5")
        if user_stats.get('level', 1) >= 10:
            achievements.append("🌟 Culinary Expert - Reached Level 10")
        
        if achievements:
            for achievement in achievements:
                st.success(achievement)
        else:
            st.info("Complete activities to unlock achievements!")
        
        # Leaderboard
        st.subheader("🏅 Leaderboard")
        
        try:
            leaderboard = get_leaderboard()
            if leaderboard:
                df = pd.DataFrame(leaderboard)
                df.index = df.index + 1  # Start ranking from 1
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No leaderboard data available yet.")
        except Exception as e:
            logger.error(f"Error loading leaderboard: {str(e)}")
            st.error("Error loading leaderboard")
        
        # Activity suggestions
        st.subheader("💡 Earn More XP")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **Recipe Generation:**
            - Generate recipes: +10 XP each
            - Use priority ingredients: +5 bonus XP
            """)
        
        with col2:
            st.info("""
            **Cooking Quiz:**
            - Complete quiz: +15 XP
            - Perfect score: +10 bonus XP
            """)
        
    except Exception as e:
        logger.error(f"Error in gamification dashboard: {str(e)}")
        st.error("Error loading gamification dashboard")

def render_cooking_quiz(ingredients, user_id):
    """Render cooking quiz component"""
    st.subheader("🧠 Cooking Knowledge Quiz")
    
    # Quiz questions (sample)
    quiz_questions = [
        {
            "question": "What is the ideal internal temperature for cooked chicken?",
            "options": ["145°F", "160°F", "165°F", "180°F"],
            "correct": 2,
            "explanation": "165°F (74°C) is the safe internal temperature for chicken."
        },
        {
            "question": "Which cooking method uses dry heat?",
            "options": ["Boiling", "Steaming", "Roasting", "Poaching"],
            "correct": 2,
            "explanation": "Roasting uses dry heat in an oven."
        },
        {
            "question": "What does 'mise en place' mean?",
            "options": ["Cooking technique", "Everything in place", "French sauce", "Knife skill"],
            "correct": 1,
            "explanation": "'Mise en place' means having all ingredients prepared and organized before cooking."
        }
    ]
    
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
        st.session_state.quiz_answers = {}
        st.session_state.quiz_score = 0
    
    if not st.session_state.quiz_started:
        st.info("Test your culinary knowledge and earn XP!")
        if st.button("Start Quiz", type="primary"):
            st.session_state.quiz_started = True
            st.session_state.quiz_answers = {}
            st.rerun()
    else:
        # Display quiz questions
        with st.form("cooking_quiz"):
            for i, q in enumerate(quiz_questions):
                st.write(f"**Question {i+1}:** {q['question']}")
                answer = st.radio(
                    f"Select your answer for question {i+1}:",
                    options=q['options'],
                    key=f"q_{i}"
                )
                st.session_state.quiz_answers[i] = q['options'].index(answer)
            
            submitted = st.form_submit_button("Submit Quiz", type="primary")
            
            if submitted:
                # Calculate score
                correct_answers = 0
                total_questions = len(quiz_questions)
                
                for i, q in enumerate(quiz_questions):
                    if st.session_state.quiz_answers.get(i) == q['correct']:
                        correct_answers += 1
                
                score_percentage = (correct_answers / total_questions) * 100
                st.session_state.quiz_score = score_percentage
                
                # Display results
                st.subheader("📊 Quiz Results")
                st.write(f"Score: {correct_answers}/{total_questions} ({score_percentage:.0f}%)")
                
                # Award XP
                base_xp = 15
                bonus_xp = 10 if score_percentage == 100 else 0
                total_xp = base_xp + bonus_xp
                
                try:
                    from modules.leftover import award_recipe_xp
                    award_recipe_xp(user_id, total_xp, "quiz")
                    show_xp_notification(total_xp, "completing cooking quiz")
                except Exception as e:
                    logger.error(f"Error awarding quiz XP: {str(e)}")
                
                # Show explanations
                st.subheader("📚 Explanations")
                for i, q in enumerate(quiz_questions):
                    user_answer = st.session_state.quiz_answers.get(i)
                    correct_answer = q['correct']
                    
                    if user_answer == correct_answer:
                        st.success(f"Q{i+1}: ✅ Correct! {q['explanation']}")
                    else:
                        st.error(f"Q{i+1}: ❌ Incorrect. {q['explanation']}")
                
                # Reset quiz
                if st.button("Take Quiz Again"):
                    st.session_state.quiz_started = False
                    st.session_state.quiz_answers = {}
                    st.rerun()

def display_daily_challenge(user_id):
    """Display daily cooking challenge"""
    st.subheader("🎯 Daily Challenge")
    
    # Generate a daily challenge based on date
    today = datetime.now().date()
    random.seed(today.toordinal())  # Consistent challenge per day
    
    challenges = [
        "Generate a recipe using at least 3 vegetables",
        "Create a recipe with ingredients expiring in 2 days",
        "Generate a vegetarian recipe",
        "Create a recipe that takes less than 30 minutes",
        "Generate a recipe using leftover rice or pasta"
    ]
    
    daily_challenge = random.choice(challenges)
    
    st.info(f"**Today's Challenge:** {daily_challenge}")
    st.write("Complete this challenge to earn bonus XP!")

# Leftover Management Components
def leftover_input_csv():
    """Handle CSV file upload for leftovers"""
    st.sidebar.subheader("📁 Upload CSV")
    uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            if 'ingredient' in df.columns:
                ingredients = df['ingredient'].dropna().tolist()
                st.sidebar.success(f"Loaded {len(ingredients)} ingredients from CSV")
                return [ing.lower().strip() for ing in ingredients]
            else:
                st.sidebar.error("CSV must have an 'ingredient' column")
        except Exception as e:
            st.sidebar.error(f"Error reading CSV: {str(e)}")
    
    return []

def leftover_input_manual():
    """Handle manual input for leftovers"""
    st.sidebar.subheader("✏️ Manual Input")
    manual_input = st.sidebar.text_area(
        "Enter ingredients (one per line)",
        placeholder="tomatoes\nonions\ngarlic\nrice"
    )
    
    if manual_input:
        ingredients = [ing.strip().lower() for ing in manual_input.split('\n') if ing.strip()]
        if ingredients:
            st.sidebar.success(f"Added {len(ingredients)} ingredients manually")
        return ingredients
    
    return []

def leftover_input_firebase():
    """Handle Firebase integration for leftovers"""
    st.sidebar.subheader("🔥 Firebase Integration")
    
    use_firebase = st.sidebar.checkbox("Use current inventory from Firebase")
    
    if use_firebase:
        max_ingredients = st.sidebar.slider(
            "Max ingredients to fetch", 
            min_value=5, 
            max_value=50, 
            value=20,
            help="Limit the number of ingredients to prioritize those expiring soon"
        )
        
        if st.sidebar.button("📥 Fetch Priority Ingredients"):
            try:
                from modules.leftover import get_priority_ingredients
                ingredients, detailed_info = get_priority_ingredients(max_ingredients)
                
                if ingredients:
                    st.sidebar.success(f"✅ Fetched {len(ingredients)} priority ingredients")
                    return ingredients, detailed_info
                else:
                    st.sidebar.warning("No ingredients found in Firebase inventory")
            except Exception as e:
                st.sidebar.error(f"Firebase error: {str(e)}")
                logger.error(f"Firebase integration error: {str(e)}")
    
    return [], []

def award_recipe_generation_xp(user_id, num_recipes):
    """Award XP for recipe generation"""
    try:
        from modules.leftover import award_recipe_xp
        
        base_xp = 10 * num_recipes  # 10 XP per recipe
        award_recipe_xp(user_id, base_xp, "recipe_generation")
        
        show_xp_notification(base_xp, f"generating {num_recipes} recipes")
        
    except Exception as e:
        logger.error(f"Error awarding recipe generation XP: {str(e)}")
