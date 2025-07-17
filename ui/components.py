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

def initialize_session_state():
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'auth_error' not in st.session_state:
        st.session_state.auth_error = None
    if 'show_signup' not in st.session_state:
        st.session_state.show_signup = False

def get_firestore_client():
    try:
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client for auth: {str(e)}")
        return None

def get_event_firestore_client():
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            init_event_firebase()
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
    except Exception as e:
        logger.error(f"Error getting event Firestore client: {str(e)}")
        return None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
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
    try:
        db = get_firestore_client()
        if not db:
            return None, "Database connection failed"
        
        hashed_password = hash_password(password)
        
        users_ref = db.collection('users')
        
        user_doc = None
        
        if validate_email(login_identifier):
            query = users_ref.where('email', '==', login_identifier).where('password_hash', '==', hashed_password)
        else:
            query = users_ref.where('username', '==', login_identifier).where('password_hash', '==', hashed_password)
        
        docs = list(query.stream())
        
        if docs:
            user_doc = docs[0]
            user_data = user_doc.to_dict()
            user_data['user_id'] = user_doc.id
            
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
    try:
        db = get_firestore_client()
        if not db:
            return True, "Database connection failed"
        
        users_ref = db.collection('users')
        
        email_query = users_ref.where('email', '==', email)
        email_docs = list(email_query.stream())
        if email_docs:
            return True, "Email already registered"
        
        username_query = users_ref.where('username', '==', username)
        username_docs = list(username_query.stream())
        if username_docs:
            return True, "Username already taken"
        
        return False, "User does not exist"
        
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        return True, f"Error checking user: {str(e)}"

