import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (
    leftover_input_csv, leftover_input_manual, leftover_input_firebase
)
from ui.components import (
    render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role
)
from ui.components import (
    display_user_stats_sidebar, render_cooking_quiz, display_gamification_dashboard,
    award_recipe_generation_xp, display_daily_challenge, show_xp_notification
)
from modules.leftover import suggest_recipes
from modules.leftover import get_user_stats, award_recipe_xp
from firebase_init import init_firebase

from app_integration import integrate_event_planner, check_event_firebase_config
from dashboard import render_dashboard, get_feature_description

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def check_feature_access(feature_name):
    """Check if the current user has access to a specific feature"""
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
    """Simplified leftover management interface"""
    st.title("♻️ Leftover Management")

    if 'all_leftovers' not in st.session_state:
        st.session_state.all_leftovers = []
    if 'detailed_ingredient_info' not in st.session_state:
        st.session_state.detailed_ingredient_info = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'recipe_generation_error' not in st.session_state:
        st.session_state.recipe_generation_error = None

    # Simplified sidebar
    with st.sidebar:
        st.header("Add Ingredients")
        
        # Simplified input methods
        csv_leftovers = leftover_input_csv()
        manual_leftovers = leftover_input_manual()
        firebase_leftovers, firebase_detailed_info = leftover_input_firebase()

    all_leftovers = csv_leftovers + manual_leftovers + firebase_leftovers
    st.session_state.all_leftovers = all_leftovers
    st.session_state.detailed_ingredient_info = firebase_detailed_info

    if all_leftovers:
        # Clean ingredient display
        st.write(f"**{len(all_leftovers)} ingredients found**")
        
        if firebase_detailed_info:
            urgent_count = len([item for item in firebase_detailed_info if item['days_until_expiry'] <= 3])
            if urgent_count > 0:
                st.warning(f"⚠️ {urgent_count} ingredients expire soon")
        
        # Simplified ingredient list
        with st.expander("View Ingredients"):
            if firebase_detailed_info:
                for item in firebase_detailed_info:
                    days_left = item['days_until_expiry']
                    if days_left <= 1:
                        st.error(f"🔴 {item['name']} - {days_left} days left")
                    elif days_left <= 3:
                        st.warning(f"🟡 {item['name']} - {days_left} days left")
                    else:
                        st.info(f"🟢 {item['name']} - {days_left} days left")
            else:
                st.write(", ".join(all_leftovers))
        
        # Simplified recipe generation
        col1, col2 = st.columns([2, 1])
        with col1:
            notes = st.text_input("Requirements (optional)", placeholder="e.g., vegetarian, quick meals")
        with col2:
            num_suggestions = st.selectbox("Recipes", [1, 2, 3, 4, 5], index=2)
        
        if st.button("Generate Recipes", type="primary", use_container_width=True):
            try:
                with st.spinner("Generating recipes..."):
                    recipes = suggest_recipes(
                        all_leftovers, 
                        num_suggestions, 
                        notes, 
                        priority_ingredients=firebase_detailed_info
                    )
                    st.session_state.recipes = recipes
                    st.session_state.recipe_generation_error = None
            except Exception as e:
                st.session_state.recipe_generation_error = str(e)
        
        # Clean recipe display
        if st.session_state.recipe_generation_error:
            st.error(f"Error: {st.session_state.recipe_generation_error}")
        elif st.session_state.recipes:
            st.success("✨ Recipe Suggestions")
            for i, recipe in enumerate(st.session_state.recipes, 1):
                st.write(f"{i}. {recipe}")
            
            user = get_current_user()
            if user and user.get('user_id'):
                award_recipe_generation_xp(user['user_id'], len(st.session_state.recipes))
    else:
        st.info("Add ingredients using the sidebar to get started")

@auth_required
def gamification_hub():
    """Simplified gamification interface"""
    user = get_current_user()
    if user and user.get('user_id'):
        display_gamification_dashboard(user['user_id'])
    else:
        st.warning("Please log in to view stats")

@auth_required
def cooking_quiz():
    """Simplified quiz interface"""
    st.title("🧠 Cooking Quiz")

    user = get_current_user()
    if not user or not user.get('user_id'):
        st.warning("Please log in to take quizzes")
        return
        
    sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
    display_daily_challenge(user['user_id'])
    render_cooking_quiz(sample_ingredients, user['user_id'])

@auth_required
def event_planning():
    """Event planning interface"""
    integrate_event_planner()

def promotion_generator():
    """Simplified placeholder"""
    st.title("📣 Promotion Generator")
    st.info("Feature coming soon")

def chef_recipe_suggestions():
    """Simplified placeholder"""
    st.title("👨‍🍳 Chef Recipe Suggestions")
    st.info("Feature coming soon")

def visual_menu_search():
    """Simplified placeholder"""
    st.title("🔍 Visual Menu Search")
    st.info("Feature coming soon")

@auth_required
def dashboard():
    """Simplified dashboard"""
    render_dashboard()

def main():
    initialize_session_state()

    if 'show_quiz' not in st.session_state:
        st.session_state.show_quiz = False
    if 'show_general_quiz' not in st.session_state:
        st.session_state.show_general_quiz = False
    if 'show_achievements' not in st.session_state:
        st.session_state.show_achievements = False

    if 'selected_feature' not in st.session_state:
        st.session_state.selected_feature = "Dashboard"

    check_event_firebase_config()

    # Simplified sidebar
    with st.sidebar:
        st.title("🔐 Login")
        auth_status = render_auth_ui()

    if not st.session_state.is_authenticated:
        # Clean welcome screen
        st.title("🍽️ Smart Restaurant Management")
        st.markdown("""
        **AI-powered restaurant system with:**
        - Smart recipe generation from leftovers
        - Gamification with quizzes and achievements  
        - Event planning assistance
        - Progress tracking and leaderboards
        
        Please log in to access features.
        """)
        return

    # Simplified feature navigation
    with st.sidebar:
        st.divider()
        st.header("Features")

        features = [
            "Dashboard",
            "Leftover Management",
            "Gamification Hub", 
            "Cooking Quiz",
            "Event Planning ChatBot",
            "Promotion Generator", 
            "Chef Recipe Suggestions",
            "Visual Menu Search"
        ]

        available_features = ["Dashboard"] + [f for f in features[1:] if check_feature_access(f)]

        user = get_current_user()
        if user and user.get('user_id'):
            display_user_stats_sidebar(user['user_id'])

        selected_feature = st.selectbox(
            "Choose Feature",
            options=available_features,
            index=available_features.index(st.session_state.selected_feature) if st.session_state.selected_feature in available_features else 0
        )

        st.session_state.selected_feature = selected_feature

    # Feature routing
    if selected_feature == "Dashboard":
        dashboard()
    elif selected_feature == "Leftover Management":
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

if __name__ == "__main__":
    main()
