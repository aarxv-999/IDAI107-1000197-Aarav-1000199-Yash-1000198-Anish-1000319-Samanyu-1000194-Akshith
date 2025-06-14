"""
Event Planning Chatbot for Smart Restaurant Management App
Created by: v0

This module provides:
1. AI-powered event planning chatbot using Gemini API
2. Integration with Firestore for recipe and ingredient data (read-only)
3. Role-based access control for different user types
4. User-friendly display of event plans
5. PDF export functionality
6. Budget estimation in INR
7. **ENHANCED: Full gamification system with achievements, streaks, and interactive elements**
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import firebase_admin
from firebase_admin import firestore, credentials
import logging
import pandas as pd
from fpdf import FPDF
import base64
import io
import random

# **ENHANCED: Import all gamification functions**
from modules.leftover import (
    get_user_stats, calculate_level, get_firestore_db,
    generate_dynamic_quiz_questions, calculate_quiz_score
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Initialize Firebase for event data (read-only)
def init_event_firebase():
    """Initialize the Firebase Admin SDK for event data (read-only)"""
    if not firebase_admin._apps or 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
        try:
            # Use environment variables with EVENT_ prefix
            cred = credentials.Certificate({
                "type": st.secrets["event_firebase_type"],
                "project_id": st.secrets["event_firebase_project_id"],
                "private_key_id": st.secrets["event_firebase_private_key_id"],
                "private_key": st.secrets["event_firebase_private_key"].replace("\\n", "\n"),
                "client_email": st.secrets["event_firebase_client_email"],
                "client_id": st.secrets["event_firebase_client_id"],
                "auth_uri": st.secrets["event_firebase_auth_uri"],
                "token_uri": st.secrets["event_firebase_token_uri"],
                "auth_provider_x509_cert_url": st.secrets["event_firebase_auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["event_firebase_client_x509_cert_url"],
            })
            firebase_admin.initialize_app(cred, name='event_app')
            logger.info("Event Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            # Fallback to display error in UI
            st.error(f"Failed to initialize Event Firebase. Please check your credentials.")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

# **ENHANCED: Advanced Gamification System for Event Planning**

def get_event_user_stats(user_id: str) -> Dict:
    """
    Get comprehensive event planning stats for a user.
    
    Args:
        user_id (str): User's unique ID
    
    Returns:
        Dict: Complete user stats including event-specific data
    """
    try:
        # Get base stats from existing system
        base_stats = get_user_stats(user_id)
        
        # Add event-specific stats if they don't exist
        event_specific_stats = {
            'event_plans_created': base_stats.get('event_plans_created', 0),
            'event_chatbot_uses': base_stats.get('event_chatbot_uses', 0),
            'event_quizzes_taken': base_stats.get('event_quizzes_taken', 0),
            'event_perfect_scores': base_stats.get('event_perfect_scores', 0),
            'event_streak_days': base_stats.get('event_streak_days', 0),
            'last_event_activity': base_stats.get('last_event_activity', None),
            'event_achievements': base_stats.get('event_achievements', []),
            'event_badges': base_stats.get('event_badges', []),
            'favorite_event_types': base_stats.get('favorite_event_types', []),
            'total_event_xp': base_stats.get('total_event_xp', 0),
            'event_level': calculate_event_level(base_stats.get('total_event_xp', 0))
        }
        
        # Merge with base stats
        base_stats.update(event_specific_stats)
        return base_stats
        
    except Exception as e:
        logger.error(f"Error getting event user stats: {str(e)}")
        return get_user_stats(user_id)

def calculate_event_level(event_xp: int) -> int:
    """Calculate event planning specific level."""
    import math
    return max(1, int(math.sqrt(event_xp / 50)) + 1)  # Faster leveling for events

def award_event_xp_with_effects(user_id: str, user_role: str, activity_type: str, bonus_multiplier: float = 1.0) -> Dict:
    """
    Enhanced XP awarding system with visual effects and comprehensive tracking.
    
    Args:
        user_id (str): User's unique ID
        user_role (str): User's role
        activity_type (str): Type of activity
        bonus_multiplier (float): Multiplier for bonus XP
    
    Returns:
        Dict: Updated stats with level up info
    """
    try:
        # Enhanced XP rewards with role-based bonuses
        base_xp_rewards = {
            'admin': {
                'chatbot_use': 20,
                'event_plan_generated': 35,
                'complex_event_plan': 50,
                'pdf_download': 10,
                'daily_login': 15
            },
            'staff': {
                'chatbot_use': 18,
                'event_plan_generated': 30,
                'complex_event_plan': 45,
                'pdf_download': 10,
                'daily_login': 12
            },
            'chef': {
                'chatbot_use': 18,
                'event_plan_generated': 30,
                'complex_event_plan': 45,
                'pdf_download': 10,
                'daily_login': 12
            },
            'user': {
                'event_quiz_correct': 20,
                'event_quiz_perfect': 50,
                'event_suggestion': 15,
                'daily_challenge': 25,
                'streak_bonus': 30,
                'daily_login': 10
            }
        }
        
        base_xp = base_xp_rewards.get(user_role, {}).get(activity_type, 0)
        
        if base_xp == 0:
            logger.warning(f"No XP defined for {user_role} doing {activity_type}")
            return get_event_user_stats(user_id)
        
        # Apply bonus multiplier
        final_xp = int(base_xp * bonus_multiplier)
        
        # Get current stats
        current_stats = get_event_user_stats(user_id)
        old_level = current_stats['level']
        old_event_level = current_stats.get('event_level', 1)
        
        # Calculate new stats
        new_total_xp = current_stats['total_xp'] + final_xp
        new_event_xp = current_stats.get('total_event_xp', 0) + final_xp
        new_level = calculate_level(new_total_xp)
        new_event_level = calculate_event_level(new_event_xp)
        
        # Update activity-specific counters
        activity_updates = {}
        if activity_type == 'chatbot_use':
            activity_updates['event_chatbot_uses'] = current_stats.get('event_chatbot_uses', 0) + 1
        elif activity_type in ['event_plan_generated', 'complex_event_plan']:
            activity_updates['event_plans_created'] = current_stats.get('event_plans_created', 0) + 1
        elif 'quiz' in activity_type:
            activity_updates['event_quizzes_taken'] = current_stats.get('event_quizzes_taken', 0) + 1
            if activity_type == 'event_quiz_perfect':
                activity_updates['event_perfect_scores'] = current_stats.get('event_perfect_scores', 0) + 1
        
        # Check for streak bonus
        streak_bonus = check_daily_streak(user_id, current_stats)
        if streak_bonus > 0:
            final_xp += streak_bonus
            new_total_xp += streak_bonus
            new_event_xp += streak_bonus
            new_level = calculate_level(new_total_xp)
            new_event_level = calculate_event_level(new_event_xp)
        
        # Check for new achievements
        new_achievements = check_event_achievements(current_stats, activity_updates, new_event_level, old_event_level)
        
        # Update Firebase
        db = get_firestore_db()
        user_stats_ref = db.collection('user_stats').document(user_id)
        
        updated_stats = current_stats.copy()
        updated_stats.update({
            'total_xp': new_total_xp,
            'level': new_level,
            'total_event_xp': new_event_xp,
            'event_level': new_event_level,
            'last_event_activity': firestore.SERVER_TIMESTAMP,
            'event_achievements': current_stats.get('event_achievements', []) + new_achievements,
            **activity_updates
        })
        
        user_stats_ref.set(updated_stats)
        
        # Store notification data in session state
        if 'event_xp_notifications' not in st.session_state:
            st.session_state.event_xp_notifications = []
        
        notification = {
            'xp': final_xp,
            'activity': activity_type,
            'level_up': new_level > old_level,
            'event_level_up': new_event_level > old_event_level,
            'new_level': new_level,
            'new_event_level': new_event_level,
            'achievements': new_achievements,
            'streak_bonus': streak_bonus,
            'timestamp': datetime.now()
        }
        
        st.session_state.event_xp_notifications.append(notification)
        
        logger.info(f"Awarded {final_xp} XP to {user_role} for {activity_type}")
        return updated_stats
        
    except Exception as e:
        logger.error(f"Error awarding event XP: {str(e)}")
        return get_event_user_stats(user_id)

def check_daily_streak(user_id: str, current_stats: Dict) -> int:
    """Check and update daily activity streak."""
    try:
        last_activity = current_stats.get('last_event_activity')
        current_streak = current_stats.get('event_streak_days', 0)
        
        if last_activity:
            # Convert Firestore timestamp to datetime if needed
            if hasattr(last_activity, 'date'):
                last_date = last_activity.date()
            else:
                last_date = datetime.now().date() - timedelta(days=1)  # Default to yesterday
            
            today = datetime.now().date()
            days_diff = (today - last_date).days
            
            if days_diff == 1:
                # Consecutive day - extend streak
                new_streak = current_streak + 1
                streak_bonus = min(new_streak * 5, 50)  # Max 50 bonus XP
                
                # Update streak in Firebase
                db = get_firestore_db()
                user_stats_ref = db.collection('user_stats').document(user_id)
                user_stats_ref.update({'event_streak_days': new_streak})
                
                return streak_bonus
            elif days_diff > 1:
                # Streak broken - reset
                db = get_firestore_db()
                user_stats_ref = db.collection('user_stats').document(user_id)
                user_stats_ref.update({'event_streak_days': 1})
        
        return 0
        
    except Exception as e:
        logger.error(f"Error checking daily streak: {str(e)}")
        return 0

def check_event_achievements(current_stats: Dict, activity_updates: Dict, new_event_level: int, old_event_level: int) -> List[str]:
    """Check for new event planning achievements."""
    new_achievements = []
    current_achievements = current_stats.get('event_achievements', [])
    
    # Event planning milestones
    event_plans = current_stats.get('event_plans_created', 0) + activity_updates.get('event_plans_created', 0)
    chatbot_uses = current_stats.get('event_chatbot_uses', 0) + activity_updates.get('event_chatbot_uses', 0)
    quizzes = current_stats.get('event_quizzes_taken', 0) + activity_updates.get('event_quizzes_taken', 0)
    perfect_scores = current_stats.get('event_perfect_scores', 0) + activity_updates.get('event_perfect_scores', 0)
    streak = current_stats.get('event_streak_days', 0)
    
    # Achievement definitions
    achievements_to_check = [
        (event_plans >= 1, "First Event Planner", "🎉"),
        (event_plans >= 5, "Event Organizer", "🎪"),
        (event_plans >= 10, "Party Master", "🎊"),
        (event_plans >= 25, "Event Legend", "👑"),
        (chatbot_uses >= 10, "Chatbot Enthusiast", "🤖"),
        (chatbot_uses >= 50, "AI Assistant Pro", "🚀"),
        (quizzes >= 5, "Event Scholar", "📚"),
        (quizzes >= 15, "Event Expert", "🎓"),
        (perfect_scores >= 3, "Quiz Perfectionist", "💯"),
        (perfect_scores >= 10, "Event Genius", "🧠"),
        (streak >= 7, "Week Warrior", "🔥"),
        (streak >= 30, "Monthly Master", "⭐"),
        (new_event_level >= 5, "Rising Event Star", "🌟"),
        (new_event_level >= 10, "Event Professional", "💼"),
        (new_event_level >= 15, "Event Virtuoso", "🎭"),
        (new_event_level >= 20, "Grand Event Master", "🏆")
    ]
    
    for condition, title, emoji in achievements_to_check:
        if condition and title not in current_achievements:
            new_achievements.append(title)
            logger.info(f"New achievement unlocked: {title}")
    
    return new_achievements

def show_enhanced_xp_notifications():
    """Display enhanced XP notifications with animations and effects."""
    if 'event_xp_notifications' in st.session_state and st.session_state.event_xp_notifications:
        for notification in st.session_state.event_xp_notifications:
            # Main XP notification
            activity_messages = {
                'chatbot_use': 'using the Event Planning ChatBot',
                'event_plan_generated': 'generating an event plan',
                'complex_event_plan': 'creating a complex event plan',
                'event_quiz_correct': 'answering event quiz correctly',
                'event_quiz_perfect': 'achieving a perfect quiz score',
                'event_suggestion': 'providing event suggestions',
                'daily_challenge': 'completing daily challenge',
                'daily_login': 'daily activity bonus'
            }
            
            activity_msg = activity_messages.get(notification['activity'], 'event planning activity')
            
            # Show XP with effects
            if notification['xp'] >= 50:
                st.success(f"🎉 **AMAZING!** +{notification['xp']} XP for {activity_msg}!")
            elif notification['xp'] >= 30:
                st.success(f"⭐ **EXCELLENT!** +{notification['xp']} XP for {activity_msg}!")
            else:
                st.success(f"✨ +{notification['xp']} XP for {activity_msg}!")
            
            # Streak bonus notification
            if notification.get('streak_bonus', 0) > 0:
                st.info(f"🔥 **STREAK BONUS!** +{notification['streak_bonus']} XP for daily activity streak!")
            
            # Level up notifications
            if notification.get('level_up', False):
                st.balloons()
                st.success(f"🎊 **LEVEL UP!** You're now Level {notification['new_level']}!")
            
            if notification.get('event_level_up', False):
                st.success(f"🎭 **EVENT LEVEL UP!** You're now Event Level {notification['new_event_level']}!")
            
            # Achievement notifications
            for achievement in notification.get('achievements', []):
                st.success(f"🏆 **NEW ACHIEVEMENT UNLOCKED:** {achievement}!")
        
        # Clear notifications after showing
        st.session_state.event_xp_notifications = []

def render_event_gamification_sidebar(user_id: str):
    """Render enhanced gamification sidebar for event planning."""
    stats = get_event_user_stats(user_id)
    
    st.sidebar.divider()
    st.sidebar.subheader("🎭 Event Planning Stats")
    
    # Main stats
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Event Level", stats.get('event_level', 1))
        st.metric("Plans Created", stats.get('event_plans_created', 0))
    with col2:
        st.metric("Event XP", stats.get('total_event_xp', 0))
        st.metric("Streak", f"{stats.get('event_streak_days', 0)} days")
    
    # Progress bar for next event level
    current_event_xp = stats.get('total_event_xp', 0)
    current_event_level = stats.get('event_level', 1)
    xp_for_current_level = ((current_event_level - 1) ** 2) * 50
    xp_for_next_level = (current_event_level ** 2) * 50
    current_level_progress = current_event_xp - xp_for_current_level
    xp_needed = xp_for_next_level - current_event_xp
    
    if xp_for_next_level > xp_for_current_level:
        progress = current_level_progress / (xp_for_next_level - xp_for_current_level)
        st.sidebar.progress(progress, text=f"{xp_needed} XP to Event Level {current_event_level + 1}")
    
    # Recent achievements
    recent_achievements = stats.get('event_achievements', [])[-3:]  # Last 3 achievements
    if recent_achievements:
        st.sidebar.subheader("🏆 Recent Achievements")
        for achievement in recent_achievements:
            st.sidebar.success(f"✨ {achievement}")
    
    # Daily challenge
    if stats.get('event_streak_days', 0) > 0:
        st.sidebar.info(f"🔥 {stats.get('event_streak_days', 0)} day streak! Keep it up!")

def render_enhanced_event_quiz(user_id: str):
    """Render enhanced event planning quiz with gamification elements."""
    st.markdown("### 🧠 Event Planning Master Quiz")
    
    # Show current stats
    stats = get_event_user_stats(user_id)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Quiz Level", stats.get('event_level', 1))
    with col2:
        st.metric("Quizzes Taken", stats.get('event_quizzes_taken', 0))
    with col3:
        st.metric("Perfect Scores", stats.get('event_perfect_scores', 0))
    with col4:
        accuracy = 0
        if stats.get('event_quizzes_taken', 0) > 0:
            accuracy = (stats.get('event_perfect_scores', 0) / stats.get('event_quizzes_taken', 1)) * 100
        st.metric("Accuracy", f"{accuracy:.1f}%")
    
    # Daily challenge
    st.info("🎯 **Daily Challenge:** Take a quiz to maintain your streak and earn bonus XP!")
    
    # Event planning focused topics
    event_topics = [
        "catering", "banquet", "buffet", "appetizers", "main course", 
        "desserts", "beverages", "party planning", "wedding catering",
        "corporate events", "birthday parties", "seasonal events",
        "event logistics", "venue management", "budget planning"
    ]
    
    if 'event_quiz_questions' not in st.session_state:
        st.session_state.event_quiz_questions = None
    if 'event_quiz_answers' not in st.session_state:
        st.session_state.event_quiz_answers = []
    if 'event_quiz_submitted' not in st.session_state:
        st.session_state.event_quiz_submitted = False
    if 'event_quiz_results' not in st.session_state:
        st.session_state.event_quiz_results = None

    col1, col2, col3 = st.columns(3)
    with col1:
        num_questions = st.selectbox("Questions:", [3, 5, 7, 10], index=1, key="event_quiz_num")
    with col2:
        difficulty = st.selectbox("Difficulty:", ["Mixed", "Easy", "Medium", "Hard"], key="event_quiz_diff")
    with col3:
        if st.button("🚀 Start Quiz", type="primary", use_container_width=True, key="start_event_quiz"):
            with st.spinner("🎭 Generating event planning questions..."):
                st.session_state.event_quiz_questions = generate_enhanced_event_quiz(event_topics, num_questions, difficulty)
                st.session_state.event_quiz_answers = []
                st.session_state.event_quiz_submitted = False
                st.session_state.event_quiz_results = None
                st.rerun()

    if st.session_state.event_quiz_questions and not st.session_state.event_quiz_submitted:
        st.divider()
        st.markdown("#### 📝 Quiz Questions")
        
        answers = []
        for i, question in enumerate(st.session_state.event_quiz_questions):
            with st.container():
                # Enhanced question display
                difficulty_colors = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
                difficulty_color = difficulty_colors.get(question.get('difficulty', 'medium'), "🟡")
                
                st.markdown(f"**Question {i+1}** {difficulty_color} **{question['xp_reward']} XP**")
                st.markdown(f"*{question['question']}*")
                
                answer = st.radio(
                    "Select your answer:",
                    options=question['options'],
                    key=f"event_q_{i}",
                    index=None,
                    label_visibility="collapsed"
                )
                
                if answer:
                    answers.append(question['options'].index(answer))
                else:
                    answers.append(-1)
                    
            if i < len(st.session_state.event_quiz_questions) - 1:
                st.divider()
        
        st.write("")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Submit Quiz", type="primary", use_container_width=True, key="submit_event_quiz"):
                if -1 in answers:
                    st.error("❗ Please answer all questions before submitting.")
                else:
                    st.session_state.event_quiz_answers = answers
                    st.session_state.event_quiz_submitted = True
                    
                    # Calculate results
                    correct, total, xp_earned = calculate_quiz_score(answers, st.session_state.event_quiz_questions)
                    st.session_state.event_quiz_results = {
                        'correct': correct,
                        'total': total,
                        'xp_earned': xp_earned,
                        'percentage': (correct / total) * 100
                    }
                    
                    # Award XP with enhanced system
                    if correct == total:
                        award_event_xp_with_effects(user_id, 'user', 'event_quiz_perfect')
                    else:
                        # Award XP for each correct answer
                        for _ in range(correct):
                            award_event_xp_with_effects(user_id, 'user', 'event_quiz_correct')
                    
                    st.rerun()
        
        with col2:
            if st.button("🔄 New Questions", use_container_width=True, key="new_event_questions"):
                st.session_state.event_quiz_questions = None
                st.rerun()

    if st.session_state.event_quiz_submitted and st.session_state.event_quiz_results:
        display_enhanced_quiz_results(st.session_state.event_quiz_results, st.session_state.event_quiz_questions, st.session_state.event_quiz_answers)

def generate_enhanced_event_quiz(topics: List[str], num_questions: int = 5, difficulty: str = "Mixed") -> List[Dict]:
    """Generate enhanced event planning quiz questions with better variety."""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found, using enhanced fallback")
            return generate_enhanced_fallback_questions(num_questions, difficulty)
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        topics_list = ", ".join(topics)
        difficulty_instruction = f"Focus on {difficulty.lower()} difficulty questions" if difficulty != "Mixed" else "Mix easy, medium, and hard questions"
        
        prompt = f'''
        Generate {num_questions} engaging and educational quiz questions about event planning and restaurant catering.
        {difficulty_instruction}.
        
        Topics to cover: {topics_list}
        
        Include questions about:
        - Professional event planning strategies
        - Catering logistics and food service
        - Budget planning and cost management
        - Venue selection and setup
        - Menu planning for different event types
        - Event coordination and timeline management
        - Customer service in event planning
        - Seasonal and themed events
        
        Make questions practical and industry-relevant. Include surprising facts and professional tips.
        
        Format as JSON array:
        [
            {{
                "question": "Engaging event planning question with real-world context?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct": 0,
                "difficulty": "easy|medium|hard",
                "xp_reward": 15,
                "explanation": "Detailed explanation with professional insights",
                "category": "Event Planning Category"
            }}
        ]

        XP Rewards: easy=15, medium=25, hard=35
        '''

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean up the response to extract JSON
        if "\`\`\`json" in response_text:
            response_text = response_text.split("\`\`\`json")[1].split("\`\`\`")[0]
        elif "\`\`\`" in response_text:
            response_text = response_text.split("\`\`\`")[1].split("\`\`\`")[0]

        try:
            questions = json.loads(response_text)
            if isinstance(questions, list) and len(questions) > 0:
                # Ensure proper XP rewards
                for q in questions:
                    if q.get('difficulty') == 'easy':
                        q['xp_reward'] = 15
                    elif q.get('difficulty') == 'medium':
                        q['xp_reward'] = 25
                    else:
                        q['xp_reward'] = 35
                
                return questions[:num_questions]
            else:
                return generate_enhanced_fallback_questions(num_questions, difficulty)
        except json.JSONDecodeError:
            return generate_enhanced_fallback_questions(num_questions, difficulty)

    except Exception as e:
        logger.error(f"Error generating enhanced event quiz: {str(e)}")
        return generate_enhanced_fallback_questions(num_questions, difficulty)

def generate_enhanced_fallback_questions(num_questions: int = 5, difficulty: str = "Mixed") -> List[Dict]:
    """Generate enhanced fallback questions with better variety and gamification."""
    all_questions = [
        {
            "question": "What's the golden rule for estimating food quantities at a buffet event?",
            "options": ["0.5 lbs per person", "1-1.5 lbs per person", "2 lbs per person", "3 lbs per person"],
            "correct": 1,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "The industry standard is 1-1.5 lbs of food per person for buffet events to ensure satisfaction without waste.",
            "category": "Catering Basics"
        },
        {
            "question": "Which seating arrangement maximizes networking opportunities at corporate events?",
            "options": ["Theater style", "Classroom style", "Round tables of 8-10", "U-shape configuration"],
            "correct": 2,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "Round tables of 8-10 people encourage conversation and networking while maintaining intimacy.",
            "category": "Event Layout"
        },
        {
            "question": "What percentage of your event budget should typically be allocated to catering?",
            "options": ["25-35%", "40-50%", "60-70%", "75-85%"],
            "correct": 1,
            "difficulty": "medium",
            "xp_reward": 25,
            "explanation": "Catering typically represents 40-50% of the total event budget, being the largest single expense.",
            "category": "Budget Planning"
        },
        {
            "question": "How far in advance should you book a premium venue for a 200+ guest event?",
            "options": ["1 month", "2-3 months", "6-12 months", "2+ years"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 25,
            "explanation": "Premium venues for large events book 6-12 months in advance, especially during peak seasons.",
            "category": "Venue Management"
        },
        {
            "question": "What's the optimal room temperature for indoor events with 100+ guests?",
            "options": ["65-68°F", "68-72°F", "72-76°F", "76-80°F"],
            "correct": 0,
            "difficulty": "medium",
            "xp_reward": 25,
            "explanation": "65-68°F accounts for body heat from crowds and keeps guests comfortable throughout the event.",
            "category": "Event Logistics"
        },
        {
            "question": "What's the professional standard for server-to-guest ratio at plated dinner events?",
            "options": ["1:8", "1:12", "1:16", "1:20"],
            "correct": 1,
            "difficulty": "hard",
            "xp_reward": 35,
            "explanation": "The professional standard is 1 server per 12 guests for plated dinners to ensure quality service.",
            "category": "Service Standards"
        },
        {
            "question": "Which factor most critically affects outdoor event menu planning?",
            "options": ["Guest preferences", "Budget constraints", "Weather and temperature", "Venue restrictions"],
            "correct": 2,
            "difficulty": "hard",
            "xp_reward": 35,
            "explanation": "Weather affects food safety, presentation, equipment needs, and guest comfort - making it the top priority.",
            "category": "Outdoor Events"
        },
        {
            "question": "How many appetizer pieces should you plan per person for a 2-hour cocktail reception?",
            "options": ["4-6 pieces", "8-10 pieces", "12-15 pieces", "18-20 pieces"],
            "correct": 2,
            "difficulty": "medium",
            "xp_reward": 25,
            "explanation": "Plan 12-15 appetizer pieces per person for a 2-hour cocktail reception without a full meal.",
            "category": "Appetizer Planning"
        },
        {
            "question": "What's the most effective way to handle dietary restrictions at large events?",
            "options": ["Ask during RSVP", "Provide options at the event", "Create separate menus", "Use universal dietary-friendly options"],
            "correct": 0,
            "difficulty": "easy",
            "xp_reward": 15,
            "explanation": "Collecting dietary information during RSVP allows proper planning and ensures all guests are accommodated.",
            "category": "Dietary Management"
        },
        {
            "question": "Which event timeline element is most often underestimated by new planners?",
            "options": ["Setup time", "Guest arrival window", "Cleanup duration", "Vendor coordination"],
            "correct": 0,
            "difficulty": "hard",
            "xp_reward": 35,
            "explanation": "Setup time is frequently underestimated - professional events typically need 2-4 hours of setup time.",
            "category": "Timeline Management"
        }
    ]
    
    # Filter by difficulty if specified
    if difficulty != "Mixed":
        filtered_questions = [q for q in all_questions if q['difficulty'] == difficulty.lower()]
        if len(filtered_questions) >= num_questions:
            all_questions = filtered_questions
    
    # Randomize and return
    random.shuffle(all_questions)
    return all_questions[:num_questions]

def display_enhanced_quiz_results(results: Dict, questions: List[Dict], user_answers: List[int]):
    """Display enhanced quiz results with gamification elements."""
    st.divider()
    st.markdown("### 🎊 Quiz Results")
    
    score = results['correct']
    total = results['total']
    percentage = results['percentage']
    xp_earned = results['xp_earned']

    # Enhanced results display
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Score", f"{score}/{total}", f"{percentage:.1f}%")
    with col2:
        if percentage == 100:
            st.metric("Performance", "PERFECT! 🏆")
        elif percentage >= 80:
            st.metric("Performance", "EXCELLENT! ⭐")
        elif percentage >= 60:
            st.metric("Performance", "GOOD! 👍")
        else:
            st.metric("Performance", "KEEP LEARNING! 📚")
    with col3:
        st.metric("XP Earned", f"+{xp_earned}")
    with col4:
        bonus_xp = 0
        if percentage == 100:
            bonus_xp = 50
        elif percentage >= 80:
            bonus_xp = 25
        st.metric("Bonus XP", f"+{bonus_xp}")

    # Performance feedback
    if percentage == 100:
        st.success("🎉 **PERFECT SCORE!** You're a true Event Planning Master! 🏆")
        st.balloons()
    elif percentage >= 80:
        st.success("⭐ **EXCELLENT WORK!** Your event planning knowledge is impressive!")
    elif percentage >= 60:
        st.info("👍 **GOOD JOB!** You're on the right track. Keep learning!")
    else:
        st.warning("📚 **KEEP STUDYING!** Event planning has many aspects to master.")

    # Show XP notifications
    show_enhanced_xp_notifications()

    # Detailed review
    with st.expander("📋 Detailed Review", expanded=False):
        for i, question in enumerate(questions):
            user_answer = user_answers[i]
            correct_answer = question['correct']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                st.success(f"✅ **Question {i+1}** (+{question['xp_reward']} XP)")
            else:
                st.error(f"❌ **Question {i+1}** (0 XP)")
            
            st.write(f"**Q:** {question['question']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Your answer:** {question['options'][user_answer]}")
            with col2:
                st.write(f"**Correct answer:** {question['options'][correct_answer]}")
            
            if question.get('explanation'):
                st.info(f"💡 **Explanation:** {question['explanation']}")
            
            if i < len(questions) - 1:
                st.divider()

    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Take Another Quiz", use_container_width=True, key="another_event_quiz"):
            st.session_state.event_quiz_questions = None
            st.session_state.event_quiz_answers = []
            st.session_state.event_quiz_submitted = False
            st.session_state.event_quiz_results = None
            st.rerun()
    
    with col2:
        if st.button("📊 View My Stats", use_container_width=True, key="view_event_stats"):
            st.info("Check the sidebar for your detailed event planning statistics!")
    
    with col3:
        if st.button("🏆 View Achievements", use_container_width=True, key="view_event_achievements"):
            stats = get_event_user_stats(st.session_state.user['user_id'])
            achievements = stats.get('event_achievements', [])
            if achievements:
                st.success(f"🏆 **Your Achievements:** {', '.join(achievements)}")
            else:
                st.info("🎯 Keep taking quizzes to unlock achievements!")

# AI Model Configuration (keeping existing)
def configure_ai_model():
    """Configure and return the Gemini AI model"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            api_key = st.secrets.get("GEMINI_API_KEY")
            
        if not api_key:
            st.error("GEMINI_API_KEY not found in environment variables or secrets!")
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        logger.error(f"Error configuring AI model: {str(e)}")
        st.error(f"Failed to configure AI model: {str(e)}")
        return None

