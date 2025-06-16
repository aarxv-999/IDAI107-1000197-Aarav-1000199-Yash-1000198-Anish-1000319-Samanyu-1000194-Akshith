"""
UI Components for the Smart Restaurant Menu Management App.
Contains authentication, gamification, and other UI elements.
Updated with staff code verification system.
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
    if 'staff_code_verified' not in st.session_state:
        st.session_state.staff_code_verified = False

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
    """Validate password strength - UPDATED: simplified requirements"""
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    return True, "Password is valid"

def validate_staff_code(code):
    """Validate staff access code"""
    return code == "staffcode123"

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
        
        logger.info(f"User registered successfully: {username} ({email}) as {role}")
        return True, "Registration successful! You can now log in."
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"

def clear_user_data(user_id):
    """Clear user's gamification data and preferences while keeping the account"""
    try:
        # Get both main and event Firebase databases
        main_db = get_firestore_client()
        event_db = get_event_firestore_client()
        
        if not main_db:
            return False, "Main database connection failed"
        
        # Reset user stats to initial values in main Firebase
        initial_stats = {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'quizzes_completed': 0,
            'quizzes_taken': 0,
            'correct_answers': 0,
            'total_questions': 0,
            'perfect_scores': 0,
            'achievements': [],
            'last_quiz_date': None,
            'last_activity': firestore.SERVER_TIMESTAMP,
            'data_cleared_at': firestore.SERVER_TIMESTAMP
        }
        
        # Update user stats document in main Firebase
        user_stats_ref = main_db.collection('user_stats').document(user_id)
        user_stats_ref.set(initial_stats, merge=False)  # Overwrite completely
        
        # Clear user preferences from event Firebase if available
        if event_db:
            try:
                # Clear user preferences
                user_prefs_ref = event_db.collection('user_preferences').document(user_id)
                user_prefs_doc = user_prefs_ref.get()
                if user_prefs_doc.exists:
                    user_prefs_ref.delete()
                    logger.info(f"Cleared user preferences for user: {user_id}")
                
                # Clear user dish likes (for AI learning)
                user_likes_ref = event_db.collection('user_dish_likes').where('user_id', '==', user_id)
                user_likes_docs = list(user_likes_ref.stream())
                for doc in user_likes_docs:
                    doc.reference.delete()
                logger.info(f"Cleared {len(user_likes_docs)} dish likes for user: {user_id}")
                
            except Exception as e:
                logger.warning(f"Could not clear event database data for user {user_id}: {str(e)}")
                # Continue anyway since main stats were cleared
        
        logger.info(f"Cleared user data and preferences for user: {user_id}")
        return True, "User data and preferences cleared successfully! Your account remains active."
        
    except Exception as e:
        logger.error(f"Error clearing user data: {str(e)}")
        return False, f"Error clearing user data: {str(e)}"

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
                st.session_state.staff_code_verified = False  # Reset staff code verification
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
    """Render the signup form with staff code verification"""
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
        
        # Staff verification section
        st.markdown("---")
        st.markdown("#### Account Type")

        is_staff = st.checkbox(
            "Restaurant staff?",
            help="Check this if you are a restaurant staff member (requires verification code)"
        )

        selected_role = "user"  # Default role
        staff_code_valid = False

        if is_staff:
            # Show code input immediately after checkbox is checked
            staff_code = st.text_input(
                "Staff Access Code *",
                type="password",
                placeholder="Enter staff access code",
                help="Contact your administrator for the staff access code"
            )
            
            if staff_code:
                if validate_staff_code(staff_code):
                    staff_code_valid = True
                    st.success("✅ Staff code verified!")
                    
                    # Show role selection immediately after valid code
                    selected_role = st.selectbox(
                        "Select Your Role *",
                        ["staff", "chef", "admin"],
                        help="Choose your role in the restaurant system"
                    )
                else:
                    st.error("❌ Invalid staff code. Please contact your administrator.")
            else:
                st.info("🔐 Please enter your staff access code to continue")
        else:
            st.info("👤 You will be registered as a **Customer/User** with access to basic features.")
        
        st.markdown("---")
        
        password = st.text_input(
            "Password *",
            type="password",
            placeholder="Create a strong password",
            help="Must be at least 5 characters with one uppercase letter"
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
                st.session_state.staff_code_verified = False
                st.rerun()
        
        if signup_button:
            # Validation
            if not all([full_name, email, username, password, confirm_password]):
                st.error("Please fill in all required fields")
            elif not terms_accepted:
                st.error("Please accept the Terms of Service and Privacy Policy")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif is_staff and not staff_code_valid:
                st.error("Please enter a valid staff access code")
            else:
                with st.spinner("Creating your account..."):
                    success, message = register_user(email, username, password, full_name, selected_role)
                    if success:
                        st.success(message)
                        st.session_state.show_signup = False
                        st.session_state.staff_code_verified = False
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
        
        # Features section with dropdown
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Features")
        
        # Feature selection dropdown
        features = [
            "Smart Leftover Recipe Generator",
            "Visual Menu Display", 
            "Cooking Quiz",
            "Gamification Hub",
            "AI Marketing Campaign Generator",
            "Event Planner",
            "Inventory Management"
        ]
        
        selected_feature = st.sidebar.selectbox(
            "Choose a feature:",
            features,
            key="feature_selector"
        )
        
        if 'selected_feature' not in st.session_state:
            st.session_state.selected_feature = selected_feature
        
        if selected_feature != st.session_state.selected_feature:
            st.session_state.selected_feature = selected_feature
            st.rerun()
        
        # Account management buttons
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Account")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("Logout", use_container_width=True):
                st.session_state.is_authenticated = False
                st.session_state.user = None
                st.session_state.show_signup = False
                st.session_state.staff_code_verified = False
                st.rerun()
        
        with col2:
            if st.button("Clear Data", use_container_width=True, type="secondary", help="Reset your XP, achievements, and progress"):
                # Show confirmation dialog
                if 'confirm_clear_data' not in st.session_state:
                    st.session_state.confirm_clear_data = False
                
                if not st.session_state.confirm_clear_data:
                    st.session_state.confirm_clear_data = True
                    st.rerun()
        
        # Handle clear data confirmation
        if st.session_state.get('confirm_clear_data', False):
            st.sidebar.markdown("---")
            st.sidebar.warning("⚠️ **Confirm Data Clearing**")
            st.sidebar.write("This will reset:")
            st.sidebar.write("• All XP and levels")
            st.sidebar.write("• Achievements")
            st.sidebar.write("• Quiz history")
            st.sidebar.write("• Recipe generation stats")
            st.sidebar.write("• User preferences & liked dishes")
            st.sidebar.write("• AI learning data")
            st.sidebar.write("")
            st.sidebar.write("Your account will remain active.")
            
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("✅ Confirm", type="primary", use_container_width=True):
                    success, message = clear_user_data(user['user_id'])
                    if success:
                        st.sidebar.success(message)
                        st.session_state.confirm_clear_data = False
                        # Force refresh of user stats
                        st.rerun()
                    else:
                        st.sidebar.error(message)
            
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirm_clear_data = False
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
        **Customer/User:** Access to basic features, quizzes, and visual menu
        
        **Staff Members** *(requires code)*:
        • **Staff:** Marketing campaigns and analytics
        • **Chef:** Recipe submissions and menu management  
        • **Admin:** Full access to all features
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
    """Display user gamification stats in sidebar as expandable section with progressive XP system"""
    try:
        from modules.leftover import get_user_stats
        from modules.xp_utils import get_xp_progress, calculate_level_from_xp
        
        # Get user stats from main Firebase (same as authentication)
        user_stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        
        # Create an expandable section for user stats
        with st.sidebar.expander("Your Stats & Progress", expanded=False):
            # Extract stats with safe defaults
            total_xp = max(0, user_stats.get('total_xp', 0))
            
            # Calculate level using progressive system
            current_level = calculate_level_from_xp(total_xp)
            
            # Get progress information
            current_level_xp, xp_needed_for_next, progress_percentage = get_xp_progress(total_xp, current_level)
            
            # Display metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Level", current_level)
            with col2:
                st.metric("Total XP", f"{total_xp:,}")
            
            # Progress bar with new calculation
            progress = progress_percentage / 100.0
            progress = max(0.0, min(1.0, progress))  # Clamp between 0 and 1
            
            st.progress(progress, text=f"{xp_needed_for_next} XP to Level {current_level + 1}")
            
            # Show current level XP details
            st.caption(f"Level {current_level}: {current_level_xp} XP earned")
            
            # Additional stats
            recipes_generated = user_stats.get('recipes_generated', 0)
            quizzes_completed = user_stats.get('quizzes_completed', 0)
            
            if recipes_generated > 0 or quizzes_completed > 0:
                st.markdown("**Activity:**")
                if recipes_generated > 0:
                    st.write(f"Recipes: {recipes_generated}")
                if quizzes_completed > 0:
                    st.write(f"Quizzes: {quizzes_completed}")
            
            # Gamification Hub button
            st.markdown("---")
            if st.button("Open Gamification Hub", use_container_width=True, type="primary", key="gamification_hub_btn"):
                st.session_state.selected_feature = "Gamification Hub"
                st.rerun()
        
        logger.info(f"Displayed progressive stats for user {user_id}: Level {current_level}, XP {total_xp}, Progress {progress_percentage:.1f}%")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_amount, activity_type):
    """Show XP notification"""
    st.success(f"+{xp_amount} XP earned for {activity_type}!")

