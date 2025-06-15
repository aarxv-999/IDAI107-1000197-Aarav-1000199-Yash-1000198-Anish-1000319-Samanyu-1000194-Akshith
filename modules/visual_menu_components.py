"""
Visual Menu UI Components for the Smart Restaurant Menu Management App.
Integrated with the main gamification system.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from modules.visual_menu_services import (
    get_visual_menu_firebase_db, configure_vision_api, configure_visual_gemini_ai,
    fetch_menu_items, fetch_order_history, fetch_challenge_entries,
    preprocess_image, analyze_image_with_vision, find_matching_dishes,
    generate_ai_dish_analysis, generate_personalized_recommendations,
    filter_menu_by_allergies, save_challenge_entry, update_challenge_interaction,
    save_order, award_visual_menu_xp, calculate_challenge_score, ALLERGY_MAPPING
)
from ui.components import show_xp_notification
import logging

logger = logging.getLogger(__name__)

def render_visual_menu_search():
    """Main function to render Visual Menu Challenge & Recommendation Platform"""
    st.title("🍽️ Visual Menu Challenge & Recommendation Platform")
    
    # Get current user
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    user_id = user.get('user_id')
    username = user.get('username', 'Unknown User')
    
    # Initialize database connection
    db = get_visual_menu_firebase_db()
    if not db:
        st.error("❌ Database connection failed. Please check your configuration.")
        return
    
    # Initialize AI services
    vision_client = configure_vision_api()
    gemini_model = configure_visual_gemini_ai()
    
    # Show Vision API status
    if not vision_client:
        st.warning("⚠️ Google Cloud Vision API not configured. Image analysis will be limited.")
    
    # Sidebar preferences
    st.sidebar.header("🎯 Customer Preferences")
    allergies = st.sidebar.multiselect(
        "Dietary Restrictions & Allergies", 
        ["Nut-Free", "Shellfish-Free", "Soy-Free", "Dairy-Free", "Veg", "Non-Veg", "Gluten-Free", "Vegan"], 
        default=[],
        help="Select your dietary restrictions and allergies"
    )
    
    # Create tabs
    tabs = st.tabs(["📷 AI Dish Detection", "🎯 Personalized Menu", "⚙️ Custom Filters", "🏅 Visual Menu Challenge", "📊 Leaderboard"])
    
    with tabs[0]:
        render_ai_dish_detection(db, vision_client, gemini_model, allergies, user_id)
    
    with tabs[1]:
        render_personalized_menu(db, gemini_model, allergies, user_id)
    
    with tabs[2]:
        render_custom_filters(db, allergies)
    
    with tabs[3]:
        render_visual_challenge(db, user_role, username, user_id)
    
    with tabs[4]:
        render_leaderboard(db, user_id)

def render_ai_dish_detection(db, vision_client, gemini_model, allergies, user_id):
    """Render AI dish detection tab"""
    st.header("📷 Visual Dish Detection (AI + Vision API)")
    st.markdown("Upload a food image and let AI identify dishes from our menu!")
    
    # XP info
    st.info("💡 **Earn 15 XP** for each dish detection analysis!")
    
    uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        # Preprocess image
        image, content = preprocess_image(uploaded_file)
        
        if image and content:
            st.image(image, caption="Uploaded Image", use_column_width=True)
            
            with st.spinner("🔍 Analyzing image with AI..."):
                # Analyze with Vision API (if available)
                labels, objects, texts, style_indicators = analyze_image_with_vision(vision_client, content)
                
                # Combine detected elements
                combined_labels = [desc.lower() for desc, score in labels + objects]
                combined_labels = list(set(combined_labels + texts))
                
                if combined_labels:
                    st.write(f"**Detected Elements:** {', '.join(combined_labels[:10])}")  # Show first 10
                else:
                    st.write("**Detected Elements:** Using basic image analysis")
                
                if style_indicators:
                    st.write(f"**Detected Plating Style:** {', '.join(style_indicators)}")
                
                # Check if food-related
                food_related = any(
                    label.lower() in ["food", "dish", "meal"] or "food" in label.lower() or 
                    any(food_term in label.lower() for food_term in ["pizza", "burger", "pasta", "salad", "sushi", "chicken", "beef"])
                    for label in combined_labels
                ) if combined_labels else True  # Assume food if no labels detected
                
                if not food_related and combined_labels:
                    st.warning("⚠️ The image doesn't appear to contain food. Please upload a food-related image.")
                    return
                
                # Fetch menu and find matches
                menu_items = fetch_menu_items(db)
                if not menu_items:
                    st.error("❌ No menu items found. Please check your menu database.")
                    return
                
                # Find matching dishes
                matching_dishes = find_matching_dishes(menu_items, combined_labels)
                
                # Generate AI analysis
                menu_text = "\n".join([
                    f"- {item.get('name', 'Unknown')}: {item.get('description', '')} (Ingredients: {', '.join(item.get('ingredients', []))})"
                    for item in menu_items[:20]  # Limit to first 20 for prompt size
                ])
                
                ai_analysis = generate_ai_dish_analysis(
                    gemini_model, labels, objects, texts, style_indicators, allergies, menu_text
                )
                
                # Display results
                st.success("✅ **AI Dish Analysis:**")
                st.markdown(ai_analysis)
                
                # Display matching dishes table
                if matching_dishes:
                    st.subheader("🎯 Related Menu Items")
                    df = pd.DataFrame([
                        {
                            "Dish Name": dish['name'],
                            "Description": dish['description'][:100] + "..." if len(dish['description']) > 100 else dish['description'],
                            "Ingredients": ', '.join(dish['ingredients'][:5]) + ("..." if len(dish['ingredients']) > 5 else ""),
                            "Similarity Score": f"{dish['score']}%"
                        }
                        for dish in matching_dishes
                    ])
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("ℹ️ No closely related menu items found based on image analysis.")
                
                # Award XP for using dish detection
                if user_id:
                    xp_earned = award_visual_menu_xp(user_id, 15, "dish_detection")
                    if xp_earned > 0:
                        show_xp_notification(15, "AI Dish Detection")
        else:
            st.error("❌ Failed to process the uploaded image. Please try again.")

def render_personalized_menu(db, gemini_model, allergies, user_id):
    """Render personalized menu recommendations tab - AI-powered without order history"""
    st.header("🎯 Personalized AI Menu")
    st.markdown("Get AI-powered menu recommendations based on your preferences and our smart analysis!")
    
    # XP info
    st.info("💡 **Earn 20 XP** for generating personalized recommendations!")
    
    # User preferences section
    st.subheader("👤 Your Preferences (Optional)")
    
    # Load existing preferences if available
    user_prefs = {}
    if user_id and db:
        try:
            prefs_doc = db.collection("user_preferences").document(user_id).get()
            if prefs_doc.exists:
                user_prefs = prefs_doc.to_dict()
                st.success("✅ Loaded your saved preferences!")
        except:
            pass
    
    # Preference input
    col1, col2 = st.columns(2)
    
    with col1:
        # Get available cuisines from menu
        menu_items = fetch_menu_items(db)
        available_cuisines = list(set([item.get('cuisine', 'Unknown') for item in menu_items if item.get('cuisine')]))
        
        favorite_cuisines = st.multiselect(
            "Favorite Cuisines",
            available_cuisines,
            default=user_prefs.get('favorite_cuisines', []),
            help="Select cuisines you enjoy most"
        )
    
    with col2:
        available_categories = list(set([item.get('category', 'Unknown') for item in menu_items if item.get('category')]))
        
        preferred_categories = st.multiselect(
            "Preferred Categories",
            available_categories,
            default=user_prefs.get('preferred_categories', []),
            help="Select meal categories you prefer"
        )
    
    # Save preferences option
    if st.button("💾 Save My Preferences"):
        if user_id and db:
            try:
                prefs_data = {
                    'user_id': user_id,
                    'favorite_cuisines': favorite_cuisines,
                    'preferred_categories': preferred_categories,
                    'last_updated': datetime.now().isoformat()
                }
                db.collection("user_preferences").document(user_id).set(prefs_data)
                st.success("✅ Preferences saved!")
            except Exception as e:
                st.error(f"❌ Error saving preferences: {str(e)}")
        else:
            st.warning("⚠️ Please log in to save preferences")
    
    # Recommendation options
    st.subheader("🤖 AI Recommendation Options")
    
    col3, col4 = st.columns(2)
    
    with col3:
        recommendation_type = st.selectbox(
            "Recommendation Style",
            ["Balanced Variety", "Cuisine Focus", "Dietary Optimized", "Chef's Special", "Quick & Easy"]
        )
        
    with col4:
        meal_context = st.selectbox(
            "Meal Context",
            ["Any Time", "Breakfast", "Lunch", "Dinner", "Snack", "Special Occasion"]
        )
    
    # Advanced options
    with st.expander("🔧 Advanced Options"):
        include_description = st.checkbox("Include detailed descriptions", value=True)
        include_ingredients = st.checkbox("Show key ingredients", value=True)
        num_recommendations = st.slider("Number of recommendations", 3, 10, 5)
    
    # Generate recommendations button
    if st.button("🚀 Generate AI Personalized Recommendations", type="primary"):
        if not gemini_model:
            st.error("❌ Gemini AI not configured. Please check your API key.")
            return
            
        with st.spinner("🤖 AI is analyzing your preferences and our menu..."):
            
            if not menu_items:
                st.error("❌ No menu items found.")
                return
            
            # Create comprehensive menu context for AI
            menu_context = []
            for item in menu_items:
                menu_context.append({
                    'name': item.get('name', 'Unknown'),
                    'category': item.get('category', 'Unknown'),
                    'cuisine': item.get('cuisine', 'Unknown'),
                    'description': item.get('description', ''),
                    'ingredients': item.get('ingredients', []),
                    'diet': item.get('diet', []),
                    'cook_time': item.get('cook_time', 'Unknown'),
                    'types': item.get('types', [])
                })
            
            # Build AI prompt
            user_profile = {
                'dietary_restrictions': allergies,
                'favorite_cuisines': favorite_cuisines,
                'preferred_categories': preferred_categories,
                'recommendation_type': recommendation_type,
                'meal_context': meal_context
            }
            
            try:
                recommendations = generate_smart_personalized_recommendations(
                    gemini_model, menu_context, user_profile, num_recommendations, 
                    include_description, include_ingredients
                )
                
                # Display recommendations
                st.success("✅ **Your AI-Powered Personalized Recommendations:**")
                st.markdown(recommendations)
                
                # Award XP for generating recommendations
                if user_id:
                    xp_earned = award_visual_menu_xp(user_id, 20, "personalized_recommendations")
                    if xp_earned > 0:
                        show_xp_notification(20, "Personalized Menu Recommendations")
                        
            except Exception as e:
                st.error(f"❌ Error generating recommendations: {str(e)}")

def generate_smart_personalized_recommendations(gemini_model, menu_context, user_profile, num_recommendations, include_description, include_ingredients):
    """Generate smart personalized recommendations using Gemini AI"""
    
    # Convert menu context to text
    menu_text = "\n".join([
        f"- {item['name']} ({item['category']}, {item['cuisine']}): {item['description']} "
        f"[Ingredients: {', '.join(item['ingredients'][:5])}] "
        f"[Diet: {', '.join(item['diet']) if isinstance(item['diet'], list) else item['diet']}] "
        f"[Cook Time: {item['cook_time']}]"
        for item in menu_context
    ])
    
    # Build comprehensive prompt
    prompt = f"""
    You are a professional restaurant AI sommelier and menu curator. Analyze the following menu and user profile to provide {num_recommendations} personalized dish recommendations.

    **User Profile:**
    - Dietary Restrictions: {', '.join(user_profile['dietary_restrictions']) if user_profile['dietary_restrictions'] else 'None'}
    - Favorite Cuisines: {', '.join(user_profile['favorite_cuisines']) if user_profile['favorite_cuisines'] else 'No preference'}
    - Preferred Categories: {', '.join(user_profile['preferred_categories']) if user_profile['preferred_categories'] else 'No preference'}
    - Recommendation Style: {user_profile['recommendation_type']}
    - Meal Context: {user_profile['meal_context']}

    **Available Menu:**
    {menu_text}

    **Instructions:**
    1. Select {num_recommendations} dishes that best match the user's profile
    2. Ensure variety in cuisines and categories unless user specifically prefers certain ones
    3. Respect all dietary restrictions strictly
    4. Consider the meal context and recommendation style
    5. For "Balanced Variety": Mix different cuisines and categories
    6. For "Cuisine Focus": Prioritize user's favorite cuisines
    7. For "Dietary Optimized": Focus on dishes that perfectly match dietary needs
    8. For "Chef's Special": Recommend unique or special items
    9. For "Quick & Easy": Prioritize dishes with shorter cook times

    **Output Format:**
    For each recommendation, provide:
    
    ## 🍽️ [Dish Name]
    **Why recommended:** [Brief explanation of why this matches the user]
    **Cuisine:** [Cuisine type] | **Category:** [Category] | **Cook Time:** [Time]
    {"**Description:** [Description]" if include_description else ""}
    {"**Key Ingredients:** [List 3-4 main ingredients]" if include_ingredients else ""}
    
    ---

    Make recommendations feel personal and explain the reasoning clearly. Focus on dishes that truly match the user's preferences and dietary needs.
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error generating recommendations: {str(e)}"

