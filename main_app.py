import streamlit as st

st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (
    leftover_input_csv,
    leftover_input_manual,
    render_auth_ui,
    initialize_session_state,
    auth_required,
    get_current_user,
    is_user_role,
    # display_user_stats_sidebar,  # <-- Removed (function does not exist)
    render_cooking_quiz,
    display_gamification_dashboard,
    award_recipe_generation_xp,
    display_daily_challenge,
    show_xp_notification,
)

from modules.leftover import suggest_recipes, get_user_stats, award_recipe_xp
from firebase_init import init_firebase
from app_integration import integrate_event_planner, check_event_firebase_config

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def check_feature_access(feature_name):
    user = get_current_user()
    public_features = ["Event Planning ChatBot", "Gamification Hub", "Cooking Quiz"]
    staff_features = ["Leftover Management", "Promotion Generator"]
    chef_features = ["Chef Recipe Suggestions"]
    admin_features = ["Visual Menu Search"]
    if feature_name in public_features:
        return True
    if not user:
        return False
    if feature_name in staff_features and user['role'] in ['staff', 'manager', 'chef', 'admin']:
        return True
    if feature_name in chef_features and user['role'] in ['chef', 'admin']:
        return True
    if feature_name in admin_features and user['role'] in ['admin']:
        return True
    return False

@auth_required
def leftover_management():
    leftovers = leftover_input_csv()
    leftovers += leftover_input_manual()
    # display_leftover_summary(leftovers)  # Uncomment if you have this function
    # Add recipe suggestion or other logic here

@auth_required
def gamification_hub():
    st.write("Gamification Hub coming soon!")

@auth_required
def cooking_quiz():
    st.write("Cooking Quiz coming soon!")

@auth_required
def event_planning():
    integrate_event_planner()

def promotion_generator():
    st.write("Promotion Generator coming soon!")

def chef_recipe_suggestions():
    st.write("Chef Recipe Suggestions coming soon!")

def visual_menu_search():
    st.write("Visual Menu Search coming soon!")

def main():
    initialize_session_state()
    if 'show_quiz' not in st.session_state:
        st.session_state.show_quiz = False
    if 'show_general_quiz' not in st.session_state:
        st.session_state.show_general_quiz = False
    if 'show_achievements' not in st.session_state:
        st.session_state.show_achievements = False
    check_event_firebase_config()
    st.sidebar.title("🔐 Authentication")
    auth_status = render_auth_ui()
    user = get_current_user()
    # if user and user.get('user_id'):
    #     display_user_stats_sidebar(user['user_id'])  # <-- Remove or comment out

    st.title("🍽️ Smart Restaurant Menu Management System")

    if user:
        stats = get_user_stats(user['user_id']) if user.get('user_id') else {}
        level = stats.get('level', 1)
        total_xp = stats.get('total_xp', 0)
        st.markdown(f'''
        Welcome to the AI-powered smart restaurant system, **{user['username']}**! 🎉

        **Your Role:** {user['role'].capitalize()} | **Level:** {level} | **Total XP:** {total_xp}

        Select a feature from the sidebar to begin your culinary journey!
        ''')
        if user.get('user_id'):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🌟 Level", level)
            with col2:
                st.metric("⚡ Total XP", total_xp)
            with col3:
                st.metric("📝 Quizzes", stats.get('quizzes_taken', 0))
            with col4:
                st.metric("🏆 Achievements", len(stats.get('achievements', [])))
    else:
        st.markdown('''
        Welcome to the AI-powered smart restaurant system! 🍽️

        **Features include:**
        - 🧠 **Smart Recipe Generation** from leftover ingredients
        - 🎮 **Gamification System** with quizzes and achievements  
        - 🏆 **Leaderboards** to compete with other chefs
        - 📊 **Progress Tracking** and skill development
        - 🎉 **Event Planning** for special occasions

        Please log in or register to access all features.
        ''')

    st.sidebar.divider()
    st.sidebar.header("🚀 Features")
    features = [
        "Leftover Management",
        "Gamification Hub",
        "Cooking Quiz",
        "Event Planning ChatBot",
        "Promotion Generator",
        "Chef Recipe Suggestions",
        "Visual Menu Search"
    ]
    available_features = [f for f in features if check_feature_access(f)]
    if user:
        selected_feature = st.sidebar.selectbox(
            "Choose a Feature",
            options=available_features,
            help="Select a feature to explore different aspects of the restaurant management system"
        )
        feature_descriptions = {
            "Leftover Management": "♻️ Generate recipes from leftover ingredients",
            "Gamification Hub": "🎮 View achievements, leaderboard, and progress",
            "Cooking Quiz": "🧠 Test your culinary knowledge and earn XP",
            "Event Planning ChatBot": "🎉 Plan restaurant events and special occasions",
            "Promotion Generator": "📣 Create marketing promotions and campaigns",
            "Chef Recipe Suggestions": "👨‍🍳 Get professional recipe recommendations",
            "Visual Menu Search": "🔍 Search menu items using images"
        }
        if selected_feature in feature_descriptions:
            st.sidebar.info(feature_descriptions[selected_feature])
        st.divider()
        if selected_feature == "Leftover Management":
            leftover_management()
        elif selected_feature == "Gamification Hub":
            gamification_hub()
        elif selected_feature == "Cooking Quiz":
            cooking_quiz()
        elif selected_feature == "Event Planning ChatBot":
            event_planning()
        elif selected_feature == "Promotion Generator":
            promotion_generator()
        elif selected_feature == "Chef Recipe Suggestions":
            chef_recipe_suggestions()
        elif selected_feature == "Visual Menu Search":
            visual_menu_search()
    else:
        st.info("🔑 Please log in or register to unlock the full potential of our smart restaurant system!")
        st.markdown("### 🌟 What you can do:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **🧠 Smart Recipe Generation**
            - Upload leftover ingredients
            - Get AI-powered recipe suggestions
            - Reduce food waste effectively
            """)
            st.markdown("""
            **🎮 Gamification System**
            - Take cooking knowledge quizzes
            - Earn XP and level up
            - Unlock achievements
            """)
        with col2:
            st.markdown("""
            **🏆 Competition & Learning**
            - Compete on global leaderboards
            - Track your culinary progress
            - Learn from detailed explanations
            """)
            st.markdown("""
            **🎉 Event Planning**
            - Plan special restaurant events
            - Get AI-generated theme ideas
            - Send invites to customers
            """)

if __name__ == "__main__":
    main()