def display_gamification_dashboard(user_id):
    """Display comprehensive gamification dashboard with progressive XP system"""
    st.title("Gamification Hub")
    
    try:
        from modules.leftover import get_user_stats, get_leaderboard
        from modules.xp_utils import get_xp_progress, calculate_level_from_xp, get_xp_breakdown_for_levels
        
        # Get user stats from main Firebase
        user_stats = get_user_stats(user_id)
        total_xp = user_stats.get('total_xp', 0)
        
        # Calculate level using progressive system
        current_level = calculate_level_from_xp(total_xp)
        
        # Get progress information
        current_level_xp, xp_needed_for_next, progress_percentage = get_xp_progress(total_xp, current_level)
        
        # Overview metrics
        st.subheader("Your Progress")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Level", current_level)
        
        with col2:
            st.metric("Total XP", f"{total_xp:,}")
        
        with col3:
            st.metric("Recipes Generated", user_stats.get('recipes_generated', 0))
        
        with col4:
            st.metric("Quizzes Completed", user_stats.get('quizzes_completed', 0))
        
        # Enhanced progress visualization
        st.subheader("Level Progress")
        
        # Progress bar
        progress = progress_percentage / 100.0
        st.progress(progress, text=f"Level {current_level} - {current_level_xp} XP earned")
        
        # Detailed progress info
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Current Level:** {current_level}\n**XP in this level:** {current_level_xp}")
        with col2:
            st.info(f"**Next Level:** {current_level + 1}\n**XP needed:** {xp_needed_for_next}")
        
        # XP Requirements Table
        st.subheader("Level Requirements")
        
        # Show XP breakdown for next few levels
        max_display_level = min(current_level + 5, 15)
        xp_breakdown = get_xp_breakdown_for_levels(max_display_level)
        
        # Create DataFrame for display
        breakdown_data = []
        for level, xp_for_level, total_xp_req in xp_breakdown:
            status = "✅ Completed" if level <= current_level else "🔒 Locked"
            if level == current_level + 1:
                status = "🎯 Next Goal"
            
            breakdown_data.append({
                "Level": level,
                "XP for Level": f"{xp_for_level:,}",
                "Total XP Required": f"{total_xp_req:,}",
                "Status": status
            })
        
        df = pd.DataFrame(breakdown_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Achievements section
        st.subheader("Achievements")
        
        achievements = []
        if user_stats.get('recipes_generated', 0) >= 1:
            achievements.append("🍳 Recipe Novice - Generated your first recipe")
        if user_stats.get('recipes_generated', 0) >= 10:
            achievements.append("👨‍🍳 Recipe Expert - Generated 10+ recipes")
        if user_stats.get('quizzes_completed', 0) >= 1:
            achievements.append("📚 Quiz Starter - Completed your first quiz")
        if user_stats.get('quizzes_completed', 0) >= 5:
            achievements.append("🧠 Quiz Master - Completed 5+ quizzes")
        if current_level >= 5:
            achievements.append("⭐ Rising Star - Reached Level 5")
        if current_level >= 10:
            achievements.append("🏆 Culinary Expert - Reached Level 10")
        if total_xp >= 1000:
            achievements.append("💎 XP Collector - Earned 1,000+ XP")
        
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
        
        # Enhanced activity suggestions
        st.subheader("Earn More XP")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **Recipe Generation:**
            - Generate recipes: +5 XP each
            - Use priority ingredients: +2 bonus XP
            - Generate 5+ recipes: +10 bonus XP
            """)
        
        with col2:
            st.info("""
            **Cooking Quiz:**
            - Complete quiz: +2 XP per question
            - Perfect score: +5 bonus XP
            - Daily streak: +2 bonus XP
            """)
        
        # XP Tips
        with st.expander("💡 XP Tips & Strategy"):
            st.markdown(f"""
            **Your Current Status:**
            - You're Level {current_level} with {total_xp:,} total XP
            - You need {xp_needed_for_next} more XP to reach Level {current_level + 1}
            
            **Fastest Ways to Level Up:**
            1. **Take Cooking Quizzes** - Up to 15 XP per quiz (10 base + 5 bonus for perfect score)
            2. **Generate Multiple Recipes** - 5 XP per recipe + bonuses for bulk generation
            3. **Use Priority Ingredients** - Extra 2 XP when using expiring ingredients
            4. **Daily Consistency** - Regular activity helps with streak bonuses
            
            **Level Scaling:**
            Each level requires progressively more XP, making higher levels more prestigious!
            """)
        
    except Exception as e:
        logger.error(f"Error in gamification dashboard: {str(e)}")
        st.error("Error loading gamification dashboard")

def render_cooking_quiz(ingredients, user_id):
    """Render cooking quiz component - AI generated questions only"""
    st.subheader("Cooking Knowledge Quiz")
    
    # Initialize all session state variables properly
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
    
    # Quiz setup section
    if not st.session_state.quiz_started or st.session_state.quiz_completed:
        st.markdown("### Quiz Setup")
        
        # Add slider for number of questions
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
            estimated_time = num_questions * 1.5  # Estimate 1.5 minutes per question
            st.metric("Estimated Time", f"{estimated_time:.0f} min")
        
        # Generate Quiz button
        button_text = "Generate New Quiz" if st.session_state.quiz_completed else "Generate Quiz"
        if st.button(button_text, type="primary", use_container_width=True):
            # Generate AI questions with selected number
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
        
        # Show previous quiz results if completed
        if st.session_state.quiz_completed and st.session_state.quiz_questions:
            st.markdown("---")
            st.markdown("### Previous Quiz Results")
            
            # Calculate and display previous score
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
    
    # Quiz taking section
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
                    # Calculate score
                    correct_answers = 0
                    total_questions = len(st.session_state.quiz_questions)
                    
                    for i, q in enumerate(st.session_state.quiz_questions):
                        if st.session_state.quiz_answers.get(i) == q['correct']:
                            correct_answers += 1
                    
                    score_percentage = (correct_answers / total_questions) * 100
                    st.session_state.quiz_score = score_percentage
                    st.session_state.quiz_completed = True
                    
                    # Display results
                    st.subheader("Quiz Results")
                    st.write(f"Score: {correct_answers}/{total_questions} ({score_percentage:.0f}%)")
                    
                    # Award XP - scale with number of questions
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
                    
                    # Show explanations
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
    
    # Reset quiz button (outside of form)
    if st.session_state.quiz_started and not st.session_state.quiz_completed:
        st.markdown("---")
        if st.button("Cancel Quiz", help="Cancel current quiz and return to setup"):
            st.session_state.quiz_started = False
            st.session_state.quiz_completed = False
            st.session_state.quiz_questions = []
            st.session_state.quiz_answers = {}
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
    """Award XP for recipe generation with reasonable amounts"""
    try:
        from modules.leftover import update_user_stats
        
        # Base XP: 5 XP per recipe
        base_xp = 5 * num_recipes
        
        # Bonus XP for bulk generation (5+ recipes)
        bonus_xp = 10 if num_recipes >= 5 else 0
        
        total_xp = base_xp + bonus_xp
        
        # Update user stats
        update_user_stats(user_id, total_xp, recipes_generated=num_recipes)
        
        # Show notification
        if bonus_xp > 0:
            show_xp_notification(total_xp, f"generating {num_recipes} recipes (includes {bonus_xp} bonus XP)")
        else:
            show_xp_notification(total_xp, f"generating {num_recipes} recipes")
        
    except Exception as e:
        logger.error(f"Error awarding recipe generation XP: {str(e)}")
