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
    st.markdown("### Login")
    
    with st.form("login_form"):
        login_identifier = st.text_input(
            "Email or Username",
            placeholder="Enter your email or username"
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
    st.markdown("### Create Account")
    
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input(
                "Full Name",
                placeholder="Enter your full name"
            )
            email = st.text_input(
                "Email Address",
                placeholder="Enter your email address"
            )
        
        with col2:
            username = st.text_input(
                "Username",
                placeholder="Choose a unique username"
            )
            role = st.selectbox(
                "Role",
                ["user", "staff", "chef", "admin"]
            )
        
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Create a strong password"
        )
        
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Confirm your password"
        )
        
        # Terms and conditions
        terms_accepted = st.checkbox("I agree to the Terms of Service and Privacy Policy")
        
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
        st.sidebar.success(f"Welcome, {user.get('full_name', user['username'])}")
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
        xp
