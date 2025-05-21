"""
Authentication module for the Smart Restaurant Menu Management App.
Handles user registration, authentication, and related functions using Firebase.
"""

import hashlib
import uuid
import logging
from typing import Dict, Optional, Tuple
import datetime
from firebase_admin import firestore
from firebase_init import init_firebase

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """
    Hash the password using SHA-256 algorithm.
    
    Args:
        password (str): The password to hash
    
    Returns:
        str: The hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()

def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate that the password meets security requirements.
    
    Args:
        password (str): The password to validate
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    
    has_upper = any(char.isupper() for char in password)
    has_digit = any(char.isdigit() for char in password)
    
    if not (has_upper and has_digit):
        return False, "Password must contain at least one uppercase letter and one number."
    return True, ""

def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate that the email has a proper format.
    
    Args:
        email (str): The email to validate
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if '@' not in email or '.' not in email.split('@')[1]:
        return False, "Please use a proper email format"
    return True, ""

def get_firestore_db():
    """
    Get a Firestore client instance.
    
    Returns:
        firestore.Client: Firestore database client
    """
    # Ensure Firebase is initialized
    init_firebase()
    return firestore.client()

def email_exists(email: str) -> bool:
    """
    Check if an email already exists in the database.
    
    Args:
        email (str): The email to check
    
    Returns:
        bool: True if email exists, False otherwise
    """
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1).get()
        return len(query) > 0
    except Exception as e:
        logger.error(f"Error checking if email exists: {str(e)}")
        return False

def username_exists(username: str) -> bool:
    """
    Check if a username already exists in the database.
    
    Args:
        username (str): The username to check
    
    Returns:
        bool: True if username exists, False otherwise
    """
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).get()
        return len(query) > 0
    except Exception as e:
        logger.error(f"Error checking if username exists: {str(e)}")
        return False

def register_user(username: str, email: str, password: str, role: str = "user") -> Tuple[bool, str]:
    """
    Register a new user in the Firebase database.
    
    Args:
        username (str): User's username
        email (str): User's email
        password (str): User's password
        role (str, optional): User's role. Defaults to "user".
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Validate inputs
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            return False, error_msg
            
        if email_exists(email):
            return False, "Email has already been registered"
            
        if username_exists(username):
            return False, "Username already taken"
            
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return False, error_msg
            
        # Hash password and prepare user data
        password_hash = hash_password(password)
        user_id = str(uuid.uuid4())
        time_created = datetime.datetime.now().strftime("%d-%m-%y %H:%M")
        
        # Store user in Firestore
        db = get_firestore_db()
        users_ref = db.collection('users')
        
        users_ref.document(user_id).set({
            'user_id': user_id,
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'role': role,
            'time_created': time_created
        })
        
        logger.info(f"{username} has been registered")
        return True, "User registration successful"
        
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return False, f"User registration unsuccessful: {str(e)}"

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Authenticate a user with username/email and password.
    
    Args:
        username_or_email (str): User's username or email
        password (str): User's password
    
    Returns:
        Tuple[bool, Optional[Dict], str]: (success, user_data, message)
    """
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        
        # Try to find user by username
        user_docs = list(users_ref.where('username', '==', username_or_email).limit(1).get())
        
        # If not found by username, try email
        if not user_docs:
            user_docs = list(users_ref.where('email', '==', username_or_email).limit(1).get())
            
        if not user_docs:
            return False, None, "Invalid username/email or password entered!"
            
        # Get user data and verify password
        user_data = user_docs[0].to_dict()
        stored_hash = user_data['password_hash']
        provided_hash = hash_password(password)
        
        if stored_hash == provided_hash:
            # Remove password hash before returning user data
            user_data.pop('password_hash', None)
            logger.info(f"User has been authenticated: {username_or_email}")
            return True, user_data, "Authentication was successful!"
        else:
            return False, None, "Invalid username/email or password."
            
    except Exception as e:
        logger.error(f"Error authenticating user: {str(e)}")
        return False, None, f"Authentication has failed: {str(e)}"
