import hashlib
import uuid
import logging
from typing import Dict, Optional, Tuple
import datetime
from firebase_admin import firestore
from firebase_init import init_firebase

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def validate_password(password: str) -> Tuple[bool, str]:
    if len(password) < 5:
        return False, "Password must be at least 5 characters"
    
    has_upper = any(char.isupper() for char in password)
    has_digit = any(char.isdigit() for char in password)
    
    if not (has_upper and has_digit):
        return False, "Password must have uppercase letter and number"
    return True, ""

def validate_email(email: str) -> Tuple[bool, str]:
    if '@' not in email or '.' not in email.split('@')[1]:
        return False, "Invalid email format"
    return True, ""

def get_firestore_db():
    init_firebase()
    return firestore.client()

def email_exists(email: str) -> bool:
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1).get()
        return len(query) > 0
    except:
        return False

def username_exists(username: str) -> bool:
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).get()
        return len(query) > 0
    except:
        return False

def register_user(username: str, email: str, password: str, role: str = "user") -> Tuple[bool, str]:
    try:
        # Validate inputs
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            return False, error_msg
            
        if email_exists(email):
            return False, "Email already registered"
            
        if username_exists(username):
            return False, "Username taken"
            
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return False, error_msg
            
        # Create user
        password_hash = hash_password(password)
        user_id = str(uuid.uuid4())
        time_created = datetime.datetime.now().strftime("%d-%m-%y %H:%M")
        
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
        
        return True, "Registration successful"
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration failed: {str(e)}"

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        
        # Try username first
        user_docs = list(users_ref.where('username', '==', username_or_email).limit(1).get())
        
        # Try email if not found
        if not user_docs:
            user_docs = list(users_ref.where('email', '==', username_or_email).limit(1).get())
            
        if not user_docs:
            return False, None, "Invalid credentials"
            
        user_data = user_docs[0].to_dict()
        stored_hash = user_data['password_hash']
        provided_hash = hash_password(password)
        
        if stored_hash == provided_hash:
            user_data.pop('password_hash', None)
            return True, user_data, "Login successful"
        else:
            return False, None, "Invalid credentials"
            
    except Exception as e:
        logger.error(f"Auth error: {str(e)}")
        return False, None, f"Login failed: {str(e)}"