def render_custom_filters(db, allergies):
    """Render custom menu filters tab - realistic implementation based on actual Firebase structure"""
    st.header("⚙️ Custom Menu Filters")
    st.markdown("Filter our menu based on available data from your restaurant database!")
    
    # Fetch menu items first to get available options
    menu_items = fetch_menu_items(db)
    if not menu_items:
        st.error("❌ No menu items found.")
        return
    
    # Extract unique values from database for realistic filter options
    available_categories = list(set([item.get('category', 'Unknown') for item in menu_items if item.get('category')]))
    available_cuisines = list(set([item.get('cuisine', 'Unknown') for item in menu_items if item.get('cuisine')]))
    available_diets = list(set([diet for item in menu_items for diet in (item.get('diet', []) if isinstance(item.get('diet'), list) else [item.get('diet')] if item.get('diet') else [])]))
    available_types = list(set([type_item for item in menu_items for type_item in (item.get('types', []) if isinstance(item.get('types'), list) else [item.get('types')] if item.get('types') else [])]))
    
    # Main filter options based on actual database fields
    st.subheader("🍽️ Menu Categories & Types")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_category = st.selectbox("Category", ["All"] + sorted(available_categories))
        selected_cuisine = st.selectbox("Cuisine", ["All"] + sorted(available_cuisines))
        
    with col2:
        selected_diet = st.selectbox("Dietary Type", ["All"] + sorted(available_diets))
        selected_type = st.selectbox("Special Types", ["All"] + sorted(available_types))

    # Cook time filter (based on actual cook_time field)
    st.subheader("⏱️ Cooking Time")
    cook_time_filter = st.selectbox(
        "Maximum Cooking Time", 
        ["All", "Quick (≤ 20 min)", "Medium (21-40 min)", "Long (> 40 min)"]
    )
    
    # Ingredient-based filters
    st.subheader("🥘 Ingredient Preferences")
    col3, col4 = st.columns(2)
    
    with col3:
        must_include = st.text_input("Must Include Ingredient", placeholder="e.g., paneer, chicken")
        
    with col4:
        must_exclude = st.text_input("Must Exclude Ingredient", placeholder="e.g., onion, garlic")

    # AI-powered smart filtering option
    with st.expander("🤖 AI Smart Filtering (Powered by Gemini)"):
        st.markdown("Use AI to find dishes based on natural language descriptions!")
        ai_query = st.text_area(
            "Describe what you're looking for", 
            placeholder="e.g., 'Something spicy and vegetarian for dinner' or 'Light appetizer with paneer'"
        )
        use_ai_filter = st.checkbox("Enable AI Smart Filtering")

    # Apply filters button
    if st.button("🔍 Apply Filters", type="primary"):
        with st.spinner("Filtering menu items based on your database..."):
            
            # Start with all menu items
            filtered_menu = menu_items.copy()
            
            # Apply allergy filters first (existing functionality)
            filtered_menu, debug_info = filter_menu_by_allergies(filtered_menu, allergies)
            
            # Apply category filter
            if selected_category != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if item.get('category', '').lower() == selected_category.lower()
                ]
            
            # Apply cuisine filter
            if selected_cuisine != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if item.get('cuisine', '').lower() == selected_cuisine.lower()
                ]
            
            # Apply diet filter
            if selected_diet != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if selected_diet in (item.get('diet', []) if isinstance(item.get('diet'), list) else [item.get('diet')] if item.get('diet') else [])
                ]
            
            # Apply type filter
            if selected_type != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if selected_type in (item.get('types', []) if isinstance(item.get('types'), list) else [item.get('types')] if item.get('types') else [])
                ]
            
            # Apply cook time filter
            if cook_time_filter != "All":
                def extract_cook_time_minutes(cook_time_str):
                    """Extract minutes from cook_time string like '30 minutes'"""
                    if not cook_time_str:
                        return 999  # Unknown cook time, treat as long
                    try:
                        # Extract number from string like "30 minutes"
                        import re
                        numbers = re.findall(r'\d+', str(cook_time_str))
                        return int(numbers[0]) if numbers else 999
                    except:
                        return 999
                
                if cook_time_filter == "Quick (≤ 20 min)":
                    filtered_menu = [item for item in filtered_menu if extract_cook_time_minutes(item.get('cook_time')) <= 20]
                elif cook_time_filter == "Medium (21-40 min)":
                    filtered_menu = [item for item in filtered_menu if 21 <= extract_cook_time_minutes(item.get('cook_time')) <= 40]
                elif cook_time_filter == "Long (> 40 min)":
                    filtered_menu = [item for item in filtered_menu if extract_cook_time_minutes(item.get('cook_time')) > 40]
            
            # Apply ingredient inclusion filter
            if must_include:
                filtered_menu = [
                    item for item in filtered_menu 
                    if any(must_include.lower() in ing.lower() for ing in item.get('ingredients', []))
                ]
            
            # Apply ingredient exclusion filter
            if must_exclude:
                filtered_menu = [
                    item for item in filtered_menu 
                    if not any(must_exclude.lower() in ing.lower() for ing in item.get('ingredients', []))
                ]
            
            # Apply AI smart filtering if enabled
            if use_ai_filter and ai_query:
                try:
                    gemini_model = configure_visual_gemini_ai()
                    if gemini_model:
                        # Create menu context for AI
                        menu_context = "\n".join([
                            f"- {item.get('name', 'Unknown')}: {item.get('description', '')} "
                            f"(Category: {item.get('category', 'Unknown')}, "
                            f"Cuisine: {item.get('cuisine', 'Unknown')}, "
                            f"Diet: {', '.join(item.get('diet', []) if isinstance(item.get('diet'), list) else [str(item.get('diet', ''))])}, "
                            f"Ingredients: {', '.join(item.get('ingredients', []))})"
                            for item in filtered_menu
                        ])
                        
                        ai_prompt = f"""
                        Based on the user query: "{ai_query}"
                        
                        From the following menu items, identify which ones best match the user's request:
                        {menu_context}
                        
                        Return only the exact dish names that match, one per line, no additional text.
                        If no dishes match well, return "NO_MATCHES".
                        """
                        
                        response = gemini_model.generate_content(ai_prompt)
                        ai_matches = response.text.strip().split('\n')
                        
                        if ai_matches and ai_matches[0] != "NO_MATCHES":
                            # Filter menu based on AI recommendations
                            ai_filtered = []
                            for item in filtered_menu:
                                for match in ai_matches:
                                    if match.strip().lower() in item.get('name', '').lower():
                                        ai_filtered.append(item)
                                        break
                            
                            if ai_filtered:
                                filtered_menu = ai_filtered
                                st.info(f"🤖 AI found {len(ai_filtered)} dishes matching your description!")
                            else:
                                st.warning("🤖 AI couldn't find exact matches, showing regular filtered results.")
                        else:
                            st.warning("🤖 AI couldn't find dishes matching your description, showing regular filtered results.")
                            
                except Exception as e:
                    st.warning(f"🤖 AI filtering unavailable: {str(e)}")
            
            # Display results
            if filtered_menu:
                st.success(f"✅ Found {len(filtered_menu)} dishes matching your criteria")
                
                # Create realistic display dataframe based on actual database fields
                display_data = []
                for item in filtered_menu:
                    display_data.append({
                        "Dish Name": item.get('name', 'Unknown'),
                        "Category": item.get('category', 'Unknown'),
                        "Cuisine": item.get('cuisine', 'Unknown'),
                        "Cook Time": item.get('cook_time', 'Unknown'),
                        "Description": item.get('description', '')[:60] + ("..." if len(item.get('description', '')) > 60 else ""),
                        "Diet": ', '.join(item.get('diet', []) if isinstance(item.get('diet'), list) else [str(item.get('diet', ''))]),
                        "Ingredients": ', '.join(item.get('ingredients', [])[:3]) + ("..." if len(item.get('ingredients', [])) > 3 else ""),
                        "Special Types": ', '.join(item.get('types', []) if isinstance(item.get('types'), list) else [str(item.get('types', ''))])
                    })
                
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True)
                
                # Show active filters summary
                active_filters = []
                if selected_category != "All": active_filters.append(f"Category: {selected_category}")
                if selected_cuisine != "All": active_filters.append(f"Cuisine: {selected_cuisine}")
                if selected_diet != "All": active_filters.append(f"Diet: {selected_diet}")
                if selected_type != "All": active_filters.append(f"Type: {selected_type}")
                if cook_time_filter != "All": active_filters.append(f"Cook Time: {cook_time_filter}")
                if must_include: active_filters.append(f"Includes: {must_include}")
                if must_exclude: active_filters.append(f"Excludes: {must_exclude}")
                if allergies: active_filters.append(f"Allergies: {', '.join(allergies)}")
                
                if active_filters:
                    st.info(f"🎯 **Active Filters:** {' | '.join(active_filters)}")
                
            else:
                st.warning("⚠️ No menu items match your selected criteria.")
                
                # Show helpful debug information
                with st.expander("🔍 Filter Debug Information"):
                    st.write("**Available in Database:**")
                    st.write(f"- Categories: {', '.join(available_categories)}")
                    st.write(f"- Cuisines: {', '.join(available_cuisines)}")
                    st.write(f"- Diet Types: {', '.join(available_diets)}")
                    st.write(f"- Special Types: {', '.join(available_types)}")
                    st.write(f"- Total Menu Items: {len(menu_items)}")
                    
                    st.write("**Your Selected Filters:**")
                    st.write(f"- Category: {selected_category}")
                    st.write(f"- Cuisine: {selected_cuisine}")
                    st.write(f"- Diet: {selected_diet}")
                    st.write(f"- Type: {selected_type}")
                    st.write(f"- Cook Time: {cook_time_filter}")
                    st.write(f"- Must Include: {must_include}")
                    st.write(f"- Must Exclude: {must_exclude}")
                    st.write(f"- Allergies: {allergies}")

