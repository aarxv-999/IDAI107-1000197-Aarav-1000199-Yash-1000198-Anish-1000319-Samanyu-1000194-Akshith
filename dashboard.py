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
    # Get current user
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    username = user.get('username', 'User')
    
    # Header section
    st.title("🏠 Restaurant Management Dashboard")
    
    # Welcome section with clean layout
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"### Welcome back, **{username}**! 👋")
        current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
        st.markdown(f"📅 {current_date}")
    
    with col2:
        st.markdown("### Your Role")
        role_emoji = {
            'admin': '👑',
            'chef': '👨‍🍳', 
            'staff': '👥',
            'user': '👤'
        }
        st.markdown(f"## {role_emoji.get(user_role, '👤')} {user_role.capitalize()}")
    
    st.divider()
    
    # Quick stats section
    st.markdown("### 📊 Quick Stats")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if user_role in ['admin', 'chef', 'staff']:
            st.metric("📦 Recipes", "24", delta="3", help="Recipes in archive")
        else:
            st.metric("⭐ XP Points", "1,240", delta="50", help="Experience points earned")
    
    with col2:
        if user_role in ['admin', 'chef']:
            st.metric("🍽️ Menu Items", "156", delta="12", help="Total menu items")
        else:
            st.metric("🏆 Achievements", "12", delta="1", help="Unlocked achievements")
    
    with col3:
        if user_role in ['admin', 'staff']:
            st.metric("📈 Campaigns", "8", delta="2", help="Active promotions")
        else:
            st.metric("🔥 Streak", "7 days", help="Daily activity streak")
    
    with col4:
        if user_role in ['admin']:
            st.metric("👥 Active Users", "45", delta="5", help="Users this week")
        else:
            st.metric("📚 Recipes Found", "89", help="Total recipes discovered")
    
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
    
    st.divider()
    
    # Recent activity section
    st.markdown("### 📋 Recent Activity")
    
    activities = get_recent_activities(user_role)
    
    for activity in activities:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"**{activity['time']}**")
            with col2:
                st.markdown(f"{activity['icon']} {activity['description']}")
    
    # Quick actions section
    st.divider()
    st.markdown("### ⚡ Quick Actions")
    
    quick_actions = get_quick_actions(user_role)
    cols = st.columns(len(quick_actions))
    
    for i, action in enumerate(quick_actions):
        with cols[i]:
            if st.button(
                f"{action['icon']} {action['title']}", 
                key=f"quick_{action['key']}", 
                use_container_width=True,
                type="secondary"
            ):
                st.session_state.selected_feature = action['key']
                st.rerun()
    
    # Help section
    with st.expander("💡 Tips & Getting Started"):
        st.markdown(f"""
        **Welcome to your dashboard, {username}!** Here's how to get started:
        
        🎯 **For {user_role.capitalize()}s:**
        {get_role_specific_tips(user_role)}
        
        📱 **Navigation:**
        - Use the **sidebar** to access all features
        - Click **feature cards** above for quick access
        - Check **Recent Activity** to see what's new
        
        🆘 **Need Help?**
        - Contact support: support@restaurant.com
        - Check the documentation in each feature
        - Use the help tooltips (ℹ️) throughout the app
        """)

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

def get_recent_activities(user_role):
    """Get recent activities based on user role (no quiz references)"""
    if user_role in ['admin', 'chef', 'staff']:
        return [
            {"time": "2 min ago", "description": "New ingredients added to inventory", "icon": "📦"},
            {"time": "1 hour ago", "description": "Weekly menu generated with 35 dishes", "icon": "🍽️"},
            {"time": "Yesterday", "description": "Chef submitted 3 new signature dishes", "icon": "👨‍🍳"},
            {"time": "2 days ago", "description": "Staff challenge received 15 customer votes", "icon": "🗳️"}
        ]
    else:
        return [
            {"time": "30 min ago", "description": "Generated 3 recipes from leftovers", "icon": "♻️"},
            {"time": "2 hours ago", "description": "Used AI dish detection feature", "icon": "📷"},
            {"time": "Yesterday", "description": "Discovered new recipe combinations", "icon": "🔍"},
            {"time": "3 days ago", "description": "Earned 'Recipe Explorer' achievement", "icon": "🏆"}
        ]

def get_quick_actions(user_role):
    """Get quick action buttons based on user role (no quiz actions)"""
    if user_role == 'admin':
        return [
            {"title": "Add Ingredients", "key": "Ingredients Management", "icon": "➕"},
            {"title": "Generate Menu", "key": "Chef Recipe Suggestions", "icon": "🍽️"},
            {"title": "Create Campaign", "key": "Promotion Generator", "icon": "📢"}
        ]
    elif user_role == 'chef':
        return [
            {"title": "Submit Recipe", "key": "Chef Recipe Suggestions", "icon": "👨‍🍳"},
            {"title": "Use Leftovers", "key": "Leftover Management", "icon": "♻️"},
            {"title": "AI Detection", "key": "Visual Menu Search", "icon": "📷"}
        ]
    elif user_role == 'staff':
        return [
            {"title": "Manage Stock", "key": "Ingredients Management", "icon": "📦"},
            {"title": "Staff Challenge", "key": "Visual Menu Search", "icon": "🏅"},
            {"title": "Create Promo", "key": "Promotion Generator", "icon": "📢"}
        ]
    else:  # user
        return [
            {"title": "Find Recipes", "key": "Leftover Management", "icon": "🔍"},
            {"title": "AI Detection", "key": "Visual Menu Search", "icon": "📷"},
            {"title": "Plan Event", "key": "Event Planning ChatBot", "icon": "🎉"}
        ]

def get_role_specific_tips(user_role):
    """Get role-specific tips and guidance (no quiz references)"""
    tips = {
        'admin': """
        - **Manage everything**: You have access to all features and user management
        - **Monitor metrics**: Check ingredient usage, menu performance, and user activity
        - **Generate reports**: Use analytics features to track restaurant performance
        - **Oversee staff**: Review chef submissions and staff challenge entries
        """,
        'chef': """
        - **Submit recipes**: Share your signature dishes and get AI feedback
        - **Generate menus**: Use AI to create weekly menus from available ingredients
        - **Manage leftovers**: Turn waste into creative new dishes
        - **Track ratings**: Monitor how customers rate your submissions
        """,
        'staff': """
        - **Manage inventory**: Keep ingredient stock updated and organized
        - **Join challenges**: Submit your dishes to staff challenges for XP
        - **Create promotions**: Generate marketing campaigns for special offers
        - **Engage customers**: Help with visual menu features and recommendations
        """,
        'user': """
        - **Discover recipes**: Use leftover ingredients to find new dishes to cook
        - **Earn XP**: Use features and engage with content to gain experience
        - **Get recommendations**: Use AI to find dishes that match your preferences
        - **Plan events**: Use the chatbot to help organize special occasions
        """
    }
    return tips.get(user_role, "Explore the available features to get started!")

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
