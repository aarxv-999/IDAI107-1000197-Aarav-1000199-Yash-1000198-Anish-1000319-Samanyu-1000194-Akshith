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

# Import the chef recipe components
from modules.chef_components import render_chef_recipe_suggestions

# Import the promotion generator components
from modules.promotion_components import render_promotion_generator

# Import the NEW visual menu components
from modules.visual_menu_components import render_visual_menu_search

# Import the notifications module
from modules.notifications import render_notifications_page

# Import the ingredients management module (your existing file)
try:
    from modules.ingredients_management import render_ingredient_management
except ImportError:
    # Fallback if the module is in a different location
    try:
        from ingredients_management import render_ingredient_management
    except ImportError:
        st.error("Ingredients management module not found. Please check the file location.")
        render_ingredient_management = None

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Updated feature access control based on new requirements
def check_feature_access(feature_name):
    """Check if the current user has access to a specific feature"""
    user = get_current_user()
    if not user:
        return False

    user_role = user['role']
    
    # Define feature access by role
    feature_access = {
        'Ingredients Management': ['admin', 'staff'],
        'Leftover Management': ['admin', 'chef', 'user'],
        'Promotion Generator': ['admin', 'staff'],
        'Chef Recipe Suggestions': ['admin', 'chef'],
        'Visual Menu Search': ['admin', 'chef', 'staff', 'user'],
        'Event Planning ChatBot': ['admin', 'chef', 'staff', 'user'],
        'Gamification Hub': ['admin', 'chef', 'staff', 'user']  # All authenticated users
    }
    
    return user_role in feature_access.get(feature_name, [])

def main():
    # Initialize session state
    initialize_session_state()
    
    # Render authentication UI in sidebar
    is_authenticated = render_auth_ui()
    
    if is_authenticated:
        user = get_current_user()
        
        # Display user stats in sidebar
        display_user_stats_sidebar(user['user_id'])
        
        # Check if notifications should be shown
        if st.session_state.get('show_notifications', False):
            render_notifications_page(user['user_id'])
            
            # Add back button
            if st.button("← Back to Dashboard", type="secondary"):
                st.session_state.show_notifications = False
                st.rerun()
            return
        
        # Main content area
        if 'selected_feature' not in st.session_state:
            st.session_state.selected_feature = None
        
        # Show dashboard if no feature is selected
        if st.session_state.selected_feature is None:
            render_dashboard()
        else:
            # Check feature access
            if not check_feature_access(st.session_state.selected_feature):
                st.error(f"Access denied. Your role ({user['role']}) does not have permission to access {st.session_state.selected_feature}.")
                if st.button("← Back to Dashboard"):
                    st.session_state.selected_feature = None
                    st.rerun()
                return
            
            # Render the selected feature
            render_selected_feature(st.session_state.selected_feature, user)
    else:
        # Show welcome page for non-authenticated users
        st.title("🍽️ Smart Restaurant Menu Management System")
        st.markdown("""
        Welcome to the Smart Restaurant Menu Management System! This comprehensive platform helps restaurants:
        
        - **Manage Ingredients** with AI-powered suggestions
        - **Reduce Food Waste** by generating recipes from leftovers
        - **Create Marketing Campaigns** with automated scoring
        - **Generate Chef Recipes** with AI assistance
        - **Search Menus Visually** using image recognition
        - **Plan Events** with intelligent chatbot assistance
        - **Track Progress** with gamification features
        
        Please log in or create an account to get started!
        """)

def render_selected_feature(feature_name, user):
    """Render the selected feature based on the feature name"""
    
    # Back to dashboard button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Dashboard", type="secondary"):
            st.session_state.selected_feature = None
            st.rerun()
    
    with col2:
        st.markdown(f"### {feature_name}")
        st.caption(get_feature_description(feature_name))
    
    st.divider()
    
    # Render the appropriate feature
    if feature_name == "Ingredients Management":
        if render_ingredient_management:
            render_ingredient_management()
        else:
            st.error("Ingredients management feature is not available.")
    
    elif feature_name == "Leftover Management":
        render_leftover_management(user)
    
    elif feature_name == "Promotion Generator":
        render_promotion_generator(user)
    
    elif feature_name == "Chef Recipe Suggestions":
        render_chef_recipe_suggestions(user)
    
    elif feature_name == "Visual Menu Search":
        render_visual_menu_search(user)
    
    elif feature_name == "Event Planning ChatBot":
        render_event_planning_chatbot(user)
    
    elif feature_name == "Gamification Hub":
        display_gamification_dashboard(user['user_id'])
    
    else:
        st.error(f"Feature '{feature_name}' is not implemented yet.")