def register_user(email, username, password, full_name, role='user'):
    try:
        db = get_firestore_client()
        if not db:
            return False, "Database connection failed"
        
        if not validate_email(email):
            return False, "Invalid email format"
        
        is_valid, password_message = validate_password(password)
        if not is_valid:
            return False, password_message
        
        exists, message = check_user_exists(email, username)
        if exists:
            return False, message
        
        password_hash = hash_password(password)
        
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
        
        staff_code = ""
        if role != "user":
            staff_code = st.text_input(
                "Staff Code *",
                type = "password",
                placeholder = "Enter your staff code"
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
        
        
        col1, col2 = st.columns(2)
        with col1:
            signup_button = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        with col2:
            if st.form_submit_button("Back to Login", use_container_width=True):
                st.session_state.show_signup = False
                st.rerun()
        
        if signup_button:
            if not all([full_name, email, username, password, confirm_password]):
                st.error("Please fill in all required fields")
            elif role != "user" and staff_code != "staffcode123":
                st.error("Invalid staff code!!")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                with st.spinner("Creating your account..."):
                    success, message = register_user(email, username, password, full_name, role)
                    if success:
                        st.success(message)
                        st.session_state.show_signup = False
                        st.balloons()
                        st.session_state.show_signup = False
                        st.info("Please login with your new information!!")
                        st.rerun()
                    else:
                        st.error(message)

def render_auth_ui():
    if st.session_state.is_authenticated:
        user = st.session_state.user
        st.sidebar.success(f"Welcome, {user.get('full_name', user['username'])}!")
        st.sidebar.write(f"**Role:** {user['role'].title()}")
        st.sidebar.write(f"**Username:** @{user['username']}")
        
        if user and user.get('user_id'):
            display_user_stats_sidebar(user['user_id'])

        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user = None
            st.session_state.show_signup = False
            st.rerun()
        
        return True
    else:
        st.sidebar.markdown("### Authentication")
        
        if st.session_state.show_signup:
            render_signup_form()
        else:
            render_login_form()
        
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
    def wrapper(*args, **kwargs):
        if not st.session_state.is_authenticated:
            st.warning("Please log in to access this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper

def get_current_user():
    return st.session_state.get('user')

def is_user_role(required_role):
    user = get_current_user()
    if not user:
        return False
    return user.get('role') == required_role

def calculate_simple_level(total_xp):
    if total_xp < 100:
        return 1
    elif total_xp < 300:
        return 2
    elif total_xp < 600:
        return 3
    elif total_xp < 1000:
        return 4
    elif total_xp < 1500:
        return 5
    elif total_xp < 2100:
        return 6
    elif total_xp < 2800:
        return 7
    elif total_xp < 3600:
        return 8
    elif total_xp < 4500:
        return 9
    else:
        return 10 + (total_xp - 4500) // 1000

def get_simple_xp_progress(total_xp):
    level_thresholds = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500]
    
    current_level = calculate_simple_level(total_xp)
    
    if current_level <= len(level_thresholds):
        current_threshold = level_thresholds[current_level - 1] if current_level > 1 else 0
        next_threshold = level_thresholds[current_level] if current_level < len(level_thresholds) else current_threshold + 1000
    else:
        current_threshold = 4500 + (current_level - 10) * 1000
        next_threshold = current_threshold + 1000
    
    current_level_xp = total_xp - current_threshold
    xp_needed = next_threshold - total_xp
    progress_percent = (current_level_xp / (next_threshold - current_threshold)) * 100
    
    return int(current_level_xp), int(max(0, xp_needed)), int(max(0, min(100, progress_percent)))

def display_user_stats_sidebar(user_id):
    try:
        from modules.leftover import get_user_stats, get_leaderboard
        user_stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        
        with st.sidebar.expander("Your Stats & Progress", expanded=False):
            total_xp = max(0, user_stats.get('total_xp', 0))
            
            current_level = calculate_simple_level(total_xp)
            current_level_xp, xp_needed_for_next, progress_percentage = get_simple_xp_progress(total_xp)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Level", current_level)
                st.metric("Recipes", user_stats.get('recipes_generated', 0))
            with col2:
                st.metric("XP", f"{total_xp:,}")
                st.metric("Quizzes", user_stats.get('quizzes_completed', 0))
            
            progress = progress_percentage / 100.0
            progress = max(0.0, min(1.0, progress))
            st.progress(progress, text=f"{xp_needed_for_next} XP to Level {current_level + 1}")
            st.caption(f"Level {current_level}: {current_level_xp} XP earned")
            
            st.markdown("**Achievements:**")
            achievements = []
            if user_stats.get('recipes_generated', 0) >= 1:
                achievements.append("Recipe Novice")
            if user_stats.get('recipes_generated', 0) >= 10:
                achievements.append("Recipe Expert")
            if user_stats.get('quizzes_completed', 0) >= 1:
                achievements.append("Quiz Starter")
            if user_stats.get('quizzes_completed', 0) >= 5:
                achievements.append("Quiz Master")
            if current_level >= 5:
                achievements.append("Rising Star")
            if current_level >= 10:
                achievements.append("Culinary Expert")
            if total_xp >= 1000:
                achievements.append("XP Collector")
            
            if achievements:
                for achievement in achievements[:3]:
                    st.success(achievement)
                if len(achievements) > 3:
                    st.info(f"+ {len(achievements) - 3} more achievements")
            else:
                st.info("Complete activities to unlock achievements!")
            
            st.markdown("**Top Players:**")
            try:
                leaderboard = get_leaderboard()
                if leaderboard:
                    top_3 = leaderboard[:3]
                    for i, player in enumerate(top_3):
                        rank = i + 1
                        if player.get('username') == user_stats.get('username'):
                            st.success(f"{rank}. **{player['username']}** - Lvl {player['level']}")
                        else:
                            st.write(f"{rank}. {player['username']} - Lvl {player['level']}")
                else:
                    st.info("No leaderboard data yet.")
            except Exception as e:
                logger.error(f"Error loading leaderboard: {str(e)}")
                st.info("Leaderboard temporarily unavailable")
            
            st.markdown("**Daily Challenge:**")
            today = datetime.now().date()
            random.seed(today.toordinal())
            
            challenges = [
                "Generate 3+ vegetable recipes",
                "Use expiring ingredients",
                "Create vegetarian recipes",
                "Make quick 30-min recipes",
                "Use leftover rice/pasta"
            ]
            
            daily_challenge = random.choice(challenges)
            st.info(daily_challenge)
            
            st.markdown("**Earn XP:**")
            st.markdown("""
            • **Recipes:** 5 XP each (+bonuses)
            • **Quizzes:** 2 XP per question (+5 for perfect)
            • **Priority ingredients:** +2 XP bonus
            """)
        
        logger.info(f"Displayed stats for user {user_id}: Level {current_level}, XP {total_xp}")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_amount, activity_type):
    st.success(f"+{xp_amount} XP earned for {activity_type}!")

