import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

# Import the updated UI components
from ui.components import (
    leftover_input_csv, leftover_input_manual, leftover_input_firebase,
    display_recipe_suggestions_enhanced, display_priority_breakdown,
    render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role,
    display_user_stats_sidebar, render_cooking_quiz, display_gamification_dashboard,
    award_recipe_generation_xp, display_daily_challenge, show_xp_notification
)

# Import the enhanced leftover management functions
from nodules.leftover import (
    suggest_recipes, get_user_stats, award_recipe_xp
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
    st.title("♻️ Smart Leftover Management")
    st.caption("AI-powered recipe suggestions with ingredient prioritization")
    
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
    st.sidebar.header("🍽️ Ingredient Sources")
    
    # Get leftovers from different sources
    csv_leftovers = leftover_input_csv()
    manual_leftovers = leftover_input_manual()
    firebase_leftovers, firebase_data = leftover_input_firebase()
    
    # Store Firebase data in session state
    if firebase_data:
        st.session_state.firebase_ingredients_data = firebase_data
    
    # Combine leftovers from all sources
    all_leftovers = csv_leftovers + manual_leftovers + firebase_leftovers
    
    # Store in session state
    st.session_state.all_leftovers = all_leftovers
    
    # Main content
    if all_leftovers:
        # Display ingredient summary
        st.success(f"✅ Found **{len(all_leftovers)}** ingredients ready for recipe generation!")
        
        # Show priority breakdown if Firebase data is available
        if st.session_state.firebase_ingredients_data:
            display_priority_breakdown(st.session_state.firebase_ingredients_data)
        
        # Enhanced ingredient display
        with st.expander("📋 View All Ingredients", expanded=False):
            if st.session_state.firebase_ingredients_data:
                st.subheader("🔥 Prioritized Firebase Ingredients")
                
                # Group by priority for better display
                priority_groups = {}
                for item in st.session_state.firebase_ingredients_data:
                    priority = item['priority']
                    if priority not in priority_groups:
                        priority_groups[priority] = []
                    priority_groups[priority].append(item)
                
                priority_colors = {1: "🔴", 2: "🟡", 3: "🟠", 4: "⚪"}
                
                for priority in sorted(priority_groups.keys()):
                    items = priority_groups[priority]
                    st.write(f"**{priority_colors[priority]} Priority {priority} ({len(items)} items)**")
                    
                    cols = st.columns(3)
                    for i, item in enumerate(items):
                        col_idx = i % 3
                        with cols[col_idx]:
                            expiry_text = f"Expires in {item['days_until_expiry']} days" if item['days_until_expiry'] < 9999 else "No expiry"
                            st.write(f"• **{item['ingredient'].title()}**")
                            st.caption(f"Qty: {item['quantity']} • {expiry_text}")
                    st.write("")
            
            # Display other ingredients
            other_ingredients = csv_leftovers + manual_leftovers
            if other_ingredients:
                st.subheader("📝 Other Ingredients")
                cols = st.columns(4)
                for i, ingredient in enumerate(other_ingredients):
                    col_idx = i % 4
                    with cols[col_idx]:
                        st.write(f"• {ingredient.title()}")
        
        # Recipe generation section
        st.divider()
        st.subheader("🤖 AI Recipe Generation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            num_suggestions = st.slider(
                "Number of recipes", 
                min_value=1, 
                max_value=10, 
                value=3,
                help="How many recipe suggestions do you want?"
            )
        
        with col2:
            notes = st.text_area(
                "Special requirements", 
                placeholder="e.g., vegetarian, quick meals, kid-friendly, spicy, etc.",
                help="Add any dietary restrictions or preferences",
                height=100
            )
        
        # Priority information display
        if st.session_state.firebase_ingredients_data:
            high_priority_items = [item for item in st.session_state.firebase_ingredients_data if item['priority'] <= 2]
            if high_priority_items:
                st.info(f"🔥 **Smart Priority**: {len(high_priority_items)} ingredients are expiring soon and will be prioritized in recipes!")
        
        # Generate recipe button
        st.write("")
        if st.button("🚀 Generate Smart Recipe Suggestions", type="primary", use_container_width=True):
            try:
                with st.spinner("🤖 AI is creating personalized recipes based on your ingredients..."):
                    # Add a progress bar for better UX
                    progress_bar = st.progress(0)
                    progress_bar.progress(25, text="Analyzing ingredients...")
                    
                    # Call the enhanced suggest_recipes function with prioritized data
                    recipes = suggest_recipes(
                        leftovers=all_leftovers, 
                        max_suggestions=num_suggestions, 
                        notes=notes,
                        prioritized_ingredients=st.session_state.firebase_ingredients_data
                    )
                    
                    progress_bar.progress(75, text="Generating recipes...")
                    
                    # Store results in session state
                    st.session_state.recipes = recipes
                    st.session_state.recipe_generation_error = None
                    
                    progress_bar.progress(100, text="Complete!")
                    progress_bar.empty()
                    
                    # Log for debugging
                    logging.info(f"Generated {len(recipes)} priority-based recipes")
                    
            except Exception as e:
                st.session_state.recipe_generation_error = str(e)
                logging.error(f"Recipe generation error: {str(e)}")
        
        # Display results
        st.write("")
        if st.session_state.recipe_generation_error:
            st.error(f"❌ **Error generating recipes**: {st.session_state.recipe_generation_error}")
            
            # Enhanced debugging information
            with st.expander("🔧 Troubleshooting Information"):
                st.write("**Debug Details:**")
                st.write(f"- Total ingredients: {len(all_leftovers)}")
                st.write(f"- Firebase data available: {len(st.session_state.firebase_ingredients_data) > 0}")
                st.write(f"- Ingredients list: {all_leftovers}")
                st.write(f"- Error: {st.session_state.recipe_generation_error}")
                
                if st.button("🔄 Retry Recipe Generation"):
                    st.session_state.recipe_generation_error = None
                    st.rerun()
                    
        elif st.session_state.recipes:
            st.success(f"🎉 **Success!** Generated {len(st.session_state.recipes)} personalized recipe suggestions!")
            
            # Display recipes using the enhanced function
            display_recipe_suggestions_enhanced(
                st.session_state.recipes, 
                st.session_state.firebase_ingredients_data
            )
            
            # Award XP for generating recipes
            user = get_current_user()
            if user and user.get('user_id'):
                try:
                    award_recipe_generation_xp(user['user_id'], len(st.session_state.recipes))
                except Exception as e:
                    logging.error(f"Error awarding XP: {str(e)}")
                    
    else:
        # Welcome screen when no ingredients are added
        st.info("👋 **Welcome to Smart Leftover Management!** Add ingredients using the sidebar to get started.")
        
        # Enhanced how-it-works section
        st.markdown("### 🚀 How It Works")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **1. 📊 Add Ingredients**
            - Upload CSV file
            - Enter manually
            - Fetch from Firebase
            """)
        
        with col2:
            st.markdown("""
            **2. 🔥 Smart Prioritization**
            - Expiring soon + Large qty
            - Expiring soon
            - Large quantity
            - Standard items
            """)
        
        with col3:
            st.markdown("""
            **3. 🤖 AI Recipe Generation**
            - Prioritizes expiring items
            - Considers your preferences
            - Reduces food waste
            - Saves money!
            """)
        
        st.divider()
        
        # Example demonstration
        st.markdown("### 📋 Example Priority System")
        
        example_data = [
            {"ingredient": "🍗 Chicken Breast", "days": 2, "quantity": 8, "priority": "🔴 High Priority", "reason": "Expires soon + Large quantity"},
            {"ingredient": "🥛 Milk", "days": 1, "quantity": 2, "priority": "🟡 Medium Priority", "reason": "Expires very soon"},
            {"ingredient": "🍚 Rice", "days": 30, "quantity": 10, "priority": "🟠 Good Quantity", "reason": "Large quantity available"},
            {"ingredient": "🧂 Salt", "days": 365, "quantity": 1, "priority": "⚪ Standard Priority", "reason": "Regular item"}
        ]
        
        for item in example_data:
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 2])
                with col1:
                    st.write(f"**{item['ingredient']}**")
                    st.caption(f"Expires: {item['days']} days | Qty: {item['quantity']}")
                with col2:
                    st.write("→")
                with col3:
                    st.write(f"**{item['priority']}**")
                    st.caption(item['reason'])

# Keep other functions unchanged but with enhanced styling
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
        Welcome to the **AI-powered smart restaurant system**! 🍽️
        
        ## ✨ **Enhanced Features**
        
        ### 🧠 **Smart Recipe Generation**
        - **Ingredient Prioritization** based on expiry dates and quantities
        - **AI-Powered Suggestions** using Google Gemini
        - **Waste Reduction** by using ingredients before they expire
        
        ### ⏰ **Intelligent Inventory Management**
        - **Expiry Date Tracking** with automatic prioritization
        - **Quantity-Based Optimization** for better ingredient usage
        - **Firebase Integration** for real-time inventory data
        
        ### 🎮 **Gamification System**
        - **Interactive Quizzes** to test culinary knowledge
        - **Achievement System** with badges and rewards
        - **Leaderboards** to compete with other chefs
        - **XP Points** for recipe generation and quiz completion
        
        ### 🎉 **Additional Features**
        - **Event Planning ChatBot** for special occasions
        - **Progress Tracking** and skill development
        - **Multi-User Support** with role-based access
        
        ---
        
        **🚀 Ready to get started?** Please log in or register to access all features.
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

print("🎉 Final enhanced main app loaded successfully!")
print("✅ All systems integrated and ready!")
print("🔥 Features:")
print("   - Smart ingredient prioritization")
print("   - Enhanced recipe generation")
print("   - Improved UI/UX")
print("   - Better error handling")
print("   - Gamification integration")
print("   - Firebase real-time data")
