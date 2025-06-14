import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (
    leftover_input_csv, leftover_input_manual, leftover_input_firebase,
    render_auth_ui, initialize_session_state, auth_required, get_current_user
)
from modules.leftover import suggest_recipes
from firebase_init import init_firebase

init_firebase()

import logging
logging.basicConfig(level=logging.INFO)

def check_feature_access(feature_name):
    """Check if the current user has access to a specific feature"""
    user = get_current_user()
    
    public_features = ["Event Planning ChatBot"]
    staff_features = ["Leftover Management"]
    admin_features = ["Visual Menu Search"]
    
    if feature_name in public_features:
        return True
    if not user:
        return False
    if feature_name in staff_features and user['role'] in ['staff', 'manager', 'chef', 'admin']:
        return True
    if feature_name in admin_features and user['role'] in ['admin']:
        return True
    return False

@auth_required
def leftover_management():
    """Simplified leftover management with integrated quiz"""
    st.title("♻️ Leftover Management")
    
    # Clear previous data when switching input methods
    if 'input_method' not in st.session_state:
        st.session_state.input_method = None
    if 'current_ingredients' not in st.session_state:
        st.session_state.current_ingredients = []
    if 'recipes' not in st.session_state:
        st.session_state.recipes = []
    
    # Simple input method selection
    st.subheader("📝 Add Ingredients")
    input_method = st.radio(
        "How would you like to add ingredients?",
        ["Manual Entry", "CSV Upload", "From Inventory"],
        horizontal=True
    )
    
    # Clear data if method changed
    if st.session_state.input_method != input_method:
        st.session_state.input_method = input_method
        st.session_state.current_ingredients = []
        st.session_state.recipes = []
    
    # Get ingredients based on selected method
    ingredients = []
    if input_method == "Manual Entry":
        ingredients_text = st.text_area(
            "Enter ingredients (one per line or comma-separated)",
            placeholder="tomatoes\nonions\nchicken\nrice",
            height=100
        )
        if ingredients_text:
            # Handle both line-separated and comma-separated
            if '\n' in ingredients_text:
                ingredients = [ing.strip() for ing in ingredients_text.split('\n') if ing.strip()]
            else:
                ingredients = [ing.strip() for ing in ingredients_text.split(',') if ing.strip()]
    
    elif input_method == "CSV Upload":
        uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
        if uploaded_file:
            try:
                import pandas as pd
                df = pd.read_csv(uploaded_file)
                if 'ingredient' in df.columns:
                    ingredients = df['ingredient'].dropna().tolist()
                else:
                    st.error("CSV must have an 'ingredient' column")
            except Exception as e:
                st.error(f"Error reading CSV: {str(e)}")
    
    elif input_method == "From Inventory":
        if st.button("Fetch from Inventory", type="primary"):
            try:
                # Simplified Firebase fetch
                firebase_ingredients, detailed_info = leftover_input_firebase()
                ingredients = firebase_ingredients
                if ingredients:
                    st.success(f"Found {len(ingredients)} ingredients from inventory")
                else:
                    st.warning("No ingredients found in inventory")
            except Exception as e:
                st.error(f"Error fetching from inventory: {str(e)}")
    
    # Store current ingredients
    if ingredients:
        st.session_state.current_ingredients = ingredients
    
    # Display current ingredients
    if st.session_state.current_ingredients:
        st.subheader("🥗 Current Ingredients")
        cols = st.columns(3)
        for i, ingredient in enumerate(st.session_state.current_ingredients):
            with cols[i % 3]:
                st.write(f"• {ingredient.title()}")
        
        # Recipe generation
        st.subheader("🍽️ Generate Recipes")
        col1, col2 = st.columns(2)
        with col1:
            num_recipes = st.slider("Number of recipes", 1, 5, 3)
        with col2:
            dietary_notes = st.text_input("Dietary requirements (optional)", 
                                        placeholder="vegetarian, gluten-free, etc.")
        
        if st.button("Generate Recipes", type="primary", use_container_width=True):
            with st.spinner("Creating recipes..."):
                try:
                    recipes = suggest_recipes(
                        st.session_state.current_ingredients, 
                        num_recipes, 
                        dietary_notes
                    )
                    st.session_state.recipes = recipes
                except Exception as e:
                    st.error(f"Error generating recipes: {str(e)}")
        
        # Display recipes
        if st.session_state.recipes:
            st.subheader("✨ Recipe Suggestions")
            for i, recipe in enumerate(st.session_state.recipes, 1):
                st.write(f"{i}. **{recipe}**")
        
        # Integrated Cooking Quiz
        st.divider()
        st.subheader("🧠 Test Your Knowledge")
        st.write("Take a quick quiz about cooking with your ingredients!")
        
        if st.button("Start Cooking Quiz", use_container_width=True):
            render_simple_quiz(st.session_state.current_ingredients)
    
    else:
        # Help section
        st.info("👆 Select an input method above to get started!")
        st.subheader("💡 How it works")
        st.write("""
        1. **Add ingredients** using one of the three methods
        2. **Generate recipes** based on your ingredients
        3. **Take a quiz** to test your cooking knowledge
        """)

