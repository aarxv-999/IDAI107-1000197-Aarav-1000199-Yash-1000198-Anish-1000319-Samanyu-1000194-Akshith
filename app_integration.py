"""
Integration module for adding the Event Planning Chatbot to the main app
"""

import streamlit as st
from modules.event_planner import event_planner, init_event_firebase

def integrate_event_planner():
    """Function to be called from main_app.py to integrate the event planner"""
    init_event_firebase()
    event_planner()

def check_event_firebase_config():
    """Check if all required environment variables for Event Firebase are set"""
    required_vars = [
        "event_firebase_type",
        "event_firebase_project_id",
        "event_firebase_private_key_id",
        "event_firebase_private_key",
        "event_firebase_client_email",
        "event_firebase_client_id",
        "event_firebase_auth_uri",
        "event_firebase_token_uri",
        "event_firebase_auth_provider_x509_cert_url",
        "event_firebase_client_x509_cert_url"
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in st.secrets:
            missing_vars.append(var)
    
    if missing_vars:
        st.error(f"Missing required environment variables for Event Firebase: {', '.join(missing_vars)}")
        return False

    return True
