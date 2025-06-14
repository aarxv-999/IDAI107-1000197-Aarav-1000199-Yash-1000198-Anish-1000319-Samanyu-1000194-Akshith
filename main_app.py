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
        st.write(f"Found {len(all_leftovers)} valid ingredients")
        
        # Display priority information if Firebase ingredients are used
        if firebase_detailed_info:
            st.info("🎯 Ingredients are prioritized by expiry date - closest to expire first!")
            st.success("✅ All ingredients shown are still valid (not expired)")
            
            # Show urgency summary
            current_date = datetime.now().date()
            urgent_count = len([item for item in firebase_detailed_info if 0 <= item['days_until_expiry'] <= 3])
            expires_today = len([item for item in firebase_detailed_info if item['days_until_expiry'] == 0])
            
            if expires_today > 0:
                st.error(f"🚨 {expires_today} ingredients expire TODAY - use them immediately!")
            elif urgent_count > 0:
                st.warning(f"⚠️ {urgent_count} ingredients expire within 3 days - recipes will prioritize these!")
        
        # Create a dropdown for ingredients with expiry info
        with st.expander("Available Valid Ingredients", expanded=False):
            if firebase_detailed_info:
                # Display Firebase ingredients with expiry info
                for item in firebase_detailed_info:
                    days_left = item['days_until_expiry']
                    
                    # Color code based on urgency
                    if days_left == 0:
                        st.error(f"🟠 **{item['name']}** - Expires: {item['expiry_date']} (expires TODAY!)")
                    elif days_left == 1:
                        st.error(f"🔴 **{item['name']}** - Expires: {item['expiry_date']} (expires tomorrow)")
                    elif days_left <= 3:
                        st.warning(f"🟡 **{item['name']}** - Expires: {item['expiry_date']} (expires in {days_left} days)")
                    elif days_left <= 7:
                        st.success(f"🟢 **{item['name']}** - Expires: {item['expiry_date']} (expires in {days_left} days)")
                    else:
                        st.info(f"⚪ **{item['name']}** - Expires: {item['expiry_date']} (expires in {days_left} days)")
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
            st.info("🤖 Ready to generate recipes using your valid inventory ingredients!")
            
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
                urgent_ingredients = [item['name'] for item in firebase_detailed_info if 0 <= item['days_until_expiry'] <= 3]
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
        1. **Firebase Integration**: Automatically fetch valid ingredients from your inventory
        2. **Expiry Filtering**: Only shows ingredients that haven't expired yet
        3. **Smart Prioritization**: Ingredients closest to expiry are prioritized in recipe suggestions
        4. **AI-Powered Recipes**: Get personalized recipe ideas that reduce food waste
        5. **Manual Options**: Also supports CSV upload and manual ingredient entry
        """)
        
        # Example workflow
        st.markdown("### Example Workflow")
        st.markdown("""
        1. ✅ Check "Use current inventory from Firebase"
        2. 🎯 Select max ingredients to use (prioritized by expiry)
        3. 📥 Click "Fetch Valid Ingredients" (expired items are automatically filtered out)
        4. 🚀 Click "Generate Smart Recipes"
        5. 🍽️ Get recipes that use ingredients expiring soonest!
        """)
        
        # Current date info
        current_date = datetime.now().strftime("%B %d, %Y")
        st.info(f"📅 Current date: {current_date} - Only ingredients expiring on or after this date will be used")
