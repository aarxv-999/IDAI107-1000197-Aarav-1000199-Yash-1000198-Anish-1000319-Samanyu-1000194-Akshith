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

# Import the enhanced leftover management functions
from modules.leftover import (
    suggest_recipes, fetch_ingredients_from_firebase, prioritize_ingredients, 
    parse_firebase_ingredients, get_user_stats, award_recipe_xp
)

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

# Enhanced leftover management function
@auth_required
def leftover_management():
    """Enhanced leftover management feature with Firebase prioritization"""
    st.title("♻️ Enhanced Leftover Management")
    
    # Initialize session state variables if they don't exist
    if 'all_leftovers' not in st.session_state:
        st.session_state.all_leftovers = []
    if 'firebase_ingredients_data' not in st.session_state:
        st.session_state.firebase_ingredients_data = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    if 'recipe_generation_error' not in st.session_state:
        st.session_state.recipe_generation_error = None
    
    # Sidebar for input methods
    st.sidebar.header("Input Methods")
    
    # Get leftovers from CSV and manual input (existing functionality)
    csv_leftovers = leftover_input_csv()
    manual_leftovers = leftover_input_manual()
    
    # Enhanced Firebase ingredient fetching with prioritization
    st.sidebar.subheader("📊 Firebase Ingredients")
    if st.sidebar.button("🔄 Fetch & Prioritize Ingredients", help="Fetch ingredients from Firebase and prioritize by expiry date and quantity"):
        try:
            with st.sidebar.spinner("Fetching and prioritizing ingredients..."):
                # Fetch raw ingredients from Firebase
                raw_firebase_ingredients = fetch_ingredients_from_firebase()
                
                # Prioritize ingredients
                prioritized_data = prioritize_ingredients(raw_firebase_ingredients)
                
                # Store both the ingredient names and the full data
                firebase_leftovers = [item['ingredient'] for item in prioritized_data]
                st.session_state.firebase_ingredients_data = prioritized_data
                
                st.sidebar.success(f"✅ Fetched {len(firebase_leftovers)} prioritized ingredients!")
                
                # Show priority breakdown
                priority_counts = {}
                for item in prioritized_data:
                    priority = item['priority']
                    priority_counts[priority] = priority_counts.get(priority, 0) + 1
                
                st.sidebar.write("**Priority Breakdown:**")
                priority_labels = {
                    1: "🔴 High Priority (Expiring Soon + Large Qty)",
                    2: "🟡 Medium Priority (Expiring Soon)",
                    3: "🟠 Good Quantity (Large Qty)",
                    4: "⚪ Standard Priority"
                }
                
                for priority in sorted(priority_counts.keys()):
                    count = priority_counts[priority]
                    label = priority_labels.get(priority, f"Priority {priority}")
                    st.sidebar.write(f"{label}: {count} items")
                    
        except Exception as e:
            st.sidebar.error(f"❌ Error fetching ingredients: {str(e)}")
            firebase_leftovers = []
    else:
        # Use existing Firebase ingredients if available
        firebase_leftovers = [item['ingredient'] for item in st.session_state.firebase_ingredients_data]
    
    # Combine leftovers from all sources
    all_leftovers = csv_leftovers + manual_leftovers + firebase_leftovers
    
    # Store in session state
    st.session_state.all_leftovers = all_leftovers
    
    # Main content
    if all_leftovers:
        st.write(f"Found {len(all_leftovers)} ingredients")
        
        # Enhanced ingredient display with priority information
        with st.expander("Available Ingredients (Prioritized)", expanded=True):
            if st.session_state.firebase_ingredients_data:
                # Display Firebase ingredients with priority info
                st.subheader("🔥 Firebase Ingredients (Prioritized)")
                
                # Group by priority
                priority_groups = {}
                for item in st.session_state.firebase_ingredients_data:
                    priority = item['priority']
                    if priority not in priority_groups:
                        priority_groups[priority] = []
                    priority_groups[priority].append(item)
                
                priority_colors = {1: "🔴", 2: "🟡", 3: "🟠", 4: "⚪"}
                priority_names = {
                    1: "High Priority (Expiring Soon + Large Quantity)",
                    2: "Medium Priority (Expiring Soon)",
                    3: "Good Quantity (Large Quantity)",
                    4: "Standard Priority"
                }
                
                for priority in sorted(priority_groups.keys()):
                    items = priority_groups[priority]
                    st.write(f"**{priority_colors[priority]} {priority_names[priority]}**")
                    
                    cols = st.columns(2)
                    for i, item in enumerate(items):
                        col_idx = i % 2
                        with cols[col_idx]:
                            expiry_text = f"Expires in {item['days_until_expiry']} days" if item['days_until_expiry'] < 9999 else "No expiry date"
                            quantity_text = f"Qty: {item['quantity']}" if item['quantity'] > 0 else "Qty: Unknown"
                            st.write(f"• **{item['ingredient'].title()}** - {expiry_text}, {quantity_text}")
                    st.write("")
            
            # Display other ingredients
            other_ingredients = csv_leftovers + manual_leftovers
            if other_ingredients:
                st.subheader("📝 Other Ingredients")
                cols = st.columns(3)
                for i, ingredient in enumerate(other_ingredients):
                    col_idx = i % 3
                    with cols[col_idx]:
                        st.write(f"• {ingredient.title()}")
        
        # Recipe generation options
        st.subheader("🍳 Recipe Generation Options")
        
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
        
        # Priority information display
        if st.session_state.firebase_ingredients_data:
            high_priority_items = [item for item in st.session_state.firebase_ingredients_data if item['priority'] <= 2]
            if high_priority_items:
                st.info(f"🔥 **Priority Focus**: {len(high_priority_items)} ingredients are expiring soon and will be prioritized in recipe suggestions!")
        
        # Generate recipe button - using a form to prevent page reloads
        with st.form(key="recipe_form"):
            submit_button = st.form_submit_button(
                label="🚀 Generate Priority-Based Recipe Suggestions", 
                type="primary",
                help="Generate recipes prioritizing ingredients that are expiring soon"
            )
            
            if submit_button:
                try:
                    with st.spinner("🤖 Generating priority-based recipes..."):
                        # Call the enhanced suggest_recipes function with prioritized data
                        recipes = suggest_recipes(
                            leftovers=all_leftovers, 
                            max_suggestions=num_suggestions, 
                            notes=notes,
                            prioritized_ingredients=st.session_state.firebase_ingredients_data
                        )
                        
                        # Store results in session state
                        st.session_state.recipes = recipes
                        st.session_state.recipe_generation_error = None
                        
                        # Log for debugging
                        logging.info(f"Generated {len(recipes)} priority-based recipes")
                        
                except Exception as e:
                    st.session_state.recipe_generation_error = str(e)
                    logging.error(f"Recipe generation error: {str(e)}")
        
        # Display recipes or error message outside the form
        if st.session_state.recipe_generation_error:
            st.error(f"❌ Error generating recipes: {st.session_state.recipe_generation_error}")
            
            # Debugging information
            with st.expander("🔧 Debug Information"):
                st.write("**Ingredients being used:**", all_leftovers)
                st.write("**Firebase data available:**", len(st.session_state.firebase_ingredients_data) > 0)
                st.write("**Error details:**", st.session_state.recipe_generation_error)
                
        elif st.session_state.recipes:
            st.success(f"🎉 Generated {len(st.session_state.recipes)} priority-based recipe suggestions!")
            
            # Display recipes with enhanced formatting
            st.subheader("🍽️ Recipe Suggestions")
            
            # Show which high-priority ingredients were considered
            if st.session_state.firebase_ingredients_data:
                high_priority_items = [item for item in st.session_state.firebase_ingredients_data if item['priority'] <= 2]
                if high_priority_items:
                    st.info(f"✨ These recipes prioritize ingredients expiring soon: {', '.join([item['ingredient'] for item in high_priority_items[:5]])}")
            
            for i, recipe in enumerate(st.session_state.recipes):
                st.markdown(f"**{i+1}.** {recipe}")
            
            # Award XP for generating recipes
            user = get_current_user()
            if user and user.get('user_id'):
                try:
                    award_recipe_generation_xp(user['user_id'], len(st.session_state.recipes))
                    st.success(f"🎮 Earned {len(st.session_state.recipes) * 5} XP for generating recipes!")
                except Exception as e:
                    logging.error(f"Error awarding XP: {str(e)}")
                    
    else:
        st.info("Please add ingredients using the sidebar options.")
        
        # Enhanced example section
        st.markdown("### 🚀 How the Enhanced System Works")
        st.markdown("""
        1. **Fetch Ingredients**: Click "Fetch & Prioritize Ingredients" to get data from Firebase
        2. **Smart Prioritization**: Ingredients are automatically prioritized by:
           - 🔴 **High Priority**: Expiring soon (≤7 days) + Large quantity (≥5 units)
           - 🟡 **Medium Priority**: Expiring soon (≤7 days) regardless of quantity  
           - 🟠 **Good Quantity**: Large quantity (≥5 units) regardless of expiry
           - ⚪ **Standard Priority**: Everything else
        3. **AI Recipe Generation**: Get recipes that prioritize using ingredients before they expire
        4. **Reduce Waste**: Save money and help the environment!
        """)
        
        # Example ingredients
        st.markdown("### 📋 Example Priority System")
        example_data = [
            {"ingredient": "Chicken Breast", "days": 2, "quantity": 8, "priority": "🔴 High Priority"},
            {"ingredient": "Milk", "days": 1, "quantity": 2, "priority": "🟡 Medium Priority"},
            {"ingredient": "Rice", "days": 30, "quantity": 10, "priority": "🟠 Good Quantity"},
            {"ingredient": "Salt", "days": 365, "quantity": 1, "priority": "⚪ Standard Priority"}
        ]
        
        for item in example_data:
            st.write(f"**{item['ingredient']}** - Expires in {item['days']} days, Qty: {item['quantity']} → {item['priority']}")

# Keep other functions unchanged
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
        
        **Enhanced Features include:**
        - 🧠 **Smart Recipe Generation** with ingredient prioritization
        - ⏰ **Expiry Date Management** to reduce food waste
        - 📊 **Quantity-Based Prioritization** for optimal ingredient usage
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

print("Enhanced main app loaded successfully!")
print("Key improvements:")
print("1. ✅ Firebase ingredient prioritization system")
print("2. ✅ Enhanced UI with priority visualization")
print("3. ✅ Better error handling and debugging")
print("4. ✅ Improved recipe generation with priority context")
