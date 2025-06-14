"""
Complete UI Components for the Smart Restaurant Menu Management App.
This file contains all the missing gamification UI functions.
"""

import streamlit as st
from typing import List, Dict, Any, Tuple, Optional
import logging
import time
from datetime import datetime
import re

from modules.auth import register_user, authenticate_user
from firebase_init import init_firebase
from modules.leftover import (
    load_leftovers, parse_manual_leftovers, suggest_recipes,
    generate_dynamic_quiz_questions, calculate_quiz_score, get_user_stats,
    update_user_stats, get_leaderboard, get_xp_progress, award_recipe_xp,
    fetch_ingredients_from_firebase, parse_firebase_ingredients,
    get_ingredients_by_expiry_priority, is_ingredient_valid
)

logger = logging.getLogger(__name__)

# =======================
# MISSING GAMIFICATION UI FUNCTIONS
# =======================

def render_cooking_quiz(ingredients: List[str], user_id: str):
    st.subheader("Cooking Knowledge Quiz")
    st.caption(f"Based on: {', '.join(ingredients[:3])}{'...' if len(ingredients) > 3 else ''}")

    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = None
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = []
    if 'quiz_submitted' not in st.session_state:
        st.session_state.quiz_submitted = False
    if 'quiz_results' not in st.session_state:
        st.session_state.quiz_results = None

    col1, col2 = st.columns([1, 2])
    with col1:
        num_questions = st.selectbox("Questions:", [3, 5, 7], index=1)
    with col2:
        if st.button("Start Quiz", type="primary", use_container_width=True):
            with st.spinner("Loading questions..."):
                st.session_state.quiz_questions = generate_dynamic_quiz_questions(ingredients, num_questions)
                st.session_state.quiz_answers = []
                st.session_state.quiz_submitted = False
                st.session_state.quiz_results = None
                st.rerun()

    if st.session_state.quiz_questions and not st.session_state.quiz_submitted:
        st.divider()
        answers = []
        for i, question in enumerate(st.session_state.quiz_questions):
            with st.container():
                st.write(f"**{i+1}.** {question['question']}")
                difficulty_map = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
                st.caption(f"{difficulty_map.get(question['difficulty'], 'Unknown')} • {question['xp_reward']} XP")
                answer = st.radio("Select answer:", options=question['options'], key=f"q_{i}", index=None, label_visibility="collapsed")
                if answer:
                    answers.append(question['options'].index(answer))
                else:
                    answers.append(-1)
            if i < len(st.session_state.quiz_questions) - 1:
                st.divider()
        
        st.write("")
        if st.button("Submit Quiz", type="primary", use_container_width=True):
            if -1 in answers:
                st.error("Please answer all questions before submitting.")
            else:
                st.session_state.quiz_answers = answers
                st.session_state.quiz_submitted = True
                correct, total, xp_earned = calculate_quiz_score(answers, st.session_state.quiz_questions)
                st.session_state.quiz_results = {
                    'correct': correct,
                    'total': total,
                    'xp_earned': xp_earned,
                    'percentage': (correct / total) * 100
                }
                update_user_stats(user_id, xp_earned, correct, total)
                st.rerun()

    if st.session_state.quiz_submitted and st.session_state.quiz_results:
        display_quiz_results(st.session_state.quiz_results, st.session_state.quiz_questions, st.session_state.quiz_answers)