# Firestore Data Functions (keeping existing)
def get_recipe_items(dietary_restrictions: Optional[str] = None) -> List[Dict]:
    """Fetch recipe items from Firestore, optionally filtered by dietary restrictions"""
    try:
        db = get_event_db()
        if not db:
            return []
            
        recipe_ref = db.collection('recipe_archive')
        
        if dietary_restrictions and dietary_restrictions.lower() != "none":
            query = recipe_ref.where('diet', 'array_contains', dietary_restrictions.lower())
            recipe_docs = query.get()
        else:
            recipe_docs = recipe_ref.get()
            
        recipe_items = []
        for doc in recipe_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            recipe_items.append(item)
            
        return recipe_items
    except Exception as e:
        logger.error(f"Error fetching recipe items: {str(e)}")
        return []

def get_available_ingredients() -> List[Dict]:
    """Fetch available ingredients from Firestore inventory"""
    try:
        db = get_event_db()
        if not db:
            return []
            
        inventory_ref = db.collection('ingredients_inventory')
        inventory_docs = inventory_ref.get()
        
        ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            ingredients.append(item)
            
        return ingredients
    except Exception as e:
        logger.error(f"Error fetching ingredients: {str(e)}")
        return []

def get_customers() -> List[Dict]:
    """Fetch customer data from Firestore"""
    try:
        db = firestore.client()
        users_ref = db.collection('users')
        users_docs = users_ref.where('role', '==', 'user').get()
        
        customers = []
        for doc in users_docs:
            user = doc.to_dict()
            customers.append({
                'user_id': user.get('user_id', ''),
                'username': user.get('username', ''),
                'email': user.get('email', '')
            })
            
        return customers
    except Exception as e:
        logger.error(f"Error fetching customers: {str(e)}")
        return []

