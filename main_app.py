"""
MAIN APP FILE for the Smart Restaurant Menu Management App
This combines all UI components and logic functions to create a complete Streamlit interface.
Enhanced with gamification system integration.
"""
import streamlit as st

# Set page config must be the first Streamlit command
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (  # Import UI functions
    leftover_input_csv, leftover_input_manual,
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
    st.subheader("♻️ Leftover Management")
    
    user = get_current_user()
    user_id = user['user_id'] if user else None
    
    # Show daily challenge at the top
    if user_id:
        display_daily_challenge(user_id)
        st.markdown("---")
    
    # Debug UI state
    leftovers_csv = leftover_input_csv()  # Input leftovers from CSV
    logging.info(f"Leftovers from CSV: {leftovers_csv}")
    
    leftovers_manual = leftover_input_manual()  # Input leftovers manually
    logging.info(f"Leftovers from manual entry: {leftovers_manual}")
    
    # Use the leftovers from either source
    leftovers = leftovers_csv or leftovers_manual  # Main leftovers based on user's choice
    logging.info(f"Final leftovers list: {leftovers}")
    
    if leftovers:
        st.success(f"Working with these ingredients: {', '.join(leftovers)}")
        
        # Add gamification elements
        col1, col2 = st.columns([2, 1])
        
        with col1:
            max_suggestions = st.slider("How many recipes do you want?", 1, 5, 3)
            logging.info(f"User requested {max_suggestions} recipes")
        
        with col2:
            if user_id:
                st.info("💡 Tip: Generate recipes to earn XP!")
        
        if st.button("Generate Recipes", type="primary"):
            with st.spinner("Generating recipe suggestions..."):
                try:
                    logging.info("Calling suggest_recipes function...")
                    suggestions = suggest_recipes(leftovers, max_suggestions)
                    logging.info(f"Received suggestions: {suggestions}")
                    
                    if suggestions and len(suggestions) > 0:
                        # Award XP for recipe generation
                        if user_id:
                            old_stats = get_user_stats(user_id)
                            old_level = old_stats['level']
                            
                            updated_stats = award_recipe_xp(user_id, len(suggestions))
                            new_level = updated_stats['level']
                            
                            # Show XP notification
                            xp_earned = len(suggestions) * 5
                            level_up = new_level > old_level
                            
                            if level_up:
                                st.balloons()
                                st.success(f"🎊 LEVEL UP! You're now Level {new_level}! +{xp_earned} XP earned!")
                            else:
                                st.success(f"⚡ +{xp_earned} XP earned for generating {len(suggestions)} recipes!")
                        
                        st.markdown("### 🍳 Recipe Suggestions:")
                        for i, recipe in enumerate(suggestions, 1):
                            with st.expander(f"Recipe {i}", expanded=True):
                                st.write(recipe)
                        
                        # Offer cooking quiz based on ingredients
                        if user_id and leftovers:
                            st.markdown("---")
                            st.markdown("### 🧠 Test Your Knowledge!")
                            st.info("Want to learn more about these ingredients? Take a cooking quiz to earn bonus XP!")
                            
                            if st.button("🎯 Start Cooking Quiz"):
                                st.session_state.show_quiz = True
                                st.session_state.quiz_ingredients = leftovers
                                st.rerun()
                    else:
                        st.warning("No recipes could be generated. Try different ingredients.")
                        logging.warning(f"No recipes returned for ingredients: {leftovers}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    logging.error(f"Error in recipe generation: {str(e)}")
        
        # Show cooking quiz if triggered
        if user_id and st.session_state.get('show_quiz', False):
            st.markdown("---")
            quiz_ingredients = st.session_state.get('quiz_ingredients', leftovers)
            render_cooking_quiz(quiz_ingredients, user_id)
            
            if st.button("🔙 Back to Recipe Generation"):
                st.session_state.show_quiz = False
                st.rerun()
    else:
        st.info("Please upload or enter some leftover ingredients to continue.")
        
        # Show some gamification motivation even without ingredients
        if user_id:
            st.markdown("---")
            st.markdown("### 🎮 While you're here...")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🧠 Take a General Cooking Quiz"):
                    st.session_state.show_general_quiz = True
                    st.rerun()
            
            with col2:
                if st.button("🏆 View Your Achievements"):
                    st.session_state.show_achievements = True
                    st.rerun()
        
        # Show general quiz or achievements if requested
        if user_id and st.session_state.get('show_general_quiz', False):
            st.markdown("---")
            # Use common cooking ingredients for general quiz
            general_ingredients = ["onion", "garlic", "tomato", "chicken", "rice"]
            render_cooking_quiz(general_ingredients, user_id)
            
            if st.button("🔙 Back"):
                st.session_state.show_general_quiz = False
                st.rerun()

@auth_required
def gamification_hub():
    """Main gamification dashboard and features"""
    st.subheader("🎮 Gamification Hub")
    
    user = get_current_user()
    user_id = user['user_id'] if user else None
    
    if not user_id:
        st.error("User ID not found. Please log in again.")
        return
    
    # Display the comprehensive gamification dashboard
    display_gamification_dashboard(user_id)

@auth_required
def cooking_quiz():
    """Standalone cooking quiz feature"""
    st.subheader("🧠 Cooking Knowledge Quiz")
    
    user = get_current_user()
    user_id = user['user_id'] if user else None
    
    if not user_id:
        st.error("User ID not found. Please log in again.")
        return
    
    # Quiz type selection
    quiz_type = st.radio(
        "Choose quiz type:",
        ["General Cooking Knowledge", "Ingredient-Based Quiz"]
    )
    
    if quiz_type == "General Cooking Knowledge":
        # Use common cooking ingredients
        ingredients = ["chicken", "beef", "vegetables", "herbs", "spices"]
        render_cooking_quiz(ingredients, user_id)
    
    else:
        # Let user input ingredients for custom quiz
        st.markdown("### Enter ingredients for a custom quiz:")
        
        # Manual ingredient input
        ingredient_input = st.text_input(
            "Enter ingredients (comma-separated):",
            placeholder="e.g., tomato, onion, garlic, chicken"
        )
        
        if ingredient_input:
            ingredients = [ing.strip() for ing in ingredient_input.split(',') if ing.strip()]
            
            if ingredients:
                st.success(f"Quiz will be based on: {', '.join(ingredients)}")
                render_cooking_quiz(ingredients, user_id)
            else:
                st.warning("Please enter valid ingredients.")

def event_planning():
    st.subheader("🎉 Event Planning ChatBot")
    st.write("This feature is coming soon!")
    # Placeholder for event planning feature

def promotion_generator():
    st.subheader("📣 Promotion Generator")
    st.write("This feature is coming soon!")
    # Placeholder for promotion generator feature

def chef_recipe_suggestions():
    st.subheader("👨‍🍳 Chef Recipe Suggestions")
    st.write("This feature is coming soon!")
    # Placeholder for chef recipe suggestions feature

def visual_menu_search():
    st.subheader("🔍 Visual Menu Search")
    st.write("This feature is coming soon!")
    # Placeholder for visual menu search feature

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
    
    # Render authentication UI in sidebar
    st.sidebar.title("🔐 Authentication")
    auth_status = render_auth_ui()
    
    # Display user gamification stats in sidebar if authenticated
    user = get_current_user()
    if user and user.get('user_id'):
        display_user_stats_sidebar(user['user_id'])
    
    # Main content
    st.title("🍽️ Smart Restaurant Menu Management System")
    
    # Welcome message based on authentication status
    if user:
        stats = get_user_stats(user['user_id']) if user.get('user_id') else {}
        level = stats.get('level', 1)
        total_xp = stats.get('total_xp', 0)
        
        st.markdown(f'''
        Welcome to the AI-powered smart restaurant system, **{user['username']}**! 🎉
        
        **Your Role:** {user['role'].capitalize()} | **Level:** {level} | **Total XP:** {total_xp}
        
        Select a feature from the sidebar to begin your culinary journey!
        ''')
        
        # Show quick stats
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
        
        Please log in or register to access all features.
        ''')
    
    # Feature selection in sidebar
    st.sidebar.divider()
    st.sidebar.header("🚀 Features")
    
    # List of all available features with enhanced descriptions
    features = [
        "Leftover Management",
        "Gamification Hub", 
        "Cooking Quiz",
        "Event Planning ChatBot",
        "Promotion Generator", 
        "Chef Recipe Suggestions",
        "Visual Menu Search"
    ]
    
    # Filter features based on user role
    available_features = [f for f in features if check_feature_access(f)]
    
    # Only show feature selection if user is authenticated
    if user:
        selected_feature = st.sidebar.selectbox(
            "Choose a Feature",
            options=available_features,
            help="Select a feature to explore different aspects of the restaurant management system"
        )
        
        # Add feature descriptions in sidebar
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
        
        # Display the selected feature
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
        # If not authenticated, show a motivational message
        st.info("🔑 Please log in or register to unlock the full potential of our smart restaurant system!")
        
        # Show some preview features
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
            **📊 Progress Tracking**
            - Monitor your cooking skills
            - Set and achieve weekly goals
            - Get personalized challenges
            """)

if __name__ == "__main__":
    main()
