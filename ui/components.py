"""
Updated UI Components with Enhanced Gamification Integration
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
import logging
import random
import hashlib
import re

# Import the new gamification system
from modules.gamification_core import (
    gamification_manager, award_xp, get_user_stats, get_user_tasks, 
    get_leaderboard, initialize_user_gamification, XP_REWARDS, 
    TASK_CATEGORIES, ACHIEVEMENTS
)

logger = logging.getLogger(__name__)

# Authentication Components (keeping existing code but adding gamification init)
def initialize_session_state():
    """Initialize session state variables for authentication"""
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'auth_error' not in st.session_state:
        st.session_state.auth_error = None
    if 'show_signup' not in st.session_state:
        st.session_state.show_signup = False

def get_firestore_client():
    """Get Firestore client for authentication - using MAIN Firebase"""
    try:
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client for auth: {str(e)}")
        return None

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"

def register_user(email, username, password, full_name, role='user'):
    """Register a new user with enhanced gamification initialization"""
    try:
        db = get_firestore_client()
        if not db:
            return False, "Database connection failed"
        
        # Validate email and password (existing validation code)
        if not validate_email(email):
            return False, "Invalid email format"
        
        is_valid, password_message = validate_password(password)
        if not is_valid:
            return False, password_message
        
        # Check if user exists (existing code)
        from components import check_user_exists  # Assuming this function exists
        exists, message = check_user_exists(email, username)
        if exists:
            return False, message
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create new user
        user_data = {
            'email': email,
            'username': username,
            'password_hash': password_hash,
            'full_name': full_name,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
            'last_login': None,
            'is_active': True,
            'profile_completed': True
        }
        
        doc_ref = db.collection('users').add(user_data)
        user_id = doc_ref[1].id
        
        # Initialize gamification system for new user
        gamification_success = initialize_user_gamification(user_id, username, role)
        if gamification_success:
            logger.info(f"Gamification initialized for new user: {username}")
        else:
            logger.warning(f"Failed to initialize gamification for user: {username}")
        
        logger.info(f"User registered successfully: {username} ({email})")
        return True, "Registration successful! You can now log in."
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return False, f"Registration error: {str(e)}"

def authenticate_user(login_identifier, password):
    """Enhanced authentication with daily login XP"""
    try:
        db = get_firestore_client()
        if not db:
            return None, "Database connection failed"
        
        hashed_password = hash_password(password)
        users_ref = db.collection('users')
        
        # Find user by email or username
        if validate_email(login_identifier):
            query = users_ref.where('email', '==', login_identifier).where('password_hash', '==', hashed_password)
        else:
            query = users_ref.where('username', '==', login_identifier).where('password_hash', '==', hashed_password)
        
        docs = list(query.stream())
        
        if docs:
            user_doc = docs[0]
            user_data = user_doc.to_dict()
            user_data['user_id'] = user_doc.id
            
            # Update last login
            user_doc.reference.update({
                'last_login': firestore.SERVER_TIMESTAMP
            })
            
            # Award daily login XP
            user_id = user_data['user_id']
            xp_awarded, level_up, achievements = award_xp(
                user_id, 
                'daily_login', 
                context={'feature': 'authentication'}
            )
            
            if xp_awarded > 0:
                logger.info(f"Awarded {xp_awarded} XP for daily login to user {user_id}")
            
            logger.info(f"User authenticated successfully: {login_identifier}")
            return user_data, None
        else:
            logger.warning(f"Authentication failed for user: {login_identifier}")
            return None, "Invalid email/username or password"
            
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None, f"Authentication error: {str(e)}"

# Enhanced Gamification Components
def display_user_stats_sidebar(user_id):
    """Enhanced sidebar with tasks, achievements, and progress"""
    try:
        # Get comprehensive user stats
        user_stats = get_user_stats(user_id)
        user_tasks = get_user_tasks(user_id)
        
        st.sidebar.markdown("---")
        
        # Expandable stats section with tasks
        with st.sidebar.expander("Your Progress & Tasks", expanded=False):
            # Basic stats
            total_xp = user_stats.get('total_xp', 0)
            level = user_stats.get('level', 1)
            
            # Level progress
            xp_for_current_level = (level - 1) * 100
            current_level_xp = total_xp - xp_for_current_level
            xp_needed = 100 - current_level_xp
            progress = max(0.0, min(1.0, current_level_xp / 100.0))
            
            # Display metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Level", level)
            with col2:
                st.metric("Total XP", f"{total_xp:,}")
            
            st.progress(progress, text=f"{max(0, xp_needed)} XP to next level")
            
            # Daily Tasks Section
            st.markdown("**Daily Tasks**")
            daily_tasks = user_tasks.get('daily_tasks', {}).get('tasks', {})
            
            if daily_tasks:
                for task_id, task_data in daily_tasks.items():
                    # Find task info
                    task_info = next((t for t in TASK_CATEGORIES['daily']['tasks'] if t['id'] == task_id), None)
                    if task_info:
                        completed = task_data.get('completed', False)
                        icon = "✅" if completed else "⏳"
                        st.write(f"{icon} {task_info['name']} (+{task_info['xp']} XP)")
            
            # Weekly Progress
            st.markdown("**Weekly Progress**")
            weekly_tasks = user_tasks.get('weekly_tasks', {}).get('tasks', {})
            
            if weekly_tasks:
                for task_id, task_data in weekly_tasks.items():
                    task_info = next((t for t in TASK_CATEGORIES['weekly']['tasks'] if t['id'] == task_id), None)
                    if task_info:
                        progress = task_data.get('progress', 0)
                        target = task_data.get('target', 1)
                        completed = task_data.get('completed', False)
                        
                        if completed:
                            st.write(f"✅ {task_info['name']} ({progress}/{target})")
                        else:
                            st.write(f"📊 {task_info['name']} ({progress}/{target})")
            
            # Recent achievements
            achievements = user_stats.get('achievements', [])
            if achievements:
                st.markdown("**Recent Achievements**")
                for achievement in achievements[-3:]:  # Show last 3
                    # Find achievement info
                    achievement_info = None
                    for ach in ACHIEVEMENTS['xp_milestones'] + ACHIEVEMENTS['activity_based']:
                        if ach['name'] == achievement:
                            achievement_info = ach
                            break
                    
                    if achievement_info:
                        badge = achievement_info.get('badge', '🏆')
                        st.write(f"{badge} {achievement}")
            
            # Gamification Hub button
            st.markdown("---")
            if st.button("Open Gamification Hub", use_container_width=True, type="primary", key="gamification_hub_btn"):
                st.session_state.selected_feature = "Gamification Hub"
                st.rerun()
        
        logger.info(f"Displayed enhanced stats for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def show_xp_notification(xp_amount, activity_type, achievements=None, level_up=False):
    """Enhanced XP notification with achievements and level up"""
    if xp_amount > 0:
        st.success(f"+{xp_amount} XP earned for {activity_type}!")
        
        if level_up:
            st.balloons()
            st.success("🎉 LEVEL UP! You've reached a new level!")
        
        if achievements:
            for achievement in achievements:
                st.success(f"🏆 Achievement Unlocked: {achievement}!")

def display_gamification_dashboard(user_id):
    """Enhanced gamification dashboard with tasks and detailed analytics"""
    st.title("Gamification Hub")
    
    try:
        # Get comprehensive data
        user_stats = get_user_stats(user_id)
        user_tasks = get_user_tasks(user_id)
        leaderboard = get_leaderboard()
        
        # Overview metrics
        st.subheader("Your Progress")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Level", user_stats.get('level', 1))
        
        with col2:
            st.metric("Total XP", f"{user_stats.get('total_xp', 0):,}")
        
        with col3:
            st.metric("Achievements", user_stats.get('achievement_count', 0))
        
        with col4:
            st.metric("Daily Streak", user_stats.get('daily_streak', 0))
        
        # Level progress visualization
        total_xp = user_stats.get('total_xp', 0)
        level = user_stats.get('level', 1)
        xp_for_current_level = (level - 1) * 100
        current_level_xp = total_xp - xp_for_current_level
        progress = min(current_level_xp / 100.0, 1.0)
        
        st.subheader("Level Progress")
        st.progress(progress, text=f"Level {level} - {current_level_xp}/100 XP")
        
        # Tasks Section
        st.subheader("Tasks & Challenges")
        
        task_tab1, task_tab2, task_tab3 = st.tabs(["Daily Tasks", "Weekly Challenges", "Achievements"])
        
        with task_tab1:
            st.markdown("#### Daily Tasks")
            daily_tasks = user_tasks.get('daily_tasks', {}).get('tasks', {})
            
            if daily_tasks:
                for task_id, task_data in daily_tasks.items():
                    task_info = next((t for t in TASK_CATEGORIES['daily']['tasks'] if t['id'] == task_id), None)
                    if task_info:
                        completed = task_data.get('completed', False)
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            status = "✅ Completed" if completed else "⏳ Pending"
                            st.write(f"**{task_info['name']}** - {status}")
                        
                        with col2:
                            st.write(f"+{task_info['xp']} XP")
                        
                        with col3:
                            if completed:
                                st.success("Done")
                            else:
                                st.info("Pending")
            else:
                st.info("No daily tasks available")
        
        with task_tab2:
            st.markdown("#### Weekly Challenges")
            weekly_tasks = user_tasks.get('weekly_tasks', {}).get('tasks', {})
            
            if weekly_tasks:
                for task_id, task_data in weekly_tasks.items():
                    task_info = next((t for t in TASK_CATEGORIES['weekly']['tasks'] if t['id'] == task_id), None)
                    if task_info:
                        progress = task_data.get('progress', 0)
                        target = task_data.get('target', 1)
                        completed = task_data.get('completed', False)
                        
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.write(f"**{task_info['name']}**")
                            st.progress(progress / target, text=f"{progress}/{target}")
                        
                        with col2:
                            st.write(f"+{task_info['xp']} XP")
                        
                        with col3:
                            if completed:
                                st.success("Complete")
                            else:
                                st.info(f"{progress}/{target}")
            else:
                st.info("No weekly challenges available")
        
        with task_tab3:
            st.markdown("#### Achievements")
            achievements = user_stats.get('achievements', [])
            
            if achievements:
                # Display earned achievements
                st.markdown("**Earned Achievements:**")
                for achievement in achievements:
                    achievement_info = None
                    for ach in ACHIEVEMENTS['xp_milestones'] + ACHIEVEMENTS['activity_based']:
                        if ach['name'] == achievement:
                            achievement_info = ach
                            break
                    
                    if achievement_info:
                        badge = achievement_info.get('badge', '🏆')
                        description = achievement_info.get('description', 'Achievement unlocked')
                        st.success(f"{badge} **{achievement}** - {description}")
                
                # Show available achievements
                st.markdown("**Available Achievements:**")
                all_achievements = [ach['name'] for ach in ACHIEVEMENTS['xp_milestones'] + ACHIEVEMENTS['activity_based']]
                remaining_achievements = [ach for ach in all_achievements if ach not in achievements]
                
                for ach_name in remaining_achievements[:5]:  # Show next 5
                    achievement_info = None
                    for ach in ACHIEVEMENTS['xp_milestones'] + ACHIEVEMENTS['activity_based']:
                        if ach['name'] == ach_name:
                            achievement_info = ach
                            break
                    
                    if achievement_info:
                        badge = achievement_info.get('badge', '🏆')
                        description = achievement_info.get('description', 'Achievement to unlock')
                        st.info(f"{badge} **{ach_name}** - {description}")
            else:
                st.info("No achievements earned yet. Complete activities to unlock achievements!")
        
        # Leaderboard
        st.subheader("Leaderboard")
        
        if leaderboard:
            # Find user's position
            user_position = None
            for i, entry in enumerate(leaderboard):
                if entry.get('username') == user_stats.get('username'):
                    user_position = i + 1
                    break
            
            if user_position:
                st.info(f"🎯 Your current rank: #{user_position}")
            
            # Display leaderboard
            df = pd.DataFrame(leaderboard)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No leaderboard data available yet.")
        
        # Activity suggestions
        st.subheader("Earn More XP")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("""
            **Recipe & Cooking:**
            - Generate recipes: +15 XP
            - Complete cooking quiz: +10 XP
            - Perfect quiz score: +15 XP bonus
            """)
        
        with col2:
            st.info("""
            **Social & Challenges:**
            - Like dishes: +5 XP each
            - Submit visual challenge: +30 XP
            - Create marketing campaign: +20-50 XP
            """)
        
    except Exception as e:
        logger.error(f"Error in gamification dashboard: {str(e)}")
        st.error("Error loading gamification dashboard")

# Convenience function for awarding XP in other modules
def award_feature_xp(user_id: str, feature_name: str, activity: str, amount: Optional[int] = None, context: Dict = None):
    """Award XP for feature usage with automatic context"""
    if not context:
        context = {}
    context['feature'] = feature_name
    
    xp_awarded, level_up, achievements = award_xp(user_id, activity, amount, context)
    
    if xp_awarded > 0:
        show_xp_notification(xp_awarded, activity, achievements, level_up)
    
    return xp_awarded, level_up, achievements

# Keep all other existing functions unchanged...
# (render_login_form, render_signup_form, render_auth_ui, etc.)
