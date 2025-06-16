"""
Dashboard module for the Smart Restaurant Menu Management App.
Provides a central dashboard view that users see after logging in.
"""

import streamlit as st
from typing import Dict, Optional
import datetime
from modules.notifications import render_notification_bell

def render_dashboard():
    """
    Render the main dashboard that users see after logging in.
    This serves as the central hub for accessing all features.
    """
    # Get current user
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    username = user.get('username', 'User')
    
    # Header section with notification bell
    col1, col2 = st.columns([4, 1])

    with col1:
        st.title("🏠 Restaurant Management Dashboard")

    with col2:
        # Add notification bell for authenticated users
        user = st.session_state.get('user', {})
        if user and user.get('user_id'):
            render_notification_bell(user['user_id'])

    # Welcome section with clean layout
    st.markdown(f"### Welcome back, **{username}**! 👋")
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    st.markdown(f"📅 {current_date}")
    
    st.divider()
    
    # Features section
    st.markdown("### 🚀 Available Features")
    st.markdown("*Click on any feature to get started*")
    
    # Get role-specific features
    features = get_features_for_role(user_role)
    
    # Display features in a clean grid
    for i in range(0, len(features), 2):
        col1, col2 = st.columns(2)
        
        # First feature in the row
        with col1:
            if i < len(features):
                render_feature_card(features[i])
        
        # Second feature in the row (if exists)
        with col2:
            if i + 1 < len(features):
                render_feature_card(features[i + 1])

def render_feature_card(feature):
    """Render a clean feature card with dark theme"""
    with st.container():
        # Create a bordered container with dark theme
        st.markdown(f"""
        <div style="
            padding: 1.5rem; 
            border-radius: 10px; 
            border: 1px solid #374151; 
            background-color: #1f2937;
            margin-bottom: 1rem;
            height: 180px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        ">
            <div>
                <h4 style="margin: 0 0 0.5rem 0; color: #f9fafb;">
                    {feature['icon']} {feature['title']}
                </h4>
                <p style="margin: 0; color: #d1d5db; font-size: 0.9rem;">
                    {feature['description']}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Button below the card
        if st.button(
            "Open Feature", 
            key=f"open_{feature['key']}", 
            use_container_width=True,
            type="primary"
        ):
            st.session_state.selected_feature = feature['key']
            st.rerun()

def get_features_for_role(user_role):
    """Get available features based on user role (excluding Gamification Hub)"""
    all_features = {
        'ingredients': {
            "title": "Ingredients Management",
            "description": "Complete CRUD operations for ingredient inventory with AI suggestions and smart categorization",
            "key": "Ingredients Management",
            "icon": "📦",
            "roles": ['admin', 'staff']
        },
        'leftover': {
            "title": "Leftover Management", 
            "description": "Generate creative recipes from leftover ingredients to reduce waste and save costs",
            "key": "Leftover Management",
            "icon": "♻️",
            "roles": ['admin', 'chef', 'user']
        },
        'promotion': {
            "title": "Promotion Generator",
            "description": "AI-powered marketing campaign generation with automatic scoring and analytics",
            "key": "Promotion Generator", 
            "icon": "📢",
            "roles": ['admin', 'staff']
        },
        'chef': {
            "title": "Chef Recipe Suggestions",
            "description": "AI-powered menu generation, chef submissions, ratings, and comprehensive analytics",
            "key": "Chef Recipe Suggestions",
            "icon": "👨‍🍳",
            "roles": ['admin', 'chef']
        },
        'visual': {
            "title": "Visual Menu Search",
            "description": "AI-powered dish detection, personalized recommendations, and interactive staff challenges",
            "key": "Visual Menu Search",
            "icon": "📷",
            "roles": ['admin', 'chef', 'staff', 'user']
        },
        'chatbot': {
            "title": "Event Planning ChatBot",
            "description": "AI-powered event planning assistance with smart recommendations and booking",
            "key": "Event Planning ChatBot",
            "icon": "🤖",
            "roles": ['admin', 'chef', 'staff', 'user']
        }
    }
    
    # Filter features based on user role
    available_features = []
    for feature_key, feature_data in all_features.items():
        if user_role in feature_data['roles']:
            available_features.append(feature_data)
    
    return available_features

def get_feature_description(feature_name: str) -> str:
    """Get the description for a specific feature"""
    descriptions = {
        "Ingredients Management": "Complete CRUD operations for ingredient inventory",
        "Leftover Management": "Generate recipes from leftover ingredients", 
        "Promotion Generator": "AI marketing campaigns with automatic scoring",
        "Chef Recipe Suggestions": "AI menu generation, chef submissions & analytics",
        "Visual Menu Search": "AI dish detection, personalized recommendations & staff challenges",
        "Event Planning ChatBot": "AI-powered event planning assistance"
    }
    return descriptions.get(feature_name, "")
