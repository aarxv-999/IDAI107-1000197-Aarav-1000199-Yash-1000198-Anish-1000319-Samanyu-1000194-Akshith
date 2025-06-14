"""
Combined UI Components for the Smart Restaurant Menu Management App.

Includes:
- Authentication UI (from auth_components.py)
- Main UI Components (from components.py)
- Gamification UI (from leftover_gamification_ui.py)
"""

import streamlit as st
from typing import List, Dict, Any, Tuple, Optional
import logging
import time
from datetime import datetime
import re

from modules.auth import register_user, authenticate_user
from firebase_init import init_firebase
from modules.leftover import (
    load_leftovers, parse_manual_leftovers, suggest_recipes,
    generate_dynamic_quiz_questions, calculate_quiz_score, get_user_stats,
    update_user_stats, get_leaderboard, get_xp_progress, award_recipe_xp,
    fetch_ingredients_from_firebase, parse_firebase_ingredients,
    get_ingredients_by_expiry_priority
)

logger = logging.getLogger(__name__)

# =======================
# AUTHENTICATION UI
# =======================

def initialize_session_state():
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
    if 'auth_mode' not in st.session_state:
        st.session_state.auth_mode = 'login'
    if 'firebase_initialized' not in st.session_state:
        st.session_state.firebase_initialized = init_firebase()

def switch_to_register():
    st.session_state.auth_mode = 'register'

def switch_to_login():
    st.session_state.auth_mode = 'login'

def logout_user():
    st.session_state.user = None
    st.session_state.is_authenticated = False
    st.session_state.auth_mode = 'login'
    st.success("You have been logged out successfully!")
    st.rerun()

