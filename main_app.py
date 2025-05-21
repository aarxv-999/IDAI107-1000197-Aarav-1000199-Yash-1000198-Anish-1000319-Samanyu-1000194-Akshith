"""
MAIN APP FILE for the Smart Restaurant Menu Management App
This combines all UI components and logic functions to create a complete Streamlit interface.
"""
import streamlit as st
from ui.components import (  # Import UI functions
    leftover_input_csv, leftover_input_manual,
)
from ui.auth_components import (
    render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role
)
from modules.leftover import suggest_recipes  # Import logic functions
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
    public_features = ["Event Planning ChatBot"]
    
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
        
        max_suggestions = st.slider("How many recipes do you want?", 1, 5, 3)
        logging.info(f"User requested {max_suggestions} recipes")
        
        if st.button("Generate Recipes"):
            with st.spinner("Generating recipe suggestions..."):
                try:
                    logging.info("Calling suggest_recipes function...")
                    suggestions = suggest_recipes(leftovers, max_suggestions)
                    logging.info(f"Received suggestions: {suggestions}")
                    
                    if suggestions and len(suggestions) > 0:
                        st.markdown("### Recipe Suggestions:")
                        for i, recipe in enumerate(suggestions, 1):
                            st.write(f"{i}. {recipe}")
                    else:
                        st.warning("No recipes could be generated. Try different ingredients.")
                        logging.warning(f"No recipes returned for ingredients: {leftovers}")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    logging.error(f"Error in recipe generation: {str(e)}")
    else:
        st.info("Please upload or enter some leftover ingredients to continue.")

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
    st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")
    
    # Initialize Firebase and session state for authentication
    initialize_session_state()
    
    # Render authentication UI in sidebar
    st.sidebar.title("Authentication")
    auth_status = render_auth_ui()
    
    # Main content
    st.title("🍽️ Smart Restaurant Menu Management System")
    
    # Welcome message based on authentication status
    user = get_current_user()
    if user:
        st.markdown(f'''
        Welcome to the AI-powered smart restaurant system, {user['username']}!
        
        Your role: **{user['role'].capitalize()}**
        
        Please select a feature from the sidebar to begin.
        ''')
    else:
        st.markdown('''
        Welcome to the AI-powered smart restaurant system!
        
        Please log in or register to access the features.
        ''')
    
    # Feature selection in sidebar
    st.sidebar.divider()
    st.sidebar.header("Features")
    
    # List of all available features
    features = [
        "Leftover Management",
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
            options=available_features
        )
        
        st.divider()
        
        # Display the selected feature
        if selected_feature == "Leftover Management":
            leftover_management()
        elif selected_feature == "Event Planning ChatBot":
            event_planning()
        elif selected_feature == "Promotion Generator":
            promotion_generator()
        elif selected_feature == "Chef Recipe Suggestions":
            chef_recipe_suggestions()
        elif selected_feature == "Visual Menu Search":
            visual_menu_search()
    else:
        # If not authenticated, show a simple placeholder
        st.info("Please log in or register to access the features.")

if __name__ == "__main__":
    main()
