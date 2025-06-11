"""
Minimalist UI components for the gamification system.
Handles quiz interface, leaderboard display, and user stats visualization.

File location: ui/gamification_ui.py
"""

import streamlit as st
from typing import List, Dict, Optional
import time
from datetime import datetime

# Import gamification functions
from modules.leftover_gamification import (
    generate_dynamic_quiz_questions, calculate_quiz_score, get_user_stats,
    update_user_stats, get_leaderboard, get_xp_progress, award_recipe_xp
)

def display_user_stats_sidebar(user_id: str) -> Dict:
    """
    Display user's gamification stats in the sidebar with minimal design.
    
    Args:
        user_id (str): User's unique ID
    
    Returns:
        Dict: User's current stats
    """
    stats = get_user_stats(user_id)
    
    st.sidebar.divider()
    st.sidebar.subheader("Player Stats")
    
    # Level and XP display
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0
    
    # Clean metrics display
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Level", stats['level'])
        st.metric("Quizzes", stats['quizzes_taken'])
    with col2:
        st.metric("XP", stats['total_xp'])
        st.metric("Perfect", stats['perfect_scores'])
    
    # Progress bar
    st.sidebar.progress(progress, text=f"{xp_needed} XP to next level")
    
    # Accuracy
    if stats['total_questions'] > 0:
        accuracy = (stats['correct_answers'] / stats['total_questions']) * 100
        st.sidebar.metric("Accuracy", f"{accuracy:.1f}%")
    
    return stats

def render_cooking_quiz(ingredients: List[str], user_id: str):
    """
    Render the cooking quiz interface with clean design.
    
    Args:
        ingredients (List[str]): List of leftover ingredients
        user_id (str): User's unique ID
    """
    st.subheader("Cooking Knowledge Quiz")
    st.caption(f"Based on: {', '.join(ingredients[:3])}{'...' if len(ingredients) > 3 else ''}")
    
    # Initialize session state for quiz
    if 'quiz_questions' not in st.session_state:
        st.session_state.quiz_questions = None
    if 'quiz_answers' not in st.session_state:
        st.session_state.quiz_answers = []
    if 'quiz_submitted' not in st.session_state:
        st.session_state.quiz_submitted = False
    if 'quiz_results' not in st.session_state:
        st.session_state.quiz_results = None
    
    # Quiz configuration
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
    
    # Display quiz if questions are loaded
    if st.session_state.quiz_questions and not st.session_state.quiz_submitted:
        st.divider()
        
        answers = []
        for i, question in enumerate(st.session_state.quiz_questions):
            with st.container():
                st.write(f"**{i+1}.** {question['question']}")
                
                # Difficulty and XP info
                difficulty_map = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
                st.caption(f"{difficulty_map.get(question['difficulty'], 'Unknown')} • {question['xp_reward']} XP")
                
                # Answer options
                answer = st.radio(
                    "Select answer:",
                    options=question['options'],
                    key=f"q_{i}",
                    index=None,
                    label_visibility="collapsed"
                )
                
                if answer:
                    answers.append(question['options'].index(answer))
                else:
                    answers.append(-1)
            
            if i < len(st.session_state.quiz_questions) - 1:
                st.divider()
        
        # Submit quiz button
        st.write("")  # Spacing
        if st.button("Submit Quiz", type="primary", use_container_width=True):
            if -1 in answers:
                st.error("Please answer all questions before submitting.")
            else:
                st.session_state.quiz_answers = answers
                st.session_state.quiz_submitted = True
                
                # Calculate results
                correct, total, xp_earned = calculate_quiz_score(answers, st.session_state.quiz_questions)
                st.session_state.quiz_results = {
                    'correct': correct,
                    'total': total,
                    'xp_earned': xp_earned,
                    'percentage': (correct / total) * 100
                }
                
                # Update user stats
                update_user_stats(user_id, xp_earned, correct, total)
                st.rerun()
    
    # Display results if quiz is submitted
    if st.session_state.quiz_submitted and st.session_state.quiz_results:
        display_quiz_results(st.session_state.quiz_results, st.session_state.quiz_questions, st.session_state.quiz_answers)

