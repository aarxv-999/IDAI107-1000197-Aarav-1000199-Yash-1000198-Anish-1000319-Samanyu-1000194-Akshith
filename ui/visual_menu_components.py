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

try:
    from google.cloud import vision
except ImportError:
    vision = None
    
logger = logging.getLogger(__name__)

def render_visual_menu_search():
    st.title("Visual Menu Challenge & Recommendation Platform")
    
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    user_id = user.get('user_id')
    username = user.get('username', 'Unknown User')
    
    db = get_visual_menu_firebase_db()
    if not db:
        st.error("Database connection failed. Please check your configuration.")
        return
    
    vision_client = configure_vision_api()
    gemini_model = configure_visual_gemini_ai()
    
    if not vision_client:
        st.warning("Google Cloud Vision API not configured. Image analysis will be limited.")
    
    st.sidebar.header("Customer Preferences")
    allergies = st.sidebar.multiselect(
        "Dietary Restrictions & Allergies", 
        ["Nut-Free", "Shellfish-Free", "Soy-Free", "Dairy-Free", "Veg", "Non-Veg", "Gluten-Free", "Vegan"], 
        default=[],
        help="Select your dietary restrictions and allergies"
    )
    
    tabs = st.tabs(["AI Dish Detection", "Personalized Menu", "Custom Filters", "Visual Menu Challenge", "Leaderboard"])
    
    with tabs[0]:
        render_ai_dish_detection(db, vision_client, gemini_model, allergies, user_id)
    
    with tabs[1]:
        render_personalized_menu(db, gemini_model, allergies, user_id)
    
    with tabs[2]:
        render_custom_filters(db, allergies)
    
    with tabs[3]:
        render_visual_challenge(db, vision_client, gemini_model, user_role, username, user_id)
    
    with tabs[4]:
        render_leaderboard(db, user_id)

