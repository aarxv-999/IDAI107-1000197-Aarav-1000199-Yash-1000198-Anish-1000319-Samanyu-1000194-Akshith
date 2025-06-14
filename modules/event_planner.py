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
\`\`\`