def display_quiz_results(results: Dict, questions: List[Dict], user_answers: List[int]):
    st.divider()
    st.subheader("Quiz Results")
    score = results['correct']
    total = results['total']
    percentage = results['percentage']
    xp_earned = results['xp_earned']

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Score", f"{score}/{total}")
    with col2:
        st.metric("Accuracy", f"{percentage:.1f}%")
    with col3:
        st.metric("XP Earned", f"+{xp_earned}")
    with col4:
        if percentage == 100:
            st.metric("Grade", "Perfect")
        elif percentage >= 80:
            st.metric("Grade", "Excellent")
        elif percentage >= 60:
            st.metric("Grade", "Good")
        else:
            st.metric("Grade", "Practice")

    if percentage == 100:
        st.success("Perfect score! Excellent culinary knowledge.")
    elif percentage >= 80:
        st.success("Great work! Your cooking knowledge is impressive.")
    elif percentage >= 60:
        st.info("Good job! Keep studying to improve further.")
    else:
        st.warning("Keep learning! Practice makes perfect.")

    with st.expander("Review Answers", expanded=False):
        for i, question in enumerate(questions):
            user_answer = user_answers[i]
            correct_answer = question['correct']
            is_correct = user_answer == correct_answer
            status = "✓" if is_correct else "✗"
            st.write(f"**{status} Question {i+1}:** {question['question']}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"Your answer: {question['options'][user_answer]}")
            with col2:
                st.write(f"Correct: {question['options'][correct_answer]}")
            if 'explanation' in question and question['explanation']:
                st.caption(f"Explanation: {question['explanation']}")
            if i < len(questions) - 1:
                st.divider()

    if st.button("Take Another Quiz", use_container_width=True):
        st.session_state.quiz_questions = None
        st.session_state.quiz_answers = []
        st.session_state.quiz_submitted = False
        st.session_state.quiz_results = None
        st.rerun()

def display_leaderboard():
    st.subheader("Leaderboard")
    st.caption("Top players by XP")
    leaderboard = get_leaderboard(10)
    if leaderboard:
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
        with col1: st.write("**Rank**")
        with col2: st.write("**Player**")
        with col3: st.write("**Level**")
        with col4: st.write("**XP**")
        with col5: st.write("**Quizzes**")
        st.divider()
        for entry in leaderboard:
            col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
            with col1:
                if entry['rank'] <= 3:
                    rank_display = {1: "🥇", 2: "🥈", 3: "🥉"}[entry['rank']]
                else:
                    rank_display = str(entry['rank'])
                st.write(rank_display)
            with col2:
                st.write(entry['username'])
            with col3:
                st.write(f"Level {entry['level']}")
            with col4:
                st.write(f"{entry['total_xp']:,}")
            with col5:
                st.write(entry['quizzes_taken'])
    else:
        st.info("No leaderboard data available. Be the first to take a quiz!")

def display_achievements_showcase(user_id: str):
    st.subheader("Achievements")
    stats = get_user_stats(user_id)
    achievements = stats.get('achievements', [])
    if not achievements:
        st.info("No achievements yet. Take quizzes to start earning achievements!")
        return

    achievement_descriptions = {
        "First Quiz": "Completed your first cooking quiz",
        "Quiz Novice": "Completed 5 cooking quizzes",
        "Quiz Enthusiast": "Completed 10 cooking quizzes",
        "Quiz Master": "Completed 25 cooking quizzes",
        "Quiz Legend": "Completed 50 cooking quizzes",
        "Perfectionist": "Achieved your first perfect score",
        "Streak Master": "Achieved 5 perfect scores",
        "Flawless Chef": "Achieved 10 perfect scores",
        "Rising Star": "Reached Level 5",
        "Kitchen Pro": "Reached Level 10",
        "Culinary Expert": "Reached Level 15",
        "Master Chef": "Reached Level 20"
    }

    cols = st.columns(2)
    for i, achievement in enumerate(achievements):
        col_idx = i % 2
        with cols[col_idx]:
            description = achievement_descriptions.get(achievement, "Special achievement")
            st.success(f"**{achievement}**\n{description}")

    st.divider()
    st.write("**Progress Tracking**")
    quizzes_taken = stats.get('quizzes_taken', 0)
    perfect_scores = stats.get('perfect_scores', 0)
    current_level = stats.get('level', 1)

    quiz_milestones = [1, 5, 10, 25, 50]
    next_quiz_milestone = next((m for m in quiz_milestones if m > quizzes_taken), None)
    if next_quiz_milestone:
        progress = quizzes_taken / next_quiz_milestone
        st.progress(progress, text=f"Quiz Progress: {quizzes_taken}/{next_quiz_milestone}")

def display_gamification_dashboard(user_id: str):
    st.title("Player Dashboard")
    stats = get_user_stats(user_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Level", stats['level'], f"{stats['total_xp']} XP")
    with col2:
        st.metric("Quizzes Taken", stats['quizzes_taken'])
    with col3:
        accuracy = (stats['correct_answers'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0
        st.metric("Accuracy", f"{accuracy:.1f}%")
    with col4:
        st.metric("Achievements", len(stats.get('achievements', [])))

    tab1, tab2, tab3 = st.tabs(["Achievements", "Progress", "Leaderboard"])
    with tab1:
        display_achievements_showcase(user_id)
    with tab2:
        display_progress_tracking(user_id)
    with tab3:
        display_leaderboard()

def display_progress_tracking(user_id: str):
    stats = get_user_stats(user_id)
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress_percentage = (current_level_xp / xp_for_current_level * 100) if xp_for_current_level > 0 else 0

    st.subheader("Level Progress")
    st.progress(current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0)
    st.write(f"Level {stats['level']}: {current_level_xp}/{xp_for_current_level} XP ({progress_percentage:.1f}%)")
    st.caption(f"{xp_needed} XP needed for Level {stats['level'] + 1}")

    st.divider()
    st.subheader("Statistics")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Quiz Performance**")
        if stats['quizzes_taken'] > 0:
            perfect_rate = (stats['perfect_scores'] / stats['quizzes_taken']) * 100
            st.metric("Perfect Score Rate", f"{perfect_rate:.1f}%")
            st.metric("Questions Answered", stats['total_questions'])
        else:
            st.info("No quizzes taken yet")
    with col2:
        st.write("**Activity**")
        st.metric("Recipes Generated", stats.get('recipes_generated', 0))
        st.metric("Days Active", calculate_days_active(stats))

    st.divider()
    st.subheader("Weekly Goals")
    display_weekly_goals(stats)

def calculate_days_active(stats: Dict) -> int:
    base_days = max(1, stats.get('quizzes_taken', 0) // 2)
    return min(base_days, 30)

def display_weekly_goals(stats: Dict):
    quizzes_this_week = min(stats.get('quizzes_taken', 0), 7)
    recipes_this_week = min(stats.get('recipes_generated', 0), 5)

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Quiz Goal (5/week)**")
        quiz_progress = min(quizzes_this_week / 5, 1.0)
        st.progress(quiz_progress, text=f"{quizzes_this_week}/5 completed")
    with col2:
        st.write("**Recipe Goal (3/week)**")
        recipe_progress = min(recipes_this_week / 3, 1.0)
        st.progress(recipe_progress, text=f"{recipes_this_week}/3 completed")

def award_recipe_generation_xp(user_id: str, num_recipes: int = 1):
    updated_stats = award_recipe_xp(user_id, num_recipes)
    xp_earned = num_recipes * 5
    st.success(f"Recipe generated! +{xp_earned} XP earned")
    if 'level_up' in st.session_state and st.session_state.level_up:
        st.balloons()
        st.success(f"Level Up! You're now Level {updated_stats['level']}")
        st.session_state.level_up = False

def show_xp_notification(xp_earned: int, level_up: bool = False):
    if level_up:
        st.balloons()
        st.success(f"Level Up! +{xp_earned} XP earned")
    else:
        st.success(f"+{xp_earned} XP earned")

def get_daily_challenge(user_id: str) -> Dict:
    import random
    challenges = [
        {"title": "Perfect Score Challenge", "description": "Get a perfect score on any quiz", "xp_reward": 25, "type": "quiz_perfect"},
        {"title": "Recipe Explorer", "description": "Generate 3 different recipes today", "xp_reward": 20, "type": "recipe_count"},
        {"title": "Knowledge Seeker", "description": "Take 2 quizzes today", "xp_reward": 15, "type": "quiz_count"},
        {"title": "Accuracy Master", "description": "Maintain 80%+ accuracy across all quizzes today", "xp_reward": 30, "type": "accuracy"}
    ]
    today_seed = datetime.now().strftime("%Y-%m-%d") + user_id
    random.seed(hash(today_seed))
    return random.choice(challenges)

def display_daily_challenge(user_id: str):
    challenge = get_daily_challenge(user_id)
    st.subheader("Daily Challenge")
    with st.container():
        st.write(f"**{challenge['title']}**")
        st.write(challenge['description'])
        st.caption(f"Reward: +{challenge['xp_reward']} XP")

def display_user_stats_sidebar(user_id: str) -> Dict:
    stats = get_user_stats(user_id)
    st.sidebar.divider()
    st.sidebar.subheader("Player Stats")
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Level", stats['level'])
        st.metric("Quizzes", stats['quizzes_taken'])
    with col2:
        st.metric("XP", stats['total_xp'])
        st.metric("Perfect", stats['perfect_scores'])

    st.sidebar.progress(progress, text=f"{xp_needed} XP to next level")
    if stats['total_questions'] > 0:
        accuracy = (stats['correct_answers'] / stats['total_questions']) * 100
        st.sidebar.metric("Accuracy", f"{accuracy:.1f}%")
    return stats

# =======================
# AUTHENTICATION UI (keeping existing functions)
# =======================

def initialize_session_state():
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'auth_mode' not in st.session_state:
        st.session_state.auth_mode = 'login'
    if 'firebase_initialized' not in st.session_state:
        st.session_state.firebase_initialized = init_firebase()

def switch_to_register():
    st.session_state.auth_mode = 'register'

def switch_to_login():
    st.session_state.auth_mode = 'login'

def logout_user():
    st.session_state.user = None
    st.session_state.is_authenticated = False
    st.session_state.auth_mode = 'login'
    st.success("You have been logged out successfully!")
    st.rerun()

def login_form() -> bool:
    st.markdown("""
    <style>
    .auth-container {max-width: 500px; margin: 0 auto; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);}
    .auth-title {text-align: center; font-size: 2rem; margin-bottom: 0.5rem; color: #ffffff;}
    .auth-subtitle {text-align: center; margin-bottom: 2rem; color: #cccccc;}
    .stTextInput > div > div > input {background-color: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: white; padding: 12px;}
    .stTextInput > div > div > input:focus {border-color: rgba(255,255,255,0.4); box-shadow: 0 0 0 2px rgba(255,255,255,0.1);}
    .auth-switch-text {text-align: center; margin-top: 1.5rem; color: #cccccc;}
    </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="auth-title">🔐 Welcome Back!</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Please sign in to your account</p>', unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            username_or_email = st.text_input("Username or Email", placeholder="Enter your username or email", help="You can use either your username or email address")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("🚀 Login", use_container_width=True)
            if submitted:
                if not username_or_email or not password:
                    st.error("⚠️ Please fill all fields!")
                    return False
                with st.spinner("Signing you in..."):
                    success, user_data, message = authenticate_user(username_or_email, password)
                    if success:
                        st.session_state.user = user_data
                        st.session_state.is_authenticated = True
                        st.success(f"🎉 Welcome back, {user_data['username']}!")
                        st.balloons()
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        st.markdown('<div class="auth-switch-text">Don\'t have an account?</div>', unsafe_allow_html=True)
        if st.button("📝 Create New Account", use_container_width=True, key="switch_to_register"):
            switch_to_register()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    return False

def registration_form() -> bool:
    st.markdown("""
    <style>
    .auth-container {max-width: 500px; margin: 0 auto; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);}
    .auth-title {text-align: center; font-size: 2rem; margin-bottom: 0.5rem; color: #ffffff;}
    .auth-subtitle {text-align: center; margin-bottom: 2rem; color: #cccccc;}
    .stTextInput > div > div > input {background-color: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: white; padding: 12px;}
    .stTextInput > div > div > input:focus {border-color: rgba(255,255,255,0.4); box-shadow: 0 0 0 2px rgba(255,255,255,0.1);}
    .auth-switch-text {text-align: center; margin-top: 1.5rem; color: #cccccc;}
    .section-header { color: #ffffff; font-weight: 600; margin: 1rem 0 0.5rem 0;}
    </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="auth-title">📝 Create Your Account</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Join our restaurant management system</p>', unsafe_allow_html=True)
        with st.form("registration_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Choose a unique username", help="Your username must be unique")
            email = st.text_input("Email", placeholder="your.email@example.com", help="We'll use this for account recovery")
            password = st.text_input("Password", type="password", placeholder="Create a strong password", help="Password must be at least 5 characters with uppercase letters and numbers")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
            st.markdown('<p class="section-header">Account Type:</p>', unsafe_allow_html=True)
            is_staff = st.checkbox("🏢 I'm restaurant staff", help="Check this if you work at the restaurant")
            role = "user"
            staff_code = ""
            if is_staff:
                role_options = {
                    "staff": "👥 Staff Member",
                    "chef": "👨‍🍳 Chef",
                    "admin": "⚡ Administrator"
                }
                role = st.selectbox("Select your role:", list(role_options.keys()), format_func=lambda x: role_options[x])
                staff_code = st.text_input("Staff Registration Code", type="password", placeholder="Enter staff code", help="Contact your manager for the registration code")
            submitted = st.form_submit_button("🎯 Create Account", use_container_width=True)
            if submitted:
                if not username or not email or not password or not confirm_password:
                    st.error("⚠️ Please fill all required fields!")
                    return False
                if password != confirm_password:
                    st.error("🔐 Passwords do not match!")
                    return False
                if is_staff and staff_code != "staffcode123":
                    st.error("🚫 Invalid staff registration code!")
                    role = "user"
                with st.spinner("Creating your account..."):
                    success, message = register_user(username, email, password, role)
                    if success:
                        st.success(f"🎉 {message}")
                        st.info("✅ Account created successfully! Please log in with your new credentials.")
                        st.balloons()
                        st.session_state.auth_mode = 'login'
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        st.markdown('<div class="auth-switch-text">Already have an account?</div>', unsafe_allow_html=True)
        if st.button("🔐 Sign In Instead", use_container_width=True, key="switch_to_login"):
            switch_to_login()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    return False

def user_profile():
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        with st.sidebar.container():
            st.markdown("### 👤 User Profile")
            st.markdown(f"**Welcome back!**  \n🏷️ **Name:** {user['username']}  \n🎭 **Role:** {user['role'].capitalize()}  ")
            role_badges = {
                'admin': '⚡ Administrator',
                'chef': '👨‍🍳 Chef',
                'staff': '👥 Staff Member',
                'user': '🙂 Customer'
            }
            if user['role'] in role_badges:
                st.markdown(f"*{role_badges[user['role']]}*")
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                logout_user()

def auth_required(func):
    def wrapper(*args, **kwargs):
        initialize_session_state()
        if st.session_state.is_authenticated:
            return func(*args, **kwargs)
        else:
            st.warning("🔒 You need to be logged in to access this feature.")
            if st.session_state.auth_mode == 'login':
                login_form()
            else:
                registration_form()
            return None
    return wrapper

def render_auth_ui():
    initialize_session_state()
    if st.session_state.is_authenticated:
        user_profile()
        return True
    if st.session_state.auth_mode == 'login':
        return login_form()
    else:
        return registration_form()

def get_current_user() -> Optional[Dict]:
    if st.session_state.is_authenticated and st.session_state.user:
        return st.session_state.user
    return None

def is_user_role(required_role: str) -> bool:
    user = get_current_user()
    return bool(user and user['role'] == required_role)

def show_auth_status():
    if st.session_state.is_authenticated:
        user = get_current_user()
        st.sidebar.success(f"✅ Signed in as {user['username']}")
    else:
        st.sidebar.info("ℹ️ Please sign in to continue")

def create_auth_tabs():
    initialize_session_state()
    if not st.session_state.is_authenticated:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        with tab1:
            login_form()
        with tab2:
            registration_form()
    else:
        user_profile()

# =======================
# MAIN UI COMPONENTS
# =======================

def leftover_input_csv() -> List[str]:
    st.sidebar.subheader("CSV Upload")
    use_csv = st.sidebar.checkbox("Upload from CSV file")
    leftovers = []
    if use_csv:
        uploaded_file = st.sidebar.file_uploader("Choose CSV file", type=["csv"], help="CSV should contain a column with ingredient names")
        if uploaded_file is not None:
            try:
                leftovers = load_leftovers(uploaded_file)
                st.sidebar.success(f"Loaded {len(leftovers)} ingredients")
            except Exception as err:
                st.sidebar.error(f"Error loading CSV: {str(err)}")
                st.sidebar.info("Please check your CSV format")
    return leftovers

def leftover_input_manual() -> List[str]:
    st.sidebar.subheader("Manual Entry")
    ingredients_text = st.sidebar.text_area("Enter ingredients (comma-separated)", placeholder="tomatoes, onions, chicken, rice", help="Separate ingredients with commas")
    leftovers = []
    if ingredients_text:
        try:
            leftovers = parse_manual_leftovers(ingredients_text)
            st.sidebar.success(f"Added {len(leftovers)} ingredients")
        except Exception as err:
            st.sidebar.error(f"Error: {str(err)}")
    return leftovers

def leftover_input_firebase() -> Tuple[List[str], List[Dict]]:
    """
    UI component to fetch ingredients from Firebase inventory with expiry priority
    Only shows and uses ingredients that haven't expired yet
    
    Returns:
        Tuple[List[str], List[Dict]]: (ingredient_names, detailed_ingredient_info)
    """
    st.sidebar.subheader("Current Inventory")
    use_firebase = st.sidebar.checkbox("Use current inventory from Firebase", help="Fetch valid ingredients from your current inventory, prioritized by expiry date")
    leftovers = []
    detailed_info = []
    
    if use_firebase:
        # Add option to select number of ingredients to use
        max_ingredients = st.sidebar.slider(
            "Max ingredients to use", 
            min_value=3, 
            max_value=15, 
            value=8,
            help="Select how many valid ingredients to use (prioritized by expiry date)"
        )
        
        if st.sidebar.button("Fetch Valid Ingredients", type="primary"):
            try:
                # Show spinner in the main area since sidebar doesn't support spinner
                with st.spinner("Fetching valid ingredients from inventory..."):
                    # Fetch ingredients from Firebase (already filtered for valid ones and sorted by expiry date)
                    firebase_ingredients = fetch_ingredients_from_firebase()
                    
                    if firebase_ingredients:
                        # Get ingredients prioritized by expiry date
                        leftovers, detailed_info = get_ingredients_by_expiry_priority(
                            firebase_ingredients, max_ingredients
                        )
                        
                        st.sidebar.success(f"Found {len(leftovers)} valid ingredients")
                        
                        # Show summary of filtering
                        st.sidebar.info(f"ℹ️ Only showing ingredients that haven't expired")
                        
                        # Show a preview of valid ingredients with expiry info
                        with st.sidebar.expander("Valid Ingredients", expanded=True):
                            current_date = datetime.now().date()
                            
                            for item in detailed_info:
                                days_left = item['days_until_expiry']
                                
                                # Color code based on urgency (only for valid ingredients)
                                if days_left == 0:
                                    urgency_color = "🟠"  # Orange for expires today
                                    urgency_text = "expires today"
                                elif days_left == 1:
                                    urgency_color = "🔴"  # Red for expires tomorrow
                                    urgency_text = "expires tomorrow"
                                elif days_left <= 3:
                                    urgency_color = "🟡"  # Yellow for expires soon (2-3 days)
                                    urgency_text = f"expires in {days_left} days"
                                elif days_left <= 7:
                                    urgency_color = "🟢"  # Green for moderate (4-7 days)
                                    urgency_text = f"expires in {days_left} days"
                                else:
                                    urgency_color = "⚪"  # White for later
                                    urgency_text = f"expires in {days_left} days"
                                
                                st.sidebar.markdown(f"{urgency_color} **{item['name']}**  \n"
                                                   f"Expires: {item['expiry_date']} ({urgency_text})  \n"
                                                   f"Type: {item['type']}")
                                st.sidebar.divider()
                        
                        # Store in session state for recipe generation
                        st.session_state.firebase_ingredients = leftovers
                        st.session_state.firebase_detailed_info = detailed_info
                        
                    else:
                        st.sidebar.warning("No valid ingredients found in inventory")
                        st.sidebar.info("All ingredients may have expired. Please check your inventory dates.")
                        
            except Exception as err:
                st.sidebar.error(f"Error fetching ingredients: {str(err)}")
    
    # Return stored ingredients if they exist
    if 'firebase_ingredients' in st.session_state:
        return st.session_state.firebase_ingredients, st.session_state.get('firebase_detailed_info', [])
    
    return leftovers, detailed_info