# Enhanced AI Event Planning Function
def generate_event_plan(query: str, user_id: str, user_role: str) -> Dict:
    """Enhanced event plan generation with bulletproof JSON parsing"""
    model = configure_ai_model()
    if not model:
        return {
            'error': 'AI model configuration failed',
            'success': False
        }

    # Award XP for using the chatbot (staff/admin only)
    if user_role in ['admin', 'staff', 'chef']:
        award_event_xp_with_effects(user_id, user_role, 'chatbot_use')

    # Get available recipe items and ingredients for context
    recipe_items = get_recipe_items()
    recipe_names = [item.get('name', '') for item in recipe_items[:10]]  # Limit to avoid token limits

    ingredients = get_available_ingredients()
    ingredient_names = [item.get('Ingredient', '') for item in ingredients[:10]]

    # Extract dietary restrictions from query
    dietary_keywords = ['vegan', 'vegetarian', 'gluten-free', 'dairy-free', 'nut-free']
    dietary_restrictions = []

    for keyword in dietary_keywords:
        if keyword in query.lower():
            dietary_restrictions.append(keyword)

    # Extract guest count from query
    guest_count = 20  # Default
    guest_matches = re.findall(r'(\d+)\s+(?:people|guests|persons)', query)
    if guest_matches:
        guest_count = int(guest_matches[0])

    # Determine complexity for bonus XP
    complexity_keywords = ['wedding', 'corporate', 'gala', 'conference', 'multi-day', 'outdoor', 'themed']
    is_complex = any(keyword in query.lower() for keyword in complexity_keywords) or guest_count > 100

    # Calculate budget values upfront to avoid JSON issues
    food_cost_per_person = 700 if is_complex else 500
    total_food_cost = food_cost_per_person * guest_count
    decoration_cost = min(10000 if is_complex else 5000, guest_count * 200)
    venue_setup_cost = 5000 if is_complex else 3000
    service_charges = int(total_food_cost * 0.15)
    total_cost = total_food_cost + decoration_cost + venue_setup_cost + service_charges
    cost_per_person = int(total_cost / guest_count)

    # Ultra-clean prompt with pre-calculated values
    prompt = f'''You are an expert event planner. Create an event plan for: "{query}"

Guest count: {guest_count}
Available recipes: {', '.join(recipe_names) if recipe_names else 'Indian cuisine'}

Return ONLY valid JSON with NO extra text, NO markdown, NO explanations:

{{
  "theme": {{
    "name": "Event Theme Name",
    "description": "Theme description here"
  }},
  "seating": {{
    "layout": "Seating description",
    "tables": [
      {{"table_number": 1, "shape": "round", "seats": 8, "location": "center"}}
    ]
  }},
  "decor": [
    "Decoration 1",
    "Decoration 2",
    "Decoration 3"
  ],
  "recipe_suggestions": [
    "Recipe 1",
    "Recipe 2", 
    "Recipe 3"
  ],
  "budget": {{
    "food_cost_per_person": {food_cost_per_person},
    "total_food_cost": {total_food_cost},
    "decoration_cost": {decoration_cost},
    "venue_setup_cost": {venue_setup_cost},
    "service_charges": {service_charges},
    "total_cost": {total_cost},
    "cost_per_person": {cost_per_person},
    "breakdown": [
      {{"item": "Food and Beverages", "cost": {total_food_cost}}},
      {{"item": "Decorations", "cost": {decoration_cost}}},
      {{"item": "Venue Setup", "cost": {venue_setup_cost}}},
      {{"item": "Service Charges", "cost": {service_charges}}}
    ]
  }},
  "invitation": "Invitation text here"
}}

IMPORTANT: Return ONLY the JSON object above. No other text.'''

    try:
        # Generate response from AI with specific parameters for clean output
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,  # Lower temperature for more consistent output
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
        )
        
        response_text = response.text.strip()
        
        # Remove any potential markdown or extra formatting
        response_text = response_text.replace('\`\`\`json', '').replace('\`\`\`', '').strip()
        
        # Find the JSON object boundaries
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            raise ValueError("No valid JSON object found in response")
        
        json_text = response_text[start_idx:end_idx + 1]
        
        # Clean up any potential issues in the JSON
        json_text = json_text.replace('\n', ' ').replace('\r', ' ')
        json_text = re.sub(r'\s+', ' ', json_text)  # Normalize whitespace
        
        # Parse the JSON
        event_plan = json.loads(json_text)
        
        # Validate the structure
        required_keys = ['theme', 'seating', 'decor', 'recipe_suggestions', 'budget', 'invitation']
        for key in required_keys:
            if key not in event_plan:
                raise ValueError(f"Missing required key: {key}")
        
        # Ensure proper data types
        if not isinstance(event_plan['theme'], dict):
            raise ValueError("Theme must be an object")
        if not isinstance(event_plan['seating'], dict):
            raise ValueError("Seating must be an object")
        if not isinstance(event_plan['decor'], list):
            raise ValueError("Decor must be an array")
        if not isinstance(event_plan['recipe_suggestions'], list):
            raise ValueError("Recipe suggestions must be an array")
        if not isinstance(event_plan['budget'], dict):
            raise ValueError("Budget must be an object")
        
        # Filter recipe suggestions based on dietary restrictions
        if dietary_restrictions and recipe_names:
            filtered_recipes = get_recipe_items(dietary_restrictions[0])
            filtered_names = [item.get('name', '') for item in filtered_recipes[:7]]
            
            if filtered_names:
                event_plan['recipe_suggestions'] = filtered_names
        
        # Add event metadata
        event_plan['date'] = datetime.now().strftime("%Y-%m-%d")
        event_plan['guest_count'] = guest_count
        event_plan['complexity'] = 'complex' if is_complex else 'standard'
        
        # Award additional XP for successfully generating an event plan
        if user_role in ['admin', 'staff', 'chef']:
            activity_type = 'complex_event_plan' if is_complex else 'event_plan_generated'
            award_event_xp_with_effects(user_id, user_role, activity_type)
        
        logger.info(f"Successfully generated event plan for {guest_count} guests")
        return {
            'plan': event_plan,
            'success': True
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        logger.error(f"Raw response: {response_text[:200]}...")
        return {
            'error': f'Failed to parse AI response as valid JSON: {str(e)}',
            'success': False
        }
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        return {
            'error': str(e),
            'success': False
        }

# PDF Generation Functions (restored working versions)
def create_event_pdf(event_plan: Dict) -> bytes:
    """Create a visually appealing PDF with proper formatting and tables"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Helper function to clean text for PDF
        def clean_text_for_pdf(text: str) -> str:
            """Replace Unicode characters with ASCII equivalents"""
            if not isinstance(text, str):
                text = str(text)
            
            replacements = {
                '•': '* ', '–': '-', '—': '-', ''': "'", ''': "'",
                '"': '"', '"': '"', '…': '...', '₹': 'Rs. ', '°': ' deg',
            }
            
            for unicode_char, ascii_replacement in replacements.items():
                text = text.replace(unicode_char, ascii_replacement)
            
            text = text.encode('ascii', 'ignore').decode('ascii')
            return text
        
        def add_section_header(title: str, y_offset: int = 5):
            """Add a styled section header"""
            pdf.ln(y_offset)
            pdf.set_fill_color(230, 230, 230)  # Light gray background
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, title, ln=True, align="L", fill=True)
            pdf.ln(2)
        
        def add_info_box(label: str, value: str, width: int = 90):
            """Add an info box with label and value"""
            pdf.set_font("Arial", "B", 10)
            pdf.cell(width, 6, f"{label}:", border=1, align="L")
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f" {value}", border=1, ln=True, align="L")
        
        # === HEADER SECTION ===
        pdf.set_fill_color(41, 128, 185)  # Blue background
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.set_font("Arial", "B", 18)
        title_text = clean_text_for_pdf(f"EVENT PLANNING PROPOSAL")
        pdf.cell(0, 15, title_text, ln=True, align="C", fill=True)
        
        # Reset colors
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        
        # === EVENT OVERVIEW ===
        pdf.set_font("Arial", "B", 16)
        event_name = clean_text_for_pdf(event_plan['theme']['name'])
        pdf.cell(0, 10, event_name, ln=True, align="C")
        pdf.ln(3)
        
        # Event details in a box
        pdf.set_draw_color(100, 100, 100)
        pdf.rect(10, pdf.get_y(), 190, 25)  # Draw border
        pdf.ln(3)
        
        # Event info in columns
        current_y = pdf.get_y()
        pdf.set_font("Arial", "B", 10)
        pdf.cell(45, 6, "Date:", align="L")
        pdf.set_font("Arial", "", 10)
        date_text = clean_text_for_pdf(str(event_plan.get('date', 'TBD')))
        pdf.cell(50, 6, date_text, align="L")
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(30, 6, "Guests:", align="L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, str(event_plan.get('guest_count', 'TBD')), ln=True, align="L")
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(45, 6, "Complexity:", align="L")
        pdf.set_font("Arial", "", 10)
        complexity = clean_text_for_pdf(str(event_plan.get('complexity', 'Standard')).title())
        pdf.cell(0, 6, complexity, ln=True, align="L")
        pdf.ln(5)
        
        # === THEME & CONCEPT ===
        add_section_header("THEME & CONCEPT")
        pdf.set_font("Arial", "", 11)
        theme_desc = clean_text_for_pdf(event_plan['theme']['description'])
        pdf.multi_cell(0, 6, theme_desc)
        
        # === BUDGET BREAKDOWN ===
        add_section_header("BUDGET ANALYSIS")
        budget = event_plan.get('budget', {})
        
        if budget:
            # Budget summary boxes
            pdf.set_font("Arial", "B", 11)
            pdf.set_fill_color(240, 248, 255)  # Light blue
            
            # Total cost box
            pdf.cell(95, 8, f"TOTAL COST: Rs. {budget.get('total_cost', 0):,}", 
                    border=1, align="C", fill=True)
            pdf.cell(95, 8, f"COST PER PERSON: Rs. {budget.get('cost_per_person', 0):,}", 
                    border=1, align="C", fill=True, ln=True)
            pdf.ln(3)
            
            # Budget breakdown table
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(120, 8, "BUDGET CATEGORY", border=1, align="C", fill=True)
            pdf.cell(70, 8, "AMOUNT (Rs.)", border=1, align="C", fill=True, ln=True)
            
            pdf.set_font("Arial", "", 10)
            pdf.set_fill_color(250, 250, 250)
            
            for i, item in enumerate(budget.get('breakdown', [])):
                fill = i % 2 == 0  # Alternate row colors
                item_name = clean_text_for_pdf(str(item.get('item', '')))
                pdf.cell(120, 6, item_name, border=1, align="L", fill=fill)
                pdf.cell(70, 6, f"Rs. {item.get('cost', 0):,}", border=1, align="R", fill=fill, ln=True)
        
        # === SEATING ARRANGEMENT ===
        add_section_header("SEATING ARRANGEMENT")
        
        # Seating description
        pdf.set_font("Arial", "", 11)
        seating_text = clean_text_for_pdf(event_plan['seating']['layout'])
        pdf.multi_cell(0, 6, seating_text)
        pdf.ln(2)
        
        # Seating table if tables data exists
        if 'tables' in event_plan['seating'] and event_plan['seating']['tables']:
            pdf.set_font("Arial", "B", 10)
            pdf.set_fill_color(220, 220, 220)
            
            # Table headers
            pdf.cell(30, 8, "TABLE #", border=1, align="C", fill=True)
            pdf.cell(40, 8, "SHAPE", border=1, align="C", fill=True)
            pdf.cell(30, 8, "SEATS", border=1, align="C", fill=True)
            pdf.cell(90, 8, "LOCATION", border=1, align="C", fill=True, ln=True)
            
            pdf.set_font("Arial", "", 9)
            pdf.set_fill_color(250, 250, 250)
            
            for i, table in enumerate(event_plan['seating']['tables']):
                fill = i % 2 == 0
                if isinstance(table, dict):
                    table_num = str(table.get("table_number", i+1))
                    shape = clean_text_for_pdf(str(table.get("shape", "Round")))
                    seats = str(table.get("seats", "8"))
                    location = clean_text_for_pdf(str(table.get("location", "Main area")))
                else:
                    table_num = str(i+1)
                    shape = "Round"
                    seats = "8"
                    location = "Main area"
                
                pdf.cell(30, 6, table_num, border=1, align="C", fill=fill)
                pdf.cell(40, 6, shape, border=1, align="C", fill=fill)
                pdf.cell(30, 6, seats, border=1, align="C", fill=fill)
                pdf.cell(90, 6, location, border=1, align="L", fill=fill, ln=True)
            
            # Total capacity
            total_seats = sum(table.get("seats", 8) if isinstance(table, dict) else 8 
                            for table in event_plan['seating']['tables'])
            pdf.ln(2)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, f"Total Seating Capacity: {total_seats} guests", ln=True, align="R")
        
        # === DECORATION PLAN ===
        add_section_header("DECORATION & AMBIANCE")
        
        pdf.set_font("Arial", "", 10)
        for i, item in enumerate(event_plan['decor'], 1):
            decor_text = clean_text_for_pdf(f"{i}. {item}")
            pdf.cell(0, 5, decor_text, ln=True)
        
        # === MENU SUGGESTIONS ===
        add_section_header("CURATED MENU")
        
        # Menu in a nice format
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(255, 248, 220)  # Light yellow
        pdf.cell(0, 8, "RECOMMENDED DISHES", border=1, align="C", fill=True, ln=True)
        
        pdf.set_font("Arial", "", 10)
        pdf.set_fill_color(250, 250, 250)
        
        for i, item in enumerate(event_plan['recipe_suggestions']):
            fill = i % 2 == 0
            menu_text = clean_text_for_pdf(f"{i+1}. {item}")
            pdf.cell(0, 6, menu_text, border=1, align="L", fill=fill, ln=True)
        
        # === INVITATION TEMPLATE ===
        add_section_header("INVITATION TEMPLATE")
        
        # Invitation in a decorative box
        pdf.set_draw_color(150, 150, 150)
        pdf.rect(15, pdf.get_y(), 180, 40, style='D')  # Decorative border
        pdf.ln(3)
        pdf.set_font("Arial", "I", 10)  # Italic for invitation
        invitation_text = clean_text_for_pdf(event_plan['invitation'])
        
        # Split invitation into lines and center them
        lines = invitation_text.split('\n')
        for line in lines:
            if line.strip():
                pdf.cell(0, 5, line.strip(), ln=True, align="C")
        
        pdf.ln(5)
        
        # === FOOTER ===
        pdf.ln(10)
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(100, 100, 100)
        footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        pdf.cell(0, 5, footer_text, ln=True, align="C")
        pdf.cell(0, 5, "AI-Powered Event Planning System", ln=True, align="C")
        
        # Generate PDF bytes with proper encoding
        pdf_output = pdf.output(dest="S")
        
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin1", errors='ignore')
        else:
            return pdf_output
            
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        return b""

def get_pdf_download_link(pdf_bytes: bytes, filename: str) -> str:
    """Generate download link for PDF"""
    if pdf_bytes:
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">📄 Download Event Plan PDF</a>'
        return href
    return ""

# Enhanced UI Components
def render_seating_visualization(tables: List):
    """Enhanced seating visualization with better formatting"""
    table_data = []
    
    for i, table in enumerate(tables):
        if isinstance(table, dict):
            table_data.append({
                "Table #": table.get("table_number", i+1),
                "Shape": table.get("shape", "Round"),
                "Seats": table.get("seats", 0),
                "Location": table.get("location", ""),
                "Notes": table.get("special_notes", "")
            })
        else:
            table_data.append({
                "Table #": i+1,
                "Shape": "Not specified",
                "Seats": 0,
                "Location": "Not specified",
                "Notes": ""
            })
    
    df = pd.DataFrame(table_data)
    
    st.dataframe(
        df,
        column_config={
            "Table #": st.column_config.NumberColumn("Table #", format="%d"),
            "Seats": st.column_config.NumberColumn("Seats", format="%d"),
            "Notes": st.column_config.TextColumn("Special Notes")
        },
        use_container_width=True,
        hide_index=True
    )
    
    total_seats = sum(table.get("seats", 0) if isinstance(table, dict) else 0 for table in tables)
    st.caption(f"🪑 Total capacity: {total_seats} guests")

def render_budget_visualization(budget: Dict):
    """Enhanced budget visualization with charts"""
    if not budget:
        st.warning("No budget information available")
        return
    
    # Enhanced budget summary
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Total Cost",
            value=f"₹{budget.get('total_cost', 0):,}",
            help="Complete event cost estimate"
        )
    
    with col2:
        st.metric(
            label="👤 Cost per Person",
            value=f"₹{budget.get('cost_per_person', 0):,}",
            help="Individual guest cost"
        )
    
    with col3:
        st.metric(
            label="🍽️ Food Cost/Person",
            value=f"₹{budget.get('food_cost_per_person', 0):,}",
            help="Food and beverage cost per guest"
        )
    
    with col4:
        food_percentage = (budget.get('total_food_cost', 0) / budget.get('total_cost', 1)) * 100
        st.metric(
            label="🥘 Food %",
            value=f"{food_percentage:.1f}%",
            help="Percentage of budget for food"
        )
    
    # Enhanced breakdown table
    st.subheader("💳 Detailed Cost Breakdown")
    
    breakdown_data = []
    for item in budget.get('breakdown', []):
        breakdown_data.append({
            "Category": item.get('item', ''),
            "Cost (₹)": f"₹{item.get('cost', 0):,}",
            "Details": item.get('details', ''),
            "Percentage": f"{(item.get('cost', 0) / budget.get('total_cost', 1) * 100):.1f}%"
        })
    
    if breakdown_data:
        df = pd.DataFrame(breakdown_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Enhanced chart
        chart_data = pd.DataFrame({
            'Category': [item.get('item', '') for item in budget.get('breakdown', [])],
            'Cost': [item.get('cost', 0) for item in budget.get('breakdown', [])]
        })
        
        if not chart_data.empty:
            st.bar_chart(chart_data.set_index('Category'), height=400)

def render_enhanced_chatbot_ui():
    """Enhanced chatbot UI with full gamification integration"""
    st.markdown("### 🤖 AI Event Planning Assistant")
    
    # Get user info for gamification
    user = st.session_state.get('user', {})
    user_id = user.get('user_id', '')
    user_role = user.get('role', 'user')
    
    # Enhanced stats display for staff/admin
    if user_role in ['admin', 'staff', 'chef']:
        stats = get_event_user_stats(user_id)
        
        # Main stats row
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("🎭 Event Level", stats.get('event_level', 1))
        with col2:
            st.metric("⚡ Total XP", stats.get('total_xp', 0))
        with col3:
            st.metric("📋 Plans Created", stats.get('event_plans_created', 0))
        with col4:
            st.metric("🤖 Chatbot Uses", stats.get('event_chatbot_uses', 0))
        with col5:
            st.metric("🔥 Streak", f"{stats.get('event_streak_days', 0)} days")
        
        # XP earning info
        st.info("💡 **Earn XP:** +18-20 XP per chatbot use, +30-50 XP per event plan generated, +bonus XP for complex events!")
        
        # Show recent achievements
        recent_achievements = stats.get('event_achievements', [])[-2:]
        if recent_achievements:
            achievement_text = " | ".join([f"🏆 {ach}" for ach in recent_achievements])
            st.success(f"**Recent Achievements:** {achievement_text}")

    # Initialize chat history
    if 'event_chat_history' not in st.session_state:
        st.session_state.event_chat_history = []
        
    if 'current_event_plan' not in st.session_state:
        st.session_state.current_event_plan = None

    # Display chat history with enhanced formatting
    for message in st.session_state.event_chat_history:
        if message['role'] == 'user':
            st.chat_message('user').write(message['content'])
        else:
            st.chat_message('assistant').write(message['content'])

    # Enhanced chat input with suggestions
    st.markdown("#### 💭 Quick Event Ideas")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎂 Birthday Party (50 guests)", use_container_width=True):
            st.session_state.suggested_query = "Plan a birthday party for 50 guests with cake, decorations, and fun activities"
    
    with col2:
        if st.button("💼 Corporate Event (100 guests)", use_container_width=True):
            st.session_state.suggested_query = "Plan a professional corporate event for 100 guests with networking opportunities"
    
    with col3:
        if st.button("💒 Wedding Reception (200 guests)", use_container_width=True):
            st.session_state.suggested_query = "Plan an elegant wedding reception for 200 guests with traditional Indian cuisine"

    # Main chat input
    user_query = st.chat_input("Describe your dream event...", key="event_chat_input")
    
    # Handle suggested queries
    if 'suggested_query' in st.session_state:
        user_query = st.session_state.suggested_query
        del st.session_state.suggested_query

    if user_query:
        # Add user message to chat history
        st.session_state.event_chat_history.append({
            'role': 'user',
            'content': user_query
        })
        
        # Display user message
        st.chat_message('user').write(user_query)
        
        # Generate response with enhanced UI
        with st.chat_message('assistant'):
            with st.spinner("🎭 Creating your perfect event plan..."):
                response = generate_event_plan(user_query, user_id, user_role)
                
                if response['success']:
                    event_plan = response['plan']
                    st.session_state.current_event_plan = event_plan
                    
                    # Show XP notifications first
                    show_enhanced_xp_notifications()
                    
                    # Enhanced event plan display
                    st.markdown(f"### 🎉 {event_plan['theme']['name']}")
                    st.markdown(f"*{event_plan['theme']['description']}*")
                    
                    # Quick stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("👥 Guests", event_plan.get('guest_count', 'N/A'))
                    with col2:
                        st.metric("💰 Total Cost", f"₹{event_plan.get('budget', {}).get('total_cost', 0):,}")
                    with col3:
                        st.metric("📊 Complexity", event_plan.get('complexity', 'Standard').title())
                    
                    # Enhanced tabs
                    tabs = st.tabs(["💺 Seating", "💰 Budget", "🎭 Decor", "🍽️ Menu", "⏰ Timeline", "✉️ Invitation", "📄 Export"])
                    
                    with tabs[0]:
                        st.markdown("#### 🪑 Seating Arrangement")
                        st.markdown(event_plan['seating']['layout'])
                        st.markdown("##### Table Details:")
                        render_seating_visualization(event_plan['seating']['tables'])
                    
                    with tabs[1]:
                        st.markdown("#### 💳 Budget Analysis")
                        render_budget_visualization(event_plan.get('budget', {}))
                    
                    with tabs[2]:
                        st.markdown("#### 🎨 Decoration & Ambiance")
                        for i, item in enumerate(event_plan['decor'], 1):
                            st.markdown(f"**{i}.** {item}")
                    
                    with tabs[3]:
                        st.markdown("#### 🍽️ Curated Menu")
                        for i, item in enumerate(event_plan['recipe_suggestions'], 1):
                            st.markdown(f"**{i}.** {item}")
                    
                    with tabs[4]:
                        st.markdown("#### ⏰ Event Timeline")
                        if 'timeline' in event_plan:
                            for item in event_plan['timeline']:
                                st.markdown(f"**{item.get('time', '')}:** {item.get('activity', '')}")
                        else:
                            st.info("Timeline will be customized based on your specific event requirements.")
                    
                    with tabs[5]:
                        st.markdown("#### ✉️ Invitation Template")
                        st.info(event_plan['invitation'])
                        
                        # Copy invitation button
                        if st.button("📋 Copy Invitation Text", key="copy_invitation"):
                            st.success("✅ Invitation text copied to clipboard!")
                    
                    with tabs[6]:
                        st.markdown("#### 📄 Export Your Event Plan")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Generate PDF
                            pdf_bytes = create_event_pdf(event_plan)
                            
                            if pdf_bytes:
                                st.download_button(
                                    label="📄 Download PDF Plan",
                                    data=pdf_bytes,
                                    file_name=f"event_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                    mime="application/pdf",
                                    key="download_pdf",
                                    use_container_width=True
                                )
                                
                                # Award XP for PDF download (only once per plan)
                                if user_role in ['admin', 'staff', 'chef']:
                                    pdf_key = f"pdf_downloaded_{hash(str(event_plan))}"
                                    if pdf_key not in st.session_state:
                                        award_event_xp_with_effects(user_id, user_role, 'pdf_download')
                                        st.session_state[pdf_key] = True
                            else:
                                st.error("❌ Failed to generate PDF")
                        
                        with col2:
                            # Text export
                            text_export = f"""EVENT PLAN: {event_plan['theme']['name']}
Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}
Guests: {event_plan.get('guest_count', 'Not specified')}

