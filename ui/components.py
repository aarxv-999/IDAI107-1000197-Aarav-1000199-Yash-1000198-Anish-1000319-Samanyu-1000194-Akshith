def leftover_input_firebase() -> Tuple[List[str], List[Dict]]:
    """
    UI component to fetch ingredients from Firebase inventory with expiry priority
    Only shows and uses ingredients that haven't expired yet
    
    Returns:
        Tuple[List[str], List[Dict]]: (ingredient_names, detailed_ingredient_info)
    """
    st.sidebar.subheader("Current Inventory")
    use_firebase = st.sidebar.checkbox("Use current inventory from Firebase", help="Fetch valid ingredients from your current inventory, prioritized by expiry date")
    leftovers = []
    detailed_info = []
    
    if use_firebase:
        # Add option to select number of ingredients to use
        max_ingredients = st.sidebar.slider(
            "Max ingredients to use", 
            min_value=3, 
            max_value=15, 
            value=8,
            help="Select how many valid ingredients to use (prioritized by expiry date)"
        )
        
        if st.sidebar.button("Fetch Valid Ingredients", type="primary"):
            try:
                # Show spinner in the main area since sidebar doesn't support spinner
                with st.spinner("Fetching valid ingredients from inventory..."):
                    # Fetch ingredients from Firebase (already filtered for valid ones and sorted by expiry date)
                    firebase_ingredients = fetch_ingredients_from_firebase()
                    
                    if firebase_ingredients:
                        # Get ingredients prioritized by expiry date
                        leftovers, detailed_info = get_ingredients_by_expiry_priority(
                            firebase_ingredients, max_ingredients
                        )
                        
                        st.sidebar.success(f"Found {len(leftovers)} valid ingredients")
                        
                        # Show summary of filtering
                        total_in_db = len(firebase_ingredients) + len([ing for ing in firebase_ingredients if not is_ingredient_valid(ing.get('Expiry Date', ''))])
                        expired_count = total_in_db - len(firebase_ingredients) if total_in_db > len(firebase_ingredients) else 0
                        
                        if expired_count > 0:
                            st.sidebar.info(f"ℹ️ Filtered out {expired_count} expired ingredients")
                        
                        # Show a preview of valid ingredients with expiry info
                        with st.sidebar.expander("Valid Ingredients", expanded=True):
                            current_date = datetime.now().date()
                            
                            for item in detailed_info:
                                days_left = item['days_until_expiry']
                                
                                # Color code based on urgency (only for valid ingredients)
                                if days_left == 0:
                                    urgency_color = "🟠"  # Orange for expires today
                                    urgency_text = "expires today"
                                elif days_left == 1:
                                    urgency_color = "🔴"  # Red for expires tomorrow
                                    urgency_text = "expires tomorrow"
                                elif days_left <= 3:
                                    urgency_color = "🟡"  # Yellow for expires soon (2-3 days)
                                    urgency_text = f"expires in {days_left} days"
                                elif days_left <= 7:
                                    urgency_color = "🟢"  # Green for moderate (4-7 days)
                                    urgency_text = f"expires in {days_left} days"
                                else:
                                    urgency_color = "⚪"  # White for later
                                    urgency_text = f"expires in {days_left} days"
                                
                                st.sidebar.markdown(f"{urgency_color} **{item['name']}**  \n"
                                                   f"Expires: {item['expiry_date']} ({urgency_text})  \n"
                                                   f"Type: {item['type']}")
                                st.sidebar.divider()
                        
                        # Store in session state for recipe generation
                        st.session_state.firebase_ingredients = leftovers
                        st.session_state.firebase_detailed_info = detailed_info
                        
                    else:
                        st.sidebar.warning("No valid ingredients found in inventory")
                        st.sidebar.info("All ingredients may have expired. Please check your inventory dates.")
                        
            except Exception as err:
                st.sidebar.error(f"Error fetching ingredients: {str(err)}")
    
    # Return stored ingredients if they exist
    if 'firebase_ingredients' in st.session_state:
        return st.session_state.firebase_ingredients, st.session_state.get('firebase_detailed_info', [])
    
    return leftovers, detailed_info