def render_simple_quiz(ingredients):
    """Simple integrated quiz"""
    if 'quiz_active' not in st.session_state:
        st.session_state.quiz_active = False
    if 'quiz_score' not in st.session_state:
        st.session_state.quiz_score = None
    
    if not st.session_state.quiz_active:
        st.session_state.quiz_active = True
        st.session_state.quiz_score = None
        st.rerun()
    
    # Simple quiz questions
    questions = [
        {
            "question": "What's the safe cooking temperature for chicken?",
            "options": ["145°F", "160°F", "165°F", "180°F"],
            "correct": 2,
            "explanation": "Chicken should be cooked to 165°F to be safe."
        },
        {
            "question": "Which cooking method uses dry heat?",
            "options": ["Boiling", "Steaming", "Roasting", "Poaching"],
            "correct": 2,
            "explanation": "Roasting uses dry heat in an oven."
        },
        {
            "question": "What does 'sauté' mean?",
            "options": ["Cook slowly", "Cook quickly in fat", "Cook in water", "Cook in oven"],
            "correct": 1,
            "explanation": "Sauté means to cook quickly in a small amount of fat."
        }
    ]
    
    if st.session_state.quiz_score is None:
        st.write("Answer these quick questions:")
        answers = []
        
        for i, q in enumerate(questions):
            st.write(f"**{i+1}. {q['question']}**")
            answer = st.radio(f"Select answer for question {i+1}:", 
                            q['options'], 
                            key=f"q{i}",
                            index=None)
            if answer:
                answers.append(q['options'].index(answer))
            else:
                answers.append(-1)
        
        if st.button("Submit Quiz"):
            if -1 not in answers:
                score = sum(1 for i, ans in enumerate(answers) if ans == questions[i]['correct'])
                st.session_state.quiz_score = score
                st.rerun()
            else:
                st.error("Please answer all questions!")
    
    else:
        # Show results
        score = st.session_state.quiz_score
        total = len(questions)
        percentage = (score / total) * 100
        
        st.success(f"Quiz Complete! Score: {score}/{total} ({percentage:.0f}%)")
        
        if percentage >= 80:
            st.balloons()
            st.write("🎉 Excellent! You know your cooking basics!")
        elif percentage >= 60:
            st.write("👍 Good job! Keep learning!")
        else:
            st.write("📚 Keep studying! Practice makes perfect!")
        
        if st.button("Take Quiz Again"):
            st.session_state.quiz_active = False
            st.session_state.quiz_score = None
            st.rerun()

@auth_required  
def event_planning():
    """Simple event planning feature"""
    st.title("🎉 Event Planning")
    st.info("Plan your restaurant events here!")
    
    event_type = st.selectbox("Event Type", 
                             ["Birthday Party", "Corporate Event", "Wedding", "Other"])
    
    guest_count = st.number_input("Number of Guests", min_value=1, max_value=200, value=20)
    
    event_notes = st.text_area("Special Requirements", 
                              placeholder="Any dietary restrictions, themes, or special requests...")
    
    if st.button("Generate Event Plan", type="primary"):
        st.success("Event plan generated!")
        st.write(f"**Event:** {event_type}")
        st.write(f"**Guests:** {guest_count}")
        st.write(f"**Notes:** {event_notes}")

def main():
    # Initialize session
    initialize_session_state()
    
    # Sidebar authentication
    st.sidebar.title("🔐 Login")
    auth_status = render_auth_ui()
    
    # Main content
    if not st.session_state.is_authenticated:
        st.title("🍽️ Smart Restaurant Management")
        st.markdown("""
        Welcome to our simple restaurant management system!
        
        **Features:**
        - 🥗 **Leftover Management** - Turn leftovers into recipes
        - 🧠 **Cooking Quiz** - Test your culinary knowledge  
        - 🎉 **Event Planning** - Plan restaurant events
        
        Please log in to get started.
        """)
        return
    
    # Feature selection
    st.sidebar.divider()
    st.sidebar.header("📋 Features")
    
    features = ["Leftover Management", "Event Planning"]
    available_features = [f for f in features if check_feature_access(f)]
    
    selected_feature = st.sidebar.selectbox("Choose Feature", available_features)
    
    # Display selected feature
    if selected_feature == "Leftover Management":
        leftover_management()
    elif selected_feature == "Event Planning":
        event_planning()

if __name__ == "__main__":
    main()