THEME:
{event_plan['theme']['description']}

BUDGET:
Total Cost: ₹{event_plan.get('budget', {}).get('total_cost', 0):,}
Cost per Person: ₹{event_plan.get('budget', {}).get('cost_per_person', 0):,}

SEATING:
{event_plan['seating']['layout']}

DECORATION:
{chr(10).join([f"• {item}" for item in event_plan['decor']])}

MENU:
{chr(10).join([f"• {item}" for item in event_plan['recipe_suggestions']])}

INVITATION:
{event_plan['invitation']}"""
                            
                            st.download_button(
                                label="📝 Download Text Plan",
                                data=text_export,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                mime="text/plain",
                                key="download_txt",
                                use_container_width=True
                            )
                    
                    # Add assistant message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"✨ I've created a {event_plan.get('complexity', 'standard')} event plan for '{event_plan['theme']['name']}' with a budget of ₹{event_plan.get('budget', {}).get('total_cost', 0):,}. Check out all the details above!"
                    })
                else:
                    st.error(f"❌ Failed to generate event plan: {response.get('error', 'Unknown error')}")
                    
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"😔 I'm sorry, I couldn't generate an event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_enhanced_user_experience():
    """Enhanced user experience with full gamification"""
    st.markdown("### 🎉 Your Event Planning Journey")
    
    user = st.session_state.get('user', {})
    user_id = user.get('user_id', '')
    
    # Enhanced user stats display
    stats = get_event_user_stats(user_id)
    
    # Main dashboard
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎭 Event Level", stats.get('event_level', 1))
    with col2:
        st.metric("⚡ Total XP", stats.get('total_xp', 0))
    with col3:
        st.metric("🧠 Quizzes Taken", stats.get('event_quizzes_taken', 0))
    with col4:
        st.metric("🔥 Current Streak", f"{stats.get('event_streak_days', 0)} days")
    
    # Achievement showcase
    achievements = stats.get('event_achievements', [])
    if achievements:
        st.markdown("### 🏆 Your Achievements")
        achievement_cols = st.columns(min(len(achievements), 4))
        for i, achievement in enumerate(achievements[-4:]):  # Show last 4 achievements
            with achievement_cols[i % 4]:
                st.success(f"✨ {achievement}")
    
    # Progress tracking
    st.markdown("### 📊 Progress Tracking")
    
    # XP Progress bar
    current_event_xp = stats.get('total_event_xp', 0)
    current_event_level = stats.get('event_level', 1)
    xp_for_current_level = ((current_event_level - 1) ** 2) * 50
    xp_for_next_level = (current_event_level ** 2) * 50
    
    if xp_for_next_level > xp_for_current_level:
        current_level_progress = current_event_xp - xp_for_current_level
        xp_needed = xp_for_next_level - current_event_xp
        progress = current_level_progress / (xp_for_next_level - xp_for_current_level)
        
        st.progress(progress, text=f"Level {current_event_level} → Level {current_event_level + 1} ({xp_needed} XP needed)")
    
    # Enhanced quiz section
    st.divider()
    render_enhanced_event_quiz(user_id)
    
    # Event suggestion system
    st.divider()
    st.markdown("### 💡 Share Your Event Ideas")
    st.markdown("*Help us improve our event planning by sharing your creative ideas!*")
    
    with st.form("enhanced_event_suggestion_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            suggestion_title = st.text_input("🎯 Event Idea Title", placeholder="e.g., Monsoon Food Festival")
            event_type = st.selectbox("🎭 Event Type", [
                "Birthday Party", "Wedding", "Corporate Event", "Festival", 
                "Workshop", "Networking", "Seasonal Event", "Other"
            ])
        
        with col2:
            guest_count = st.number_input("👥 Expected Guests", min_value=1, max_value=1000, value=50)
            budget_range = st.selectbox("💰 Budget Range", [
                "₹10,000 - ₹25,000", "₹25,000 - ₹50,000", 
                "₹50,000 - ₹1,00,000", "₹1,00,000+"
            ])
        
        suggestion_description = st.text_area(
            "📝 Describe Your Event Concept", 
            placeholder="Share your creative event idea, theme, activities, and what makes it special...",
            height=100
        )
        
        special_requirements = st.text_area(
            "✨ Special Requirements or Features",
            placeholder="Any unique requirements, dietary restrictions, accessibility needs, etc.",
            height=60
        )
        
        if st.form_submit_button("🚀 Submit Event Idea", type="primary", use_container_width=True):
            if suggestion_title and suggestion_description:
                # Award XP for providing suggestions
                award_event_xp_with_effects(user_id, 'user', 'event_suggestion')
                
                # Store suggestion (you could save this to Firebase if needed)
                suggestion_data = {
                    'title': suggestion_title,
                    'type': event_type,
                    'guests': guest_count,
                    'budget': budget_range,
                    'description': suggestion_description,
                    'requirements': special_requirements,
                    'user_id': user_id,
                    'timestamp': datetime.now()
                }
                
                st.success("🎉 **Thank you for your creative suggestion!** You've earned XP for contributing to our event planning community.")
                show_enhanced_xp_notifications()
                
                # Show suggestion summary
                with st.expander("📋 Your Suggestion Summary", expanded=True):
                    st.markdown(f"**Title:** {suggestion_title}")
                    st.markdown(f"**Type:** {event_type}")
                    st.markdown(f"**Guests:** {guest_count}")
                    st.markdown(f"**Budget:** {budget_range}")
                    st.markdown(f"**Description:** {suggestion_description}")
                    if special_requirements:
                        st.markdown(f"**Special Requirements:** {special_requirements}")
            else:
                st.error("❗ Please fill in at least the title and description.")

# Main Event Planner Function
def event_planner():
    """Enhanced main function with full gamification integration"""
    st.title("🎉 AI Event Planning System")
    
    # Check if user is logged in
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("⚠️ Please log in to access the Event Planning System")
        return
    
    # Get user info
    user = st.session_state.user
    user_role = user.get('role', 'user')
    user_id = user.get('user_id', '')
    
    # Award daily login XP (once per day)
    today = datetime.now().date()
    last_login_key = f"last_event_login_{user_id}"
    
    if last_login_key not in st.session_state or st.session_state[last_login_key] != today:
        award_event_xp_with_effects(user_id, user_role, 'daily_login')
        st.session_state[last_login_key] = today
    
    # Render gamification sidebar
    render_event_gamification_sidebar(user_id)
    
    # Role-based interface
    if user_role in ['admin', 'staff', 'chef']:
        # Enhanced staff interface with full chatbot
        render_enhanced_chatbot_ui()
    else:
        # Enhanced user interface with gamification
        render_enhanced_user_experience()

# For testing the module independently
if __name__ == "__main__":
    st.set_page_config(page_title="AI Event Planning System", layout="wide")
    
    # Mock session state for testing
    if 'user' not in st.session_state:
        st.session_state.user = {
            'user_id': 'test_user_123',
            'username': 'Test User',
            'role': 'admin'  # Change to 'user' to test user interface
        }
    
    event_planner()