def render_cooking_quiz(ingredients, user_id):
    st.subheader("Cooking Knowledge Quiz")
    
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = []
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = {}
    if 'quiz_score' not in st.session_state:
        st.session_state.quiz_score = 0
    if 'quiz_num_questions' not in st.session_state:
        st.session_state.quiz_num_questions = 5
    if 'quiz_completed' not in st.session_state:
        st.session_state.quiz_completed = False
    
    if not st.session_state.quiz_started or st.session_state.quiz_completed:
        st.markdown("### Quiz Setup")
        
        num_questions = st.slider(
            "Number of questions",
            min_value=3,
            max_value=15,
            value=st.session_state.quiz_num_questions,
            help="Select how many questions you want in your quiz"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Questions", num_questions)
        with col2:
            estimated_time = num_questions * 1.5
            st.metric("Estimated Time", f"{estimated_time:.0f} min")
        
        button_text = "Generate New Quiz" if st.session_state.quiz_completed else "Generate Quiz"
        if st.button(button_text, type="primary", use_container_width=True):
            with st.spinner(f"Generating {num_questions} quiz questions..."):
                from modules.leftover import generate_dynamic_quiz_questions
                questions = generate_dynamic_quiz_questions(ingredients, num_questions)
                
                if questions:
                    st.session_state.quiz_questions = questions
                    st.session_state.quiz_started = True
                    st.session_state.quiz_completed = False
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_num_questions = num_questions
                    st.rerun()
                else:
                    st.error("Unable to generate quiz questions. Please try again later.")
        
        if st.session_state.quiz_completed and st.session_state.quiz_questions:
            st.markdown("---")
            st.markdown("### Previous Quiz Results")
            
            correct_answers = 0
            total_questions = len(st.session_state.quiz_questions)
            
            for i, q in enumerate(st.session_state.quiz_questions):
                if st.session_state.quiz_answers.get(i) == q['correct']:
                    correct_answers += 1
            
            score_percentage = (correct_answers / total_questions) * 100
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Score", f"{correct_answers}/{total_questions}")
            with col2:
                st.metric("Percentage", f"{score_percentage:.0f}%")
            with col3:
                base_xp_per_question = 2
                base_xp = base_xp_per_question * total_questions
                bonus_xp = 5 if score_percentage == 100 else 0
                total_xp = base_xp + bonus_xp
                st.metric("XP Earned", total_xp)
    
    elif st.session_state.quiz_started and not st.session_state.quiz_completed:
        if st.session_state.quiz_questions:
            st.markdown(f"### Quiz in Progress ({len(st.session_state.quiz_questions)} questions)")
            
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
                    correct_answers = 0
                    total_questions = len(st.session_state.quiz_questions)
                    
                    for i, q in enumerate(st.session_state.quiz_questions):
                        if st.session_state.quiz_answers.get(i) == q['correct']:
                            correct_answers += 1
                    
                    score_percentage = (correct_answers / total_questions) * 100
                    st.session_state.quiz_score = score_percentage
                    st.session_state.quiz_completed = True
                    
                    st.subheader("Quiz Results")
                    st.write(f"Score: {correct_answers}/{total_questions} ({score_percentage:.0f}%)")
                    
                    base_xp_per_question = 2
                    base_xp = base_xp_per_question * len(st.session_state.quiz_questions)
                    bonus_xp = 5 if score_percentage == 100 else 0
                    total_xp = base_xp + bonus_xp
                    
                    try:
                        from modules.leftover import update_user_stats
                        update_user_stats(user_id, total_xp, quizzes_completed=1)
                        show_xp_notification(total_xp, "completing cooking quiz")
                    except Exception as e:
                        logger.error(f"Error awarding quiz XP: {str(e)}")
                    
                    st.subheader("Explanations")
                    for i, q in enumerate(st.session_state.quiz_questions):
                        user_answer = st.session_state.quiz_answers.get(i)
                        correct_answer = q['correct']
                        
                        if user_answer == correct_answer:
                            st.success(f"Q{i+1}: Correct! {q.get('explanation', 'No explanation available.')}")
                        else:
                            st.error(f"Q{i+1}: Incorrect. {q.get('explanation', 'No explanation available.')}")
                    
                    st.rerun()
        else:
            st.error("No quiz questions available. Please try generating the quiz again.")
    
    if st.session_state.quiz_started and not st.session_state.quiz_completed:
        st.markdown("---")
        if st.button("Cancel Quiz", help="Cancel current quiz and return to setup"):
            st.session_state.quiz_started = False
            st.session_state.quiz_completed = False
            st.session_state.quiz_questions = []
            st.session_state.quiz_answers = {}
            st.rerun()

def display_daily_challenge(user_id):
    st.subheader("Daily Challenge")
    
    today = datetime.now().date()
    random.seed(today.toordinal())
    
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

def leftover_input_csv():
    st.sidebar.subheader("Upload CSV")
    uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")
    st.info("""
    **CSV Format Instructions:**
    - **Required Column:** `ingredient` (e.g., `tomatoes`)
    **Example CSV:**
    \`\`\`
    ingredient
    tomatoes
    onions
    chicken
    \`\`\`
    """)
    
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
    try:
        from modules.leftover import update_user_stats
        
        base_xp = 5 * num_recipes
        
        bonus_xp = 10 if num_recipes >= 5 else 0
        
        total_xp = base_xp + bonus_xp
        
        update_user_stats(user_id, total_xp, recipes_generated=num_recipes)
        
        if bonus_xp > 0:
            show_xp_notification(total_xp, f"generating {num_recipes} recipes (includes {bonus_xp} bonus XP)")
        else:
            show_xp_notification(total_xp, f"generating {num_recipes} recipes")
        
    except Exception as e:
        logger.error(f"Error awarding recipe generation XP: {str(e)}")