def render_ai_dish_detection(db, vision_client, gemini_model, allergies, user_id):
    st.header("Visual Dish Detection (AI + Vision API)")
    st.markdown("Upload a food image and let AI identify dishes from our menu!")
    
    st.info("Earn 15 XP for each dish detection analysis!")
    
    uploaded_file = st.file_uploader("Upload Food Image", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image, content = preprocess_image(uploaded_file)
        
        if image and content:
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            with st.spinner("Analyzing image with AI..."):
                labels, objects, texts, style_indicators = analyze_image_with_vision(vision_client, content)
                
                combined_labels = [desc.lower() for desc, score in labels + objects]
                combined_labels = list(set(combined_labels + texts))
                
                if combined_labels:
                    st.write(f"**Detected Elements:** {', '.join(combined_labels[:10])}")
                else:
                    st.write("**Detected Elements:** Using basic image analysis")
                
                if style_indicators:
                    st.write(f"**Detected Plating Style:** {', '.join(style_indicators)}")
                
                food_related = any(
                    label.lower() in ["food", "dish", "meal"] or "food" in label.lower() or 
                    any(food_term in label.lower() for food_term in ["pizza", "burger", "pasta", "salad", "sushi", "chicken", "beef"])
                    for label in combined_labels
                ) if combined_labels else True
                
                if not food_related and combined_labels:
                    st.warning("The image doesn't appear to contain food. Please upload a food-related image.")
                    return
                
                menu_items = fetch_menu_items(db)
                if not menu_items:
                    st.error("No menu items found. Please check your menu database.")
                    return
                
                matching_dishes = find_matching_dishes(menu_items, combined_labels)
                
                menu_text = "\n".join([
                    f"- {item.get('name', 'Unknown')}: {item.get('description', '')} (Ingredients: {', '.join(item.get('ingredients', []))})"
                    for item in menu_items[:20]
                ])
                
                ai_analysis = generate_ai_dish_analysis(
                    gemini_model, labels, objects, texts, style_indicators, allergies, menu_text
                )
                
                st.success("AI Dish Analysis:")
                st.markdown(ai_analysis)
                
                if matching_dishes:
                    st.subheader("Related Menu Items")
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
                    st.info("No closely related menu items found based on image analysis.")
                
                if user_id:
                    xp_earned = award_visual_menu_xp(user_id, 15, "dish_detection")
                    if xp_earned > 0:
                        show_xp_notification(15, "AI Dish Detection")
        else:
            st.error("Failed to process the uploaded image. Please try again.")

def render_personalized_menu(db, gemini_model, allergies, user_id):
    st.header("Personalized AI Menu")
    st.markdown("Get AI-powered menu recommendations that learn from your preferences!")

    if not user_id:
        st.warning("Please log in to use personalized features")
        return
        
    st.info("Earn 20 XP for generating recommendations • Earn 5 XP for each like!")
    
    st.subheader("Your Preferences (Optional)")
    
    user_prefs = {}
    try:
        prefs_doc = db.collection("user_preferences").document(user_id).get()
        if prefs_doc.exists:
            user_prefs = prefs_doc.to_dict()
            if not user_prefs.get('is_system_init', False):
                st.success("Loaded your saved preferences!")
    except Exception as e:
        st.info("No saved preferences found (this is normal for first-time users)")
        logger.info(f"No preferences found for user {user_id}: {str(e)}")
    
    user_likes = []
    try:
        likes_docs = db.collection("user_dish_likes").where("user_id", "==", user_id).stream()
        user_likes = [doc.to_dict() for doc in likes_docs if not doc.to_dict().get('is_system_init', False)]
        if user_likes:
            st.info(f"AI has learned from {len(user_likes)} dishes you've liked!")
    except Exception as e:
        st.info("No liked dishes found yet")
        logger.info(f"No likes found for user {user_id}: {str(e)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        menu_items = fetch_menu_items(db)
        available_cuisines = list(set([item.get('cuisine', 'Unknown') for item in menu_items if item.get('cuisine')]))
        
        saved_favorite_cuisines = user_prefs.get('favorite_cuisines', [])
        valid_favorite_cuisines = [cuisine for cuisine in saved_favorite_cuisines if cuisine in available_cuisines]
        
        favorite_cuisines = st.multiselect(
            "Favorite Cuisines",
            available_cuisines,
            default=valid_favorite_cuisines,
            help="Select cuisines you enjoy most"
        )
    
    with col2:
        available_categories = list(set([item.get('category', 'Unknown') for item in menu_items if item.get('category')]))
        
        saved_preferred_categories = user_prefs.get('preferred_categories', [])
        valid_preferred_categories = [category for category in saved_preferred_categories if category in available_categories]
        
        preferred_categories = st.multiselect(
            "Preferred Categories",
            available_categories,
            default=valid_preferred_categories,
            help="Select meal categories you prefer"
        )
    
    if st.button("Save My Preferences"):
        try:
            prefs_data = {
                'user_id': user_id,
                'favorite_cuisines': favorite_cuisines,
                'preferred_categories': preferred_categories,
                'last_updated': datetime.now().isoformat(),
                'is_system_init': False
            }
            db.collection("user_preferences").document(user_id).set(prefs_data)
            st.success("Preferences saved to Event Firebase!")
        except Exception as e:
            st.error(f"Error saving preferences: {str(e)}")
            st.info("Make sure collections are initialized first")
    
    st.subheader("AI Recommendation Options")
    
    col3, col4 = st.columns(2)
    
    with col3:
        recommendation_type = st.selectbox(
            "Recommendation Style",
            ["Balanced Variety", "Cuisine Focus", "Dietary Optimized", "Chef's Special", "Quick & Easy", "Based on Likes"]
        )
        
    with col4:
        meal_context = st.selectbox(
            "Meal Context",
            ["Any Time", "Breakfast", "Lunch", "Dinner", "Snack", "Special Occasion"]
        )
    
    with st.expander("Advanced Options"):
        include_description = st.checkbox("Include detailed descriptions", value=True)
        include_ingredients = st.checkbox("Show key ingredients", value=True)
        num_recommendations = st.slider("Number of recommendations", 3, 10, 5)
    
    if st.button("Generate AI Personalized Recommendations", type="primary"):
        if not gemini_model:
            st.error("Gemini AI not configured. Please check your API key.")
            return
            
        with st.spinner("AI is analyzing your preferences and learning from your likes..."):
            
            if not menu_items:
                st.error("No menu items found.")
                return
            
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
            
            user_profile = {
                'dietary_restrictions': allergies,
                'favorite_cuisines': favorite_cuisines,
                'preferred_categories': preferred_categories,
                'recommendation_type': recommendation_type,
                'meal_context': meal_context,
                'liked_dishes': user_likes
            }
            
            try:
                recommendations_data = generate_smart_personalized_recommendations_with_learning(
                    gemini_model, menu_context, user_profile, num_recommendations, 
                    include_description, include_ingredients
                )
                
                with st.expander("Debug Information"):
                    st.write(f"**Total menu items:** {len(menu_items)}")
                    st.write(f"**Selected cuisines:** {favorite_cuisines}")
                    st.write(f"**Selected categories:** {preferred_categories}")
                    st.write(f"**AI returned dishes:** {len(recommendations_data['dishes'])}")
                    st.write(f"**Raw AI response length:** {len(recommendations_data['explanation'])}")
                    if recommendations_data['dishes']:
                        st.write("**Dish names found:**")
                        for dish in recommendations_data['dishes']:
                            st.write(f"- {dish.get('name', 'NO NAME')} ({dish.get('cuisine', 'NO CUISINE')})")
                
                if not recommendations_data['dishes']:
                    st.warning("No recommendations generated. Let me try with relaxed filtering...")
                    
                    relaxed_recommendations = generate_relaxed_recommendations(
                        gemini_model, menu_context, user_profile, num_recommendations,
                        include_description, include_ingredients
                    )
                    
                    if relaxed_recommendations['dishes']:
                        recommendations_data = relaxed_recommendations
                        st.info("Generated recommendations with relaxed filtering")
                    else:
                        st.error("Could not generate any recommendations. Please try different preferences.")
                        return
                
                st.session_state['current_recommendations'] = recommendations_data['dishes']
                st.session_state['recommendation_context'] = f"{recommendation_type}_{meal_context}"
                
                st.success("Your AI-Powered Personalized Recommendations:")

                strategy_lines = recommendations_data['explanation'].split('\n')
                strategy_text = ""
                for line in strategy_lines:
                    if line.strip().startswith('**Recommendation Strategy:**'):
                        strategy_text = line.strip()
                        break

                if strategy_text:
                    st.info(strategy_text)

                st.subheader("Your Personalized Dishes - Like to help AI learn!")

                for i, dish in enumerate(recommendations_data['dishes']):
                    with st.container():
                        st.markdown("---")
                        col_dish, col_like = st.columns([4, 1])
                        
                        with col_dish:
                            st.markdown(f"### {dish['name']}")
                            st.write(f"**Cuisine:** {dish['cuisine']} | **Category:** {dish['category']}")
                            if dish.get('description'):
                                st.write(f"**Description:** {dish['description']}")
                            if dish.get('ingredients'):
                                st.write(f"**Key Ingredients:** {', '.join(dish['ingredients'])}")
                            st.write(f"**Why recommended:** {dish['reason']}")
                        
                        with col_like:
                            already_liked = any(
                                like['dish_name'].lower() == dish['name'].lower() 
                                for like in user_likes
                            )
                            
                            if already_liked:
                                st.success("Liked!")
                            else:
                                if st.button(f"Like", key=f"like_rec_{i}"):
                                    if save_dish_like(db, user_id, dish, st.session_state.get('recommendation_context', 'unknown')):
                                        st.success("Liked! AI will learn from this.")
                                        if user_id:
                                            award_visual_menu_xp(user_id, 5, "dish_like")
                                            show_xp_notification(5, "Liking Dish")
                                        st.rerun()
                
                if user_id:
                    xp_earned = award_visual_menu_xp(user_id, 20, "personalized_recommendations")
                    if xp_earned > 0:
                        show_xp_notification(20, "Personalized Menu Recommendations")
                        
            except Exception as e:
                st.error(f"Error generating recommendations: {str(e)}")
                st.write("**Error details:**", str(e))

def save_dish_like(db, user_id, dish, recommendation_context):
    try:
        if not db or not user_id:
            return False
            
        try:
            existing_likes = list(db.collection("user_dish_likes").where("user_id", "==", user_id).where("dish_name", "==", dish['name']).stream())
            if existing_likes:
                logger.info(f"Dish {dish['name']} already liked by user {user_id}")
                return True
        except:
            pass
            
        like_data = {
            'user_id': user_id,
            'dish_name': dish['name'],
            'dish_cuisine': dish['cuisine'],
            'dish_category': dish['category'],
            'dish_ingredients': dish.get('ingredients', []),
            'liked_at': datetime.now().isoformat(),
            'recommendation_context': recommendation_context,
            'is_system_init': False
        }
        
        db.collection("user_dish_likes").add(like_data)
        logger.info(f"Saved dish like for user {user_id}: {dish['name']}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving dish like: {str(e)}")
        st.error(f"Error saving like: {str(e)}")
        return False

def generate_smart_personalized_recommendations_with_learning(gemini_model, menu_context, user_profile, num_recommendations, include_description, include_ingredients):
    
    menu_text = "\n".join([
        f"- {item['name']} ({item['category']}, {item['cuisine']}): {item['description']} "
        f"[Ingredients: {', '.join(item['ingredients'][:5])}] "
        f"[Diet: {', '.join(item['diet']) if isinstance(item['diet'], list) else item['diet']}] "
        f"[Cook Time: {item['cook_time']}]"
        for item in menu_context
    ])
    
    learning_context = ""
    if user_profile['liked_dishes']:
        liked_cuisines = [like['dish_cuisine'] for like in user_profile['liked_dishes']]
        liked_categories = [like['dish_category'] for like in user_profile['liked_dishes']]
        liked_ingredients = []
        for like in user_profile['liked_dishes']:
            liked_ingredients.extend(like.get('dish_ingredients', []))
        
        learning_context = f"""
        **LEARNING DATA - User has previously liked:**
        - Cuisines: {', '.join(set(liked_cuisines))}
        - Categories: {', '.join(set(liked_categories))}
        - Common ingredients in liked dishes: {', '.join(set(liked_ingredients))}
        - Recently liked dishes: {', '.join([like['dish_name'] for like in user_profile['liked_dishes'][-5:]])}
        
        IMPORTANT: Use this learning data to influence recommendations.
        """
    
    preference_text = ""
    if user_profile['favorite_cuisines']:
        preference_text += f"- User prefers these cuisines: {', '.join(user_profile['favorite_cuisines'])}\n"
    if user_profile['preferred_categories']:
        preference_text += f"- User prefers these categories: {', '.join(user_profile['preferred_categories'])}\n"
    if user_profile['dietary_restrictions']:
        preference_text += f"- User wants to avoid: {', '.join(user_profile['dietary_restrictions'])}\n"
    
    prompt = f"""
    You are a professional restaurant AI sommelier. Analyze the menu and provide {num_recommendations} personalized dish recommendations.

    **User Preferences:**
    {preference_text if preference_text else "- No specific preferences set"}
    - Recommendation Style: {user_profile['recommendation_type']}
    - Meal Context: {user_profile['meal_context']}

    {learning_context}

    **Available Menu:**
    {menu_text}

    **Instructions:**
    1. If user has cuisine preferences, try to prioritize those cuisines but don't exclude others entirely
    2. If user has category preferences, try to prioritize those categories
    3. Avoid dietary restrictions strictly
    4. If learning data exists, consider similar dishes
    5. Select exactly {num_recommendations} diverse dishes
    6. Ensure variety in your recommendations

    **Output Format:**
    Start with: **Recommendation Strategy:** [Brief explanation]

    Then for each dish:
    ## [Dish Name]
    **Cuisine:** [Cuisine] | **Category:** [Category]
    {"**Description:** [Description]" if include_description else ""}
    {"**Key Ingredients:** [List 3-4 main ingredients]" if include_ingredients else ""}
    **Why recommended:** [Specific reason]
    
    ---
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text.strip()
        
        dishes = []
        lines = response_text.split('\n')
        current_dish = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('## '):
                if current_dish:
                    dishes.append(current_dish)
                current_dish = {'name': line.replace('## ', '').strip()}
            elif line.startswith('**Cuisine:**'):
                parts = line.split('|')
                current_dish['cuisine'] = parts[0].replace('**Cuisine:**', '').strip()
                current_dish['category'] = parts[1].replace('**Category:**', '').strip() if len(parts) > 1 else 'Unknown'
            elif line.startswith('**Description:**'):
                current_dish['description'] = line.replace('**Description:**', '').strip()
            elif line.startswith('**Key Ingredients:**'):
                ingredients_text = line.replace('**Key Ingredients:**', '').strip()
                current_dish['ingredients'] = [ing.strip() for ing in ingredients_text.split(',')]
            elif line.startswith('**Why recommended:**'):
                current_dish['reason'] = line.replace('**Why recommended:**', '').strip()
        
        if current_dish:
            dishes.append(current_dish)
        
        return {
            'explanation': response_text,
            'dishes': dishes
        }
        
    except Exception as e:
        return {
            'explanation': f"Error generating recommendations: {str(e)}",
            'dishes': []
        }

def generate_relaxed_recommendations(gemini_model, menu_context, user_profile, num_recommendations, include_description, include_ingredients):
    
    menu_text = "\n".join([
        f"- {item['name']} ({item['category']}, {item['cuisine']}): {item['description']}"
        for item in menu_context[:20]
    ])
    
    prompt = f"""
    You are a restaurant AI. Recommend {num_recommendations} dishes from this menu:

    {menu_text}

    User context: {user_profile['recommendation_type']} for {user_profile['meal_context']}

    Format each as:
    ## [Dish Name]
    **Cuisine:** [Cuisine] | **Category:** [Category]
    **Why recommended:** [Brief reason]
    ---
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        response_text = response.text.strip()
        
        dishes = []
        lines = response_text.split('\n')
        current_dish = {}
        
        for line in lines:
            line = line.strip()
            if line.startswith('## '):
                if current_dish:
                    dishes.append(current_dish)
                current_dish = {'name': line.replace('## ', '').strip()}
            elif line.startswith('**Cuisine:**'):
                parts = line.split('|')
                current_dish['cuisine'] = parts[0].replace('**Cuisine:**', '').strip()
                current_dish['category'] = parts[1].replace('**Category:**', '').strip() if len(parts) > 1 else 'Unknown'
            elif line.startswith('**Why recommended:**'):
                current_dish['reason'] = line.replace('**Why recommended:**', '').strip()
        
        if current_dish:
            dishes.append(current_dish)
        
        return {
            'explanation': "**Recommendation Strategy:** Relaxed filtering applied to ensure recommendations are shown.",
            'dishes': dishes
        }
        
    except Exception as e:
        return {
            'explanation': f"Error in relaxed recommendations: {str(e)}",
            'dishes': []
        }

def render_custom_filters(db, allergies):
    st.header("Custom Menu Filters")
    st.markdown("Filter our menu based on available data from your restaurant database!")
    
    menu_items = fetch_menu_items(db)
    if not menu_items:
        st.error("No menu items found.")
        return
    
    available_categories = list(set([item.get('category', 'Unknown') for item in menu_items if item.get('category')]))
    available_cuisines = list(set([item.get('cuisine', 'Unknown') for item in menu_items if item.get('cuisine')]))
    available_diets = list(set([diet for item in menu_items for diet in (item.get('diet', []) if isinstance(item.get('diet'), list) else [item.get('diet')] if item.get('diet') else [])]))
    available_types = list(set([type_item for item in menu_items for type_item in (item.get('types', []) if isinstance(item.get('types'), list) else [item.get('types')] if item.get('types') else [])]))
    
    st.subheader("Menu Categories & Types")
    col1, col2 = st.columns(2)
    
    with col1:
        selected_category = st.selectbox("Category", ["All"] + sorted(available_categories))
        selected_cuisine = st.selectbox("Cuisine", ["All"] + sorted(available_cuisines))
        
    with col2:
        selected_diet = st.selectbox("Dietary Type", ["All"] + sorted(available_diets))
        selected_type = st.selectbox("Special Types", ["All"] + sorted(available_types))

    st.subheader("Cooking Time")
    cook_time_filter = st.selectbox(
        "Maximum Cooking Time", 
        ["All", "Quick (≤ 20 min)", "Medium (21-40 min)", "Long (> 40 min)"]
    )
    
    st.subheader("Ingredient Preferences")
    col3, col4 = st.columns(2)
    
    with col3:
        must_include = st.text_input("Must Include Ingredient", placeholder="e.g., paneer, chicken")
        
    with col4:
        must_exclude = st.text_input("Must Exclude Ingredient", placeholder="e.g., onion, garlic")

    with st.expander("AI Smart Filtering (Powered by Gemini)"):
        st.markdown("Use AI to find dishes based on natural language descriptions!")
        ai_query = st.text_area(
            "Describe what you're looking for", 
            placeholder="e.g., 'Something spicy and vegetarian for dinner' or 'Light appetizer with paneer'"
        )
        use_ai_filter = st.checkbox("Enable AI Smart Filtering")

    if st.button("Apply Filters", type="primary"):
        with st.spinner("Filtering menu items based on your database..."):
            
            filtered_menu = menu_items.copy()
            
            filtered_menu, debug_info = filter_menu_by_allergies(filtered_menu, allergies)
            
            if selected_category != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if item.get('category', '').strip().lower() == selected_category.strip().lower()
                ]
            
            if selected_cuisine != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if item.get('cuisine', '').strip().lower() == selected_cuisine.strip().lower()
                ]
            
            if selected_diet != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if selected_diet in (item.get('diet', []) if isinstance(item.get('diet'), list) else [item.get('diet')] if item.get('diet') else [])
                ]
            
            if selected_type != "All":
                filtered_menu = [
                    item for item in filtered_menu 
                    if selected_type in (item.get('types', []) if isinstance(item.get('types'), list) else [item.get('types')] if item.get('types') else [])
                ]
            
            if cook_time_filter != "All":
                def extract_cook_time_minutes(cook_time_str):
                    if not cook_time_str:
                        return 999
                    try:
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
            
            if must_include:
                filtered_menu = [
                    item for item in filtered_menu 
                    if any(must_include.lower() in ing.lower() for ing in item.get('ingredients', []))
                ]
            
            if must_exclude:
                filtered_menu = [
                    item for item in filtered_menu 
                    if not any(must_exclude.lower() in ing.lower() for ing in item.get('ingredients', []))
                ]
            
            if use_ai_filter and ai_query:
                try:
                    gemini_model = configure_visual_gemini_ai()
                    if gemini_model:
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
                            ai_filtered = []
                            for item in filtered_menu:
                                for match in ai_matches:
                                    if match.strip().lower() in item.get('name', '').lower():
                                        ai_filtered.append(item)
                                        break
                            
                            if ai_filtered:
                                filtered_menu = ai_filtered
                                st.info(f"AI found {len(ai_filtered)} dishes matching your description!")
                            else:
                                st.warning("AI couldn't find exact matches, showing regular filtered results.")
                        else:
                            st.warning("AI couldn't find dishes matching your description, showing regular filtered results.")
                            
                except Exception as e:
                    st.warning(f"AI filtering unavailable: {str(e)}")
            
            if filtered_menu:
                st.success(f"Found {len(filtered_menu)} dishes matching your criteria")
                
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
                    st.info(f"**Active Filters:** {' | '.join(active_filters)}")
                
            else:
                st.warning("No menu items match your selected criteria.")
                
                with st.expander("Filter Debug Information"):
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

