import streamlit as st
from typing import Dict, Optional, Tuple
import logging
from modules.auth import register_user, authenticate_user

logger = logging.getLogger(__name__)

def initialize_session_state():
    '''Initialize the session state variables if they don't already  exist'''
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'show_login' not in st.session_state:
        st.session_state.show_login = True  # defaults to showing login form
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False

def toggle_login_register():
    '''ability to toggle between login and registration forms'''
    st.session_state.show_login = not st.session_state.show_login
    st.session_state.show_register = not st.session_state.show_register

def logout_user():
    '''log out option for the current user'''
    st.session_state.user = None
    st.session_state.is_authenticated = False
    st.session_state.show_login = True
    st.session_state.show_register = False
    st.success("You have been logged out successfully!")
    st.rerun()

def login_form() -> bool:
    '''
    create a login form and process any attempts
    
    RETURN - bool: true if the lgoin is succesful or else false
    '''
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
                return True
            else:
                st.error(message)
                return False
    

    st.markdown("Don't have an account already?? [Register here](#)")
    if st.button("Create an account"):
        toggle_login_register()
    
    return False

def registration_form() -> bool:
    '''
    create a registration form and process registration attempts
    
    RETURN - bool: true if registration successful, or else fals
    '''

    st.subheader("Create An Account")
    
    with st.form("registration_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password", 
                                help="Password must be at least 5 characters with uppercase letters and numbers")
        confirm_password = st.text_input("Confirm Password", type="password")
        role = "user"  # default role, assigned to all users 
        
        # to register as a restaurant staff or admin .
        is_staff = st.checkbox("Register as restaurant staff")
        if is_staff:
            role_options = ["staff", "admin", "chef"]
            role = st.selectbox("Select your role", role_options)
            staff_code = st.text_input("Registration code", type="password")
            if staff_code != "staffcode123":  
                role = "user"  # if code entered is wrong then it will revert to user
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
                st.session_state.show_login = True # now switch to login page
                st.session_state.show_register = False
                return True
            else:
                st.error(message)
                return False
    
    # adding the option to go back to login after going to register page.
    st.markdown("Already have an account? [Login here](#)")
    if st.button("Log in instead"):
        toggle_login_register()
    return False

def user_profile():
    '''showcasing the user profile section'''
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        
        st.sidebar.subheader("User Profile")
        st.sidebar.write(f"Welcome, {user['username']}!")
        st.sidebar.write(f"Your Role: {user['role'].capitalize()}")
        if st.sidebar.button("Logout"):
            logout_user()

def auth_required(func):
    '''
    decorator so as to require authentication to access some pages or features 
    USAGE - @auth_required at the beginning of any function

    '''
    def wrapper(*args, **kwargs):
        initialize_session_state()
        
        if st.session_state.is_authenticated:
            return func(*args, **kwargs)
        else:
            st.warning("It is required to be logged in so you can use this feature.")
            if st.session_state.show_login:
                login_form()
            else:
                registration_form()
            return None
    return wrapper

def render_auth_ui():
    '''show the authentication ui based on the current state'''
    initialize_session_state()
    
    if st.session_state.is_authenticated: # if the user is already authenticated then it will show their profile 
        user_profile()
        return True
    
    if st.session_state.show_login: #if not it will show login or registration form
        return login_form()
    else:
        return registration_form()

def get_current_user() -> Optional[Dict]:
    '''
    get the currently logged in user
    
    RETURN - Optional[Dict]: user data if already authenticated, or else None
    '''

    if st.session_state.is_authenticated and st.session_state.user:
        return st.session_state.user
    return None

def is_user_role(required_role: str) -> bool:
    '''
    check if user has required role for some tasks

    ARGUMENT - required_role(str): the role which has to be checked
        
    RETURN - bool: true if user has role or else False
    '''

    user = get_current_user()
    if user and user['role'] == required_role:
        return True
    return False
