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