def render_leftover_management(user):
    """Render the leftover management feature"""
    st.title("♻️ Leftover Management")
    st.markdown("Transform your leftover ingredients into delicious recipes and reduce food waste!")
    
    # Input methods in sidebar
    st.sidebar.title("Input Methods")
    
    # Get ingredients from different sources
    csv_ingredients = leftover_input_csv()
    manual_ingredients = leftover_input_manual()
    firebase_ingredients, detailed_info = leftover_input_firebase()
    
    # Combine all ingredients
    all_ingredients = []
    all_ingredients.extend(csv_ingredients)
    all_ingredients.extend(manual_ingredients)
    all_ingredients.extend(firebase_ingredients)
    
    # Remove duplicates while preserving order
    ingredients = list(dict.fromkeys(all_ingredients))
    
    if ingredients:
        st.success(f"Found {len(ingredients)} ingredients to work with!")
        
        # Display ingredients
        with st.expander("View Selected Ingredients", expanded=False):
            if detailed_info:
                # Show detailed Firebase info
                st.markdown("**Priority Ingredients (expiring soon):**")
                for info in detailed_info[:10]:  # Show top 10
                    expiry_date = info.get('expiry_date', 'Unknown')
                    days_left = info.get('days_until_expiry', 'Unknown')
                    st.write(f"• **{info['name']}** - Expires: {expiry_date} ({days_left} days)")
            else:
                # Show simple ingredient list
                cols = st.columns(3)
                for i, ingredient in enumerate(ingredients):
                    with cols[i % 3]:
                        st.write(f"• {ingredient.title()}")
        
        # Recipe generation section
        st.subheader("Recipe Generation")
        
        col1, col2 = st.columns(2)
        with col1:
            num_recipes = st.slider("Number of recipes to generate", 1, 10, 3)
        with col2:
            recipe_type = st.selectbox(
                "Recipe type preference",
                ["Any", "Vegetarian", "Vegan", "Quick (< 30 min)", "Healthy", "Comfort Food"]
            )
        
        # Advanced options
        with st.expander("Advanced Options"):
            dietary_restrictions = st.multiselect(
                "Dietary restrictions",
                ["Gluten-free", "Dairy-free", "Nut-free", "Low-sodium", "Low-carb"]
            )
            
            cooking_time = st.slider("Maximum cooking time (minutes)", 15, 180, 60)
            
            difficulty_level = st.selectbox(
                "Difficulty level",
                ["Any", "Beginner", "Intermediate", "Advanced"]
            )
        
        # Generate recipes button
        if st.button("🍳 Generate Recipes", type="primary", use_container_width=True):
            with st.spinner(f"Generating {num_recipes} recipes..."):
                try:
                    # Build preferences
                    preferences = {
                        'recipe_type': recipe_type,
                        'dietary_restrictions': dietary_restrictions,
                        'max_cooking_time': cooking_time,
                        'difficulty_level': difficulty_level
                    }
                    
                    # Generate recipes
                    recipes = suggest_recipes(ingredients, num_recipes, preferences)
                    
                    if recipes:
                        st.success(f"Generated {len(recipes)} recipes!")
                        
                        # Award XP for recipe generation
                        award_recipe_generation_xp(user['user_id'], len(recipes))
                        
                        # Display recipes
                        for i, recipe in enumerate(recipes, 1):
                            with st.expander(f"Recipe {i}: {recipe.get('name', 'Unnamed Recipe')}", expanded=i==1):
                                
                                # Recipe header
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Prep Time", recipe.get('prep_time', 'N/A'))
                                with col2:
                                    st.metric("Cook Time", recipe.get('cook_time', 'N/A'))
                                with col3:
                                    st.metric("Servings", recipe.get('servings', 'N/A'))
                                
                                # Ingredients
                                if recipe.get('ingredients'):
                                    st.markdown("**Ingredients:**")
                                    for ingredient in recipe['ingredients']:
                                        st.write(f"• {ingredient}")
                                
                                # Instructions
                                if recipe.get('instructions'):
                                    st.markdown("**Instructions:**")
                                    for j, instruction in enumerate(recipe['instructions'], 1):
                                        st.write(f"{j}. {instruction}")
                                
                                # Additional info
                                if recipe.get('tips'):
                                    st.markdown("**Tips:**")
                                    st.info(recipe['tips'])
                                
                                # Nutritional info if available
                                if recipe.get('nutrition'):
                                    st.markdown("**Nutritional Information:**")
                                    nutrition = recipe['nutrition']
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Calories", nutrition.get('calories', 'N/A'))
                                    with col2:
                                        st.metric("Protein", nutrition.get('protein', 'N/A'))
                                    with col3:
                                        st.metric("Carbs", nutrition.get('carbs', 'N/A'))
                                    with col4:
                                        st.metric("Fat", nutrition.get('fat', 'N/A'))
                    else:
                        st.error("Unable to generate recipes. Please try with different ingredients or preferences.")
                        
                except Exception as e:
                    st.error(f"Error generating recipes: {str(e)}")
                    logging.error(f"Recipe generation error: {str(e)}")
        
        # Cooking Quiz Section
        st.markdown("---")
        render_cooking_quiz(ingredients, user['user_id'])
        
        # Daily Challenge
        st.markdown("---")
        display_daily_challenge(user['user_id'])
        
    else:
        st.info("Please add some ingredients using the sidebar options to get started!")
        
        # Show sample ingredients for demo
        st.markdown("### Sample Ingredients")
        st.markdown("Try these sample ingredients to see how the system works:")
        
        sample_ingredients = ["tomatoes", "onions", "garlic", "rice", "chicken", "cheese"]
        if st.button("Use Sample Ingredients"):
            # Add sample ingredients to manual input (this is just for demo)
            st.info("Sample ingredients loaded! Use the manual input in the sidebar to try them out.")

def render_event_planning_chatbot(user):
    """Render the event planning chatbot feature"""
    st.title("🤖 Event Planning ChatBot")
    st.markdown("Get AI-powered assistance for planning your restaurant events!")
    
    # Check if event Firebase is configured
    if not check_event_firebase_config():
        st.error("Event planning feature is not properly configured. Please check the Firebase configuration.")
        return
    
    # Integrate the event planner
    integrate_event_planner(user)

if __name__ == "__main__":
    main()
