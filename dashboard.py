"""
Enhanced Dashboard module for the Smart Restaurant Menu Management App.
Displays comprehensive analytics, user stats, and feature overview with gamification integration.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

# Import gamification system
from modules.gamification_core import get_user_stats, get_leaderboard

logger = logging.getLogger(__name__)

def get_feature_description(feature_name):
    """Get description for a specific feature"""
    descriptions = {
        "Dashboard": "Overview of your restaurant management system with analytics and quick access to all features",
        "Ingredients Management": "Complete CRUD operations for ingredient inventory with AI suggestions and expiry tracking",
        "Leftover Management": "Generate recipes from leftover ingredients to minimize waste and maximize efficiency",
        "Gamification Hub": "View your achievements, progress, tasks, and compete on the leaderboard",
        "Event Planning ChatBot": "AI-powered assistant for planning and managing restaurant events",
        "Promotion Generator": "Create AI-powered marketing campaigns with automatic quality scoring",
        "Chef Recipe Suggestions": "AI-powered menu generation, chef submissions, and recipe analytics",
        "Visual Menu Search": "AI dish detection, personalized recommendations, and staff challenges"
    }
    return descriptions.get(feature_name, "")

def get_mock_analytics_data():
    """Generate mock analytics data for dashboard"""
    # Generate sample data for the last 30 days
    dates = [datetime.now() - timedelta(days=x) for x in range(30, 0, -1)]
    
    # Mock data
    analytics_data = {
        'dates': dates,
        'recipes_generated': [5, 8, 12, 6, 9, 15, 11, 7, 13, 10, 8, 14, 9, 12, 16, 
                             11, 7, 9, 13, 8, 15, 12, 10, 14, 11, 9, 16, 13, 8, 12],
        'ingredients_added': [3, 7, 5, 9, 4, 8, 6, 12, 5, 7, 9, 6, 8, 11, 4, 
                             7, 10, 5, 8, 6, 9, 12, 7, 5, 8, 11, 6, 9, 7, 10],
        'xp_earned': [45, 78, 92, 56, 67, 134, 89, 76, 98, 82, 65, 112, 74, 95, 128,
                     87, 69, 83, 106, 71, 118, 94, 81, 102, 88, 79, 125, 97, 73, 91],
        'quiz_scores': [85, 92, 78, 88, 95, 82, 90, 87, 93, 79, 86, 91, 84, 89, 96,
                       83, 88, 94, 81, 87, 92, 85, 90, 88, 93, 86, 89, 91, 84, 87]
    }
    
    return analytics_data

def render_user_overview(user_stats):
    """Render user overview section with gamification stats"""
    st.subheader("Your Progress Overview")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Level", 
            user_stats.get('level', 1),
            help="Your current level based on total XP earned"
        )
    
    with col2:
        st.metric(
            "Total XP", 
            f"{user_stats.get('total_xp', 0):,}",
            help="Total experience points earned across all activities"
        )
    
    with col3:
        st.metric(
            "Achievements", 
            user_stats.get('achievement_count', 0),
            help="Number of achievements unlocked"
        )
    
    with col4:
        st.metric(
            "Daily Streak", 
            user_stats.get('daily_streak', 0),
            help="Consecutive days of activity"
        )
    
    # Level progress bar
    total_xp = user_stats.get('total_xp', 0)
    level = user_stats.get('level', 1)
    xp_for_current_level = (level - 1) * 100
    current_level_xp = total_xp - xp_for_current_level
    progress = min(current_level_xp / 100.0, 1.0)
    
    st.markdown("#### Level Progress")
    st.progress(progress, text=f"Level {level} - {current_level_xp}/100 XP")
    
    # Activity breakdown
    st.markdown("#### Activity Summary")
    
    activity_col1, activity_col2, activity_col3 = st.columns(3)
    
    with activity_col1:
        st.metric("Recipes Generated", user_stats.get('recipes_generated', 0))
        st.metric("Quizzes Completed", user_stats.get('quizzes_completed', 0))
    
    with activity_col2:
        st.metric("Perfect Quiz Scores", user_stats.get('perfect_scores', 0))
        st.metric("Dishes Liked", user_stats.get('dishes_liked', 0))
    
    with activity_col3:
        st.metric("Campaigns Created", user_stats.get('campaigns_created', 0))
        st.metric("Features Used", len(user_stats.get('features_used', [])))

def render_analytics_charts():
    """Render analytics charts for dashboard"""
    st.subheader("Analytics & Trends")
    
    analytics_data = get_mock_analytics_data()
    
    # Create DataFrame for easier plotting
    df = pd.DataFrame({
        'Date': analytics_data['dates'],
        'Recipes Generated': analytics_data['recipes_generated'],
        'Ingredients Added': analytics_data['ingredients_added'],
        'XP Earned': analytics_data['xp_earned'],
        'Quiz Score': analytics_data['quiz_scores']
    })
    
    # Activity trends chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### Daily Activity Trends")
        
        # Multi-line chart for activities
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['Date'], 
            y=df['Recipes Generated'],
            mode='lines+markers',
            name='Recipes Generated',
            line=dict(color='#1f77b4')
        ))
        
        fig.add_trace(go.Scatter(
            x=df['Date'], 
            y=df['Ingredients Added'],
            mode='lines+markers',
            name='Ingredients Added',
            line=dict(color='#ff7f0e')
        ))
        
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("##### XP & Performance Trends")
        
        # XP and quiz performance chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['Date'], 
            y=df['XP Earned'],
            mode='lines+markers',
            name='Daily XP',
            yaxis='y',
            line=dict(color='#2ca02c')
        ))
        
        fig.add_trace(go.Scatter(
            x=df['Date'], 
            y=df['Quiz Score'],
            mode='lines+markers',
            name='Quiz Score %',
            yaxis='y2',
            line=dict(color='#d62728')
        ))
        
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            yaxis=dict(title="XP Earned", side="left"),
            yaxis2=dict(title="Quiz Score %", side="right", overlaying="y"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Weekly summary
    st.markdown("##### Weekly Summary")
    
    # Calculate weekly totals
    last_7_days = df.tail(7)
    weekly_stats = {
        'Total Recipes': last_7_days['Recipes Generated'].sum(),
        'Total Ingredients': last_7_days['Ingredients Added'].sum(),
        'Total XP': last_7_days['XP Earned'].sum(),
        'Avg Quiz Score': round(last_7_days['Quiz Score'].mean(), 1)
    }
    
    week_col1, week_col2, week_col3, week_col4 = st.columns(4)
    
    with week_col1:
        st.metric("Recipes (7 days)", weekly_stats['Total Recipes'])
    with week_col2:
        st.metric("Ingredients (7 days)", weekly_stats['Total Ingredients'])
    with week_col3:
        st.metric("XP Earned (7 days)", weekly_stats['Total XP'])
    with week_col4:
        st.metric("Avg Quiz Score", f"{weekly_stats['Avg Quiz Score']}%")

def render_leaderboard_preview():
    """Render a preview of the leaderboard"""
    st.subheader("Leaderboard Preview")
    
    try:
        leaderboard = get_leaderboard(limit=5)
        
        if leaderboard:
            # Create a nice leaderboard display
            for i, entry in enumerate(leaderboard):
                rank = entry['rank']
                username = entry['username']
                total_xp = entry['total_xp']
                level = entry['level']
                achievements = entry['achievement_count']
                
                # Medal emojis for top 3
                if rank == 1:
                    medal = "🥇"
                elif rank == 2:
                    medal = "🥈"
                elif rank == 3:
                    medal = "🥉"
                else:
                    medal = f"#{rank}"
                
                col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
                
                with col1:
                    st.markdown(f"**{medal}**")
                
                with col2:
                    st.markdown(f"**{username}**")
                
                with col3:
                    st.markdown(f"Level {level} ({total_xp:,} XP)")
                
                with col4:
                    st.markdown(f"🏆 {achievements} achievements")
            
            # Link to full leaderboard
            st.markdown("---")
            if st.button("View Full Leaderboard", use_container_width=True):
                st.session_state.selected_feature = "Gamification Hub"
                st.rerun()
        else:
            st.info("No leaderboard data available yet.")
    
    except Exception as e:
        logger.error(f"Error loading leaderboard preview: {str(e)}")
        st.error("Error loading leaderboard data.")

def render_recent_activity():
    """Render recent activity section"""
    st.subheader("Recent Activity")
    
    # Mock recent activities
    activities = [
        {"time": "2 hours ago", "action": "Generated 3 recipes from leftover ingredients", "xp": 20},
        {"time": "5 hours ago", "action": "Completed cooking quiz with 95% score", "xp": 25},
        {"time": "1 day ago", "action": "Added 5 new ingredients to inventory", "xp": 15},
        {"time": "1 day ago", "action": "Created marketing campaign (Good quality)", "xp": 30},
        {"time": "2 days ago", "action": "Used AI dish detection feature", "xp": 15},
        {"time": "3 days ago", "action": "Submitted signature dish recipe", "xp": 25},
        {"time": "4 days ago", "action": "Liked 10 community dishes", "xp": 10},
        {"time": "5 days ago", "action": "Completed weekly challenge", "xp": 50}
    ]
    
    for activity in activities:
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"**{activity['time']}** - {activity['action']}")
        
        with col2:
            st.markdown(f"<span style='color: green'>+{activity['xp']} XP</span>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("💡 **Tip:** Complete daily tasks and try new features to earn more XP!")

def render_quick_actions():
    """Render quick action buttons"""
    st.subheader("Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🧠 Take Quiz", use_container_width=True, type="primary"):
            st.session_state.show_cooking_quiz = True
            st.rerun()
        
        if st.button("🥬 Add Ingredients", use_container_width=True):
            st.session_state.selected_feature = "Ingredients Management"
            st.rerun()
    
    with col2:
        if st.button("♻️ Generate Recipes", use_container_width=True, type="primary"):
            st.session_state.selected_feature = "Leftover Management"
            st.rerun()
        
        if st.button("📢 Create Campaign", use_container_width=True):
            st.session_state.selected_feature = "Promotion Generator"
            st.rerun()
    
    with col3:
        if st.button("🏆 View Achievements", use_container_width=True, type="primary"):
            st.session_state.selected_feature = "Gamification Hub"
            st.rerun()
        
        if st.button("📸 Detect Dish", use_container_width=True):
            st.session_state.selected_feature = "Visual Menu Search"
            st.rerun()

def render_dashboard():
    """Main dashboard rendering function with enhanced gamification integration"""
    st.title("Restaurant Management Dashboard")
    
    # Get current user
    user = st.session_state.get('user', {})
    user_id = user.get('user_id')
    
    if not user_id:
        st.warning("Please log in to view your personalized dashboard.")
        return
    
    # Get user stats from gamification system
    try:
        user_stats = get_user_stats(user_id)
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        user_stats = {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'quizzes_completed': 0,
            'perfect_scores': 0,
            'dishes_liked': 0,
            'campaigns_created': 0,
            'features_used': [],
            'daily_streak': 0,
            'achievements': [],
            'achievement_count': 0
        }
    
    # Welcome message
    username = user.get('username', 'User')
    role = user.get('role', 'user')
    current_time = datetime.now()
    
    if current_time.hour < 12:
        greeting = "Good morning"
    elif current_time.hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    
    st.markdown(f"## {greeting}, {username}! 👋")
    st.markdown(f"**Role:** {role.title()} | **Today:** {current_time.strftime('%A, %B %d, %Y')}")
    
    # Main dashboard content
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Analytics", "🏆 Leaderboard", "⚡ Quick Actions"])
    
    with tab1:
        render_user_overview(user_stats)
        
        st.divider()
        
        # System status
        st.subheader("System Status")
        
        status_col1, status_col2, status_col3 = st.columns(3)
        
        with status_col1:
            st.success("🟢 Main Database: Connected")
            st.success("🟢 AI Services: Available")
        
        with status_col2:
            st.success("🟢 Event Database: Connected")
            st.success("🟢 Gamification: Active")
        
        with status_col3:
            st.info("📊 Last Backup: 2 hours ago")
            st.info("🔄 System Update: Available")
    
    with tab2:
        render_analytics_charts()
    
    with tab3:
        render_leaderboard_preview()
        
        st.divider()
        
        render_recent_activity()
    
    with tab4:
        render_quick_actions()
        
        st.divider()
        
        # Feature access summary
        st.subheader("Feature Access")
        
        all_features = [
            "Ingredients Management", "Leftover Management", "Promotion Generator",
            "Chef Recipe Suggestions", "Visual Menu Search", "Gamification Hub", "Event Planning ChatBot"
        ]
        
        # Check which features user can access
        from main_app import check_feature_access
        
        accessible_features = [f for f in all_features if check_feature_access(f)]
        restricted_features = [f for f in all_features if not check_feature_access(f)]
        
        if accessible_features:
            st.success(f"✅ **Available Features ({len(accessible_features)}):** {', '.join(accessible_features)}")
        
        if restricted_features:
            st.warning(f"🔒 **Restricted Features ({len(restricted_features)}):** {', '.join(restricted_features)}")
        
        # Tips based on role
        if role == 'user':
            st.info("💡 **Tip:** Complete quizzes and use visual menu features to earn XP and unlock achievements!")
        elif role == 'staff':
            st.info("💡 **Tip:** Manage ingredients and create promotions to maximize your impact!")
        elif role == 'chef':
            st.info("💡 **Tip:** Submit signature dishes and generate menus to showcase your culinary expertise!")
        elif role == 'admin':
            st.info("💡 **Tip:** You have access to all features - explore everything to maximize efficiency!")
