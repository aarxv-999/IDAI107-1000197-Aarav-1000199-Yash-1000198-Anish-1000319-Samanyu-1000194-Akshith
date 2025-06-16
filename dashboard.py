"""
Dashboard module for the Smart Restaurant Menu Management App.
Provides a central dashboard view that users see after logging in.
"""

import streamlit as st
from typing import Dict, Optional
import datetime
import logging

logger = logging.getLogger(__name__)

def render_dashboard():
    """
    Render the main dashboard that users see after logging in.
    This serves as the central hub for accessing all features.
    """
    try:
        # Get current user
        user = st.session_state.get('user', {})
        user_role = user.get('role', 'user')
        username = user.get('username', 'User')
        full_name = user.get('full_name', username)
        
        # Header section
        st.title("🏠 Restaurant Management Dashboard")
        
        # Welcome section with clean layout
        st.markdown(f"### Welcome back, **{full_name}**! 👋")
        current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
        st.markdown(f"📅 {current_date}")
        
        # Role badge
        role_colors = {
            'admin': '🔴',
            'staff': '🟡', 
            'chef': '🟢',
            'user': '🔵'
        }
        role_color = role_colors.get(user_role, '🔵')
        st.markdown(f"**Role:** {role_color} {user_role.title()}")
        
        st.divider()
        
        # Quick stats section
        render_quick_stats(user)
        
        st.divider()
        
        # Features section
        st.markdown("### 🚀 Available Features")
        st.markdown("*Click on any feature to get started*")
        
        # Get role-specific features
        features = get_features_for_role(user_role)
        
        if not features:
            st.warning("No features available for your role. Please contact an administrator.")
            return
        
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
                else:
                    # Empty placeholder to maintain layout
                    st.empty()
        
        # Help section
        st.divider()
        render_help_section(user_role)
        
    except Exception as e:
        logger.error(f"Error rendering dashboard: {str(e)}")
        st.error("Error loading dashboard. Please refresh the page.")
        st.exception(e)

def render_quick_stats(user):
    """Render quick stats section"""
    try:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Features Available", len(get_features_for_role(user.get('role', 'user'))))
        
        with col2:
            # Try to get user stats
            try:
                from modules.leftover import get_user_stats
                user_stats = get_user_stats(user.get('user_id'))
                if isinstance(user_stats, dict):
                    total_xp = user_stats.get('total_xp', 0)
                elif isinstance(user_stats, tuple):
                    total_xp = user_stats[0] if len(user_stats) > 0 else 0
                else:
                    total_xp = 0
                st.metric("Total XP", f"{total_xp:,}")
            except Exception:
                st.metric("Total XP", "N/A")
        
        with col3:
            # Current time
            current_time = datetime.datetime.now().strftime("%H:%M")
            st.metric("Current Time", current_time)
        
        with col4:
            # Days since registration
            try:
                created_at = user.get('created_at')
                if created_at:
                    # Handle different date formats
                    if hasattr(created_at, 'date'):
                        created_date = created_at.date()
                    else:
                        created_date = datetime.datetime.now().date()
                    
                    days_since = (datetime.datetime.now().date() - created_date).days
                    st.metric("Days Active", days_since)
                else:
                    st.metric("Days Active", "N/A")
            except Exception:
                st.metric("Days Active", "N/A")
                
    except Exception as e:
        logger.error(f"Error rendering quick stats: {str(e)}")