def login_form() -> bool:
    st.markdown("""
    <style>
    .auth-container {max-width: 500px; margin: 0 auto; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);}
    .auth-title {text-align: center; font-size: 2rem; margin-bottom: 0.5rem; color: #ffffff;}
    .auth-subtitle {text-align: center; margin-bottom: 2rem; color: #cccccc;}
    .stTextInput > div > div > input {background-color: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: white; padding: 12px;}
    .stTextInput > div > div > input:focus {border-color: rgba(255,255,255,0.4); box-shadow: 0 0 0 2px rgba(255,255,255,0.1);}
    .auth-switch-text {text-align: center; margin-top: 1.5rem; color: #cccccc;}
    </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="auth-title">🔐 Welcome Back!</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Please sign in to your account</p>', unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            username_or_email = st.text_input("Username or Email", placeholder="Enter your username or email", help="You can use either your username or email address")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("🚀 Login", use_container_width=True)
            if submitted:
                if not username_or_email or not password:
                    st.error("⚠️ Please fill all fields!")
                    return False
                with st.spinner("Signing you in..."):
                    success, user_data, message = authenticate_user(username_or_email, password)
                    if success:
                        st.session_state.user = user_data
                        st.session_state.is_authenticated = True
                        st.success(f"🎉 Welcome back, {user_data['username']}!")
                        st.balloons()
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        st.markdown('<div class="auth-switch-text">Don\'t have an account?</div>', unsafe_allow_html=True)
        if st.button("📝 Create New Account", use_container_width=True, key="switch_to_register"):
            switch_to_register()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    return False

def registration_form() -> bool:
    st.markdown("""
    <style>
    .auth-container {max-width: 500px; margin: 0 auto; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);}
    .auth-title {text-align: center; font-size: 2rem; margin-bottom: 0.5rem; color: #ffffff;}
    .auth-subtitle {text-align: center; margin-bottom: 2rem; color: #cccccc;}
    .stTextInput > div > div > input {background-color: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: white; padding: 12px;}
    .stTextInput > div > div > input:focus {border-color: rgba(255,255,255,0.4); box-shadow: 0 0 0 2px rgba(255,255,255,0.1);}
    .auth-switch-text {text-align: center; margin-top: 1.5rem; color: #cccccc;}
    .section-header { color: #ffffff; font-weight: 600; margin: 1rem 0 0.5rem 0;}
    </style>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        st.markdown('<h2 class="auth-title">📝 Create Your Account</h2>', unsafe_allow_html=True)
        st.markdown('<p class="auth-subtitle">Join our restaurant management system</p>', unsafe_allow_html=True)
        with st.form("registration_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Choose a unique username", help="Your username must be unique")
            email = st.text_input("Email", placeholder="your.email@example.com", help="We'll use this for account recovery")
            password = st.text_input("Password", type="password", placeholder="Create a strong password", help="Password must be at least 5 characters with uppercase letters and numbers")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password")
            st.markdown('<p class="section-header">Account Type:</p>', unsafe_allow_html=True)
            is_staff = st.checkbox("🏢 I'm restaurant staff", help="Check this if you work at the restaurant")
            role = "user"
            staff_code = ""
            if is_staff:
                role_options = {
                    "staff": "👥 Staff Member",
                    "chef": "👨‍🍳 Chef",
                    "admin": "⚡ Administrator"
                }
                role = st.selectbox("Select your role:", list(role_options.keys()), format_func=lambda x: role_options[x])
                staff_code = st.text_input("Staff Registration Code", type="password", placeholder="Enter staff code", help="Contact your manager for the registration code")
            submitted = st.form_submit_button("🎯 Create Account", use_container_width=True)
            if submitted:
                if not username or not email or not password or not confirm_password:
                    st.error("⚠️ Please fill all required fields!")
                    return False
                if password != confirm_password:
                    st.error("🔐 Passwords do not match!")
                    return False
                if is_staff and staff_code != "staffcode123":
                    st.error("🚫 Invalid staff registration code!")
                    role = "user"
                with st.spinner("Creating your account..."):
                    success, message = register_user(username, email, password, role)
                    if success:
                        st.success(f"🎉 {message}")
                        st.info("✅ Account created successfully! Please log in with your new credentials.")
                        st.balloons()
                        st.session_state.auth_mode = 'login'
                        st.rerun()
                        return True
                    else:
                        st.error(f"❌ {message}")
                        return False
        st.markdown('<div class="auth-switch-text">Already have an account?</div>', unsafe_allow_html=True)
        if st.button("🔐 Sign In Instead", use_container_width=True, key="switch_to_login"):
            switch_to_login()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    return False

def user_profile():
    if st.session_state.is_authenticated and st.session_state.user:
        user = st.session_state.user
        with st.sidebar.container():
            st.markdown("### 👤 User Profile")
            st.markdown(f"**Welcome back!**  \n🏷️ **Name:** {user['username']}  \n🎭 **Role:** {user['role'].capitalize()}  ")
            role_badges = {
                'admin': '⚡ Administrator',
                'chef': '👨‍🍳 Chef',
                'staff': '👥 Staff Member',
                'user': '🙂 Customer'
            }
            if user['role'] in role_badges:
                st.markdown(f"*{role_badges[user['role']]}*")
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True, type="secondary"):
                logout_user()

def auth_required(func):
    def wrapper(*args, **kwargs):
        initialize_session_state()
        if st.session_state.is_authenticated:
            return func(*args, **kwargs)
        else:
            st.warning("🔒 You need to be logged in to access this feature.")
            if st.session_state.auth_mode == 'login':
                login_form()
            else:
                registration_form()
            return None
    return wrapper

def render_auth_ui():
    initialize_session_state()
    if st.session_state.is_authenticated:
        user_profile()
        return True
    if st.session_state.auth_mode == 'login':
        return login_form()
    else:
        return registration_form()

def get_current_user() -> Optional[Dict]:
    if st.session_state.is_authenticated and st.session_state.user:
        return st.session_state.user
    return None

def is_user_role(required_role: str) -> bool:
    user = get_current_user()
    return bool(user and user['role'] == required_role)

def show_auth_status():
    if st.session_state.is_authenticated:
        user = get_current_user()
        st.sidebar.success(f"✅ Signed in as {user['username']}")
    else:
        st.sidebar.info("ℹ️ Please sign in to continue")

def create_auth_tabs():
    initialize_session_state()
    if not st.session_state.is_authenticated:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        with tab1:
            login_form()
        with tab2:
            registration_form()
    else:
        user_profile()

# =======================
# MAIN UI COMPONENTS
# =======================

def leftover_input_csv() -> List[str]:
    st.sidebar.subheader("CSV Upload")
    use_csv = st.sidebar.checkbox("Upload from CSV file")
    leftovers = []
    if use_csv:
        uploaded_file = st.sidebar.file_uploader("Choose CSV file", type=["csv"], help="CSV should contain a column with ingredient names")
        if uploaded_file is not None:
            try:
                leftovers = load_leftovers(uploaded_file)
                st.sidebar.success(f"Loaded {len(leftovers)} ingredients")
            except Exception as err:
                st.sidebar.error(f"Error loading CSV: {str(err)}")
                st.sidebar.info("Please check your CSV format")
    return leftovers

def leftover_input_manual() -> List[str]:
    st.sidebar.subheader("Manual Entry")
    ingredients_text = st.sidebar.text_area("Enter ingredients (comma-separated)", placeholder="tomatoes, onions, chicken, rice", help="Separate ingredients with commas")
    leftovers = []
    if ingredients_text:
        try:
            leftovers = parse_manual_leftovers(ingredients_text)
            st.sidebar.success(f"Added {len(leftovers)} ingredients")
        except Exception as err:
            st.sidebar.error(f"Error: {str(err)}")
    return leftovers

def leftover_input_firebase() -> Tuple[List[str], List[Dict]]:
    """
    UI component to fetch ingredients from Firebase inventory with expiry priority
    
    Returns:
        Tuple[List[str], List[Dict]]: (ingredient_names, detailed_ingredient_info)
    """
    st.sidebar.subheader("Current Inventory")
    use_firebase = st.sidebar.checkbox("Use current inventory from Firebase", help="Fetch ingredients from your current inventory, prioritized by expiry date")
    leftovers = []
    detailed_info = []
    
    if use_firebase:
        # Add option to select number of ingredients to use
        max_ingredients = st.sidebar.slider(
            "Max ingredients to use", 
            min_value=3, 
            max_value=15, 
            value=8,
            help="Select how many ingredients to use (prioritized by expiry date)"
        )
        
        if st.sidebar.button("Fetch Priority Ingredients", type="primary"):
            try:
                # Show spinner in the main area since sidebar doesn't support spinner
                with st.spinner("Fetching ingredients from inventory..."):
                    # Fetch ingredients from Firebase (already sorted by expiry date)
                    firebase_ingredients = fetch_ingredients_from_firebase()
                    
                    if firebase_ingredients:
                        # Get ingredients prioritized by expiry date
                        leftovers, detailed_info = get_ingredients_by_expiry_priority(
                            firebase_ingredients, max_ingredients
                        )
                        
                        st.sidebar.success(f"Found {len(leftovers)} priority ingredients")
                        
                        # Show a preview of ingredients with expiry info
                        with st.sidebar.expander("Priority Ingredients", expanded=True):
                            for item in detailed_info:
                                days_left = item['days_until_expiry']
                                
                                # Color code based on urgency
                                if days_left <= 1:
                                    urgency_color = "🔴"  # Red for urgent (expires today/tomorrow)
                                elif days_left <= 3:
                                    urgency_color = "🟡"  # Yellow for soon (2-3 days)
                                elif days_left <= 7:
                                    urgency_color = "🟢"  # Green for moderate (4-7 days)
                                else:
                                    urgency_color = "⚪"  # White for later
                                
                                st.sidebar.markdown(f"{urgency_color} **{item['name']}**  \n"
                                                   f"Expires: {item['expiry_date']}  \n"
                                                   f"Days left: {days_left}  \n"
                                                   f"Type: {item['type']}")
                                st.sidebar.divider()
                        
                        # Store in session state for recipe generation
                        st.session_state.firebase_ingredients = leftovers
                        st.session_state.firebase_detailed_info = detailed_info
                        
                    else:
                        st.sidebar.warning("No ingredients found in inventory")
            except Exception as err:
                st.sidebar.error(f"Error fetching ingredients: {str(err)}")
    
    # Return stored ingredients if they exist
    if 'firebase_ingredients' in st.session_state:
        return st.session_state.firebase_ingredients, st.session_state.get('firebase_detailed_info', [])
    
    return leftovers, detailed_info

def display_leftover_summary(leftovers: List[str]):
    if leftovers:
        st.subheader("Current Ingredients")
        cols = st.columns(min(len(leftovers), 3))
        for i, ingredient in enumerate(leftovers):
            col_idx = i % 3
            with cols[col_idx]:
                st.info(ingredient.title())
    else:
        st.info("No ingredients added yet")

def display_recipe_suggestions(recipes: List[Dict], leftovers: List[str]):
    if not recipes:
        st.warning("No recipe suggestions found")
        return
    st.subheader("Recipe Suggestions")
    for i, recipe in enumerate(recipes):
        with st.expander(f"{recipe.get('name', f'Recipe {i+1}')}", expanded=i==0):
            col1, col2 = st.columns([2, 1])
            with col1:
                if 'description' in recipe:
                    st.write(recipe['description'])
                if 'cooking_time' in recipe:
                    st.caption(f"Cooking Time: {recipe['cooking_time']}")
                if 'difficulty' in recipe:
                    st.caption(f"Difficulty: {recipe['difficulty']}")
            with col2:
                if 'servings' in recipe:
                    st.metric("Servings", recipe['servings'])
            if 'ingredients' in recipe:
                st.write("**Ingredients:**")
                for ingredient in recipe['ingredients']:
                    if any(leftover.lower() in ingredient.lower() for leftover in leftovers):
                        st.write(f"✓ {ingredient}")
                    else:
                        st.write(f"• {ingredient}")
            if 'instructions' in recipe:
                st.write("**Instructions:**")
                for j, instruction in enumerate(recipe['instructions'], 1):
                    st.write(f"{j}. {instruction}")
            if 'nutrition' in recipe:
                st.write("**Nutrition Info:**")
                nutrition = recipe['nutrition']
                cols = st.columns(len(nutrition))
                for k, (key, value) in enumerate(nutrition.items()):
                    with cols[k]:
                        st.metric(key.title(), value)

def display_ingredient_filter():
    st.sidebar.divider()
    st.sidebar.subheader("Filters")
    dietary_options = st.sidebar.multiselect("Dietary Restrictions", ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Paleo"], help="Filter recipes by dietary needs")
    cuisine_type = st.sidebar.selectbox("Cuisine Type", ["Any", "Italian", "Asian", "Mexican", "American", "Mediterranean", "Indian"], help="Choose preferred cuisine style")
    max_time = st.sidebar.slider("Max Cooking Time (minutes)", min_value=15, max_value=120, value=60, step=15, help="Maximum time you want to spend cooking")
    difficulty = st.sidebar.selectbox("Max Difficulty", ["Any", "Easy", "Medium", "Hard"], help="Choose maximum difficulty level")
    return {
        "dietary": dietary_options,
        "cuisine": cuisine_type if cuisine_type != "Any" else None,
        "max_time": max_time,
        "difficulty": difficulty if difficulty != "Any" else None
    }

def display_recipe_stats(recipes: List[Dict]):
    if not recipes:
        return
    st.sidebar.divider()
    st.sidebar.subheader("Recipe Stats")
    total_recipes = len(recipes)
    st.sidebar.metric("Total Recipes", total_recipes)
    cooking_times = []
    for recipe in recipes:
        if 'cooking_time' in recipe:
            time_str = recipe['cooking_time']
            try:
                numbers = re.findall(r'\d+', time_str)
                if numbers:
                    cooking_times.append(int(numbers[0]))
            except:
                pass
    if cooking_times:
        avg_time = sum(cooking_times) / len(cooking_times)
        st.sidebar.metric("Avg. Cooking Time", f"{avg_time:.0f} min")
    difficulties = {}
    for recipe in recipes:
        if 'difficulty' in recipe:
            diff = recipe['difficulty']
            difficulties[diff] = difficulties.get(diff, 0) + 1
    if difficulties:
        st.sidebar.write("**Difficulty Breakdown:**")
        for diff, count in difficulties.items():
            st.sidebar.write(f"• {diff}: {count}")

def display_shopping_list(recipes: List[Dict], available_ingredients: List[str]):
    if not recipes:
        return
    st.subheader("Shopping List")
    all_ingredients = set()
    for recipe in recipes:
        if 'ingredients' in recipe:
            for ingredient in recipe['ingredients']:
                clean_ingredient = ingredient.lower().strip()
                all_ingredients.add(clean_ingredient)
    available_lower = [ing.lower().strip() for ing in available_ingredients]
    missing_ingredients = []
    for ingredient in all_ingredients:
        if not any(avail in ingredient or ingredient in avail for avail in available_lower):
            missing_ingredients.append(ingredient)
    if missing_ingredients:
        st.write("**Items to buy:**")
        for ingredient in sorted(missing_ingredients):
            st.write(f"• {ingredient.title()}")
    else:
        st.success("You have all ingredients needed!")

def display_recipe_search():
    st.subheader("Recipe Search")
    search_query = st.text_input("Search recipes", placeholder="Enter dish name, ingredient, or cuisine type...", help="Search for specific recipes or ingredients")
    return search_query

def display_save_recipe_option(recipe: Dict):
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Save Recipe", key=f"save_{recipe.get('name', 'recipe')}", type="secondary"):
            st.success("Recipe saved!")
            return True
    return False

def display_nutrition_info(recipe: Dict):
    if 'nutrition' not in recipe:
        return
    st.write("**Nutrition Information (per serving):**")
    nutrition = recipe['nutrition']
    cols = st.columns(min(len(nutrition), 4))
    for i, (key, value) in enumerate(nutrition.items()):
        col_idx = i % 4
        with cols[col_idx]:
            st.metric(key.replace('_', ' ').title(), value)

def display_recipe_rating(recipe: Dict):
    st.write("**Rate this recipe:**")
    col1, col2 = st.columns([2, 1])
    with col1:
        rating = st.selectbox("Rating", options=[1, 2, 3, 4, 5], format_func=lambda x: "★" * x + "☆" * (5-x), key=f"rating_{recipe.get('name', 'recipe')}")
    with col2:
        if st.button("Submit Rating", key=f"submit_rating_{recipe.get('name', 'recipe')}"):
            st.success(f"Rated {rating} stars!")
            return rating
    return None

def display_cooking_timer():
    st.sidebar.divider()
    st.sidebar.subheader("Cooking Timer")
    timer_minutes = st.sidebar.number_input("Minutes", min_value=1, max_value=180, value=15, step=1)
    if st.sidebar.button("Start Timer"):
        st.sidebar.success(f"Timer set for {timer_minutes} minutes!")
    return timer_minutes

def display_meal_planner():
    st.subheader("Weekly Meal Planner")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meals = ["Breakfast", "Lunch", "Dinner"]
    meal_plan = {}
    for day in days:
        with st.expander(day):
            meal_plan[day] = {}
            cols = st.columns(3)
            for i, meal in enumerate(meals):
                with cols[i]:
                    meal_plan[day][meal] = st.text_input(meal, key=f"{day}_{meal}", placeholder="Enter recipe name")
    if st.button("Save Meal Plan", type="primary"):
        st.success("Meal plan saved!")
    return meal_plan

def display_ingredient_substitutions(ingredient: str):
    substitutions = {
        "butter": ["margarine", "vegetable oil", "coconut oil", "applesauce"],
        "eggs": ["flax eggs", "chia eggs", "applesauce", "banana"],
        "milk": ["almond milk", "soy milk", "oat milk", "coconut milk"],
        "flour": ["almond flour", "coconut flour", "oat flour", "rice flour"],
        "sugar": ["honey", "maple syrup", "stevia", "coconut sugar"],
        "cream": ["coconut cream", "cashew cream", "greek yogurt"]
    }
    ingredient_lower = ingredient.lower()
    possible_subs = []
    for key, subs in substitutions.items():
        if key in ingredient_lower or ingredient_lower in key:
            possible_subs = subs
            break
    if possible_subs:
        st.write(f"**Substitutions for {ingredient}:**")
        for sub in possible_subs:
            st.write(f"• {sub}")
    return possible_subs

def display_cost_calculator(recipes: List[Dict]):
    if not recipes:
        return 0.0
    st.subheader("Cost Estimate")
    base_cost_per_serving = 3.50
    total_cost = len(recipes) * base_cost_per_serving
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Recipes", len(recipes))
    with col2:
        st.metric("Est. Cost per Recipe", f"${base_cost_per_serving:.2f}")
    with col3:
        st.metric("Total Estimated Cost", f"${total_cost:.2f}")
    st.caption("*Estimates based on average ingredient costs")
    return total_cost

def display_recipe_export_options(recipes: List[Dict]):
    if not recipes:
        return
    st.subheader("Export Options")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Export as PDF", use_container_width=True):
            st.info("PDF export feature coming soon!")
    with col2:
        if st.button("Email Recipes", use_container_width=True):
            st.info("Email feature coming soon!")
    with col3:
        if st.button("Share Link", use_container_width=True):
            st.info("Share feature coming soon!")

def display_quick_actions():
    st.sidebar.divider()
    st.sidebar.subheader("Quick Actions")
    actions = {
        "Random Recipe": "Get a random recipe suggestion",
        "Clear All": "Clear all ingredients and start over",
        "Save Session": "Save current session",
        "Load Favorites": "Load your favorite recipes"
    }
    selected_action = None
    for action, description in actions.items():
        if st.sidebar.button(action, help=description, use_container_width=True):
            selected_action = action
            break
    return selected_action

def display_app_settings():
    st.sidebar.divider()
    st.sidebar.subheader("Settings")
    settings = {}
    settings['theme'] = st.sidebar.selectbox("Theme", ["Light", "Dark", "Auto"], help="Choose your preferred theme")
    settings['units'] = st.sidebar.selectbox("Units", ["Metric", "Imperial"], help="Choose measurement units")
    settings['notifications'] = st.sidebar.checkbox("Enable notifications", value=True, help="Receive cooking tips and reminders")
    return settings

# =======================
# GAMIFICATION UI
# =======================

def display_user_stats_sidebar(user_id: str) -> Dict:
    stats = get_user_stats(user_id)
    st.sidebar.divider()
    st.sidebar.subheader("Player Stats")
    current_level_xp, xp_needed = get_xp_progress(stats['total_xp'], stats['level'])
    xp_for_current_level = (stats['level'] ** 2) * 100 - ((stats['level'] - 1) ** 2) * 100
    progress = current_level_xp / xp_for_current_level if xp_for_current_level > 0 else 0
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Level", stats['level'])
        st.metric("Quizzes", stats['quizzes_taken'])
    with col2:
        st.metric("XP", stats['total_xp'])
        st.metric("Perfect", stats['perfect_scores'])
    st.sidebar.progress(progress, text=f"{xp_needed} XP to next level")
    if stats['total_questions'] > 0:
        accuracy = (stats['correct_answers'] / stats['total_questions']) * 100
        st.sidebar.metric("Accuracy", f"{accuracy:.1f}%")
    return stats

def render_cooking_quiz(ingredients: List[str], user_id: str):
    st.subheader
