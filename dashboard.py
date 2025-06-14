"""
Dashboard module for the Smart Restaurant Menu Management App.
Provides a central dashboard view that users see after logging in.
"""

import streamlit as st
from typing import Dict, Optional
import datetime

def render_dashboard():
    """
    Render the main dashboard that users see after logging in.
    This serves as the central hub for accessing all features.
    """
    st.title("🍽️ Restaurant Management Dashboard")
    
    # Get current user
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    
    # Welcome message with current date
    current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
    st.markdown(f"### Welcome, {user.get('username', 'User')}!")
    st.markdown(f"**Today is:** {current_date}")
    
    # Dashboard metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Role",
            value=user_role.capitalize(),
            delta=None,
            help="Your current role in the system"
        )
    
    with col2:
        # Different metrics based on user role
        if user_role in ['admin', 'chef', 'staff']:
            st.metric(
                label="Recipe Archive",
                value="24",
                delta="+3 from last week",
                help="Number of recipes in the archive"
            )
        else:
            st.metric(
                label="Quiz Score",
                value="85%",
                delta=None,
                help="Your average quiz score"
            )
    
    with col3:
        if user_role in ['admin', 'chef']:
            st.metric(
                label="Menu Items",
                value="156",
                delta="+12 new",
                help="Total number of menu items"
            )
        else:
            st.metric(
                label="XP Points",
                value="120",
                delta=None,
                help="Your experience points"
            )
    
    # Feature cards
    st.markdown("### Features")
    st.markdown("Select a feature from the sidebar or click on a card below to get started.")
    
    # Define available features based on user role
    features = []
    
    # Role-specific features
    if user_role in ['admin', 'chef']:
        features.append({
            "title": "Leftover Management",
            "description": "Generate recipes from leftover ingredients to reduce waste",
            "icon": "♻️",
            "key": "Leftover Management"
        })
    
    if user_role in ['admin', 'staff']:
        features.append({
            "title": "Promotion Generator",
            "description": "AI-powered marketing campaign generation with automatic scoring",
            "icon": "📣",
            "key": "Promotion Generator"
        })
    
    if user_role in ['admin', 'chef']:
        features.append({
            "title": "Chef Recipe Suggestions",
            "description": "AI-powered menu generation, chef submissions, and analytics",
            "icon": "👨‍🍳",
            "key": "Chef Recipe Suggestions"
        })
    
    # Common features for all users
    features.append({
        "title": "Visual Menu Search",
        "description": "AI-powered dish detection, personalized recommendations, and staff challenges",
        "icon": "📷",
        "key": "Visual Menu Search"
    })
    
    features.append({
        "title": "Gamification Hub",
        "description": "View achievements, leaderboard, and progress",
        "icon": "🎮",
        "key": "Gamification Hub"
    })
    
    features.append({
        "title": "Cooking Quiz",
        "description": "Test your culinary knowledge and earn XP",
        "icon": "🧠",
        "key": "Cooking Quiz"
    })
    
    features.append({
        "title": "Event Planning ChatBot",
        "description": "AI-powered event planning assistance",
        "icon": "🎉",
        "key": "Event Planning ChatBot"
    })
    
    # Display feature cards in a grid
    cols = st.columns(3)
    for i, feature in enumerate(features):
        col_idx = i % 3
        with cols[col_idx]:
            with st.container():
                st.markdown(f"""
                <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid #e0e0e0; margin-bottom: 1rem;">
                    <h3>{feature['icon']} {feature['title']}</h3>
                    <p>{feature['description']}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Open", key=f"open_{feature['key']}", use_container_width=True):
                    st.session_state.selected_feature = feature['key']
                    st.rerun()
    
    # Recent activity section
    st.markdown("### Recent Activity")
    
    # Different activity items based on user role
    if user_role in ['admin', 'chef', 'staff']:
        activities = [
            {"time": "Today, 10:30 AM", "description": "New recipes added to the archive"},
            {"time": "Yesterday", "description": "Weekly menu generated with 35 dishes"},
            {"time": "2 days ago", "description": "Chef submitted 3 new signature dishes"},
            {"time": "3 days ago", "description": "Staff challenge received 15 customer votes"}
        ]
    else:
        activities = [
            {"time": "Today", "description": "Completed cooking quiz with 90% score"},
            {"time": "Yesterday", "description": "Generated 3 recipes from leftovers"},
            {"time": "2 days ago", "description": "Used AI dish detection feature"},
            {"time": "Last week", "description": "Earned 'Quiz Novice' achievement"}
        ]
    
    for activity in activities:
        st.markdown(f"**{activity['time']}**: {activity['description']}")
    
    # Tips and help section
    with st.expander("Tips & Help"):
        st.markdown("""
        - Use the sidebar to navigate between different features
        - Click on feature cards above for quick access
        - Check the Gamification Hub to track your progress
        - Chefs and Admins can access advanced menu management tools
        - Staff and Admins can create AI-powered marketing campaigns
        - All users can use Visual Menu Search for AI dish detection
        - Vote on staff challenge dishes to earn XP
        - Need help? Contact support at support@restaurant.com
        """)

def get_feature_description(feature_name: str) -> str:
    """Get the description for a specific feature"""
    descriptions = {
        "Leftover Management": "♻️ Generate recipes from leftover ingredients",
        "Gamification Hub": "🎮 View achievements, leaderboard, and progress",
        "Cooking Quiz": "🧠 Test your culinary knowledge and earn XP",
        "Promotion Generator": "📣 AI marketing campaigns with automatic scoring",
        "Chef Recipe Suggestions": "👨‍🍳 AI menu generation, chef submissions & analytics",
        "Visual Menu Search": "📷 AI dish detection, personalized recommendations & staff challenges",
        "Event Planning ChatBot": "🎉 AI-powered event planning assistance"
    }
    return descriptions.get(feature_name, "")
