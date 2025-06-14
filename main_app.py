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

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Page/feature access control
def check_feature_access(feature_name):
    """Check if the current user has access to a specific feature"""
    user = get_current_user()

    # Public features accessible to all authenticated users
    public_features = ["Event Planning ChatBot", "Gamification Hub", "Cooking Quiz", "Visual Menu Search"]

    # Staff/admin only features
    staff_admin_features = ["Leftover Management", "Promotion Generator"]

    # Chef/admin features
    chef_features = ["Chef Recipe Suggestions"]

    # Admin only features (none currently, but keeping structure)
    admin_features = []

    if feature_name in public_features:
        return True

    if not user:
        return False
        
    if feature_name in staff_admin_features and user['role'] in ['staff', 'admin']:
        return True
        
    if feature_name in chef_features and user['role'] in ['chef', 'admin']:
        return True
        
    if feature_name in admin_features and user['role'] in ['admin']:
        return True
        
    return False

# Individual feature functions
@auth_required
def leftover_management():
    """Leftover management feature with automatic Firebase integration"""
    st.title("♻️ Leftover Management")

    # Initialize session state variables if they don't exist
    if 'all_leftovers' not in st.session_state:
        st.session_state.all_leftovers = []
    if 'detailed_ingredient_info' not in st.session_state:
        st.session_state.detailed_ingredient_info = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'recipe_generation_error' not in st.session_state:
        st.session_state.recipe_generation_error = None

    # Sidebar for input methods
    st.sidebar.header("Input Methods")

    # Get leftovers from CSV, manual input, or Firebase
    csv_leftovers = leftover_input_csv()
    manual_leftovers = leftover_input_manual()
    firebase_leftovers, firebase_detailed_info = leftover_input_firebase()

    # Combine leftovers from all sources
    all_leftovers = csv_leftovers + manual_leftovers + firebase_leftovers

    # Store in session state
    st.session_state.all_leftovers = all_leftovers
    st.session_state.detailed_ingredient_info = firebase_detailed_info

    # Main content
    if all_leftovers:
        st.write(f"Found {len(all_leftovers)} ingredients")
        
        # Display priority information if Firebase ingredients are used
        if firebase_detailed_info:
            st.info("🎯 Ingredients are prioritized by expiry date - closest to expire first!")
            
            # Show urgency summary
            urgent_count = len([item for item in firebase_detailed_info if item['days_until_expiry'] <= 3])
            if urgent_count > 0:
                st.warning(f"⚠️ {urgent_count} ingredients expire within 3 days - recipes will prioritize these!")
        
        # Create a dropdown for ingredients with expiry info
        with st.expander("Available Ingredients", expanded=False):
            if firebase_detailed_info:
                # Display Firebase ingredients with expiry info
                for item in firebase_detailed_info:
                    days_left = item['days_until_expiry']
                    
                    # Color code based on urgency
                    if days_left <= 1:
                        st.error(f"🔴 **{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                    elif days_left <= 3:
                        st.warning(f"🟡 **{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                    elif days_left <= 7:
                        st.success(f"🟢 **{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                    else:
                        st.info(f"⚪ **{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
            else:
                # Display other ingredients in a compact format
                cols = st.columns(3)
                for i, ingredient in enumerate(all_leftovers):
                    col_idx = i % 3
                    with cols[col_idx]:
                        st.write(f"• {ingredient.title()}")
        
        # Recipe generation options
        st.subheader("Recipe Generation Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Number of recipe suggestions
            num_suggestions = st.slider("Number of recipe suggestions", 
                                       min_value=1, 
                                       max_value=10, 
                                       value=3,
                                       help="Select how many recipe suggestions you want")
        
        with col2:
            # Additional notes or requirements
            notes = st.text_area("Additional notes or requirements", 
                                placeholder="E.g., vegetarian only, quick meals, kid-friendly, etc.",
                                help="Add any specific requirements for your recipes")
        
        # Auto-generate recipes for Firebase ingredients or manual generation
        if firebase_leftovers and firebase_detailed_info:
            # Automatic generation for Firebase ingredients
            st.info("🤖 Ready to generate recipes using your inventory ingredients!")
            
            # Show auto-generate button
            if st.button("🚀 Generate Smart Recipes", type="primary", use_container_width=True):
                try:
                    with st.spinner("Generating recipes based on expiry priority..."):
                        # Call the suggest_recipes function with priority information
                        recipes = suggest_recipes(
                            all_leftovers, 
                            num_suggestions, 
                            notes, 
                            priority_ingredients=firebase_detailed_info
                        )
                        
                        # Store results in session state
                        st.session_state.recipes = recipes
                        st.session_state.recipe_generation_error = None
                        
                        # Log for debugging
                        logging.info(f"Generated {len(recipes)} recipes with priority ingredients")
                except Exception as e:
                    st.session_state.recipe_generation_error = str(e)
                    logging.error(f"Recipe generation error: {str(e)}")
        else:
            # Manual generation for other ingredients
            with st.form(key="recipe_form"):
                submit_button = st.form_submit_button(label="Generate Recipe Suggestions", type="primary")
                
                if submit_button:
                    try:
                        with st.spinner("Generating recipes..."):
                            # Call the suggest_recipes function
                            recipes = suggest_recipes(all_leftovers, num_suggestions, notes)
                            
                            # Store results in session state
                            st.session_state.recipes = recipes
                            st.session_state.recipe_generation_error = None
                            
                            # Log for debugging
                            logging.info(f"Generated {len(recipes)} recipes")
                    except Exception as e:
                        st.session_state.recipe_generation_error = str(e)
                        logging.error(f"Recipe generation error: {str(e)}")
        
        # Display recipes or error message
        if st.session_state.recipe_generation_error:
            st.error(f"Error generating recipes: {st.session_state.recipe_generation_error}")
        elif st.session_state.recipes:
            st.success(f"Generated {len(st.session_state.recipes)} recipe suggestions!")
            
            # Display recipes
            st.subheader("🍽️ Recipe Suggestions")
            for i, recipe in enumerate(st.session_state.recipes):
                st.write(f"{i+1}. **{recipe}**")
            
            # Show which ingredients were prioritized
            if firebase_detailed_info:
                urgent_ingredients = [item['name'] for item in firebase_detailed_info if item['days_until_expiry'] <= 3]
                if urgent_ingredients:
                    st.info(f"✨ These recipes prioritize ingredients expiring soon: {', '.join(urgent_ingredients)}")
            
            # Award XP for generating recipes
            user = get_current_user()
            if user and user.get('user_id'):
                award_recipe_generation_xp(user['user_id'], len(st.session_state.recipes))
    else:
        st.info("Please add ingredients using the sidebar options.")
        
        # Example section
        st.markdown("### How it works")
        st.markdown("""
        1. **Firebase Integration**: Automatically fetch ingredients from your inventory, sorted by expiry date
        2. **Smart Prioritization**: Ingredients closest to expiry are prioritized in recipe suggestions
        3. **AI-Powered Recipes**: Get personalized recipe ideas that reduce food waste
        4. **Manual Options**: Also supports CSV upload and manual ingredient entry
        """)
        
        # Example ingredients
        st.markdown("### Example Workflow")
        st.markdown("""
        1. ✅ Check "Use current inventory from Firebase"
        2. 🎯 Select max ingredients to use (prioritized by expiry)
        3. 📥 Click "Fetch Priority Ingredients"
        4. 🚀 Click "Generate Smart Recipes"
        5. 🍽️ Get recipes that use ingredients expiring soonest!
        """)

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

@auth_required
def promotion_generator():
    """Promotion generator feature"""
    render_promotion_generator()

@auth_required
def chef_recipe_suggestions():
    """Chef recipe suggestions feature"""
    render_chef_recipe_suggestions()

@auth_required
def visual_menu_search():
    """Visual menu search feature - UPDATED with full functionality"""
    render_visual_menu_search()

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
        - 🎯 **Expiry-Based Prioritization** to reduce food waste
        - 🎮 **Gamification System** with quizzes and achievements  
        - 🏆 **Leaderboards** to compete with other chefs
        - 📊 **Progress Tracking** and skill development
        - 🎉 **Event Planning** for special occasions
        - 👨‍🍳 **Chef Recipe Management** with AI-powered menu generation
        - 📣 **Marketing Campaign Generator** for promotions
        - 📷 **Visual Menu Search** with AI dish detection
        
        Please log in or register to access all features.
        ''')
        return

    # Feature selection in sidebar
    st.sidebar.divider()
    st.sidebar.header("🚀 Features")

    # List of all available features
    features = [
        "Dashboard",
        "Leftover Management",
        "Gamification Hub", 
        "Cooking Quiz",
        "Event Planning ChatBot",
        "Promotion Generator", 
        "Chef Recipe Suggestions",
        "Visual Menu Search"  # Updated feature name
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
        index=available_features.index(st.session_state.selected_feature) if st.session_state.selected_feature in available_features else 0,
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
        visual_menu_search()  # Updated to call new integrated function

if __name__ == "__main__":
    main()
