import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (  # Import UI functions
    leftover_input_csv, leftover_input_manual, leftover_input_firebase
)
from ui.components import (
    render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role
)
from ui.components import (  # Import gamification UI functions
    render_cooking_quiz, display_gamification_dashboard,
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
    role_access = {
        'user': [
            'Visual Menu Search',
            'Event Planning ChatBot',
            'Gamification Hub'
        ],
        'staff': [
            'Leftover Management',
            'Ingredients Management', 
            'Visual Menu Search',
            'Promotion Generator',
            'Gamification Hub',
            'Event Planning ChatBot'
        ],
        'chef': [
            'Leftover Management',
            'Chef Recipe Suggestions',
            'Ingredients Management',
            'Visual Menu Search',
            'Gamification Hub',
            'Event Planning ChatBot'
        ],
        'admin': [
            'Leftover Management',
            'Ingredients Management',
            'Promotion Generator',
            'Chef Recipe Suggestions',
            'Visual Menu Search',
            'Gamification Hub',
            'Event Planning ChatBot'
        ]
    }
    
    return feature_name in role_access.get(user_role, [])
    
def get_inaccessible_features_message(user_role):
    """Get message about features the user cannot access"""
    all_features = {
        'Leftover Management': 'Staff, Chef, and Admin only',
        'Ingredients Management': 'Staff, Chef, and Admin only', 
        'Promotion Generator': 'Staff and Admin only',
        'Chef Recipe Suggestions': 'Chef and Admin only',
        'Visual Menu Search': 'Available to all users',
        'Gamification Hub': 'Available to all users',
        'Event Planning ChatBot': 'Available to all users'
    }
    
    # Get features the current user cannot access
    inaccessible = []
    
    for feature, access_info in all_features.items():
        if not check_feature_access(feature):
            inaccessible.append(f"{feature} ({access_info})")
    
    if inaccessible:
        return "**Features you can't access:** " + ", ".join(inaccessible)
    else:
        return "**You have access to all features!**"

# Individual feature functions
@auth_required
def leftover_management():
    """Leftover management feature with step-by-step selection"""
    st.title("Leftover Management")

    # Initialize session state variables if they don't exist
    if 'leftover_method' not in st.session_state:
        st.session_state.leftover_method = None
    if 'all_leftovers' not in st.session_state:
        st.session_state.all_leftovers = []
    if 'detailed_ingredient_info' not in st.session_state:
        st.session_state.detailed_ingredient_info = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'recipe_generation_error' not in st.session_state:
        st.session_state.recipe_generation_error = None

    # Step 1: Method Selection
    if st.session_state.leftover_method is None:
        st.subheader("Choose Input Method")
        st.markdown("Select how you want to input your leftover ingredients:")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Manual Entry", use_container_width=True, type="primary"):
                st.session_state.leftover_method = "manual"
                st.rerun()
            st.markdown("Enter ingredients manually")
        
        with col2:
            if st.button("CSV Upload", use_container_width=True, type="primary"):
                st.session_state.leftover_method = "csv"
                st.rerun()
            st.markdown("Upload a CSV file with ingredients")
        
        with col3:
            if st.button("Firebase Inventory", use_container_width=True, type="primary"):
                st.session_state.leftover_method = "firebase"
                st.rerun()
            st.markdown("Use ingredients from your inventory")
    
    # Step 2: Input based on selected method
    else:
        # Back button
        if st.button("← Back to Method Selection"):
            st.session_state.leftover_method = None
            st.session_state.all_leftovers = []
            st.session_state.detailed_ingredient_info = []
            st.session_state.recipes = []
            st.rerun()
        
        st.subheader(f"Input Method: {st.session_state.leftover_method.title()}")
        
        # Handle different input methods
        if st.session_state.leftover_method == "manual":
            manual_input = st.text_area(
                "Enter ingredients (one per line or comma-separated)",
                placeholder="tomatoes\nonions\ngarlic\nrice\n\nOr: tomatoes, onions, garlic, rice",
                height=150
            )
            
            if st.button("Process Ingredients", type="primary"):
                if manual_input:
                    # Handle both line-separated and comma-separated input
                    if '\n' in manual_input:
                        ingredients = [ing.strip().lower() for ing in manual_input.split('\n') if ing.strip()]
                    else:
                        ingredients = [ing.strip().lower() for ing in manual_input.split(',') if ing.strip()]
                    
                    st.session_state.all_leftovers = ingredients
                    st.session_state.detailed_ingredient_info = []
                    st.success(f"Added {len(ingredients)} ingredients")
                else:
                    st.error("Please enter some ingredients")
        
        elif st.session_state.leftover_method == "csv":
            uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
            
            if uploaded_file is not None:
                try:
                    import pandas as pd
                    df = pd.read_csv(uploaded_file)
                    if 'ingredient' in df.columns:
                        ingredients = df['ingredient'].dropna().tolist()
                        ingredients = [ing.lower().strip() for ing in ingredients]
                        st.session_state.all_leftovers = ingredients
                        st.session_state.detailed_ingredient_info = []
                        st.success(f"Loaded {len(ingredients)} ingredients from CSV")
                    else:
                        st.error("CSV must have an 'ingredient' column")
                except Exception as e:
                    st.error(f"Error reading CSV: {str(e)}")
        
        elif st.session_state.leftover_method == "firebase":
            max_ingredients = st.slider(
                "Max ingredients to fetch", 
                min_value=5, 
                max_value=50, 
                value=20,
                help="Limit the number of ingredients to prioritize those expiring soon"
            )
            
            if st.button("Fetch Priority Ingredients", type="primary"):
                try:
                    from modules.leftover import get_ingredients_by_expiry_priority, fetch_ingredients_from_firebase
                    firebase_ingredients = fetch_ingredients_from_firebase()
                    ingredients, detailed_info = get_ingredients_by_expiry_priority(firebase_ingredients, max_ingredients)
                    
                    if ingredients:
                        st.session_state.all_leftovers = ingredients
                        st.session_state.detailed_ingredient_info = detailed_info
                        st.success(f"Fetched {len(ingredients)} priority ingredients")
                    else:
                        st.error("No ingredients found in Firebase inventory")
                except Exception as e:
                    st.error(f"Firebase error: {str(e)}")
                    logging.error(f"Firebase integration error: {str(e)}")
        
        # Step 3: Recipe Generation (if ingredients are loaded)
        if st.session_state.all_leftovers:
            st.markdown("---")
            st.subheader("Generate Recipes")
            
            # Display loaded ingredients
            with st.expander("Loaded Ingredients", expanded=False):
                if st.session_state.detailed_ingredient_info:
                    # Display Firebase ingredients with expiry info
                    for item in st.session_state.detailed_ingredient_info:
                        days_left = item['days_until_expiry']
                        
                        # Color code based on urgency
                        if days_left <= 1:
                            st.error(f"**{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                        elif days_left <= 3:
                            st.warning(f"**{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                        elif days_left <= 7:
                            st.success(f"**{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                        else:
                            st.info(f"**{item['name']}** - Expires: {item['expiry_date']} ({days_left} days left)")
                else:
                    # Display other ingredients in a compact format
                    cols = st.columns(3)
                    for i, ingredient in enumerate(st.session_state.all_leftovers):
                        col_idx = i % 3
                        with cols[col_idx]:
                            st.write(f"• {ingredient.title()}")
            
            # Recipe generation options
            col1, col2 = st.columns(2)
            
            with col1:
                num_suggestions = st.slider("Number of recipe suggestions", 
                                           min_value=1, 
                                           max_value=10, 
                                           value=3,
                                           help="Select how many recipe suggestions you want")
            
            with col2:
                notes = st.text_area("Additional notes or requirements", 
                                    placeholder="E.g., vegetarian only, quick meals, kid-friendly, etc.",
                                    help="Add any specific requirements for your recipes")
            
            # Generate recipes button
            if st.button("Generate Recipe Suggestions", type="primary", use_container_width=True):
                try:
                    with st.spinner("Generating recipes..."):
                        recipes = suggest_recipes(
                            st.session_state.all_leftovers, 
                            num_suggestions, 
                            notes, 
                            priority_ingredients=st.session_state.detailed_ingredient_info
                        )
                        
                        st.session_state.recipes = recipes
                        st.session_state.recipe_generation_error = None
                        
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
                st.subheader("Recipe Suggestions")
                for i, recipe in enumerate(st.session_state.recipes):
                    st.write(f"{i+1}. **{recipe}**")
                
                # Show which ingredients were prioritized
                if st.session_state.detailed_ingredient_info:
                    urgent_ingredients = [item['name'] for item in st.session_state.detailed_ingredient_info if item['days_until_expiry'] <= 3]
                    if urgent_ingredients:
                        st.info(f"These recipes prioritize ingredients expiring soon: {', '.join(urgent_ingredients)}")
                
                # Award XP for generating recipes - with error handling
                user = get_current_user()
                if user and user.get('user_id'):
                    try:
                        award_recipe_generation_xp(user['user_id'], len(st.session_state.recipes))
                    except Exception as e:
                        logging.error(f"Error awarding XP: {str(e)}")

@auth_required
def ingredients_management():
    """Ingredients management feature - CRUD operations for inventory"""
    if render_ingredient_management:
        render_ingredient_management()
    else:
        st.error("Ingredients management feature is not available. Please check the module installation.")

@auth_required
def gamification_hub():
    """Gamification hub feature"""
    user = get_current_user()
    if user and user.get('user_id'):
        try:
            display_gamification_dashboard(user['user_id'])
        except Exception as e:
            logging.error(f"Error displaying gamification dashboard: {str(e)}")
            st.error("Unable to load gamification dashboard")
            st.markdown("### 🎮 Gamification Hub")
            st.markdown("Your gamification stats are temporarily unavailable.")
    else:
        st.warning("Please log in to view your gamification stats")

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

    # Render authentication UI in sidebar - THIS WILL NOW CALL THE FIXED display_user_stats_sidebar
    auth_status = render_auth_ui()

    # Main content
    if not st.session_state.is_authenticated:
        st.title("Smart Restaurant Menu Management System")
        st.markdown('''
        Welcome to the AI-powered smart restaurant system! 
        
        **The current features are:**
        1. Leftover management: Generates recipes from the ingredients about to expire soon to minimize waste
        2. Menu generator: Menu generator with lots of customization options, to generate the menu for a whole week
        3. Event Planning: An AI powered chatbot assisting users plan their events and staff members execute them. 
        4. AI driven promotions generator: Generate high quality marketing campaigns with the help of AI
        5. Visual menu search & Personalized recipe recommender
        6. Full ingredient management & direct connection to Firestore 
        Please log in or register to access all features.
        ''')
        return

    # List of all available features
    all_features = [
        "Dashboard",
        "Ingredients Management",
        "Leftover Management",
        "Gamification Hub", 
        "Event Planning ChatBot",
        "Promotion Generator", 
        "Chef Recipe Suggestions",
        "Visual Menu Search"
    ]

    # Filter features based on user role
    available_features = ["Dashboard"] + [f for f in all_features[1:] if check_feature_access(f)]

    # Show inaccessible features message
    user = get_current_user()
    if user:
        inaccessible_message = get_inaccessible_features_message(user['role'])
        st.sidebar.markdown("---")
        st.sidebar.markdown(inaccessible_message)

    # Update session state with selected feature
    if 'selected_feature' in st.session_state:
        selected_feature = st.session_state.selected_feature
    else:
        selected_feature = "Dashboard"

    # Add feature descriptions in sidebar
    feature_description = get_feature_description(selected_feature)
    if feature_description:
        st.sidebar.info(feature_description)

    # UPDATED: Only show cooking quiz button when on Leftover Management page
    if selected_feature == "Leftover Management":
        st.sidebar.divider()
        if st.sidebar.button("Take Cooking Quiz", use_container_width=True, type="secondary"):
            st.session_state.show_cooking_quiz = True

    # Show cooking quiz if requested
    if st.session_state.get('show_cooking_quiz', False):
        st.title("Cooking Knowledge Quiz")
        user = get_current_user()
        if user and user.get('user_id'):
            # Sample ingredients for quiz generation
            sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
            
            try:
                # Display daily challenge
                display_daily_challenge(user['user_id'])
                
                # Render the cooking quiz
                render_cooking_quiz(sample_ingredients, user['user_id'])
            except Exception as e:
                logging.error(f"Error displaying cooking quiz: {str(e)}")
                st.error("Unable to load cooking quiz")
            
            # Back button
            if st.button("← Back to Dashboard"):
                st.session_state.show_cooking_quiz = False
                st.rerun()
        else:
            st.warning("Please log in to take quizzes")
        return

    # Display the selected feature
    if selected_feature == "Dashboard":
        dashboard()
    elif selected_feature == "Ingredients Management":
        ingredients_management()
    elif selected_feature == "Leftover Management":
        leftover_management()
    elif selected_feature == "Gamification Hub":
        gamification_hub()
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