def display_quiz_results(results: Dict, questions: List[Dict], user_answers: List[int]):
    """
    Display quiz results with clean feedback design.
    
    Args:
        results (Dict): Quiz results
        questions (List[Dict]): Quiz questions
        user_answers (List[int]): User's answers
    """
    st.divider()
    st.subheader("Quiz Results")
    
    # Score display
    score = results['correct']
    total = results['total']
    percentage = results['percentage']
    xp_earned = results['xp_earned']
    
    # Results metrics
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
    
    # Performance message
    if percentage == 100:
        st.success("Perfect score! Excellent culinary knowledge.")
    elif percentage >= 80:
        st.success("Great work! Your cooking knowledge is impressive.")
    elif percentage >= 60:
        st.info("Good job! Keep studying to improve further.")
    else:
        st.warning("Keep learning! Practice makes perfect.")
    
    # Question review
    with st.expander("Review Answers", expanded=False):
        for i, question in enumerate(questions):
            user_answer = user_answers[i]
            correct_answer = question['correct']
            is_correct = user_answer == correct_answer
            
            # Question header
            status = "✓" if is_correct else "✗"
            st.write(f"**{status} Question {i+1}:** {question['question']}")
            
            # Answer details
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"Your answer: {question['options'][user_answer]}")
            with col2:
                st.write(f"Correct: {question['options'][correct_answer]}")
            
            # Explanation
            if 'explanation' in question and question['explanation']:
                st.caption(f"Explanation: {question['explanation']}")
            
            if i < len(questions) - 1:
                st.divider()
    
    # New quiz button
    if st.button("Take Another Quiz", use_container_width=True):
        st.session_state.quiz_questions = None
        st.session_state.quiz_answers = []
        st.session_state.quiz_submitted = False
        st.session_state.quiz_results = None
        st.rerun()

def display_leaderboard():
    """Display the global leaderboard with clean design."""
    st.subheader("Leaderboard")
    st.caption("Top players by XP")
    
    leaderboard = get_leaderboard(10)
    
    if leaderboard:
        # Header
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 2])
        with col1:
            st.write("**Rank**")
        with col2:
            st.write("**Player**")
        with col3:
            st.write("**Level**")
        with col4:
            st.write("**XP**")
        with col5:
            st.write("**Quizzes**")
        
        st.divider()
        
        # Leaderboard entries
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
    """
    Display user's achievements in a clean showcase format.
    
    Args:
        user_id (str): User's unique ID
    """
    st.subheader("Achievements")
    
    stats = get_user_stats(user_id)
    achievements = stats.get('achievements', [])
    
    if not achievements:
        st.info("No achievements yet. Take quizzes to start earning achievements!")
        return
    
    # Achievement definitions
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
    
    # Display achievements in a clean grid
    cols = st.columns(2)
    for i, achievement in enumerate(achievements):
        col_idx = i % 2
        with cols[col_idx]:
            description = achievement_descriptions.get(achievement, "Special achievement")
            st.success(f"**{achievement}**\n{description}")
    
    # Achievement progress
    st.divider()
    st.write("**Progress Tracking**")
    
    quizzes_taken = stats.get('quizzes_taken', 0)
    perfect_scores = stats.get('perfect_scores', 0)
    current_level = stats.get('level', 1)
    
    # Next milestones
    quiz_milestones = [1, 5, 10, 25, 50]
    next_quiz_milestone = next((m for m in quiz_milestones if m > quizzes_taken), None)
    
    if next_quiz_milestone:
        progress = quizzes_taken / next_quiz_milestone
        st.progress(progress, text=f"Quiz Progress: {quizzes_taken}/{next_quiz_milestone}")

