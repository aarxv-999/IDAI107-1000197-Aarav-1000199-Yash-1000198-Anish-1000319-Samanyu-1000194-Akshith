import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (  # Import UI functions
    leftover_input_csv, leftover_input_manual, leftover_input_firebase
)
from ui.components import (
    render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role
)
from ui.components import (  # Import gamification UI functions
    display_user_stats_sidebar, render_cooking_quiz, display_gamification_dashboard,
    award_recipe_generation_xp, display_daily_challenge, show_xp_notification
)
from modules.leftover import suggest_recipes  # Import logic functions
from modules.leftover import get_user_stats, award_recipe_xp  # Import gamification logic
from firebase_init import init_firebase

# Import the event planner integration
from app_integration import integrate_event_planner, check_event_firebase_config

# Import the dashboard module
from dashboard import render_dashboard, get_feature_description

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Page/feature access control
def check_feature_access(feature_name):
    """Check if the current user has access to a specific feature"""
    user = get_current_user()
    
    # Public features accessible to all authenticated users
    public_features = ["Event Planning ChatBot", "Gamification Hub", "Cooking Quiz"]
    
    # Staff/admin only features
    staff_features = ["Leftover Management", "Promotion Generator"]
    
    # Chef only features
    chef_features = ["Chef Recipe Suggestions"]
    
    # Admin only features
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

# Individual feature functions
@auth_required
def leftover_management():
    """Leftover management feature"""
    st.title("♻️ Leftover Management")
    
    # Sidebar for input methods
    st.sidebar.header("Input Methods")
    
    # Get leftovers from CSV, manual input, or Firebase
    csv_leftovers = leftover_input_csv()
    manual_leftovers = leftover_input_manual()
    firebase_leftovers = leftover_input_firebase()  # Add this line
    
    # Combine leftovers from all sources
    leftovers = csv_leftovers + manual_leftovers + firebase_leftovers  # Update this line
    
    # Main content
    if leftovers:
        st.write(f"Found {len(leftovers)} ingredients")
        
        # Display ingredients
        st.subheader("Available Ingredients")
        cols = st.columns(3)
        for i, ingredient in enumerate(leftovers):
            col_idx = i % 3
            with cols[col_idx]:
                st.info(ingredient.title())
        
        # Generate recipe button
        if st.button("Generate Recipe Suggestions", type="primary"):
            with st.spinner("Generating recipes..."):
                recipes = suggest_recipes(leftovers)
                
                if recipes:
                    st.success(f"Generated {len(recipes)} recipe suggestions!")
                    
                    # Display recipes
                    st.subheader("Recipe Suggestions")
                    for i, recipe in enumerate(recipes):
                        st.write(f"{i+1}. {recipe}")
                    
                    # Award XP for generating recipes
                    user = get_current_user()
                    if user and user.get('user_id'):
                        award_recipe_generation_xp(user['user_id'], len(recipes))
                else:
                    st.error("Could not generate recipes with these ingredients. Try adding more ingredients.")
    else:
        st.info("Please add ingredients using the sidebar options.")
        
        # Example section
        st.markdown("### How it works")
        st.markdown("""
        1. Add leftover ingredients using the sidebar
        2. Click 'Generate Recipe Suggestions'
        3. Get AI-powered recipe ideas that use your ingredients
        4. Reduce food waste and create delicious meals!
        """)
        
        # Example ingredients
        st.markdown("### Example Ingredients")
        example_ingredients = ["chicken", "rice", "bell peppers", "onions", "tomatoes", "garlic"]
        example_cols = st.columns(3)
        for i, ingredient in enumerate(example_ingredients):
            col_idx = i % 3
            with example_cols[col_idx]:
                st.markdown(f"• {ingredient.title()}")

@auth_required
def gamification_hub():
    """Gamification hub feature"""
    user = get_current_user()
    if user and user.get('user_id'):
        display_gamification_dashboard(user['user_id'])
    else:
        st.warning("Please log in to view your gamification stats")

@auth_required
def cooking_quiz():
    """Cooking quiz feature"""
    st.title("🧠 Cooking Knowledge Quiz")
    
    user = get_current_user()
    if not user or not user.get('user_id'):
        st.warning("Please log in to take quizzes")
        return
        
    # Sample ingredients for quiz generation
    sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
    
    # Display daily challenge
    display_daily_challenge(user['user_id'])
    
    # Render the cooking quiz
    render_cooking_quiz(sample_ingredients, user['user_id'])

@auth_required
def event_planning():
    """Event Planning ChatBot feature"""
    # Call the integrated event planner function
    integrate_event_planner()

def promotion_generator():
    """Promotion generator feature"""
    st.title("📣 Promotion Generator")
    st.info("This feature is coming soon!")

def chef_recipe_suggestions():
    """Chef recipe suggestions feature"""
    st.title("👨‍🍳 Chef Recipe Suggestions")
    st.info("This feature is coming soon!")

def visual_menu_search():
    """Visual menu search feature"""
    st.title("🔍 Visual Menu Search")
    st.info("This feature is coming soon!")

@auth_required
def dashboard():
    """Main dashboard feature"""
    render_dashboard()

# Main app function
def main():
    # Initialize Firebase and session state for authentication
    initialize_session_state()
    
    # Initialize gamification session state
    if 'show_quiz' not in st.session_state:
        st.session_state.show_quiz = False
    if 'show_general_quiz' not in st.session_state:
        st.session_state.show_general_quiz = False
    if 'show_achievements' not in st.session_state:
        st.session_state.show_achievements = False
    
    # Initialize selected feature state
    if 'selected_feature' not in st.session_state:
        st.session_state.selected_feature = "Dashboard"
    
    # Check Event Firebase configuration
    check_event_firebase_config()
    
    # Render authentication UI in sidebar
    st.sidebar.title("🔐 Authentication")
    auth_status = render_auth_ui()
    
    # Main content
    if not st.session_state.is_authenticated:
        st.title("🍽️ Smart Restaurant Menu Management System")
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
        return
    
    # Feature selection in sidebar
    st.sidebar.divider()
    st.sidebar.header("🚀 Features")
    
    # List of all available features with enhanced descriptions
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
    
    # Filter features based on user role
    available_features = ["Dashboard"] + [f for f in features[1:] if check_feature_access(f)]
    
    # Display user gamification stats in sidebar if authenticated
    user = get_current_user()
    if user and user.get('user_id'):
        display_user_stats_sidebar(user['user_id'])
    
    # Feature selection
    selected_feature = st.sidebar.selectbox(
        "Choose a Feature",
        options=available_features,
        index=available_features.index(st.session_state.selected_feature),
        help="Select a feature to explore different aspects of the restaurant management system"
    )
    
    # Update session state with selected feature
    st.session_state.selected_feature = selected_feature
    
    # Add feature descriptions in sidebar
    feature_description = get_feature_description(selected_feature)
    if feature_description:
        st.sidebar.info(feature_description)
    
    # Display the selected feature
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
