"""
Enhanced UI Components for Smart Restaurant Menu Management App
Handles authentication, gamification display, and user interface elements
"""

import streamlit as st
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
import datetime
from firebase_admin import firestore
from firebase_init import init_firebase

# Import centralized gamification system
from modules.gamification_core import (
    get_user_stats, award_xp, get_leaderboard, get_achievements,
    get_daily_challenge, complete_daily_challenge, get_user_tasks,
    update_daily_streak
)

logger = logging.getLogger(__name__)

def get_current_user():
    """Get the current authenticated user from session state"""
    return st.session_state.get('user', {})

def is_user_role(required_roles):
    """Check if current user has one of the required roles"""
    user = get_current_user()
    if not user:
        return False
    return user.get('role', '') in required_roles

def initialize_session_state():
    """Initialize session state variables for authentication"""
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = {}
    if 'show_register' not in st.session_state:
        st.session_state.show_register = False

def auth_required(func):
    """Decorator to require authentication for a function"""
    def wrapper(*args, **kwargs):
        if not st.session_state.get('is_authenticated', False):
            st.warning("Please log in to access this feature.")
            return None
        return func(*args, **kwargs)
    return wrapper

def get_firestore_db():
    """Get a Firestore client instance for user authentication"""
    init_firebase()
    return firestore.client()

def hash_password(password: str) -> str:
    """Hash the password using SHA-256 algorithm"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_password(password: str) -> Tuple[bool, str]:
    """Validate that the password meets security requirements"""
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"
    
    has_upper = any(char.isupper() for char in password)
    has_digit = any(char.isdigit() for char in password)
    
    if not (has_upper and has_digit):
        return False, "Password must contain at least one uppercase letter and one number."
    return True, ""

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate that the email has a proper format"""
    if '@' not in email or '.' not in email.split('@')[1]:
        return False, "Please use a proper email format"
    return True, ""

def email_exists(email: str) -> bool:
    """Check if an email already exists in the database"""
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1).get()
        return len(query) > 0
    except Exception as e:
        logger.error(f"Error checking if email exists: {str(e)}")
        return False

def username_exists(username: str) -> bool:
    """Check if a username already exists in the database"""
    try:
        db = get_firestore_db()
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).get()
        return len(query) > 0
    except Exception as e:
        logger.error(f"Error checking if username exists: {str(e)}")
        return False

def register_user(username: str, email: str, password: str, role: str = "user") -> Tuple[bool, str]:
    """Register a new user in the Firebase database with gamification initialization"""
    try:
        # Import here to avoid circular imports
        from auth import register_user as auth_register_user
        return auth_register_user(username, email, password, role)
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return False, f"Registration failed: {str(e)}"

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, Optional[Dict], str]:
    """Authenticate a user with username/email and password"""
    try:
        # Import here to avoid circular imports
        from auth import authenticate_user as auth_authenticate_user
        return auth_authenticate_user(username_or_email, password)
    except Exception as e:
        logger.error(f"Error authenticating user: {str(e)}")
        return False, None, f"Authentication failed: {str(e)}"

def render_auth_ui():
    """Render the authentication UI in the sidebar"""
    if st.session_state.is_authenticated:
        user = st.session_state.user
        st.sidebar.success(f"Welcome, {user.get('username', 'User')}!")
        st.sidebar.write(f"**Role:** {user.get('role', 'user').title()}")
        
        # Update daily streak on login
        user_id = user.get('user_id')
        if user_id:
            update_daily_streak(user_id)
        
        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.user = {}
            st.rerun()
        
        return True
    else:
        # Toggle between login and register
        if st.session_state.show_register:
            render_register_form()
        else:
            render_login_form()
        
        return False

def render_login_form():
    """Render the login form"""
    st.sidebar.subheader("Login")
    
    with st.sidebar.form("login_form"):
        username_or_email = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login", use_container_width=True)
        
        if login_button:
            if username_or_email and password:
                success, user_data, message = authenticate_user(username_or_email, password)
                
                if success:
                    st.session_state.is_authenticated = True
                    st.session_state.user = user_data
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")
    
    if st.sidebar.button("Don't have an account? Register", use_container_width=True):
        st.session_state.show_register = True
        st.rerun()

