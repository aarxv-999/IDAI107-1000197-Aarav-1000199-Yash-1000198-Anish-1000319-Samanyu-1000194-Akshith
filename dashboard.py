"""
Simplified dashboard module for the Smart Restaurant Menu Management App.
"""

import streamlit as st
from typing import Dict, Optional
import datetime

def render_dashboard():
    """Simplified dashboard interface"""
    st.title("🍽️ Dashboard")
    
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    
    # Clean welcome section
    st.markdown(f"### Welcome, {user.get('username', 'User')}!")
    
    # Simplified metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Role", user_role.capitalize())
    
    with col2:
        if user_role in ['admin', 'chef', 'staff']:
            st.metric("Recipes", "24", "+3")
        else:
            st.metric("Quiz Score", "85%")
    
    with col3:
        if user_role in ['admin', 'chef']:
            st.metric("Archive", "24", "+3")
        else:
            st.metric("XP Points", "120")
    
    # Clean feature grid
    st.markdown("### Quick Access")
    
    features = []
    
    if user_role in ['admin', 'staff', 'chef']:
        features.append({
            "title": "Kitchen Management",  # Updated name
            "description": "Generate recipes from leftovers & take cooking quizzes",
            "icon": "🍽️",
            "key": "Kitchen Management"
        })
    
    if user_role in ['admin', 'staff']:
        features.append({
            "title": "Promotion Generator",
            "description": "Create marketing campaigns",
            "icon": "📣",
            "key": "Promotion Generator"
        })
    
    if user_role in ['admin', 'chef']:
        features.append({
            "title": "Chef Recipe Suggestions",
            "description": "Professional recipe recommendations",
            "icon": "👨‍🍳",
            "key": "Chef Recipe Suggestions"
        })
    
    if user_role == 'admin':
        features.append({
            "title": "Visual Menu Search",
            "description": "Search menu items using images",
            "icon": "🔍",
            "key": "Visual Menu Search"
        })
    
    features.extend([
        {
            "title": "Gamification Hub",
            "description": "View achievements and progress",
            "icon": "🎮",
            "key": "Gamification Hub"
        },
        {
            "title": "Event Planning ChatBot",
            "description": "AI-powered event planning assistance",
            "icon": "🎉",
            "key": "Event Planning ChatBot"
        }
    ])
    
    # Simple feature cards
    cols = st.columns(2)
    for i, feature in enumerate(features):
        col_idx = i % 2
        with cols[col_idx]:
            if st.button(f"{feature['icon']} {feature['title']}", key=f"btn_{feature['key']}", use_container_width=True):
                st.session_state.selected_feature = feature['key']
                st.rerun()
            st.caption(feature['description'])
    
    # Simple activity section
    st.markdown("### Recent Activity")
    
    if user_role in ['admin', 'chef', 'staff']:
        activities = [
            "New recipes generated from leftovers",
            "5 cooking quizzes completed by staff",
            "Menu updated with seasonal items"
        ]
    else:
        activities = [
            "Completed cooking quiz (90% score)",
            "Generated 3 recipes from leftovers",
            "Earned 'Quiz Novice' achievement"
        ]
    
    for activity in activities:
        st.write(f"• {activity}")

def get_feature_description(feature_name: str) -> str:
    """Get simplified feature descriptions"""
    descriptions = {
        "Kitchen Management": "🍽️ Generate recipes from leftovers & take cooking quizzes",
        "Gamification Hub": "🎮 View achievements and progress",
        "Event Planning ChatBot": "🎉 AI-powered event planning assistance",
        "Promotion Generator": "📣 Create marketing campaigns",
        "Chef Recipe Suggestions": "👨‍🍳 Professional recipes",
        "Visual Menu Search": "🔍 Search with images"
    }
    return descriptions.get(feature_name, "")
