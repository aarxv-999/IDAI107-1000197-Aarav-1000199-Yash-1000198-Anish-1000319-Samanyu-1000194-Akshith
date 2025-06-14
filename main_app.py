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
from modules.ingredient_management import render_ingredient_management

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(levelname)s - %(message)s')

def check_feature_access(feature_name):
  """Check if the current user has access to a specific feature"""
  user = get_current_user()

  public_features = ["Event Planning ChatBot", "Gamification Hub", "Cooking Quiz"]
  staff_features = ["Leftover Management", "Promotion Generator"]
  chef_features = ["Chef Recipe Suggestions", "Ingredient Management"]  # Added Ingredient Management
  admin_features = ["Visual Menu Search", "Ingredient Management"]  # Added Ingredient Management

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
  """Combined leftover management and cooking quiz interface"""
  st.title("♻️ Leftover Management")
  
  user = get_current_user()
  user_id = user.get('user_id', '') if user else ''
  
  # Create tabs for different functions
  tab1, tab2 = st.tabs(["♻️ Leftover Recipes", "🧠 Cooking Quiz"])
  
  with tab1:
      render_leftover_management(user_id)
  
  with tab2:
      render_cooking_quiz_tab(user_id)

def render_leftover_management(user_id: str):
  """Clean step-by-step leftover management section"""
  st.markdown("### ♻️ Generate New Recipes from Leftovers")
  
  # Initialize session state
  if 'leftover_step' not in st.session_state:
      st.session_state.leftover_step = 'select_method'
  if 'selected_method' not in st.session_state:
      st.session_state.selected_method = None
  if 'max_ingredients' not in st.session_state:
      st.session_state.max_ingredients = 8
  if 'all_leftovers' not in st.session_state:
      st.session_state.all_leftovers = []
  if 'detailed_ingredient_info' not in st.session_state:
      st.session_state.detailed_ingredient_info = []
  if 'recipes' not in st.session_state:
      st.session_state.recipes = []
  if 'recipe_generation_error' not in st.session_state:
      st.session_state.recipe_generation_error = None

  # Step 1: Method Selection
  if st.session_state.leftover_step == 'select_method':
      st.markdown("#### Step 1: Choose Your Ingredient Input Method")
      
      col1, col2, col3 = st.columns(3)
      
      with col1:
          if st.button("📁 Upload CSV File", use_container_width=True, type="primary", key="csv_method"):
              st.session_state.selected_method = 'csv'
              st.session_state.leftover_step = 'input_ingredients'
              st.rerun()
          st.caption("Upload a CSV file with ingredient list")
      
      with col2:
          if st.button("✏️ Manual Entry", use_container_width=True, type="primary", key="manual_method"):
              st.session_state.selected_method = 'manual'
              st.session_state.leftover_step = 'input_ingredients'
              st.rerun()
          st.caption("Type ingredients manually")
      
      with col3:
          if st.button("🔥 Current Inventory", use_container_width=True, type="primary", key="firebase_method"):
              st.session_state.selected_method = 'firebase'
              st.session_state.leftover_step = 'firebase_config'  # New step for Firebase
              st.rerun()
          st.caption("Fetch from restaurant database")

  # Step 2: Firebase Configuration (only for Firebase method)
  elif st.session_state.leftover_step == 'firebase_config':
      st.markdown("#### Step 2: Configure Inventory Fetch")
      
      # Back button
      if st.button("← Back to Method Selection", key="back_to_method"):
          st.session_state.leftover_step = 'select_method'
          st.session_state.selected_method = None
          st.rerun()
      
      st.info("Configure how many ingredients to fetch from your restaurant inventory")
      
      max_ingredients = st.slider(
          "Maximum ingredients to fetch", 
          min_value=3, 
          max_value=20, 
          value=st.session_state.max_ingredients,
          help="Select how many ingredients you want to work with"
      )
      st.session_state.max_ingredients = max_ingredients
      
      if st.button("Continue to Fetch Ingredients →", type="primary", use_container_width=True, key="continue_firebase"):
          st.session_state.leftover_step = 'input_ingredients'
          st.rerun()

  # Step 3: Input Ingredients
  elif st.session_state.leftover_step == 'input_ingredients':
      method_names = {
          'csv': '📁 CSV Upload',
          'manual': '✏️ Manual Entry', 
          'firebase': '🔥 Current Inventory'
      }
      
      st.markdown(f"#### Step {'3' if st.session_state.selected_method == 'firebase' else '2'}: {method_names[st.session_state.selected_method]}")
      
      # Back button - different logic for Firebase vs others
      if st.session_state.selected_method == 'firebase':
          if st.button("← Back to Configuration", key="back_to_config"):
              st.session_state.leftover_step = 'firebase_config'
              st.rerun()
      else:
          if st.button("← Back to Method Selection", key="back_to_method_from_input"):
              st.session_state.leftover_step = 'select_method'
              st.session_state.selected_method = None
              st.session_state.all_leftovers = []
              st.session_state.detailed_ingredient_info = []
              st.rerun()
      
      # Handle different input methods
      leftovers = []
      detailed_info = []
      
      if st.session_state.selected_method == 'csv':
          leftovers = leftover_input_csv()
          
      elif st.session_state.selected_method == 'manual':
          leftovers = leftover_input_manual()
          
      elif st.session_state.selected_method == 'firebase':
          # Pass the max_ingredients parameter
          leftovers, detailed_info = leftover_input_firebase_with_limit(st.session_state.max_ingredients)
      
      # Update session state
      st.session_state.all_leftovers = leftovers
      st.session_state.detailed_ingredient_info = detailed_info
      
      # Show ingredients if found and move to next step
      if leftovers:
          st.session_state.leftover_step = 'review_ingredients'
          st.rerun()

  # Step 4: Review Ingredients
  elif st.session_state.leftover_step == 'review_ingredients':
      step_number = '4' if st.session_state.selected_method == 'firebase' else '3'
      st.markdown(f"#### Step {step_number}: Review Your Ingredients")
      
      # Back button
      if st.button("← Back to Input", key="back_to_input"):
          st.session_state.leftover_step = 'input_ingredients'
          # Clear ingredients when going back
          st.session_state.all_leftovers = []
          st.session_state.detailed_ingredient_info = []
          st.rerun()
      
      all_leftovers = st.session_state.all_leftovers
      firebase_detailed_info = st.session_state.detailed_ingredient_info
      
      # Display ingredient summary
      col1, col2 = st.columns([2, 1])
      with col1:
          st.success(f"✅ **{len(all_leftovers)} ingredients found**")
      with col2:
          if firebase_detailed_info:
              urgent_count = len([item for item in firebase_detailed_info if item['days_until_expiry'] <= 3])
              if urgent_count > 0:
                  st.warning(f"⚠️ {urgent_count} expire soon")
      
      # Show ingredient details
      if firebase_detailed_info:
          st.markdown("**Ingredient Details:**")
          for item in firebase_detailed_info:
              days_left = item['days_until_expiry']
              if days_left <= 1:
                  st.error(f"🔴 {item['name']} - expires in {days_left} days")
              elif days_left <= 3:
                  st.warning(f"🟡 {item['name']} - expires in {days_left} days")
              else:
                  st.info(f"🟢 {item['name']} - expires in {days_left} days")
      else:
          st.markdown("**Your Ingredients:**")
          st.write(", ".join(all_leftovers))
      
      # Continue to recipe generation
      if st.button("Continue to Recipe Generation →", type="primary", use_container_width=True, key="continue_to_recipes"):
          st.session_state.leftover_step = 'generate_recipes'
          st.rerun()

  # Step 5: Generate Recipes
  elif st.session_state.leftover_step == 'generate_recipes':
      step_number = '5' if st.session_state.selected_method == 'firebase' else '4'
      st.markdown(f"#### Step {step_number}: Generate Creative Recipes")
      
      # Back button
      if st.button("← Back to Review", key="back_to_review"):
          st.session_state.leftover_step = 'review_ingredients'
          st.rerun()
      
      all_leftovers = st.session_state.all_leftovers
      firebase_detailed_info = st.session_state.detailed_ingredient_info
      
      # Quick ingredient summary
      st.info(f"Using {len(all_leftovers)} ingredients: {', '.join(all_leftovers[:5])}" + 
              (f" and {len(all_leftovers) - 5} more..." if len(all_leftovers) > 5 else ""))
      
      # Recipe generation controls
      col1, col2 = st.columns([2, 1])
      with col1:
          notes = st.text_input("Special Requirements (optional)", 
                              placeholder="e.g., vegetarian, quick meals, spicy",
                              key="recipe_notes")
      with col2:
          num_suggestions = st.selectbox("Number of Recipes", [1, 2, 3, 4, 5], index=2, key="num_recipes")
      
      if st.button("🆕 Generate Creative Recipes", type="primary", use_container_width=True, key="generate_recipes_btn"):
          try:
              with st.spinner("Creating new recipes from your leftovers..."):
                  recipes = suggest_recipes(
                      all_leftovers, 
                      num_suggestions, 
                      notes, 
                      priority_ingredients=firebase_detailed_info
                  )
                  st.session_state.recipes = recipes
                  st.session_state.recipe_generation_error = None
                  
                  # Award XP for recipe generation
                  if user_id:
                      award_recipe_generation_xp(user_id, len(recipes))
          except Exception as e:
              st.session_state.recipe_generation_error = str(e)
      
      # Display results
      if st.session_state.recipe_generation_error:
          st.error(f"❌ Error: {st.session_state.recipe_generation_error}")
          
      elif st.session_state.recipes:
          st.success("✨ **New Creative Recipe Suggestions**")
          for i, recipe in enumerate(st.session_state.recipes, 1):
              st.write(f"**{i}.** {recipe}")
          
          st.divider()
          
          # Action buttons
          col1, col2 = st.columns(2)
          with col1:
              if st.button("🔄 Generate More Recipes", use_container_width=True, key="more_recipes"):
                  st.session_state.recipes = []
                  st.rerun()
          with col2:
              if st.button("🆕 Start Over", use_container_width=True, key="start_over"):
                  # Reset everything
                  st.session_state.leftover_step = 'select_method'
                  st.session_state.selected_method = None
                  st.session_state.max_ingredients = 8
                  st.session_state.all_leftovers = []
                  st.session_state.detailed_ingredient_info = []
                  st.session_state.recipes = []
                  st.session_state.recipe_generation_error = None
                  st.rerun()

