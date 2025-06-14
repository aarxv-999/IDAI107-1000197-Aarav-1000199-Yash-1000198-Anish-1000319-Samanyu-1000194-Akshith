import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

# Import functions
from modules.leftover import (
    load_leftovers, parse_manual_leftovers, fetch_ingredients_from_firebase, 
    prioritize_ingredients, suggest_recipes, get_user_stats, award_recipe_xp
)

from ui.components import (
    render_auth_ui, initialize_session_state, auth_required, get_current_user,
    display_user_stats_sidebar, render_cooking_quiz, display_gamification_dashboard,
    display_daily_challenge
)

from firebase_init import init_firebase
from app_integration import integrate_event_planner, check_event_firebase_config
from dashboard import render_dashboard, get_feature_description

init_firebase()

import logging
logging.basicConfig(level=logging.INFO)

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
    st.title("♻️ Leftover Management")
    
    # Initialize session state
    if 'all_leftovers' not in st.session_state:
        st.session_state.all_leftovers = []
    if 'firebase_ingredients_data' not in st.session_state:
        st.session_state.firebase_ingredients_data = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'recipe_generation_error' not in st.session_state:
        st.session_state.recipe_generation_error = None
    
    # Sidebar inputs
    st.sidebar.header("Add Ingredients")
    
    # CSV Upload
    st.sidebar.subheader("📄 CSV Upload")
    csv_leftovers = []
    uploaded_file = st.sidebar.file_uploader("Choose CSV file", type=["csv"])
    if uploaded_file is not None:
        try:
            csv_leftovers = load_leftovers(uploaded_file)
            st.sidebar.success(f"✅ {len(csv_leftovers)} ingredients")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
    
    # Manual Entry
    st.sidebar.subheader("✏️ Manual Entry")
    manual_leftovers = []
    ingredients_text = st.sidebar.text_area("Enter ingredients (comma-separated)", 
                                           placeholder="tomatoes, onions, chicken")
    if ingredients_text:
        manual_leftovers = parse_manual_leftovers(ingredients_text)
        st.sidebar.success(f"✅ {len(manual_leftovers)} ingredients")
    
    # Firebase
    st.sidebar.subheader("🔥 Firebase")
    firebase_leftovers = []
    if st.sidebar.button("Fetch Ingredients", type="primary"):
        try:
            with st.spinner("Fetching..."):
                raw_ingredients = fetch_ingredients_from_firebase()
                prioritized_data = prioritize_ingredients(raw_ingredients)
                st.session_state.firebase_ingredients_data = prioritized_data
                firebase_leftovers = [item['ingredient'] for item in prioritized_data]
                st.sidebar.success(f"✅ {len(firebase_leftovers)} ingredients")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
    else:
        firebase_leftovers = [item['ingredient'] for item in st.session_state.firebase_ingredients_data]
    
    # Combine all ingredients
    all_leftovers = csv_leftovers + manual_leftovers + firebase_leftovers
    st.session_state.all_leftovers = all_leftovers
    
    # Main content
    if all_leftovers:
        st.success(f"Found {len(all_leftovers)} ingredients")
        
        # Show ingredients
        with st.expander("View Ingredients", expanded=False):
            cols = st.columns(3)
            for i, ingredient in enumerate(all_leftovers):
                col_idx = i % 3
                with cols[col_idx]:
                    st.write(f"• {ingredient.title()}")
        
        # Recipe generation
        col1, col2 = st.columns(2)
        with col1:
            num_suggestions = st.slider("Number of recipes", 1, 10, 3)
        with col2:
            notes = st.text_area("Requirements", placeholder="vegetarian, quick meals, etc.")
        
        # Generate button
        if st.button("🚀 Generate Recipes", type="primary", use_container_width=True):
            try:
                with st.spinner("Generating recipes..."):
                    recipes = suggest_recipes(
                        leftovers=all_leftovers,
                        max_suggestions=num_suggestions,
                        notes=notes,
                        prioritized_ingredients=st.session_state.firebase_ingredients_data
                    )
                    st.session_state.recipes = recipes
                    st.session_state.recipe_generation_error = None
            except Exception as e:
                st.session_state.recipe_generation_error = str(e)
        
        # Display results
        if st.session_state.recipe_generation_error:
            st.error(f"❌ Error: {st.session_state.recipe_generation_error}")
        elif st.session_state.recipes:
            st.success(f"🎉 Generated {len(st.session_state.recipes)} recipes!")
            
            # Show priority info only when recipes are generated
            if st.session_state.firebase_ingredients_data:
                high_priority = [item for item in st.session_state.firebase_ingredients_data if item['priority'] <= 2]
                if high_priority:
                    priority_names = [item['ingredient'] for item in high_priority]
                    st.info(f"🔥 Prioritized: {', '.join(priority_names)} (expiring soon)")
            
            # Display recipes
            st.subheader("Recipe Suggestions")
            for i, recipe in enumerate(st.session_state.recipes):
                st.write(f"**{i+1}.** {recipe}")
            
            # Award XP
            user = get_current_user()
            if user and user.get('user_id'):
                try:
                    award_recipe_xp(user['user_id'], len(st.session_state.recipes))
                    st.success(f"🎮 +{len(st.session_state.recipes) * 5} XP earned!")
                except Exception as e:
                    logging.error(f"XP error: {str(e)}")
    else:
        st.info("Add ingredients using the sidebar to get started.")

@auth_required
def gamification_hub():
    user = get_current_user()
    if user and user.get('user_id'):
        display_gamification_dashboard(user['user_id'])
    else:
        st.warning("Please log in to view stats")

@auth_required
def cooking_quiz():
    st.title("🧠 Cooking Quiz")
    user = get_current_user()
    if not user or not user.get('user_id'):
        st.warning("Please log in to take quizzes")
        return
    sample_ingredients = ["chicken", "rice", "tomatoes", "onions"]
    display_daily_challenge(user['user_id'])
    render_cooking_quiz(sample_ingredients, user['user_id'])

@auth_required
def event_planning():
    integrate_event_planner()

def promotion_generator():
    st.title("📣 Promotion Generator")
    st.info("Coming soon!")

def chef_recipe_suggestions():
    st.title("👨‍🍳 Chef Recipes")
    st.info("Coming soon!")

def visual_menu_search():
    st.title("🔍 Visual Search")
    st.info("Coming soon!")

@auth_required
def dashboard():
    render_dashboard()

def main():
    initialize_session_state()
    
    if 'selected_feature' not in st.session_state:
        st.session_state.selected_feature = "Dashboard"
    
    check_event_firebase_config()
    
    # Auth UI
    st.sidebar.title("🔐 Authentication")
    render_auth_ui()
    
    if not st.session_state.is_authenticated:
        st.title("🍽️ Smart Restaurant Management")
        st.markdown("Please log in to access features.")
        return
    
    # Feature selection
    st.sidebar.divider()
    st.sidebar.header("🚀 Features")
    
    features = [
        "Dashboard", "Leftover Management", "Gamification Hub", 
        "Cooking Quiz", "Event Planning ChatBot", "Promotion Generator", 
        "Chef Recipe Suggestions", "Visual Menu Search"
    ]
    
    available_features = ["Dashboard"] + [f for f in features[1:] if check_feature_access(f)]
    
    user = get_current_user()
    if user and user.get('user_id'):
        display_user_stats_sidebar(user['user_id'])
    
    selected_feature = st.sidebar.selectbox("Choose Feature", available_features)
    st.session_state.selected_feature = selected_feature
    
    # Display feature
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

print("✅ Minimalistic app loaded!")