def render_register_form():
    """Render the registration form"""
    st.sidebar.subheader("Register")
    
    with st.sidebar.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Role", ["user", "staff", "chef", "admin"])
        register_button = st.form_submit_button("Register", use_container_width=True)
        
        if register_button:
            if username and email and password:
                success, message = register_user(username, email, password, role)
                
                if success:
                    st.success(message)
                    st.session_state.show_register = False
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields")
    
    if st.sidebar.button("Already have an account? Login", use_container_width=True):
        st.session_state.show_register = False
        st.rerun()

def show_xp_notification(xp_amount: int, activity: str, achievements: List[str] = None, level_up: bool = False):
    """Show XP notification with achievements and level up"""
    if xp_amount > 0:
        st.success(f"🎉 +{xp_amount} XP for {activity}!")
        
        if level_up:
            st.balloons()
            st.success("🎉 **LEVEL UP!** 🎉")
        
        if achievements:
            for achievement in achievements:
                st.success(f"🏆 **Achievement Unlocked:** {achievement}!")

def display_user_stats_sidebar(user_id: str):
    """Display user gamification stats in sidebar"""
    try:
        user_stats = get_user_stats(user_id)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🎮 Your Stats")
        
        # Level and XP
        level = user_stats.get('level', 1)
        total_xp = user_stats.get('total_xp', 0)
        
        st.sidebar.metric("Level", level)
        st.sidebar.metric("Total XP", f"{total_xp:,}")
        
        # Level progress
        xp_for_current_level = (level - 1) * 100
        current_level_xp = total_xp - xp_for_current_level
        progress = min(current_level_xp / 100.0, 1.0)
        
        st.sidebar.progress(progress, text=f"{current_level_xp}/100 XP to next level")
        
        # Quick stats
        st.sidebar.metric("Achievements", user_stats.get('achievement_count', 0))
        st.sidebar.metric("Daily Streak", user_stats.get('daily_streak', 0))
        
    except Exception as e:
        logger.error(f"Error displaying user stats: {str(e)}")
        st.sidebar.error("Error loading stats")

