"""
Complete UI components for the gamification system.
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
    Display user's gamification stats in the sidebar.
    
    Args:
        user_id (str): User's unique ID
    
    Returns:
        Dict: User's current stats
    """
    stats = get_user_stats(user_id)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎮 Your Stats")
    
    # Level and XP display
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0
    
    st.sidebar.markdown(f"**Level:** {stats['level']} 🌟")
    st.sidebar.markdown(f"**Total XP:** {stats['total_xp']} ⚡")
    st.sidebar.progress(progress)
    st.sidebar.markdown(f"*{xp_needed} XP to next level*")
    
    # Quiz stats
    st.sidebar.markdown(f"**Quizzes Taken:** {stats['quizzes_taken']} 📝")
    st.sidebar.markdown(f"**Perfect Scores:** {stats['perfect_scores']} 💯")
    st.sidebar.markdown(f"**Recipes Generated:** {stats.get('recipes_generated', 0)} 🍳")
    
    # Accuracy
    if stats['total_questions'] > 0:
        accuracy = (stats['correct_answers'] / stats['total_questions']) * 100
        st.sidebar.markdown(f"**Accuracy:** {accuracy:.1f}% 🎯")
    
    # Recent achievements
    achievements = stats.get('achievements', [])
    if achievements:
        st.sidebar.markdown("**Recent Achievements:**")
        for achievement in achievements[-3:]:  # Show last 3 achievements
            st.sidebar.markdown(f"🏆 {achievement}")
    
    return stats