def leftover_input_firebase_with_limit(max_ingredients: int):
  """Firebase input with ingredient limit"""
  from ui.components import leftover_input_firebase
  
  # Store the max_ingredients in session state for the component to use
  st.session_state.firebase_max_ingredients = max_ingredients
  
  # Call the original function
  return leftover_input_firebase()

def render_cooking_quiz_tab(user_id: str):
  """Cooking quiz section"""
  st.markdown("### 🧠 Test Your Culinary Knowledge")
  
  if not user_id:
      st.warning("Please log in to take quizzes")
      return
  
  # Display daily challenge
  display_daily_challenge(user_id)
  
  # Sample ingredients for quiz context
  sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
  
  # Render the quiz
  render_cooking_quiz(sample_ingredients, user_id)

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

@auth_required
def ingredient_management():
  """Ingredient management interface"""
  render_ingredient_management()

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
      - Ingredient inventory management
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
          "Ingredient Management",  # Added new feature
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
  elif selected_feature == "Ingredient Management":  # Added new route
      ingredient_management()
  elif selected_feature == "Promotion Generator":
      promotion_generator()
  elif selected_feature == "Chef Recipe Suggestions":
      chef_recipe_suggestions()
  elif selected_feature == "Visual Menu Search":
      visual_menu_search()

if __name__ == "__main__":
  main()