def display_gamification_dashboard(user_id: str):
    """
    Display a clean gamification dashboard.
    
    Args:
        user_id (str): User's unique ID
    """
    st.title("Player Dashboard")
    
    # Get user stats
    stats = get_user_stats(user_id)
    
    # Overview metrics
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
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Achievements", "Progress", "Leaderboard"])
    
    with tab1:
        display_achievements_showcase(user_id)
    
    with tab2:
        display_progress_tracking(user_id)
    
    with tab3:
        display_leaderboard()

def display_progress_tracking(user_id: str):
    """
    Display clean progress tracking for the user.
    
    Args:
        user_id (str): User's unique ID
    """
    stats = get_user_stats(user_id)
    
    # XP Progress
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress_percentage = (current_level_xp / xp_for_current_level * 100) if xp_for_current_level > 0 else 0
    
    st.subheader("Level Progress")
    st.progress(current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0)
    st.write(f"Level {stats['level']}: {current_level_xp}/{xp_for_current_level} XP ({progress_percentage:.1f}%)")
    st.caption(f"{xp_needed} XP needed for Level {stats['level'] + 1}")
    
    # Performance metrics
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
    
    # Weekly goals
    st.divider()
    st.subheader("Weekly Goals")
    display_weekly_goals(stats)

def calculate_days_active(stats: Dict) -> int:
    """Calculate approximate days active based on user stats."""
    base_days = max(1, stats.get('quizzes_taken', 0) // 2)
    return min(base_days, 30)

def display_weekly_goals(stats: Dict):
    """Display weekly goals with clean progress bars."""
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
    """
    Award XP for recipe generation with clean notification.
    
    Args:
        user_id (str): User's unique ID
        num_recipes (int): Number of recipes generated
    """
    updated_stats = award_recipe_xp(user_id, num_recipes)
    xp_earned = num_recipes * 5
    
    # Show clean success message
    st.success(f"Recipe generated! +{xp_earned} XP earned")
    
    # Check for level up
    if 'level_up' in st.session_state and st.session_state.level_up:
        st.balloons()
        st.success(f"Level Up! You're now Level {updated_stats['level']}")
        st.session_state.level_up = False

def show_xp_notification(xp_earned: int, level_up: bool = False):
    """
    Show clean XP earned notification.
    
    Args:
        xp_earned (int): XP amount earned
        level_up (bool): Whether user leveled up
    """
    if level_up:
        st.balloons()
        st.success(f"Level Up! +{xp_earned} XP earned")
    else:
        st.success(f"+{xp_earned} XP earned")

def get_daily_challenge(user_id: str) -> Dict:
    """
    Generate a daily challenge for the user.
    
    Args:
        user_id (str): User's unique ID
    
    Returns:
        Dict: Daily challenge information
    """
    import random
    
    challenges = [
        {
            "title": "Perfect Score Challenge",
            "description": "Get a perfect score on any quiz",
            "xp_reward": 25,
            "type": "quiz_perfect"
        },
        {
            "title": "Recipe Explorer",
            "description": "Generate 3 different recipes today",
            "xp_reward": 20,
            "type": "recipe_count"
        },
        {
            "title": "Knowledge Seeker",
            "description": "Take 2 quizzes today",
            "xp_reward": 15,
            "type": "quiz_count"
        },
        {
            "title": "Accuracy Master",
            "description": "Maintain 80%+ accuracy across all quizzes today",
            "xp_reward": 30,
            "type": "accuracy"
        }
    ]
    
    # Simple daily challenge selection
    today_seed = datetime.now().strftime("%Y-%m-%d") + user_id
    random.seed(hash(today_seed))
    
    return random.choice(challenges)

def display_daily_challenge(user_id: str):
    """Display the daily challenge with clean design."""
    challenge = get_daily_challenge(user_id)
    
    st.subheader("Daily Challenge")
    with st.container():
        st.write(f"**{challenge['title']}**")
        st.write(challenge['description'])
        st.caption(f"Reward: +{challenge['xp_reward']} XP")