def render_cooking_quiz(ingredients: List[str], user_id: str):
    """
    Render the cooking quiz interface.
    
    Args:
        ingredients (List[str]): List of leftover ingredients
        user_id (str): User's unique ID
    """
    st.subheader("🧠 Cooking Knowledge Quiz")
    st.markdown(f"**Based on your ingredients:** {', '.join(ingredients)}")
    
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
    col1, col2 = st.columns(2)
    with col1:
        num_questions = st.selectbox("Number of Questions:", [3, 5, 7], index=1)
    with col2:
        if st.button("🚀 Start New Quiz"):
            with st.spinner("Generating personalized quiz questions..."):
                st.session_state.quiz_questions = generate_dynamic_quiz_questions(ingredients, num_questions)
                st.session_state.quiz_answers = []
                st.session_state.quiz_submitted = False
                st.session_state.quiz_results = None
                st.rerun()
    
    # Display quiz if questions are loaded
    if st.session_state.quiz_questions and not st.session_state.quiz_submitted:
        st.markdown("---")
        st.markdown("### Quiz Questions")
        
        answers = []
        for i, question in enumerate(st.session_state.quiz_questions):
            st.markdown(f"**Question {i+1}:** {question['question']}")
            
            # Difficulty indicator
            difficulty_colors = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
            st.markdown(f"{difficulty_colors.get(question['difficulty'], '⚪')} Difficulty: {question['difficulty'].title()} | XP: {question['xp_reward']}")
            
            # Multiple choice options
            answer = st.radio(
                f"Select your answer for Question {i+1}:",
                options=question['options'],
                key=f"q_{i}",
                index=None
            )
            
            if answer:
                answers.append(question['options'].index(answer))
            else:
                answers.append(-1)  # No answer selected
            
            st.markdown("---")
        
        # Submit quiz button
        if st.button("📝 Submit Quiz", type="primary"):
            if -1 in answers:
                st.error("Please answer all questions before submitting!")
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
    Display quiz results with detailed feedback.
    
    Args:
        results (Dict): Quiz results
        questions (List[Dict]): Quiz questions
        user_answers (List[int]): User's answers
    """
    st.markdown("---")
    st.markdown("## 🎉 Quiz Results")
    
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
        st.metric("Percentage", f"{percentage:.1f}%")
    with col3:
        st.metric("XP Earned", f"+{xp_earned}")
    with col4:
        if percentage == 100:
            st.metric("Bonus", "Perfect! 🎯")
        elif percentage >= 80:
            st.metric("Grade", "Excellent! 🌟")
        elif percentage >= 60:
            st.metric("Grade", "Good! 👍")
        else:
            st.metric("Grade", "Keep Learning! 📚")
    
    # Performance message
    if percentage == 100:
        st.success("🎯 Perfect score! You're a true culinary expert!")
    elif percentage >= 80:
        st.success("🌟 Excellent work! Your cooking knowledge is impressive!")
    elif percentage >= 60:
        st.info("👍 Good job! Keep studying to become a cooking master!")
    else:
        st.warning("📚 Keep learning! Practice makes perfect in the kitchen!")
    
    # Detailed question review
    st.markdown("### 📋 Question Review")
    for i, question in enumerate(questions):
        user_answer = user_answers[i]
        correct_answer = question['correct']
        is_correct = user_answer == correct_answer
        
        # Question header
        status_icon = "✅" if is_correct else "❌"
        st.markdown(f"**{status_icon} Question {i+1}:** {question['question']}")
        
        # Answer details
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Your answer:** {question['options'][user_answer]}")
        with col2:
            st.markdown(f"**Correct answer:** {question['options'][correct_answer]}")
        
        # Explanation if available
        if 'explanation' in question and question['explanation']:
            st.markdown(f"**💡 Explanation:** {question['explanation']}")
        
        st.markdown("---")
    
    # New quiz button
    if st.button("🔄 Take Another Quiz"):
        st.session_state.quiz_questions = None
        st.session_state.quiz_answers = []
        st.session_state.quiz_submitted = False
        st.session_state.quiz_results = None
        st.rerun()

def display_leaderboard():
    """Display the global leaderboard."""
    st.subheader("🏆 Global Leaderboard")
    st.markdown("*Top chefs by total XP earned*")
    
    leaderboard = get_leaderboard(10)
    
    if leaderboard:
        # Create leaderboard table
        for entry in leaderboard:
            rank = entry['rank']
            username = entry['username']
            total_xp = entry['total_xp']
            level = entry['level']
            quizzes = entry['quizzes_taken']
            perfect_scores = entry['perfect_scores']
            achievements = entry['achievements']
            
            # Rank icons
            rank_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
            rank_icon = rank_icons.get(rank, f"{rank}.")
            
            # Create expandable row for each user
            with st.expander(f"{rank_icon} {username} - Level {level} ({total_xp} XP)"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Quizzes Taken", quizzes)
                with col2:
                    st.metric("Perfect Scores", perfect_scores)
                with col3:
                    st.metric("Achievements", achievements)
    else:
        st.info("No leaderboard data available yet. Be the first to take a quiz!")

def display_achievements_showcase(user_id: str):
    """
    Display user's achievements in a showcase format.
    
    Args:
        user_id (str): User's unique ID
    """
    st.subheader("🏆 Achievement Showcase")
    
    stats = get_user_stats(user_id)
    achievements = stats.get('achievements', [])
    
    if not achievements:
        st.info("🎯 No achievements yet! Take some quizzes to start earning achievements!")
        return
    
    # Achievement definitions with emojis and descriptions
    achievement_info = {
        "First Quiz": {"emoji": "🎯", "description": "Completed your first cooking quiz"},
        "Quiz Novice": {"emoji": "📚", "description": "Completed 5 cooking quizzes"},
        "Quiz Enthusiast": {"emoji": "🔥", "description": "Completed 10 cooking quizzes"},
        "Quiz Master": {"emoji": "👑", "description": "Completed 25 cooking quizzes"},
        "Quiz Legend": {"emoji": "⭐", "description": "Completed 50 cooking quizzes"},
        "Perfectionist": {"emoji": "💯", "description": "Achieved your first perfect score"},
        "Streak Master": {"emoji": "🎯", "description": "Achieved 5 perfect scores"},
        "Flawless Chef": {"emoji": "👨‍🍳", "description": "Achieved 10 perfect scores"},
        "Rising Star": {"emoji": "🌟", "description": "Reached Level 5"},
        "Kitchen Pro": {"emoji": "🔪", "description": "Reached Level 10"},
        "Culinary Expert": {"emoji": "👨‍🍳", "description": "Reached Level 15"},
        "Master Chef": {"emoji": "🏆", "description": "Reached Level 20"}
    }
    
    # Display achievements in a grid
    cols = st.columns(3)
    for i, achievement in enumerate(achievements):
        col_idx = i % 3
        with cols[col_idx]:
            info = achievement_info.get(achievement, {"emoji": "🏅", "description": "Special achievement"})
            st.markdown(f"""
            <div style="
                border: 2px solid #FFD700;
                border-radius: 10px;
                padding: 15px;
                text-align: center;
                background: linear-gradient(135deg, #FFF8DC, #FFFACD);
                margin: 10px 0;
            ">
                <div style="font-size: 2em;">{info['emoji']}</div>
                <div style="font-weight: bold; color: #B8860B;">{achievement}</div>
                <div style="font-size: 0.8em; color: #696969;">{info['description']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Achievement progress
    st.markdown("### 🎯 Achievement Progress")
    
    # Calculate progress for various achievements
    quizzes_taken = stats.get('quizzes_taken', 0)
    perfect_scores = stats.get('perfect_scores', 0)
    current_level = stats.get('level', 1)
    
    # Quiz milestones
    quiz_milestones = [1, 5, 10, 25, 50]
    next_quiz_milestone = next((m for m in quiz_milestones if m > quizzes_taken), None)
    
    if next_quiz_milestone:
        progress = quizzes_taken / next_quiz_milestone
        st.progress(progress)
        st.markdown(f"**Next Quiz Milestone:** {quizzes_taken}/{next_quiz_milestone} quizzes completed")
    
    # Perfect score milestones
    perfect_milestones = [1, 5, 10]
    next_perfect_milestone = next((m for m in perfect_milestones if m > perfect_scores), None)
    
    if next_perfect_milestone:
        progress = perfect_scores / next_perfect_milestone
        st.progress(progress)
        st.markdown(f"**Next Perfect Score Milestone:** {perfect_scores}/{next_perfect_milestone} perfect scores")
    
    # Level milestones
    level_milestones = [5, 10, 15, 20]
    next_level_milestone = next((m for m in level_milestones if m > current_level), None)
    
    if next_level_milestone:
        progress = current_level / next_level_milestone
        st.progress(progress)
        st.markdown(f"**Next Level Milestone:** Level {current_level}/{next_level_milestone}")

def display_gamification_dashboard(user_id: str):
    """
    Display a comprehensive gamification dashboard.
    
    Args:
        user_id (str): User's unique ID
    """
    st.title("🎮 Gamification Dashboard")
    
    # Get user stats
    stats = get_user_stats(user_id)
    
    # Overview metrics
    st.markdown("## 📊 Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🌟 Level",
            value=stats['level'],
            delta=f"+{stats['total_xp']} XP"
        )
    
    with col2:
        st.metric(
            label="📝 Quizzes",
            value=stats['quizzes_taken'],
            delta=f"{stats['perfect_scores']} perfect"
        )
    
    with col3:
        accuracy = (stats['correct_answers'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0
        st.metric(
            label="🎯 Accuracy",
            value=f"{accuracy:.1f}%",
            delta=f"{stats['correct_answers']}/{stats['total_questions']}"
        )
    
    with col4:
        st.metric(
            label="🏆 Achievements",
            value=len(stats.get('achievements', [])),
            delta="unlocked"
        )
    
    # Tabs for different sections
    tab1, tab2, tab3 = st.tabs(["🏆 Achievements", "📈 Progress", "🥇 Leaderboard"])
    
    with tab1:
        display_achievements_showcase(user_id)
    
    with tab2:
        display_progress_tracking(user_id)
    
    with tab3:
        display_leaderboard()

def display_progress_tracking(user_id: str):
    """
    Display detailed progress tracking for the user.
    
    Args:
        user_id (str): User's unique ID
    """
    st.markdown("## 📈 Your Progress")
    
    stats = get_user_stats(user_id)
    
    # XP Progress
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress_percentage = (current_level_xp / xp_for_current_level * 100) if xp_for_current_level > 0 else 0
    
    st.markdown("### ⚡ XP Progress")
    st.progress(current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0)
    st.markdown(f"**Level {stats['level']}:** {current_level_xp}/{xp_for_current_level} XP ({progress_percentage:.1f}%)")
    st.markdown(f"**{xp_needed} XP needed for Level {stats['level'] + 1}**")
    
    # Performance metrics
    st.markdown("### 📊 Performance Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Quiz Performance:**")
        if stats['quizzes_taken'] > 0:
            perfect_rate = (stats['perfect_scores'] / stats['quizzes_taken']) * 100
            st.markdown(f"- Perfect Score Rate: {perfect_rate:.1f}%")
            st.markdown(f"- Average Accuracy: {(stats['correct_answers'] / stats['total_questions'] * 100):.1f}%")
            st.markdown(f"- Total Questions Answered: {stats['total_questions']}")
        else:
            st.markdown("- No quizzes taken yet")
    
    with col2:
        st.markdown("**Activity Summary:**")
        st.markdown(f"- Recipes Generated: {stats.get('recipes_generated', 0)}")
        st.markdown(f"- Days Active: {calculate_days_active(stats)}")
        st.markdown(f"- Last Quiz: {format_last_activity(stats.get('last_quiz_date'))}")
    
    # Weekly goals
    st.markdown("### 🎯 Weekly Goals")
    display_weekly_goals(stats)

def calculate_days_active(stats: Dict) -> int:
    """Calculate approximate days active based on user stats."""
    # Simple estimation based on activity
    base_days = max(1, stats.get('quizzes_taken', 0) // 2)
    return min(base_days, 30)  # Cap at 30 days for display

def format_last_activity(last_date) -> str:
    """Format the last activity date."""
    if not last_date:
        return "Never"
    
    # If it's a Firestore timestamp, convert it
    try:
        if hasattr(last_date, 'seconds'):
            last_date = datetime.fromtimestamp(last_date.seconds)
        
        days_ago = (datetime.now() - last_date).days
        if days_ago == 0:
            return "Today"
        elif days_ago == 1:
            return "Yesterday"
        else:
            return f"{days_ago} days ago"
    except:
        return "Unknown"

def display_weekly_goals(stats: Dict):
    """Display weekly goals and progress."""
    quizzes_this_week = min(stats.get('quizzes_taken', 0), 7)  # Simplified for demo
    recipes_this_week = min(stats.get('recipes_generated', 0), 5)  # Simplified for demo
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Quiz Goal (5/week):**")
        quiz_progress = min(quizzes_this_week / 5, 1.0)
        st.progress(quiz_progress)
        st.markdown(f"{quizzes_this_week}/5 quizzes completed")
    
    with col2:
        st.markdown("**Recipe Goal (3/week):**")
        recipe_progress = min(recipes_this_week / 3, 1.0)
        st.progress(recipe_progress)
        st.markdown(f"{recipes_this_week}/3 recipes generated")

def award_recipe_generation_xp(user_id: str, num_recipes: int = 1):
    """
    Award XP for recipe generation and show notification.
    
    Args:
        user_id (str): User's unique ID
        num_recipes (int): Number of recipes generated
    """
    updated_stats = award_recipe_xp(user_id, num_recipes)
    xp_earned = num_recipes * 5
    
    # Show success message
    st.success(f"🎉 Recipe generated! +{xp_earned} XP earned!")
    
    # Check for level up
    if 'level_up' in st.session_state and st.session_state.level_up:
        st.balloons()
        st.success(f"🎊 LEVEL UP! You're now Level {updated_stats['level']}!")
        st.session_state.level_up = False

def show_xp_notification(xp_earned: int, level_up: bool = False):
    """
    Show XP earned notification.
    
    Args:
        xp_earned (int): XP amount earned
        level_up (bool): Whether user leveled up
    """
    if level_up:
        st.balloons()
        st.success(f"🎊 LEVEL UP! +{xp_earned} XP earned!")
    else:
        st.success(f"⚡ +{xp_earned} XP earned!")

# Additional utility functions for enhanced gamification

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
    
    # Simple daily challenge selection (in real app, this would be more sophisticated)
    today_seed = datetime.now().strftime("%Y-%m-%d") + user_id
    random.seed(hash(today_seed))
    
    return random.choice(challenges)

def display_daily_challenge(user_id: str):
    """Display the daily challenge for the user."""
    challenge = get_daily_challenge(user_id)
    
    st.markdown("### 🎯 Daily Challenge")
    st.markdown(f"""
    <div style="
        border: 2px solid #4CAF50;
        border-radius: 10px;
        padding: 15px;
        background: linear-gradient(135deg, #E8F5E8, #F1F8E9);
        margin: 10px 0;
    ">
        <h4 style="color: #2E7D32; margin: 0;">{challenge['title']}</h4>
        <p style="margin: 5px 0;">{challenge['description']}</p>
        <p style="margin: 0; font-weight: bold; color: #4CAF50;">Reward: +{challenge['xp_reward']} XP</p>
    </div>
    """, unsafe_allow_html=True)