def analyze_challenge_image_with_ai(vision_client, gemini_model, image_content, dish_name, ingredients, plating_style):
    try:
        vision_score = 0
        gemini_score = 0
        
        if vision_client and vision:
            try:
                vision_image = vision.Image(content=image_content)
                
                label_response = vision_client.label_detection(image=vision_image)
                labels = [(label.description, label.score) for label in label_response.label_annotations]
                
                obj_response = vision_client.object_localization(image=vision_image)
                objects = [(obj.name, obj.score) for obj in obj_response.localized_object_annotations]
                
                properties_response = vision_client.image_properties(image=vision_image)
                dominant_colors = properties_response.image_properties_annotation.dominant_colors.colors
                
                food_labels = [label for label, score in labels if 'food' in label.lower() or 'dish' in label.lower()]
                food_objects = [obj for obj, score in objects if 'food' in obj.lower()]
                
                if food_labels or food_objects:
                    vision_score += 20
                
                high_confidence_food = [label for label, score in labels if score > 0.8 and any(food_term in label.lower() for food_term in ['food', 'dish', 'meal', 'cuisine'])]
                vision_score += len(high_confidence_food) * 5
                
                if len(dominant_colors) >= 3:
                    vision_score += 10
                
                vision_score = min(vision_score, 50)
                
            except Exception as e:
                logger.warning(f"Vision API analysis failed: {str(e)}")
                vision_score = 25
        else:
            vision_score = 25
            if not vision:
                logger.warning("Google Cloud Vision library not installed")
        
        if gemini_model:
            try:
                prompt = f"""
                Analyze this dish submission for a restaurant staff challenge:
                
                Dish Name: {dish_name}
                Ingredients: {ingredients}
                Plating Style: {plating_style}
                
                Rate this dish submission on a scale of 1-100 based on:
                1. Creativity and uniqueness (25%)
                2. Ingredient quality and combination (25%)
                3. Plating and presentation style (25%)
                4. Overall appeal and professionalism (25%)
                
                Consider:
                - Is this a creative and interesting dish?
                - Do the ingredients work well together?
                - Does the plating style sound appealing?
                - Would customers be interested in ordering this?
                
                Return ONLY a number between 1-100, no other text.
                """
                
                response = gemini_model.generate_content(prompt)
                try:
                    gemini_score = int(response.text.strip())
                    gemini_score = max(1, min(100, gemini_score))
                except:
                    gemini_score = 50
                    
            except Exception as e:
                logger.warning(f"Gemini AI analysis failed: {str(e)}")
                gemini_score = 50
        else:
            gemini_score = 50
        
        base_xp = max(30, min(100, (vision_score + gemini_score) // 2))
        
        feedback = f"Vision API Score: {vision_score}/50, Gemini AI Score: {gemini_score}/100"
        
        return base_xp, feedback, {
            'vision_score': vision_score,
            'gemini_score': gemini_score,
            'total_score': base_xp
        }
        
    except Exception as e:
        logger.error(f"Error in AI image analysis: {str(e)}")
        return 40, f"AI analysis error: {str(e)}", {'vision_score': 0, 'gemini_score': 0, 'total_score': 40}

def save_enhanced_challenge_entry(db, staff_name, staff_user_id, dish_name, ingredients, plating_style, trendy, diet_match, ai_analysis_result):
    try:
        if not db:
            return False, "Database connection failed"
            
        challenge_data = {
            "staff": staff_name,
            "staff_user_id": staff_user_id,
            "dish": dish_name,
            "ingredients": [i.strip() for i in ingredients.split(",") if i.strip()],
            "style": plating_style,
            "trendy": trendy,
            "diet_match": diet_match,
            "timestamp": datetime.now().timestamp(),
            "created_at": datetime.now().isoformat(),
            "views": 0,
            "likes": 0,
            "orders": 0,
            "ai_analysis": ai_analysis_result,
            "initial_xp_awarded": ai_analysis_result['total_score']
        }
        
        db.collection("visual_challenges").add(challenge_data)
        logger.info(f"Saved enhanced challenge entry for {staff_name}: {dish_name}")
        return True, "Challenge entry saved successfully"
        
    except Exception as e:
        logger.error(f"Error saving enhanced challenge entry: {str(e)}")
        return False, f"Error saving challenge: {str(e)}"

def render_visual_challenge(db, vision_client, gemini_model, user_role, username, user_id):
    st.header("AI-Powered Visual Menu Challenge")
    
    if user_role not in ['staff', 'chef', 'admin']:
        st.warning("This feature is available for Staff, Chefs, and Administrators only.")
        st.info("Customers can vote on staff submissions in the Leaderboard tab!")
        return
    
    st.markdown("Submit your signature dish photos and get AI-powered XP rewards based on creativity and presentation!")
    
    st.info("""
    AI-Powered XP Rewards:
    • Initial AI Analysis: 30-100 XP based on Vision API + Gemini AI evaluation
    • Customer likes: +8 XP per like (awarded to you)
    • Customer views: +3 XP per view (awarded to you)  
    • Customer orders: +15 XP per order (awarded to you)
    
    AI evaluates your dish on:
    - Creativity and uniqueness (25%)
    - Ingredient quality and combination (25%)
    - Plating and presentation style (25%)
    - Overall appeal and professionalism (25%)
    """)
    
    if 'challenge_submitted' not in st.session_state:
        st.session_state.challenge_submitted = False
    if 'challenge_results' not in st.session_state:
        st.session_state.challenge_results = None
    
    if st.session_state.challenge_submitted and st.session_state.challenge_results:
        st.markdown("### Latest Submission Results")
        results = st.session_state.challenge_results
        
        st.markdown("### AI Analysis Results")
        
        col_results1, col_results2, col_results3 = st.columns(3)
        with col_results1:
            st.metric("Vision API Score", f"{results['ai_analysis']['vision_score']}/50")
        with col_results2:
            st.metric("Gemini AI Score", f"{results['ai_analysis']['gemini_score']}/100")
        with col_results3:
            st.metric("Total XP Earned", f"{results['ai_xp']} XP")
        
        st.info(f"AI Feedback: {results['ai_feedback']}")
        
        if results.get('image'):
            st.image(results['image'], caption=f"Your submitted dish: {results['dish_name']}", use_container_width=True)
        
        st.success("Your dish is now live in the leaderboard for customer voting!")
        
        if st.button("Submit Another Dish"):
            st.session_state.challenge_submitted = False
            st.session_state.challenge_results = None
            st.rerun()
        
        st.markdown("---")
    
    if not st.session_state.challenge_submitted:
        with st.form("challenge_form"):
            st.markdown("#### Submit Your Dish for AI Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                dish_name = st.text_input("Dish Name *", placeholder="e.g., Truffle Pasta Supreme")
                plating_style = st.text_input("Plating Style *", placeholder="e.g., Modern, Classic, Rustic, Minimalist")
            
            with col2:
                ingredients = st.text_area("Ingredients (comma separated) *", placeholder="pasta, truffle oil, parmesan, garlic, herbs")
                
            col3, col4 = st.columns(2)
            with col3:
                trendy = st.checkbox("Matches current food trends", help="Is this dish following current culinary trends?")
            with col4:
                diet_match = st.checkbox("Matches dietary preferences", help="Does this dish cater to popular dietary preferences?")
            
            challenge_image = st.file_uploader("Dish Photo *", type=["jpg", "png", "jpeg"], help="Upload a high-quality photo of your dish for AI analysis")
            
            submitted = st.form_submit_button("Submit for AI Analysis & Challenge", type="primary")
            
            if submitted:
                if not dish_name or not ingredients or not plating_style:
                    st.error("Please fill in all required fields (Dish Name, Ingredients, Plating Style).")
                elif not challenge_image:
                    st.error("Please upload a dish photo for AI analysis.")
                else:
                    with st.spinner("Analyzing your dish with AI (Vision API + Gemini)..."):
                        image, content = preprocess_image(challenge_image)
                        
                        if image and content:
                            ai_xp, ai_feedback, ai_analysis = analyze_challenge_image_with_ai(
                                vision_client, gemini_model, content, dish_name, ingredients, plating_style
                            )
                            
                            success, message = save_enhanced_challenge_entry(
                                db, username, user_id, dish_name, ingredients, plating_style, trendy, diet_match, ai_analysis
                            )
                            
                            if success:
                                st.session_state.challenge_results = {
                                    'dish_name': dish_name,
                                    'ai_xp': ai_xp,
                                    'ai_feedback': ai_feedback,
                                    'ai_analysis': ai_analysis,
                                    'image': image,
                                    'message': message
                                }
                                st.session_state.challenge_submitted = True
                                
                                if user_id:
                                    xp_earned = award_visual_menu_xp(user_id, ai_xp, "ai_challenge_submission")
                                    if xp_earned > 0:
                                        show_xp_notification(ai_xp, f"AI Challenge Analysis ({ai_analysis['gemini_score']}/100 score)")
                                
                                st.rerun()
                            else:
                                st.error(f"{message}")
                        else:
                            st.error("Failed to process the uploaded image. Please try again with a different image.")

def render_leaderboard(db, user_id):
    st.header("Leaderboard & Customer Voting")
    st.markdown("Vote on staff-submitted dishes and see who's leading the competition!")
    
    st.info("Earn 5 XP for each vote you cast!")
    
    entries = fetch_challenge_entries(db)
    
    if not entries:
        st.info("No challenge entries yet. Staff members can submit dishes in the Visual Menu Challenge tab!")
        return
    
    st.subheader("Vote on Staff Dishes")
    
    for entry in entries:
        with st.container():
            st.markdown("---")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"{entry.get('dish', 'Unknown Dish')}")
                st.write(f"**Chef:** {entry.get('staff', 'Unknown')}")
                st.write(f"**Style:** {entry.get('style', 'Not specified')}")
                st.write(f"**Ingredients:** {', '.join(entry.get('ingredients', []))}")
                
                ai_analysis = entry.get('ai_analysis', {})
                if ai_analysis:
                    st.write(f"**AI Score:** {ai_analysis.get('total_score', 'N/A')}/100 (Vision: {ai_analysis.get('vision_score', 'N/A')}/50, Gemini: {ai_analysis.get('gemini_score', 'N/A')}/100)")
            
            with col2:
                st.metric("Total Score", calculate_challenge_score(entry))
                initial_xp = entry.get('initial_xp_awarded', 0)
                if initial_xp:
                    st.metric("Initial AI XP", f"{initial_xp} XP")
            
            col3, col4, col5 = st.columns(3)
            
            with col3:
                if st.button(f"Like ({entry.get('likes', 0)})", key=f"like_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'likes'):
                        if user_id:
                            award_visual_menu_xp(user_id, 5, "customer_vote")
                            show_xp_notification(5, "Voting on Dish")
                        
                        staff_user_id = entry.get('staff_user_id')
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 8, "received_like")
                        
                        st.rerun()
            
            with col4:
                if st.button(f"View ({entry.get('views', 0)})", key=f"view_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'views'):
                        if user_id:
                            award_visual_menu_xp(user_id, 5, "customer_engagement")
                            show_xp_notification(5, "Viewing Dish")
                        
                        staff_user_id = entry.get('staff_user_id')
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 3, "received_view")
                        
                        st.rerun()
            
            with col5:
                if st.button(f"Order ({entry.get('orders', 0)})", key=f"order_{entry['id']}"):
                    if update_challenge_interaction(db, entry['id'], 'orders'):
                        if user_id:
                            save_order(db, user_id, entry.get('dish', 'Unknown Dish'))
                            award_visual_menu_xp(user_id, 5, "placed_order")
                            show_xp_notification(5, "Placing Order")
                        
                        staff_user_id = entry.get('staff_user_id')
                        if staff_user_id:
                            award_visual_menu_xp(staff_user_id, 15, "received_order")
                        
                        st.rerun()
            
            badges = []
            if entry.get('trendy'):
                badges.append("Trendy")
            if entry.get('diet_match'):
                badges.append("Diet-Friendly")
            
            ai_analysis = entry.get('ai_analysis', {})
            if ai_analysis.get('total_score', 0) >= 80:
                badges.append("AI Excellent")
            elif ai_analysis.get('total_score', 0) >= 60:
                badges.append("AI Good")
            
            if badges:
                st.write(f"**Badges:** {' '.join(badges)}")
    
    st.subheader("Live Leaderboard")
    
    leaderboard = sorted(entries, key=lambda e: calculate_challenge_score(e), reverse=True)
    
    leaderboard_data = []
    for i, entry in enumerate(leaderboard[:10]):
        ai_score = entry.get('ai_analysis', {}).get('total_score', 'N/A')
        initial_xp = entry.get('initial_xp_awarded', 0)
        
        leaderboard_data.append({
            "Rank": f"#{i+1}",
            "Dish": entry.get('dish', 'Unknown'),
            "Chef": entry.get('staff', 'Unknown'),
            "Total Score": calculate_challenge_score(entry),
            "AI Score": f"{ai_score}/100" if ai_score != 'N/A' else 'N/A',
            "Initial XP": f"{initial_xp} XP" if initial_xp else 'N/A',
            "Likes": entry.get('likes', 0),
            "Views": entry.get('views', 0),
            "Orders": entry.get('orders', 0)
        })
    
    if leaderboard_data:
        df = pd.DataFrame(leaderboard_data)
        st.dataframe(df, use_container_width=True)
        
        st.markdown("#### Top 3 Champions")
        for i, entry in enumerate(leaderboard[:3]):
            medals = ["🥇", "🥈", "🥉"]
            ai_score = entry.get('ai_analysis', {}).get('total_score', 'N/A')
            ai_text = f" (AI: {ai_score}/100)" if ai_score != 'N/A' else ""
            st.success(f"{medals[i]} **{entry.get('dish', 'Unknown')}** by {entry.get('staff', 'Unknown')} - {calculate_challenge_score(entry)} points{ai_text}")
    else:
        st.info("No entries to display in leaderboard yet.")
    
    st.markdown("---")
    st.info("Leaderboard resets weekly to give everyone a fresh chance to compete!")
