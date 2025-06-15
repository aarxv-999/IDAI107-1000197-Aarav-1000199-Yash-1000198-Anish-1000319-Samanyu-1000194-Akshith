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
import hashlib
import re

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
    if 'show_signup' not in st.session_state:
        st.session_state.show_signup = False

def get_firestore_client():
    """Get Firestore client for authentication - using MAIN Firebase"""
    try:
        # Use the main Firebase app (default) for user authentication
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            # Initialize main Firebase if not already done
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client for auth: {str(e)}")
        return None

def get_event_firestore_client():
    """Get event Firestore client for other features"""
    try:
        # Use the event Firebase app for other features
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            # Initialize event Firebase if not already done
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting event Firestore client: {str(e)}")
        return None

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def authenticate_user(login_identifier, password):
    """Authenticate user against MAIN Firebase using email or username"""
    try:
        db = get_firestore_client()
        if not db:
            return None, "Database connection failed"
        
        # Hash the provided password
        hashed_password = hash_password(password)
        
        # Query users collection in MAIN Firebase
        users_ref = db.collection('users')
        
        # Try to find user by email first, then by username
        user_doc = None
        
        # Check if login_identifier is an email
        if validate_email(login_identifier):
            query = users_ref.where('email', '==', login_identifier).where('password_hash', '==', hashed_password)
        else:
            query = users_ref.where('username', '==', login_identifier).where('password_hash', '==', hashed_password)
        
        docs = list(query.stream())
        
        if docs:
            user_doc = docs[0]
            user_data = user_doc.to_dict()
            user_data['user_id'] = user_doc.id
            
            # Update last login
            user_doc.reference.update({
                'last_login': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"User authenticated successfully: {login_identifier}")
            return user_data, None
        else:
            logger.warning(f"Authentication failed for user: {login_identifier}")
            return None, "Invalid email/username or password"
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None, f"Authentication error: {str(e)}"

def check_user_exists(email, username):
    """Check if user already exists with given email or username"""
    try:
        db = get_firestore_client()
        if not db:
            return True, "Database connection failed"
        
        users_ref = db.collection('users')
        
        # Check email
        email_query = users_ref.where('email', '==', email)
        email_docs = list(email_query.stream())
        if email_docs:
            return True, "Email already registered"
        
        # Check username
        username_query = users_ref.where('username', '==', username)
        username_docs = list(username_query.stream())
        if username_docs:
            return True, "Username already taken"
        
        return False, "User does not exist"
        
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        return True, f"Error checking user: {str(e)}"

def register_user(email, username, password, full_name, role='user'):
    """Register a new user in MAIN Firebase with proper validation"""
    try:
        db = get_firestore_client()
        if not db:
            return False, "Database connection failed"
        
        # Validate email
        if not validate_email(email):
            return False, "Invalid email format"
        
        # Validate password
        is_valid, password_message = validate_password(password)
        if not is_valid:
            return False, password_message
        
        # Check if user already exists
        exists, message = check_user_exists(email, username)
        if exists:
            return False, message
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create new user
        user_data = {
            'email': email,
            'username': username,
            'password_hash': password_hash,
            'full_name': full_name,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
            'last_login': None,
            'is_active': True,
            'profile_completed': True
        }
        
        doc_ref = db.collection('users').add(user_data)
        user_data['user_id'] = doc_ref[1].id
        
        # Initialize user stats in gamification system
        try:
            stats_data = {
                'user_id': doc_ref[1].id,
                'username': username,
                'total_xp': 0,
                'level': 1,
                'recipes_generated': 0,
                'quizzes_completed': 0,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP
            }
            db.collection('user_stats').document(doc_ref[1].id).set(stats_data)
            logger.info(f"Created user stats for new user: {username}")
        except Exception as e:
            logger.warning(f"Failed to create user stats: {str(e)}")
        
        logger.info(f"User registered successfully: {username} ({email})")
        return True, "Registration successful! You can now log in."
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"

def render_login_form():
    """Render the login form"""
    st.markdown("### Login to Your Account")
    
    with st.form("login_form"):
        login_identifier = st.text_input(
            "Email or Username",
            placeholder="Enter your email or username",
            help="You can use either your email address or username to log in"
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            login_button = st.form_submit_button("Login", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("Create Account", use_container_width=True):
                st.session_state.show_signup = True
                st.rerun()
        
        if login_button:
            if not login_identifier or not password:
                st.error("Please fill in all fields")
            else:
                with st.spinner("Authenticating..."):
                    user_data, error = authenticate_user(login_identifier, password)
                    if user_data:
                        st.session_state.is_authenticated = True
                        st.session_state.user = user_data
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(error)

def render_signup_form():
    """Render the signup form"""
    st.markdown("### Create Your Account")
    
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input(
                "Full Name *",
                placeholder="Enter your full name",
                help="Your display name in the system"
            )
            email = st.text_input(
                "Email Address *",
                placeholder="Enter your email address",
                help="Used for login and notifications"
            )
        
        with col2:
            username = st.text_input(
                "Username *",
                placeholder="Choose a unique username",
                help="Used for login and leaderboards"
            )
            role = st.selectbox(
                "Role *",
                ["user", "staff", "chef", "admin"],
                help="Select your role in the restaurant system"
            )
        
        password = st.text_input(
            "Password *",
            type="password",
            placeholder="Create a strong password",
            help="Must be at least 8 characters with uppercase, lowercase, and numbers"
        )
        
        confirm_password = st.text_input(
            "Confirm Password *",
            type="password",
            placeholder="Confirm your password"
        )
        
        # Terms and conditions
        terms_accepted = st.checkbox(
            "I agree to the Terms of Service and Privacy Policy",
            help="You must accept the terms to create an account"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            signup_button = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("Back to Login", use_container_width=True):
                st.session_state.show_signup = False
                st.rerun()
        
        if signup_button:
            # Validation
            if not all([full_name, email, username, password, confirm_password]):
                st.error("Please fill in all required fields")
            elif not terms_accepted:
                st.error("Please accept the Terms of Service and Privacy Policy")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                with st.spinner("Creating your account..."):
                    success, message = register_user(email, username, password, full_name, role)
                    if success:
                        st.success(message)
                        st.session_state.show_signup = False
                        st.balloons()
                        
                        # Auto-login after successful registration
                        user_data, _ = authenticate_user(email, password)
                        if user_data:
                            st.session_state.is_authenticated = True
                            st.session_state.user = user_data
                            st.rerun()
                    else:
                        st.error(message)

def render_auth_ui():
    """Render authentication UI in sidebar"""
    if st.session_state.is_authenticated:
        user = st.session_state.user
        st.sidebar.success(f"Welcome, {user.get('full_name', user['username'])}!")
        st.sidebar.write(f"**Role:** {user['role'].title()}")
        st.sidebar.write(f"**Username:** @{user['username']}")
        
        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user = None
            st.session_state.show_signup = False
            st.rerun()
        
        return True
    else:
        st.sidebar.markdown("### Authentication")
        
        # Show signup or login form based on state
        if st.session_state.show_signup:
            render_signup_form()
        else:
            render_login_form()
        
        # Additional info
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Account Types")
        st.sidebar.markdown("""
        **User:** Access to basic features, quizzes, and visual menu
        **Staff:** Can create marketing campaigns and access analytics
        **Chef:** Can submit recipes and manage menu items
        **Admin:** Full access to all features and management tools
        """)
        
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
        
        # Get user stats from main Firebase (same as authentication)
        user_stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Your Stats")
        
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
                st.sidebar.write(f"Recipes: {recipes_generated}")
            if quizzes_completed > 0:
                st.sidebar.write(f"Quizzes: {quizzes_completed}")
        
        logger.info(f"Displayed stats for user {user_id}: Level {level}, XP {total_xp}, Progress {progress:.2f}")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_amount, activity_type):
    """Show XP notification"""
    st.success(f"+{xp_amount} XP earned for {activity_type}!")

def display_gamification_dashboard(user_id):
    """Display comprehensive gamification dashboard"""
    st.title("Gamification Hub")
    
    try:
        from modules.leftover import get_user_stats, get_leaderboard
        
        # Get user stats from main Firebase
        user_stats = get_user_stats(user_id)
        
        # Overview metrics
        st.subheader("Your Progress")
        
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
        
        st.subheader("Level Progress")
        st.progress(progress, text=f"Level {level} - {current_level_xp}/100 XP")
        
        # Achievements section
        st.subheader("Achievements")
        
        achievements = []
        if user_stats.get('recipes_generated', 0) >= 1:
            achievements.append("Recipe Novice - Generated your first recipe")
        if user_stats.get('recipes_generated', 0) >= 10:
            achievements.append("Recipe Expert - Generated 10+ recipes")
        if user_stats.get('quizzes_completed', 0) >= 1:
            achievements.append("Quiz Starter - Completed your first quiz")
        if user_stats.get('quizzes_completed', 0) >= 5:
            achievements.append("Quiz Master - Completed 5+ quizzes")
        if user_stats.get('level', 1) >= 5:
            achievements.append("Rising Star - Reached Level 5")
        if user_stats.get('level', 1) >= 10:
            achievements.append("Culinary Expert - Reached Level 10")
        
        if achievements:
            for achievement in achievements:
                st.success(achievement)
        else:
            st.info("Complete activities to unlock achievements!")
        
        # Leaderboard
        st.subheader("Leaderboard")
        
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
        st.subheader("Earn More XP")
        
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
    """Render cooking quiz component - AI generated questions only"""
    st.subheader("Cooking Knowledge Quiz")
    
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
        st.session_state.quiz_questions = []
        st.session_state.quiz_answers = {}
        st.session_state.quiz_score = 0
    
    if not st.session_state.quiz_started:
        st.info("Test your culinary knowledge and earn XP!")
        if st.button("Start Quiz", type="primary"):
            # Generate AI questions
            with st.spinner("Generating quiz questions..."):
                from modules.leftover import generate_dynamic_quiz_questions
                questions = generate_dynamic_quiz_questions(ingredients, 5)
                
                if questions:
                    st.session_state.quiz_questions = questions
                    st.session_state.quiz_started = True
                    st.session_state.quiz_answers = {}
                    st.rerun()
                else:
                    st.error("Unable to generate quiz questions. Please try again later.")
    else:
        # Display quiz questions
        if st.session_state.quiz_questions:
            with st.form("cooking_quiz"):
                for i, q in enumerate(st.session_state.quiz_questions):
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
                    total_questions = len(st.session_state.quiz_questions)
                    
                    for i, q in enumerate(st.session_state.quiz_questions):
                        if st.session_state.quiz_answers.get(i) == q['correct']:
                            correct_answers += 1
                    
                    score_percentage = (correct_answers / total_questions) * 100
                    st.session_state.quiz_score = score_percentage
                    
                    # Display results
                    st.subheader("Quiz Results")
                    st.write(f"Score: {correct_answers}/{total_questions} ({score_percentage:.0f}%)")
                    
                    # Award XP
                    base_xp = 15
                    bonus_xp = 10 if score_percentage == 100 else 0
                    total_xp = base_xp + bonus_xp
                    
                    try:
                        from modules.leftover import update_user_stats
                        update_user_stats(user_id, total_xp, correct_answers, total_questions)
                        show_xp_notification(total_xp, "completing cooking quiz")
                    except Exception as e:
                        logger.error(f"Error awarding quiz XP: {str(e)}")
                    
                    # Show explanations
                    st.subheader("Explanations")
                    for i, q in enumerate(st.session_state.quiz_questions):
                        user_answer = st.session_state.quiz_answers.get(i)
                        correct_answer = q['correct']
                        
                        if user_answer == correct_answer:
                            st.success(f"Q{i+1}: Correct! {q.get('explanation', 'No explanation available.')}")
                        else:
                            st.error(f"Q{i+1}: Incorrect. {q.get('explanation', 'No explanation available.')}")
                    
                    # Reset quiz
                    if st.button("Take Quiz Again"):
                        st.session_state.quiz_started = False
                        st.session_state.quiz_questions = []
                        st.session_state.quiz_answers = {}
                        st.rerun()
        else:
            st.error("No quiz questions available. Please try starting the quiz again.")
            if st.button("Restart Quiz"):
                st.session_state.quiz_started = False
                st.rerun()

def display_daily_challenge(user_id):
    """Display daily cooking challenge"""
    st.subheader("Daily Challenge")
    
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
    st.sidebar.subheader("Upload CSV")
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
    st.sidebar.subheader("Manual Input")
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
    st.sidebar.subheader("Firebase Integration")
    
    use_firebase = st.sidebar.checkbox("Use current inventory from Firebase")
    
    if use_firebase:
        max_ingredients = st.sidebar.slider(
            "Max ingredients to fetch", 
            min_value=5, 
            max_value=50, 
            value=20,
            help="Limit the number of ingredients to prioritize those expiring soon"
        )
        
        if st.sidebar.button("Fetch Priority Ingredients"):
            try:
                from modules.leftover import get_ingredients_by_expiry_priority, fetch_ingredients_from_firebase
                firebase_ingredients = fetch_ingredients_from_firebase()
                ingredients, detailed_info = get_ingredients_by_expiry_priority(firebase_ingredients, max_ingredients)
                
                if ingredients:
                    st.sidebar.success(f"Fetched {len(ingredients)} priority ingredients")
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
        award_recipe_xp(user_id, base_xp)
        
        show_xp_notification(base_xp, f"generating {num_recipes} recipes")
        
    except Exception as e:
        logger.error(f"Error awarding recipe generation XP: {str(e)}")
