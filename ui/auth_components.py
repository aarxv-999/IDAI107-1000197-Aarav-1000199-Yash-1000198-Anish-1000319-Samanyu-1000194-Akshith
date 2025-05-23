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
    if 'auth_mode' not in st.session_state:
        st.session_state.auth_mode = 'login'  # 'login' or 'register'
    
    # Initialize Firebase at app startup
    if 'firebase_initialized' not in st.session_state:
        st.session_state.firebase_initialized = init_firebase()

def switch_to_register():
    """Switch to registration mode"""
    st.session_state.auth_mode = 'register'

def switch_to_login():
    """Switch to login mode"""
    st.session_state.auth_mode = 'login'

def logout_user():
    """Log out the current user"""
    st.session_state.user = None
    st.session_state.is_authenticated = False
    st.session_state.auth_mode = 'login'
    st.success("You have been logged out successfully!")
    st.rerun()

def login_form() -> bool:
    """
    Create a login form and process login attempts
    
    Returns:
        bool: True if login is successful, False otherwise
    """
    # Create a container for better styling
    with st.container():
        st.markdown("### 🔐 Welcome Back!")
        st.markdown("Please sign in to your account")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            col1, col2 = st.columns([1, 4])
            with col2:
                username_or_email = st.text_input(
                    "Username or Email", 
                    placeholder="Enter your username or email",
                    help="You can use either your username or email address"
                )
                password = st.text_input(
                    "Password", 
                    type="password",
                    placeholder="Enter your password"
                )
                
                # Center the submit button
                col_left, col_center, col_right = st.columns([1, 2, 1])
                with col_center:
                    submitted = st.form_submit_button("🚀 Login", use_container_width=True)
            
            # Process form submission
            if submitted:
                if not username_or_email or not password:
                    st.error("⚠️ Please fill all fields!")
                    return False
                    
                with st.spinner("Signing you in..."):
                    success, user_data, message = authenticate_user(username_or_email, password)
                    
                    if success:
                        st.session_state.user = user_data
                        st.session_state.is_authenticated = True
                        st.success(f"🎉 Welcome back, {user_data['username']}!")
                        st.balloons()  # Add celebration effect
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        
        # Switch to registration
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("Don't have an account?")
            if st.button("📝 Create New Account", use_container_width=True, key="switch_to_register"):
                switch_to_register()
                st.rerun()
    
    return False

def registration_form() -> bool:
    """
    Create a registration form and process registration attempts
    
    Returns:
        bool: True if registration is successful, False otherwise
    """
    with st.container():
        st.markdown("### 📝 Create Your Account")
        st.markdown("Join our restaurant management system")
        
        # Add some spacing
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.form("registration_form", clear_on_submit=False):
            col1, col2 = st.columns([1, 4])
            with col2:
                username = st.text_input(
                    "Username", 
                    placeholder="Choose a unique username",
                    help="Your username must be unique"
                )
                email = st.text_input(
                    "Email", 
                    placeholder="your.email@example.com",
                    help="We'll use this for account recovery"
                )
                password = st.text_input(
                    "Password", 
                    type="password",
                    placeholder="Create a strong password",
                    help="Password must be at least 5 characters with uppercase letters and numbers"
                )
                confirm_password = st.text_input(
                    "Confirm Password", 
                    type="password",
                    placeholder="Re-enter your password"
                )
                
                # Role selection with better UI
                st.markdown("**Account Type:**")
                is_staff = st.checkbox("🏢 I'm restaurant staff", help="Check this if you work at the restaurant")
                
                role = "user"  # default role
                staff_code = ""
                
                if is_staff:
                    role_options = {
                        "staff": "👥 Staff Member",
                        "chef": "👨‍🍳 Chef",
                        "admin": "⚡ Administrator"
                    }
                    role = st.selectbox("Select your role:", list(role_options.keys()), 
                                      format_func=lambda x: role_options[x])
                    staff_code = st.text_input(
                        "Staff Registration Code", 
                        type="password",
                        placeholder="Enter staff code",
                        help="Contact your manager for the registration code"
                    )
                
                # Center the submit button
                col_left, col_center, col_right = st.columns([1, 2, 1])
                with col_center:
                    submitted = st.form_submit_button("🎯 Create Account", use_container_width=True)
            
            # Process form submission
            if submitted:
                # Validation
                if not username or not email or not password or not confirm_password:
                    st.error("⚠️ Please fill all required fields!")
                    return False
                    
                if password != confirm_password:
                    st.error("🔐 Passwords do not match!")
                    return False
                
                # Validate staff code if needed
                if is_staff and staff_code != "staffcode123":
                    st.error("🚫 Invalid staff registration code!")
                    role = "user"  # Reset to user role
                
                with st.spinner("Creating your account..."):
                    success, message = register_user(username, email, password, role)
                    
                    if success:
                        st.success(f"🎉 {message}")
                        st.info("✅ Account created successfully! Please log in with your new credentials.")
                        st.balloons()  # Add celebration effect
                        
                        # Switch to login after successful registration
                        st.session_state.auth_mode = 'login'
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        
        # Switch to login
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("Already have an account?")
            if st.button("🔐 Sign In Instead", use_container_width=True, key="switch_to_login"):
                switch_to_login()
                st.rerun()
    
    return False

def user_profile():
    """Display the user profile section in the sidebar"""
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        
        # Create a nice profile card
        with st.sidebar.container():
            st.markdown("### 👤 User Profile")
            
            # User info with better formatting
            st.markdown(f"""
            **Welcome back!**  
            🏷️ **Name:** {user['username']}  
            🎭 **Role:** {user['role'].capitalize()}  
            """)
            
            # Role-specific badges
            role_badges = {
                'admin': '⚡ Administrator',
                'chef': '👨‍🍳 Chef',
                'staff': '👥 Staff Member',
                'user': '🙂 Customer'
            }
            
            if user['role'] in role_badges:
                st.markdown(f"*{role_badges[user['role']]}*")
            
            st.markdown("---")
            
            # Logout button with confirmation
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
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
            st.warning("🔒 You need to be logged in to access this feature.")
            
            # Show appropriate auth form
            if st.session_state.auth_mode == 'login':
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
    
    if st.session_state.is_authenticated:
        user_profile()
        return True
    
    # Show auth form based on current mode
    if st.session_state.auth_mode == 'login':
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

# Additional utility functions for better UX
def show_auth_status():
    """Show a small authentication status indicator"""
    if st.session_state.is_authenticated:
        user = get_current_user()
        st.sidebar.success(f"✅ Signed in as {user['username']}")
    else:
        st.sidebar.info("ℹ️ Please sign in to continue")

def create_auth_tabs():
    """Create tabbed interface for login/register (alternative UI)"""
    initialize_session_state()
    
    if not st.session_state.is_authenticated:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            login_form()
        
        with tab2:
            registration_form()
    else:
        user_profile()