def render_cooking_quiz(ingredients: List[str], user_id: str):
    """Render an interactive cooking quiz with gamification"""
    try:
        # Import here to avoid circular imports
        import google.generativeai as genai
        import os
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("AI quiz generation unavailable - API key not found")
            return
        
        # Initialize quiz state
        if 'quiz_questions' not in st.session_state:
            st.session_state.quiz_questions = []
        if 'current_question' not in st.session_state:
            st.session_state.current_question = 0
        if 'quiz_answers' not in st.session_state:
            st.session_state.quiz_answers = []
        if 'quiz_completed' not in st.session_state:
            st.session_state.quiz_completed = False
        if 'quiz_score' not in st.session_state:
            st.session_state.quiz_score = 0
        
        # Generate quiz if not already generated
        if not st.session_state.quiz_questions and not st.session_state.quiz_completed:
            if st.button("🎯 Generate Cooking Quiz", type="primary", use_container_width=True):
                with st.spinner("Generating quiz questions..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        ingredient_list = ", ".join(ingredients[:5])  # Use first 5 ingredients
                        
                        prompt = f"""Generate exactly 5 cooking quiz questions. Include questions about:
1. Food safety and temperatures
2. Cooking techniques
3. Ingredient knowledge (using: {ingredient_list})
4. Kitchen equipment
5. Culinary terms

For each question, provide:
- Question text
- 4 multiple choice options (A, B, C, D)
- Correct answer (A, B, C, or D)
- Brief explanation

Format as:
Q1: [Question]
A) [Option A]
B) [Option B] 
C) [Option C]
D) [Option D]
Correct: [Letter]
Explanation: [Brief explanation]

Q2: [Next question...]
"""
                        
                        response = model.generate_content(prompt)
                        quiz_text = response.text.strip()
                        
                        # Parse quiz questions
                        questions = []
                        current_question = {}
                        
                        for line in quiz_text.split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            
                            if line.startswith('Q') and ':' in line:
                                if current_question:
                                    questions.append(current_question)
                                current_question = {
                                    'question': line.split(':', 1)[1].strip(),
                                    'options': [],
                                    'correct': '',
                                    'explanation': ''
                                }
                            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                                if current_question:
                                    current_question['options'].append(line[2:].strip())
                            elif line.startswith('Correct:'):
                                if current_question:
                                    current_question['correct'] = line.split(':', 1)[1].strip()
                            elif line.startswith('Explanation:'):
                                if current_question:
                                    current_question['explanation'] = line.split(':', 1)[1].strip()
                        
                        # Add the last question
                        if current_question:
                            questions.append(current_question)
                        
                        # Fallback questions if parsing fails
                        if len(questions) < 3:
                            questions = [
                                {
                                    'question': 'What is the safe internal temperature for cooking chicken?',
                                    'options': ['145°F (63°C)', '160°F (71°C)', '165°F (74°C)', '180°F (82°C)'],
                                    'correct': 'C',
                                    'explanation': 'Chicken should be cooked to 165°F (74°C) to ensure safety.'
                                },
                                {
                                    'question': 'Which cooking method uses dry heat?',
                                    'options': ['Boiling', 'Steaming', 'Roasting', 'Poaching'],
                                    'correct': 'C',
                                    'explanation': 'Roasting uses dry heat in an oven.'
                                },
                                {
                                    'question': 'What does "mise en place" mean?',
                                    'options': ['A cooking technique', 'Everything in its place', 'A type of sauce', 'A kitchen tool'],
                                    'correct': 'B',
                                    'explanation': 'Mise en place means having all ingredients prepared and organized.'
                                }
                            ]
                        
                        st.session_state.quiz_questions = questions[:5]  # Limit to 5 questions
                        st.session_state.current_question = 0
                        st.session_state.quiz_answers = []
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error generating quiz: {str(e)}")
                        logger.error(f"Quiz generation error: {str(e)}")
        
        # Display quiz questions
        elif st.session_state.quiz_questions and not st.session_state.quiz_completed:
            questions = st.session_state.quiz_questions
            current_q = st.session_state.current_question
            
            if current_q < len(questions):
                question_data = questions[current_q]
                
                st.markdown(f"### Question {current_q + 1} of {len(questions)}")
                st.markdown(f"**{question_data['question']}**")
                
                # Display options
                options = question_data['options']
                if len(options) >= 4:
                    selected_option = st.radio(
                        "Choose your answer:",
                        options,
                        key=f"quiz_q_{current_q}",
                        index=None
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("⏭️ Next Question", disabled=selected_option is None):
                            # Store answer
                            correct_letter = question_data['correct'].upper()
                            correct_index = ord(correct_letter) - ord('A')
                            selected_index = options.index(selected_option)
                            
                            st.session_state.quiz_answers.append({
                                'question': question_data['question'],
                                'selected': selected_option,
                                'correct': options[correct_index] if correct_index < len(options) else options[0],
                                'is_correct': selected_index == correct_index,
                                'explanation': question_data['explanation']
                            })
                            
                            st.session_state.current_question += 1
                            
                            if st.session_state.current_question >= len(questions):
                                # Quiz completed
                                st.session_state.quiz_completed = True
                                correct_count = sum(1 for ans in st.session_state.quiz_answers if ans['is_correct'])
                                st.session_state.quiz_score = correct_count
                                
                                # Award XP based on performance
                                score_percentage = (correct_count / len(questions)) * 100
                                
                                if score_percentage == 100:
                                    xp_awarded, level_up, achievements = award_xp(
                                        user_id, 'quiz_perfect_score',
                                        context={'feature': 'cooking_quiz', 'score': score_percentage}
                                    )
                                elif score_percentage >= 80:
                                    xp_awarded, level_up, achievements = award_xp(
                                        user_id, 'quiz_completion',
                                        context={'feature': 'cooking_quiz', 'score': score_percentage}
                                    )
                                else:
                                    xp_awarded, level_up, achievements = award_xp(
                                        user_id, 'quiz_attempt',
                                        context={'feature': 'cooking_quiz', 'score': score_percentage}
                                    )
                                
                                if xp_awarded > 0:
                                    show_xp_notification(xp_awarded, f"quiz completion ({score_percentage:.0f}%)", achievements, level_up)
                            
                            st.rerun()
                    
                    with col2:
                        if st.button("🔄 Restart Quiz"):
                            st.session_state.quiz_questions = []
                            st.session_state.current_question = 0
                            st.session_state.quiz_answers = []
                            st.session_state.quiz_completed = False
                            st.rerun()
        
        # Display quiz results
        elif st.session_state.quiz_completed:
            st.markdown("### 🎉 Quiz Completed!")
            
            score = st.session_state.quiz_score
            total = len(st.session_state.quiz_questions)
            percentage = (score / total) * 100
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Score", f"{score}/{total}")
            with col2:
                st.metric("Percentage", f"{percentage:.0f}%")
            with col3:
                if percentage == 100:
                    st.metric("Grade", "Perfect! 🌟")
                elif percentage >= 80:
                    st.metric("Grade", "Great! 🎯")
                elif percentage >= 60:
                    st.metric("Grade", "Good! 👍")
                else:
                    st.metric("Grade", "Keep trying! 💪")
            
            # Show detailed results
            st.markdown("### 📊 Detailed Results")
            
            for i, answer in enumerate(st.session_state.quiz_answers):
                with st.expander(f"Question {i+1}: {'✅ Correct' if answer['is_correct'] else '❌ Incorrect'}"):
                    st.markdown(f"**Q:** {answer['question']}")
                    st.markdown(f"**Your answer:** {answer['selected']}")
                    st.markdown(f"**Correct answer:** {answer['correct']}")
                    st.markdown(f"**Explanation:** {answer['explanation']}")
            
            # Reset button
            if st.button("🔄 Take Another Quiz", type="primary", use_container_width=True):
                st.session_state.quiz_questions = []
                st.session_state.current_question = 0
                st.session_state.quiz_answers = []
                st.session_state.quiz_completed = False
                st.session_state.quiz_score = 0
                st.rerun()
    
    except Exception as e:
        logger.error(f"Error in cooking quiz: {str(e)}")
        st.error("Error loading quiz. Please try again.")

def display_gamification_dashboard(user_id: str):
    """Display comprehensive gamification dashboard"""
    try:
        st.title("🎮 Gamification Hub")
        
        # Get user stats
        user_stats = get_user_stats(user_id)
        
        # Main stats overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Level", user_stats.get('level', 1))
        with col2:
            st.metric("Total XP", f"{user_stats.get('total_xp', 0):,}")
        with col3:
            st.metric("Achievements", user_stats.get('achievement_count', 0))
        with col4:
            st.metric("Daily Streak", user_stats.get('daily_streak', 0))
        
        # Level progress
        level = user_stats.get('level', 1)
        total_xp = user_stats.get('total_xp', 0)
        xp_for_current_level = (level - 1) * 100
        current_level_xp = total_xp - xp_for_current_level
        progress = min(current_level_xp / 100.0, 1.0)
        
        st.markdown("### 📈 Level Progress")
        st.progress(progress, text=f"Level {level} - {current_level_xp}/100 XP to next level")
        
        # Tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Achievements", "📊 Leaderboard", "🎯 Daily Challenge", "📋 Tasks"])
        
        with tab1:
            display_achievements_tab(user_id)
        
        with tab2:
            display_leaderboard_tab(user_id)
        
        with tab3:
            display_daily_challenge(user_id)
        
        with tab4:
            display_tasks_tab(user_id)
    
    except Exception as e:
        logger.error(f"Error displaying gamification dashboard: {str(e)}")
        st.error("Error loading gamification data")

def display_achievements_tab(user_id: str):
    """Display achievements tab"""
    try:
        achievements = get_achievements(user_id)
        
        if achievements:
            st.markdown("### 🏆 Your Achievements")
            
            for achievement in achievements:
                col1, col2 = st.columns([1, 4])
                
                with col1:
                    st.markdown("🏆")
                
                with col2:
                    st.markdown(f"**{achievement['name']}**")
                    st.caption(f"Earned: {achievement['earned_date']}")
                    if achievement.get('description'):
                        st.caption(achievement['description'])
        else:
            st.info("No achievements yet. Keep using the app to unlock achievements!")
    
    except Exception as e:
        logger.error(f"Error displaying achievements: {str(e)}")
        st.error("Error loading achievements")

def display_leaderboard_tab(user_id: str):
    """Display leaderboard tab"""
    try:
        leaderboard = get_leaderboard(limit=10)
        
        if leaderboard:
            st.markdown("### 🏅 Top Users")
            
            for entry in leaderboard:
                rank = entry['rank']
                username = entry['username']
                total_xp = entry['total_xp']
                level = entry['level']
                
                # Highlight current user
                if entry['user_id'] == user_id:
                    st.success(f"**#{rank} {username}** (You!) - Level {level} ({total_xp:,} XP)")
                else:
                    # Medal emojis for top 3
                    if rank == 1:
                        medal = "🥇"
                    elif rank == 2:
                        medal = "🥈"
                    elif rank == 3:
                        medal = "🥉"
                    else:
                        medal = f"#{rank}"
                    
                    st.markdown(f"{medal} **{username}** - Level {level} ({total_xp:,} XP)")
        else:
            st.info("Leaderboard is empty. Be the first to earn XP!")
    
    except Exception as e:
        logger.error(f"Error displaying leaderboard: {str(e)}")
        st.error("Error loading leaderboard")

def display_daily_challenge(user_id: str):
    """Display daily challenge"""
    try:
        challenge = get_daily_challenge(user_id)
        
        if challenge:
            st.markdown("### 🎯 Today's Challenge")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"**{challenge['name']}**")
                st.markdown(challenge['description'])
                
                # Progress bar
                progress = challenge['progress'] / challenge['target']
                st.progress(progress, text=f"{challenge['progress']}/{challenge['target']}")
            
            with col2:
                st.metric("Reward", f"{challenge['xp_reward']} XP")
                
                if challenge['completed']:
                    st.success("✅ Completed!")
                elif challenge['progress'] >= challenge['target']:
                    if st.button("🎁 Claim Reward", type="primary"):
                        success = complete_daily_challenge(user_id, challenge['challenge_id'])
                        if success:
                            st.success(f"🎉 Claimed {challenge['xp_reward']} XP!")
                            st.rerun()
        else:
            st.info("No daily challenge available today.")
    
    except Exception as e:
        logger.error(f"Error displaying daily challenge: {str(e)}")
        st.error("Error loading daily challenge")

def display_tasks_tab(user_id: str):
    """Display user tasks"""
    try:
        tasks = get_user_tasks(user_id)
        
        if tasks:
            st.markdown("### 📋 Your Tasks")
            
            for task in tasks:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{task['name']}**")
                        st.caption(task['description'])
                        
                        # Progress bar
                        progress = min(task['progress'] / task['target'], 1.0)
                        st.progress(progress, text=f"{task['progress']}/{task['target']}")
                    
                    with col2:
                        st.metric("Reward", f"{task['xp_reward']} XP")
                    
                    with col3:
                        if task['completed']:
                            st.success("✅ Done")
                        elif task['progress'] >= task['target']:
                            st.info("🎁 Ready")
                        else:
                            remaining = task['target'] - task['progress']
                            st.info(f"{remaining} left")
                    
                    st.divider()
        else:
            st.info("No active tasks. Complete activities to unlock tasks!")
    
    except Exception as e:
        logger.error(f"Error displaying tasks: {str(e)}")
        st.error("Error loading tasks")

def award_feature_xp(user_id: str, feature_name: str, activity: str, amount: Optional[int] = None, context: Dict = None):
    """Award XP for feature usage with UI feedback"""
    try:
        if context is None:
            context = {}
        
        context['feature'] = feature_name
        
        xp_awarded, level_up, achievements = award_xp(user_id, activity, amount, context)
        
        if xp_awarded > 0:
            show_xp_notification(xp_awarded, f"{activity} in {feature_name}", achievements, level_up)
        
        return xp_awarded > 0
    
    except Exception as e:
        logger.error(f"Error awarding feature XP: {str(e)}")
        return False
