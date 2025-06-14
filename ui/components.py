"""
Simplified UI Components for the Smart Restaurant Menu Management App.
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

# Simplified gamification UI functions
def render_cooking_quiz(ingredients: List[str], user_id: str):
    st.subheader("Cooking Quiz")

    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = None
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = []
    if 'quiz_submitted' not in st.session_state:
        st.session_state.quiz_submitted = False
    if 'quiz_results' not in st.session_state:
        st.session_state.quiz_results = None

    col1, col2 = st.columns(2)
    with col1:
        num_questions = st.selectbox("Questions:", [3, 5, 7], index=1)
    with col2:
        if st.button("Start Quiz", type="primary", use_container_width=True):
            with st.spinner("Loading..."):
                st.session_state.quiz_questions = generate_dynamic_quiz_questions(ingredients, num_questions)
                st.session_state.quiz_answers = []
                st.session_state.quiz_submitted = False
                st.session_state.quiz_results = None
                st.rerun()

    if st.session_state.quiz_questions and not st.session_state.quiz_submitted:
        st.divider()
        answers = []
        for i, question in enumerate(st.session_state.quiz_questions):
            st.write(f"**{i+1}.** {question['question']}")
            st.caption(f"{question['difficulty'].title()} • {question['xp_reward']} XP")
            answer = st.radio("", options=question['options'], key=f"q_{i}", index=None, label_visibility="collapsed")
            if answer:
                answers.append(question['options'].index(answer))
            else:
                answers.append(-1)
            if i < len(st.session_state.quiz_questions) - 1:
                st.divider()
        
        if st.button("Submit", type="primary", use_container_width=True):
            if -1 in answers:
                st.error("Please answer all questions")
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
    st.subheader("Results")
    score = results['correct']
    total = results['total']
    percentage = results['percentage']
    xp_earned = results['xp_earned']

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Score", f"{score}/{total}")
    with col2:
        st.metric("Accuracy", f"{percentage:.1f}%")
    with col3:
        st.metric("XP Earned", f"+{xp_earned}")

    if percentage == 100:
        st.success("Perfect score!")
    elif percentage >= 80:
        st.success("Great work!")
    elif percentage >= 60:
        st.info("Good job!")
    else:
        st.warning("Keep practicing!")

    with st.expander("Review Answers"):
        for i, question in enumerate(questions):
            user_answer = user_answers[i]
            correct_answer = question['correct']
            is_correct = user_answer == correct_answer
            status = "✓" if is_correct else "✗"
            st.write(f"**{status} {i+1}.** {question['question']}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"Your: {question['options'][user_answer]}")
            with col2:
                st.write(f"Correct: {question['options'][correct_answer]}")

    if st.button("New Quiz", use_container_width=True):
        st.session_state.quiz_questions = None
        st.session_state.quiz_answers = []
        st.session_state.quiz_submitted = False
        st.session_state.quiz_results = None
        st.rerun()

def display_leaderboard():
    st.subheader("Leaderboard")
    leaderboard = get_leaderboard(10)
    if leaderboard:
        for entry in leaderboard:
            rank_display = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry['rank'], str(entry['rank']))
            st.write(f"{rank_display} {entry['username']} - Level {entry['level']} ({entry['total_xp']:,} XP)")
    else:
        st.info("No data available")

def display_achievements_showcase(user_id: str):
    st.subheader("Achievements")
    stats = get_user_stats(user_id)
    achievements = stats.get('achievements', [])
    if achievements:
        for achievement in achievements:
            st.success(f"🏆 {achievement}")
    else:
        st.info("No achievements yet")

def display_gamification_dashboard(user_id: str):
    st.title("Player Stats")
    stats = get_user_stats(user_id)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Level", stats['level'])
    with col2:
        st.metric("Quizzes", stats['quizzes_taken'])
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
    
    st.subheader("Level Progress")
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0
    st.progress(progress)
    st.write(f"Level {stats['level']}: {current_level_xp}/{xp_for_current_level} XP")
    st.caption(f"{xp_needed} XP needed for next level")

def award_recipe_generation_xp(user_id: str, num_recipes: int = 1):
    updated_stats = award_recipe_xp(user_id, num_recipes)
    xp_earned = num_recipes * 5
    st.success(f"Recipe generated! +{xp_earned} XP")

def display_daily_challenge(user_id: str):
    st.info("🎯 **Daily Challenge:** Take a quiz to earn bonus XP!")

def display_user_stats_sidebar(user_id: str) -> Dict:
    stats = get_user_stats(user_id)
    st.sidebar.divider()
    st.sidebar.subheader("Player Stats")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Level", stats['level'])
        st.metric("Quizzes", stats['quizzes_taken'])
    with col2:
        st.metric("XP", stats['total_xp'])
        st.metric("Perfect", stats['perfect_scores'])

    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0
    st.sidebar.progress(progress, text=f"{xp_needed} XP to next level")
    
    return stats

# Simplified authentication UI
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
    st.success("Logged out successfully!")
    st.rerun()

def login_form() -> bool:
    st.subheader("🔐 Login")
    with st.form("login_form"):
        username_or_email = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)
        
        if submitted:
            if not username_or_email or not password:
                st.error("Please fill all fields")
                return False
            with st.spinner("Signing in..."):
                success, user_data, message = authenticate_user(username_or_email, password)
                if success:
                    st.session_state.user = user_data
                    st.session_state.is_authenticated = True
                    st.success(f"Welcome back, {user_data['username']}!")
                    st.rerun()
                    return True
                else:
                    st.error(message)
                    return False
    
    if st.button("Create Account", use_container_width=True):
        switch_to_register()
        st.rerun()
    return False

def registration_form() -> bool:
    st.subheader("📝 Register")
    with st.form("registration_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        is_staff = st.checkbox("I'm restaurant staff")
        role = "user"
        staff_code = ""
        
        if is_staff:
            role_options = {
                "staff": "Staff Member",
                "chef": "Chef",
                "admin": "Administrator"
            }
            role = st.selectbox("Role:", list(role_options.keys()), format_func=lambda x: role_options[x])
            staff_code = st.text_input("Staff Code", type="password")
        
        submitted = st.form_submit_button("Create Account", use_container_width=True)
        
        if submitted:
            if not username or not email or not password or not confirm_password:
                st.error("Please fill all fields")
                return False
            if password != confirm_password:
                st.error("Passwords do not match")
                return False
            if is_staff and staff_code != "staffcode123":
                st.error("Invalid staff code")
                role = "user"
            
            with st.spinner("Creating account..."):
                success, message = register_user(username, email, password, role)
                if success:
                    st.success(message)
                    st.info("Account created! Please log in.")
                    st.session_state.auth_mode = 'login'
                    st.rerun()
                    return True
                else:
                    st.error(message)
                    return False
    
    if st.button("Sign In Instead", use_container_width=True):
        switch_to_login()
        st.rerun()
    return False

def user_profile():
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        st.markdown(f"**{user['username']}**")
        st.caption(f"{user['role'].capitalize()}")
        if st.button("Logout", use_container_width=True):
            logout_user()

def auth_required(func):
    def wrapper(*args, **kwargs):
        initialize_session_state()
        if st.session_state.is_authenticated:
            return func(*args, **kwargs)
        else:
            st.warning("Please log in to access this feature")
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

# Simplified leftover input functions
def leftover_input_csv() -> List[str]:
    st.subheader("CSV Upload")
    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
    leftovers = []
    if uploaded_file is not None:
        try:
            leftovers = load_leftovers(uploaded_file)
            st.success(f"✅ Loaded {len(leftovers)} ingredients")
        except Exception as err:
            st.error(f"❌ Error: {str(err)}")
    return leftovers

def leftover_input_manual() -> List[str]:
    st.subheader("Manual Entry")
    ingredients_text = st.text_area("Enter ingredients (comma-separated)", 
                                   placeholder="tomatoes, onions, chicken, rice")
    leftovers = []
    if ingredients_text:
        try:
            leftovers = parse_manual_leftovers(ingredients_text)
            if leftovers:
                st.success(f"✅ Added {len(leftovers)} ingredients")
        except Exception as err:
            st.error(f"❌ Error: {str(err)}")
    return leftovers

def leftover_input_firebase() -> Tuple[List[str], List[Dict]]:
    st.subheader("Current Inventory")
    
    # Get max ingredients from session state (set by the main flow)
    max_ingredients = st.session_state.get('firebase_max_ingredients', 8)
    
    st.info(f"Fetching up to {max_ingredients} ingredients from inventory")
    
    leftovers = []
    detailed_info = []
    
    if st.button("🔥 Fetch Ingredients from Database", type="primary", use_container_width=True):
        try:
            with st.spinner("Fetching ingredients from database..."):
                firebase_ingredients = fetch_ingredients_from_firebase()
                
                if firebase_ingredients:
                    leftovers, detailed_info = get_ingredients_by_expiry_priority(
                        firebase_ingredients, max_ingredients
                    )
                    
                    if leftovers:
                        st.success(f"✅ Found {len(leftovers)} valid ingredients")
                        
                        # Show preview
                        st.markdown("**Preview:**")
                        for item in detailed_info[:3]:  # Show first 3
                            days_left = item['days_until_expiry']
                            if days_left <= 1:
                                st.error(f"🔴 {item['name']} - expires in {days_left} days")
                            elif days_left <= 3:
                                st.warning(f"🟡 {item['name']} - expires in {days_left} days")
                            else:
                                st.info(f"🟢 {item['name']} - expires in {days_left} days")
                        
                        if len(detailed_info) > 3:
                            st.caption(f"... and {len(detailed_info) - 3} more ingredients")
                    else:
                        st.warning("⚠️ No valid ingredients found")
                else:
                    st.warning("⚠️ No ingredients found in database")
                    
        except Exception as err:
            st.error(f"❌ Error: {str(err)}")
    
    return leftovers, detailed_info

def show_xp_notification(xp_earned: int, level_up: bool = False):
    if level_up:
        st.success(f"Level Up! +{xp_earned} XP")
    else:
        st.success(f"+{xp_earned} XP")
