'''MADE BY: Aarav Agarwal 100097, IBCP CRS: AI
This file will serve as the functionality for the user authentication feature

Packages used:
- pandas: to store and read user data in CSV files
- hashlib: for hashing passwords
- uuid: to generate UUIDs
- os: for all file operations
'''

import pandas as pd
import hashlib
import uuid
import os
from typing import Dict, Optional, Tuple
import logging

#setting logging for debugging 
logger = logging.getLogger(__name__)

#setting path for user database
USER_DB_PATH = "data/users.csv"

def ensure_user_db_exists():
    # making sure that the database for users is available
    os.makedirs(os.path.dirname(USER_DB_PATH), exist_ok=True)
    #creating the database if its not found
    if not os.path.exists(USER_DB_PATH):
        df.to_csv(USER_DB_PATH, index=False)
        df = pd.DataFrame(columns=['user_id', 'username', 'email', 'password_hash', 'role', 'time'])
        logger.info(f"DEBUGGING: created a user database at {USER_DB_PATH}")

def hash_password(password: str) -> str:
    '''
    hashing the password using "sha-256" (security-hash-algorithm, not the most secure yet fast, just for demo)
    ARGUMENT: password(str): the password that has to be hashed
    
    RETURN: str: hashed password
    '''
    return hashlib.sha256(password.encode()).hexdigest()

def validate_password(password: str) -> Tuple[bool, str]:
    '''
    making sure that the passwords meeet a sample security tequirement
    ARGUMENT: password(str): the password that has to be checked
    
    RETURN: Tuple[bool, str]: (is_valid, error_message) 
        (it will definitely return a boolean value, stating whether the password is eligible or not)
        (if it is not, then it will also return an error message to explain that the password doesnt meet requirment or any other error)
    '''
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    
    has_upper = any(char.isupper() for char in password)
    has_digit = any(char.isdigit() for char in password)
    
    if not (has_upper and has_digit):
        return False, "Password must contain at least one uppercase letter and one number."
    return True, "" 
    # this means that the password that has been given has been returned since it hhss passed the tests, "" means no error msg

def validate_email(email: str) -> Tuple[bool, str]:
    '''
    this will check if the email entered by the user is a valid email
    ARGUMENT: email (str): user's email
        
    RETURN: Tuple[bool, str]: (is_valid, error_message): just like the password it will return a boolean value and a error message
    '''

    if '@' not in email or '.' not in email.split('@')[1]: #basically this will check if there is an @ or not and if there's a . after it (like how there is gmail"."com)
        return False, "Please use a proper email format"
    return True, ""

def email_exists(email: str) -> bool:
    '''
    Making sure that the mail is not already registered in the daabse
    
    ARGUMENT: email(str): user's email
        
    RETURN: bool: true if email is already there, or else false
    '''
    ensure_user_db_exists()
    try:
        df = pd.read_csv(USER_DB_PATH)
        return email in df['email'].values #this part checks if the email is there or not after turning it into an arrau of email values
    except Exception as e:
        logger.error(f"There was an issue checking if the email exists: {str(e)}")
        return False

def username_exists(username: str) -> bool:
    '''
    making sure that the username is not already taken by another user
    
    ARGUMENT: username (str): the username to check
    
    RETURN: bool: True - username exists , false - Username doesnt exist
    '''
    ensure_user_db_exists()
    try:
        df = pd.read_csv(USER_DB_PATH)
        return username in df['username'].values
    except Exception as e:
        logger.error(f"There was an error in checking if the username exists: {str(e)}")
        return False

def register_user(username: str, email: str, password: str, role: str = "user") -> Tuple[bool, str]:
    '''
    this will register the user assuming all previous checks have passed
    
    ARGUMENT: username(str), email(str), password(str), role(str) - This is the role of the user [user, staff, admin]

    RETURN: Tuple[bool,str]: (success, msg)
    '''
    ensure_user_db_exists()
    
    try:
        is_valid, error_msg = validate_email(email) # checking if mail format is right
        if not is_valid:
            return False, error_msg
        if email_exists(email): # checking if mail already taken
            return False, "Email has already been registered"
        if username_exists(username): # check if username already taken
            return False, "Username already taken"
        is_valid, error_msg = validate_password(password) # check if password is correct
        if not is_valid:
            return False, error_msg
        password_hash = hash_password(password) # encrypting password
        
        user_id = str(uuid.uuid4()) # creating a uuid for the user. 
        
        import datetime
        time = datetime.datetime.now().strftime("%d-%m-%y %H:%M") # this is to get a timestamp of when exactly the account was made
        
        df = pd.read_csv(USER_DB_PATH)
        
        #finally, adding the new user
        new = pd.DataFrame({
            'user_id': [user_id],
            'username': [username],
            'email': [email],
            'password_hash': [password_hash],
            'role': [role],
            'time': [time]
        })
        
        df = pd.concat([df, new], ignore_index=True) #adding the new person to the pre-existing dataframe (df)
        df.to_csv(USER_DB_PATH, index=False) #saving all updated changes to the csv 
    
        logger.info(f"{username} has been registered")
        return True, "User registration sucess"
    
    except Exception as e:
        logger.error(f"There was an eror in registering user: {str(e)}")
        return False, f"User registration unsuccessful: {str(e)}"

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    '''
    authenticating the user with username or email and password
    
    ARGUMENT: username_or_email (str), password(str)

    RETURN: Tuple[bool, Optional[Dict], str]: (success, user_data, message)
    '''

    ensure_user_db_exists()
    
    try:
        df = pd.read_csv(USER_DB_PATH)
    
        user = df[(df['username'] == username_or_email) | (df['email'] == username_or_email)] # finding the username or mail
        
        if user.empty:
            return False, None, "Invalid username/email or password entered!"
        
        stored_hash = user.iloc[0]['password_hash'] # checking password.
        
        provided_hash = hash_password(password) # hashing the given passwod
        
        if stored_hash == provided_hash: # comparing passwords
            user_data = user.iloc[0].to_dict() # converting dataframe to a dictionary for more convenient data manipulation in next step
            user_data.pop('password_hash') # removing the password hash from the dictionary so that its not expose
            logger.info(f"User has been authenticated!: {username_or_email}")
            return True, user_data, "Authentication was successful!"
        else:
            return False, None, "Invalid username/email or password."
    
    except Exception as e:
        logger.error(f"Error in authenticating user: {str(e)}")
        return False, None, f"Authentication has failed: {str(e)}"

