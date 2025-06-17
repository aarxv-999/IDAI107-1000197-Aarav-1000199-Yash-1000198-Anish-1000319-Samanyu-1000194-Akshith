import streamlit as st
from typing import Dict, Optional
import datetime

def render_dashboard():
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    username = user.get('username', 'User')
    
    st.title("Restaurant Management Dashboard")    
    st.markdown(f"### Welcome back, **{username}**! ")
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    st.markdown(f"{current_date}")
    st.divider()
    
    st.markdown("### Available Features")
    st.markdown("*Click on any feature to get started*")
    
    features = get_features_for_role(user_role)
    
    for i in range(0, len(features), 2):
        col1, col2 = st.columns(2)        
        with col1:
            if i < len(features):
                render_feature_card(features[i])        
        with col2:
            if i + 1 < len(features):
                render_feature_card(features[i + 1])

def render_feature_card(feature):
    """Render a clean feature card with dark theme"""
    with st.container():
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
                    {feature.get('icon', '')} {feature['title']}
                </h4>
                <p style="margin: 0; color: #d1d5db; font-size: 0.9rem;">
                    {feature['description']}
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
            "roles": ['admin', 'staff']
        },
        'leftover': {
            "title": "Leftover Management", 
            "description": "Generate creative recipes from leftover ingredients to reduce waste and save costs",
            "key": "Leftover Management",
            "roles": ['admin', 'chef', 'user']
        },
        'promotion': {
            "title": "Promotion Generator",
            "description": "AI-powered marketing campaign generation with automatic scoring and analytics",
            "key": "Promotion Generator", 
            "roles": ['admin', 'staff']
        },
        'chef': {
            "title": "Chef Recipe Suggestions",
            "description": "AI-powered menu generation, chef submissions, ratings, and comprehensive analytics",
            "key": "Chef Recipe Suggestions",
            "roles": ['admin', 'chef']
        },
        'visual': {
            "title": "Visual Menu Search",
            "description": "AI-powered dish detection, personalized recommendations, and interactive staff challenges",
            "key": "Visual Menu Search",
            "roles": ['admin', 'chef', 'staff', 'user']
        },
        'chatbot': {
            "title": "Event Planning ChatBot",
            "description": "AI-powered event planning assistance with smart recommendations and booking",
            "key": "Event Planning ChatBot",
            "roles": ['admin', 'chef', 'staff', 'user']
        }
    }
    
    available_features = []
    for feature_key, feature_data in all_features.items():
        if user_role in feature_data['roles']:
            available_features.append(feature_data)
    
    return available_features

def get_feature_description(feature_name: str) -> str:
    descriptions = {
        "Ingredients Management": "Complete CRUD operations for ingredient inventory",
        "Leftover Management": "Generate recipes from leftover ingredients", 
        "Promotion Generator": "AI marketing campaigns with automatic scoring",
        "Chef Recipe Suggestions": "AI menu generation, chef submissions & analytics",
        "Visual Menu Search": "AI dish detection, personalized recommendations & staff challenges",
        "Event Planning ChatBot": "AI-powered event planning assistance"
    }
    return descriptions.get(feature_name, "")
