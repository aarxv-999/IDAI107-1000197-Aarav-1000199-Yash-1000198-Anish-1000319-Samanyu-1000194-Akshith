"""
Integration module for adding the Event Planning Chatbot to the main app
This file provides the necessary functions to integrate with main_app.py
"""

import streamlit as st
from modules.event_planner import event_planner

def integrate_event_planner():
    """
    Function to be called from main_app.py to integrate the event planner
    
    This replaces the placeholder function in main_app.py
    """
    # Call the main event planner function directly
    # No Firebase initialization needed
    event_planner()

# Simplified check function that always returns True
def check_event_firebase_config():
    """
    Simplified function that always returns True since we no longer need Firebase
    
    Returns:
        bool: Always True
    """
    # Log that we're using the simplified version
    st.session_state.event_firebase_enabled = False
    return True
