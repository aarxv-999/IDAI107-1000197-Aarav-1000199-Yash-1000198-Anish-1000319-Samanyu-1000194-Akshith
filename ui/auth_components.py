"""
Authentication UI components for the Smart Restaurant Menu Management App.
Provides Streamlit UI elements for authentication and user management.
"""

import streamlit as st
from typing import Dict, Optional
import logging
from modules.auth import register_user, authenticate_user
from firebase_init import init_firebase

logger = logging.getLogger(__name__)

def initialize_session_state():
    """Initialize the session state variables if they don't already exist"""
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'show_login' not in st.session_state:
        st.session_state.show_login = True  # defaults to showing login form
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False
    
    # Initialize Firebase at app startup
    if 'firebase_initialized' not in st.session_state:
        st.session_state.firebase_initialized = init_firebase()

def toggle_login_register():
    """Toggle between login and registration forms"""
    st.session_state.show_login = not st.session_state.show_login
    st.session_state.show_register = not st.session_state.show_register

def logout_user():
    """Log out the current user"""
    st.session_state.user = None
    st.session_state.is_authenticated = False
    st.session_state.show_login = True
    st.session_state.show_register = False
    st.success("You have been logged out successfully!")
    st.rerun()

def login_form() -> bool:
    """
    Create a login form and process login attempts
    
    Returns:
        bool: True if login is successful, False otherwise
    """
    st.subheader("Login")

    with st.form("login_form"):
        username_or_email = st.text_input("Username / Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if not username_or_email or not password:
                st.error("Please fill all fields! MANDATORY")
                return False
                
            success, user_data, message = authenticate_user(username_or_email, password)
            
            if success:
                st.session_state.user = user_data
                st.session_state.is_authenticated = True
                st.success(f"Welcome back, {user_data['username']}!")
                st.rerun()  # Refresh page to update UI based on authentication
                return True
            else:
                st.error(message)
                return False
    
    st.markdown("Don't have an account already? [Register here](#)")
    if st.button("Create an account"):
        toggle_login_register()
    
    return False

def registration_form() -> bool:
    """
    Create a registration form and process registration attempts
    
    Returns:
        bool: True if registration is successful, False otherwise
    """
    st.subheader("Create An Account")
    
    with st.form("registration_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password", 
                                help="Password must be at least 5 characters with uppercase letters and numbers")
        confirm_password = st.text_input("Confirm Password", type="password")
        role = "user"  # default role, assigned to all users 
        
        # Registration for staff roles
        is_staff = st.checkbox("Register as restaurant staff")
        if is_staff:
            role_options = ["staff", "admin", "chef"]
            role = st.selectbox("Select your role", role_options)
            staff_code = st.text_input("Registration code", type="password")
            if staff_code != "staffcode123":  # Simple code verification
                role = "user"  # Reset to user if wrong code
                
        submitted = st.form_submit_button("Register")
        
        if submitted:
            if not username or not email or not password or not confirm_password:
                st.error("Please fill all fields! MANDATORY")
                return False
                
            if password != confirm_password:
                st.error("Passwords do not match!!")
                return False
            
            success, message = register_user(username, email, password, role)
            
            if success:
                st.success(message)
                st.info("Please log in with your new account!")
                st.session_state.show_login = True  # Switch to login page
                st.session_state.show_register = False
                st.rerun()  # Refresh page to show login form
                return True
            else:
                st.error(message)
                return False
    
    # Option to go back to login
    st.markdown("Already have an account? [Login here](#)")
    if st.button("Log in instead"):
        toggle_login_register()
    return False

def user_profile():
    """Display the user profile section in the sidebar"""
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        
        st.sidebar.subheader("User Profile")
        st.sidebar.write(f"Welcome, {user['username']}!")
        st.sidebar.write(f"Your Role: {user['role'].capitalize()}")
        
        if st.sidebar.button("Logout"):
            logout_user()

def auth_required(func):
    """
    Decorator to require authentication to access certain pages or features
    Usage: @auth_required at the beginning of any function
    """
    def wrapper(*args, **kwargs):
        initialize_session_state()
        
        if st.session_state.is_authenticated:
            return func(*args, **kwargs)
        else:
            st.warning("You need to be logged in to use this feature.")
            if st.session_state.show_login:
                login_form()
            else:
                registration_form()
            return None
    return wrapper

def render_auth_ui():
    """
    Show the authentication UI based on the current state
    
    Returns:
        bool: True if user is authenticated, False otherwise
    """
    initialize_session_state()
    
    if st.session_state.is_authenticated:  # Show profile if authenticated
        user_profile()
        return True
    
    if st.session_state.show_login:  # Show login or registration form
        return login_form()
    else:
        return registration_form()

def get_current_user() -> Optional[Dict]:
    """
    Get the currently logged in user
    
    Returns:
        Optional[Dict]: User data if authenticated, None otherwise
    """
    if st.session_state.is_authenticated and st.session_state.user:
        return st.session_state.user
    return None

def is_user_role(required_role: str) -> bool:
    """
    Check if user has a required role for certain tasks
    
    Args:
        required_role (str): The role to check for
        
    Returns:
        bool: True if user has the role, False otherwise
    """
    user = get_current_user()
    if user and user['role'] == required_role:
        return True
    return False