def render_visual_challenge(db, user_role, username, user_id):
    """Render visual menu challenge tab (Staff/Chef/Admin only)"""
    st.header("🏅 Visual Menu Challenge Submission")
    
    # Check access permissions
    if user_role not in ['staff', 'chef', 'admin']:
        st.warning("⚠️ This feature is available for Staff, Chefs, and Administrators only.")
        st.info("💡 Customers can vote on staff submissions in the Leaderboard tab!")
        return
    
    st.markdown("Submit your signature dish photos and compete with other staff members!")
    
    # XP info for staff
    st.info("""
    💡 **XP Rewards for Staff:**
    • Submit dish photo: **+30 XP**
    • Customer likes your dish: **+8 XP per like**
    • Customer views your dish: **+3 XP per view**
    • Customer orders your dish: **+15 XP per order**
    """)
    
    # Challenge submission form
    with st.form("challenge_form"):
        st.markdown("#### 📸 Submit Your Dish")
        
        col1, col2 = st.columns(2)
        
        with col1:
            dish_name = st.text_input("Dish Name", placeholder="e.g., Truffle Pasta Supreme")
            plating_style = st.text_input("Plating Style", placeholder="e.g., Modern, Classic, Rustic")
        
        with col2:
            ingredients = st.text_area("Ingredients (comma separated)", placeholder="pasta, truffle oil, parmesan, garlic")
            
        # Challenge options
        col3, col4 = st.columns(2)
        with col3:
            trendy = st.checkbox("Matches current food trends", help="Is this dish following current culinary trends?")
        with col4:
            diet_match = st.checkbox("Matches dietary preferences", help="Does this dish cater to popular dietary preferences?")
        
        # Image upload
        challenge_image = st.file_uploader("Dish Photo", type=["jpg", "png", "jpeg"], help="Upload a high-quality photo of your dish")
        
        submitted = st.form_submit_button("🚀 Submit Dish Challenge", type="primary")
        
        if submitted:
            if not dish_name or not ingredients:
                st.error("❌ Please fill in Dish Name and Ingredients.")
            elif not challenge_image:
                st.error("❌ Please upload a dish photo.")
            else:
                # Save challenge entry
                success, message = save_challenge_entry(
                    db, username, dish_name, ingredients, plating_style, trendy, diet_match
                )
                
                if success:
                    st.success(f"✅ {message}")
                    
                    # Award XP for submission
                    if user_id:
                        xp_earned = award_visual_menu_xp(user_id, 30, "challenge_submission")
                        if xp_earned > 0:
                            show_xp_notification(30, "Visual Challenge Submission")
                    
                    # Clear form by rerunning
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def render_leaderboard(db, user_id):
    """Render leaderboard and voting tab"""
    st.header("📊 Leaderboard & Customer Voting")
    st.markdown("Vote on staff-submitted dishes and see who's leading the competition!")
    
    # XP info for customers
    st.info("💡 **Earn 5 XP** for each vote you cast!")
    
    # Fetch challenge entries
    entries = fetch_challenge_entries(db)
    
    if not entries:
        st.info("📝 No challenge entries yet. Staff members can submit dishes in the Visual Menu Challenge tab!")
        return
    
    # Display challenge entries for voting
    st.subheader("🗳️ Vote on Staff Dishes")
    
    for entry in entries:
        with st.container():
            st.markdown("---")
            
            # Dish header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"🍽️ {entry.get('dish', 'Unknown Dish')}")
                st.write(f"**Chef:** {entry.get('staff', 'Unknown')}")
                st.write(f"**Style:** {entry.get('style', 'Not specified')}")
                st.write(f"**Ingredients:** {', '.join(entry.get('ingredients', []))}")
            
            with col2:
                # Display current stats
                st.metric("Score", calculate_challenge_score(entry))
            
            # Voting buttons
            col3, col4, col5 = st.columns(3)
            
            with col3:
                if st.button(f"❤️ Like ({entry.get('likes', 0)})", key=f"like_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'likes'):
                        # Award XP to customer for voting
                        if user_id:
                            award_visual_menu_xp(user_id, 5, "customer_vote")
                            show_xp_notification(5, "Voting on Dish")
                        
                        # Award XP to staff member for receiving like
                        staff_user_id = entry.get('staff_user_id')  # Would need to store this
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 8, "received_like")
                        
                        st.rerun()
            
            with col4:
                if st.button(f"👀 View ({entry.get('views', 0)})", key=f"view_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'views'):
                        # Award XP to customer for engagement
                        if user_id:
                            award_visual_menu_xp(user_id, 5, "customer_engagement")
                            show_xp_notification(5, "Viewing Dish")
                        
                        # Award XP to staff member for receiving view
                        staff_user_id = entry.get('staff_user_id')
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 3, "received_view")
                        
                        st.rerun()
            
            with col5:
                if st.button(f"🛒 Order ({entry.get('orders', 0)})", key=f"order_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'orders'):
                        # Save order to database
                        if user_id:
                            save_order(db, user_id, entry.get('dish', 'Unknown Dish'))
                            award_visual_menu_xp(user_id, 5, "placed_order")
                            show_xp_notification(5, "Placing Order")
                        
                        # Award XP to staff member for receiving order
                        staff_user_id = entry.get('staff_user_id')
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 15, "received_order")
                        
                        st.rerun()
            
            # Show special badges
            badges = []
            if entry.get('trendy'):
                badges.append("🔥 Trendy")
            if entry.get('diet_match'):
                badges.append("🥗 Diet-Friendly")
            
            if badges:
                st.write(f"**Badges:** {' '.join(badges)}")
    
    # Live Leaderboard
    st.subheader("🏆 Live Leaderboard")
    
    # Calculate and sort leaderboard
    leaderboard = sorted(entries, key=lambda e: calculate_challenge_score(e), reverse=True)
    
    # Display top 10
    leaderboard_data = []
    for i, entry in enumerate(leaderboard[:10]):
        leaderboard_data.append({
            "Rank": f"#{i+1}",
            "Dish": entry.get('dish', 'Unknown'),
            "Chef": entry.get('staff', 'Unknown'),
            "Score": calculate_challenge_score(entry),
            "Likes": entry.get('likes', 0),
            "Views": entry.get('views', 0),
            "Orders": entry.get('orders', 0)
        })
    
    if leaderboard_data:
        df = pd.DataFrame(leaderboard_data)
        st.dataframe(df, use_container_width=True)
        
        # Show top 3 with special styling
        st.markdown("#### 🥇 Top 3 Champions")
        for i, entry in enumerate(leaderboard[:3]):
            medals = ["🥇", "🥈", "🥉"]
            st.success(f"{medals[i]} **{entry.get('dish', 'Unknown')}** by {entry.get('staff', 'Unknown')} - {calculate_challenge_score(entry)} points")
    else:
        st.info("No entries to display in leaderboard yet.")
    
    # Weekly reset info
    st.markdown("---")
    st.info("🔄 **Leaderboard resets weekly** to give everyone a fresh chance to compete!")