def render_feature_card(feature):
    """Render a clean feature card"""
    try:
        with st.container():
            # Create a clean card layout
            st.markdown(f"""
            <div style="
                padding: 1.5rem; 
                border-radius: 10px; 
                border: 1px solid #e5e7eb; 
                background-color: #f9fafb;
                margin-bottom: 1rem;
                min-height: 160px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            ">
                <div>
                    <h4 style="margin: 0 0 0.5rem 0; color: #1f2937; font-size: 1.1rem;">
                        {feature['icon']} {feature['title']}
                    </h4>
                    <p style="margin: 0; color: #6b7280; font-size: 0.9rem; line-height: 1.4;">
                        {feature['description']}
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Button below the card
            if st.button(
                f"Open {feature['title']}", 
                key=f"open_{feature['key']}", 
                use_container_width=True,
                type="primary"
            ):
                st.session_state.selected_feature = feature['key']
                st.rerun()
                
    except Exception as e:
        logger.error(f"Error rendering feature card: {str(e)}")
        st.error(f"Error loading feature: {feature.get('title', 'Unknown')}")

def get_features_for_role(user_role):
    """Get available features based on user role"""
    try:
        all_features = {
            'ingredients': {
                "title": "Ingredients Management",
                "description": "Complete CRUD operations for ingredient inventory with AI suggestions and smart categorization",
                "key": "Ingredients Management",
                "icon": "📦",
                "roles": ['admin', 'staff', 'chef']
            },
            'leftover': {
                "title": "Leftover Management", 
                "description": "Generate creative recipes from leftover ingredients to reduce waste and save costs",
                "key": "Leftover Management",
                "icon": "♻️",
                "roles": ['admin', 'chef', 'staff']
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
            },
            'gamification': {
                "title": "Gamification Hub",
                "description": "Track your progress, earn XP, unlock achievements, and compete on leaderboards",
                "key": "Gamification Hub",
                "icon": "🎮",
                "roles": ['admin', 'chef', 'staff', 'user']
            }
        }
        
        # Filter features based on user role
        available_features = []
        for feature_key, feature_data in all_features.items():
            if user_role in feature_data['roles']:
                available_features.append(feature_data)
        
        return available_features
        
    except Exception as e:
        logger.error(f"Error getting features for role {user_role}: {str(e)}")
        return []

def render_help_section(user_role):
    """Render help and tips section"""
    try:
        st.markdown("### 💡 Quick Tips")
        
        tips_by_role = {
            'admin': [
                "🔧 Use Ingredients Management to maintain inventory",
                "📊 Check Promotion Generator for marketing campaigns",
                "👥 Monitor all features for team productivity"
            ],
            'staff': [
                "📢 Create marketing campaigns with Promotion Generator",
                "📦 Manage inventory with Ingredients Management",
                "🎮 Earn XP by completing tasks in Gamification Hub"
            ],
            'chef': [
                "👨‍🍳 Submit recipes via Chef Recipe Suggestions",
                "♻️ Use Leftover Management to reduce waste",
                "📷 Try Visual Menu Search for dish inspiration"
            ],
            'user': [
                "📷 Explore dishes with Visual Menu Search",
                "🤖 Plan events with Event Planning ChatBot",
                "🎮 Track progress in Gamification Hub"
            ]
        }
        
        tips = tips_by_role.get(user_role, tips_by_role['user'])
        
        for tip in tips:
            st.markdown(f"- {tip}")
            
    except Exception as e:
        logger.error(f"Error rendering help section: {str(e)}")

def get_feature_description(feature_name: str) -> str:
    """Get the description for a specific feature"""
    try:
        descriptions = {
            "Dashboard": "Central hub for accessing all restaurant management features",
            "Ingredients Management": "Complete CRUD operations for ingredient inventory with AI suggestions",
            "Leftover Management": "Generate creative recipes from leftover ingredients to reduce waste", 
            "Promotion Generator": "AI-powered marketing campaign generation with automatic scoring",
            "Chef Recipe Suggestions": "AI menu generation, chef submissions, ratings & comprehensive analytics",
            "Visual Menu Search": "AI dish detection, personalized recommendations & interactive challenges",
            "Event Planning ChatBot": "AI-powered event planning assistance with smart recommendations",
            "Gamification Hub": "Track progress, earn XP, unlock achievements, and compete on leaderboards"
        }
        return descriptions.get(feature_name, "")
    except Exception as e:
        logger.error(f"Error getting feature description for {feature_name}: {str(e)}")
        return ""

# Additional utility functions
def get_user_activity_summary(user_id):
    """Get a summary of user activity"""
    try:
        from modules.leftover import get_user_stats
        user_stats = get_user_stats(user_id)
        
        if isinstance(user_stats, dict):
            return {
                'total_xp': user_stats.get('total_xp', 0),
                'level': user_stats.get('level', 1),
                'recipes_generated': user_stats.get('recipes_generated', 0),
                'quizzes_completed': user_stats.get('quizzes_completed', 0)
            }
        elif isinstance(user_stats, tuple) and len(user_stats) >= 3:
            return {
                'total_xp': user_stats[0],
                'level': user_stats[1],
                'additional_stats': user_stats[2] if len(user_stats) > 2 else {}
            }
        else:
            return {
                'total_xp': 0,
                'level': 1,
                'recipes_generated': 0,
                'quizzes_completed': 0
            }
    except Exception as e:
        logger.error(f"Error getting user activity summary: {str(e)}")
        return {
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'quizzes_completed': 0
        }

def check_feature_availability(feature_key, user_role):
    """Check if a feature is available for a specific user role"""
    try:
        features = get_features_for_role(user_role)
        return any(feature['key'] == feature_key for feature in features)
    except Exception as e:
        logger.error(f"Error checking feature availability: {str(e)}")
        return False
