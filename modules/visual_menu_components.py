"""
Enhanced Visual Menu Components - Updated to work with improved services.
"""

import streamlit as st
from PIL import Image
import logging
from typing import Dict, List, Optional
from modules.visual_menu_services import (
    search_similar_dishes, analyze_food_image_with_gemini, FilterCriteria,
    get_smart_filter_suggestions
)

logger = logging.getLogger(__name__)

def render_visual_menu_search():
    """Main enhanced visual search interface"""
    st.title("🔍 Visual Menu Search")
    st.markdown("Upload a food image and use advanced filters to find similar dishes!")
    
    # Check user access
    user = st.session_state.get('user', {})
    if not user:
        st.warning("Please log in to access Visual Search")
        return
    
    # Create main layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_image_upload_section()
    
    with col2:
        render_filters_section()
    
    # Search results section
    if st.session_state.get('visual_search_results'):
        render_results_section()

def render_image_upload_section():
    """Enhanced image upload section with analysis preview"""
    st.markdown("### 📸 Upload Food Image")
    
    uploaded_file = st.file_uploader(
        "Choose a food image...",
        type=['png', 'jpg', 'jpeg'],
        help="Upload a clear image of food for best results"
    )
    
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Store image in session state
            st.session_state.uploaded_image = image
            
            # Quick analysis button
            if st.button("🔍 Analyze Image", type="primary", use_container_width=True):
                with st.spinner("Analyzing image..."):
                    analysis = analyze_food_image_with_gemini(image)
                    
                    if "error" not in analysis:
                        st.session_state.image_analysis = analysis
                        
                        # Show analysis results
                        st.success("✅ Image analyzed successfully!")
                        
                        with st.expander("🧠 AI Analysis Results", expanded=True):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"**Dish:** {analysis.get('dish_name', 'Unknown')}")
                                st.write(f"**Cuisine:** {analysis.get('cuisine_type', 'Unknown')}")
                                st.write(f"**Spice Level:** {analysis.get('spice_level', 'Unknown')}")
                                st.write(f"**Cooking Method:** {analysis.get('cooking_method', 'Unknown')}")
                            
                            with col2:
                                st.write(f"**Meal Type:** {analysis.get('meal_type', 'Unknown')}")
                                st.write(f"**Confidence:** {analysis.get('confidence', 0):.1%}")
                                
                                dietary_info = analysis.get('dietary_info', [])
                                if dietary_info:
                                    st.write(f"**Dietary:** {', '.join(dietary_info)}")
                        
                        # Generate smart filter suggestions
                        suggestions = get_smart_filter_suggestions(analysis)
                        st.session_state.filter_suggestions = suggestions
                        
                        st.info("💡 Smart filter suggestions have been generated!")
                    else:
                        st.error(f"❌ Analysis failed: {analysis['error']}")
        
        except Exception as e:
            st.error(f"❌ Error processing image: {str(e)}")

def render_filters_section():
    """Enhanced filters section with smart suggestions"""
    st.markdown("### 🎛️ Search Filters")
    
    # Smart suggestions section
    if st.session_state.get('filter_suggestions'):
        render_smart_suggestions()
    
    # Create filter tabs for better organization
    tab1, tab2 = st.tabs(["🍽️ Basic Filters", "🌶️ Advanced Filters"])
    
    with tab1:
        render_basic_filters()
    
    with tab2:
        render_advanced_filters()
    
    # Search button
    st.markdown("---")
    if st.button("🔍 Search with Filters", type="primary", use_container_width=True):
        perform_search()
    
    # Clear filters button
    if st.button("🗑️ Clear All Filters", use_container_width=True):
        clear_all_filters()

def render_smart_suggestions():
    """Render AI-generated smart filter suggestions"""
    st.markdown("#### 🤖 Smart Suggestions")
    suggestions = st.session_state.get('filter_suggestions', {})
    
    if not any(suggestions.values()):
        return
    
    st.info("💡 Based on your image analysis:")
    
    cols = st.columns(2)
    
    with cols[0]:
        # Cuisine suggestions
        if suggestions.get('cuisine_types'):
            st.write("**Suggested Cuisine:**")
            for cuisine in suggestions['cuisine_types']:
                if st.button(f"🌍 {cuisine}", key=f"suggest_cuisine_{cuisine}"):
                    if 'selected_cuisine_types' not in st.session_state:
                        st.session_state.selected_cuisine_types = []
                    if cuisine not in st.session_state.selected_cuisine_types:
                        st.session_state.selected_cuisine_types.append(cuisine)
                        st.rerun()
        
        # Dietary suggestions
        if suggestions.get('dietary_preferences'):
            st.write("**Suggested Dietary:**")
            for diet in suggestions['dietary_preferences'][:2]:
                if st.button(f"🥗 {diet}", key=f"suggest_diet_{diet}"):
                    if 'selected_dietary_preferences' not in st.session_state:
                        st.session_state.selected_dietary_preferences = []
                    if diet not in st.session_state.selected_dietary_preferences:
                        st.session_state.selected_dietary_preferences.append(diet)
                        st.rerun()
    
    with cols[1]:
        # Spice level suggestions
        if suggestions.get('spice_levels'):
            st.write("**Suggested Spice:**")
            for spice in suggestions['spice_levels']:
                if st.button(f"🌶️ {spice}", key=f"suggest_spice_{spice}"):
                    st.session_state.selected_spice_levels = [spice]
                    st.rerun()
        
        # Cooking method suggestions
        if suggestions.get('cooking_methods'):
            st.write("**Suggested Cooking:**")
            for method in suggestions['cooking_methods']:
                if st.button(f"🔥 {method}", key=f"suggest_cooking_{method}"):
                    if 'selected_cooking_methods' not in st.session_state:
                        st.session_state.selected_cooking_methods = []
                    if method not in st.session_state.selected_cooking_methods:
                        st.session_state.selected_cooking_methods.append(method)
                        st.rerun()

def render_basic_filters():
    """Render basic filter options"""
    col1, col2 = st.columns(2)
    
    with col1:
        # Dietary preferences
        dietary_options = [
            "Vegetarian", "Vegan", "Gluten-Free", "Keto", "Halal", "Jain",
            "Dairy-Free", "Nut-Free", "Low-Sugar", "Pescatarian"
        ]
        
        selected_dietary = st.multiselect(
            "🥗 Dietary Preferences",
            options=dietary_options,
            default=st.session_state.get('selected_dietary_preferences', []),
            help="Select dietary restrictions or preferences"
        )
        st.session_state.selected_dietary_preferences = selected_dietary
        
        # Cuisine types
        cuisine_options = [
            "Indian", "Chinese", "Italian", "Mexican", "Thai", "Japanese",
            "Mediterranean", "American", "French", "Korean", "Vietnamese"
        ]
        
        selected_cuisine = st.multiselect(
            "🌍 Cuisine Types",
            options=cuisine_options,
            default=st.session_state.get('selected_cuisine_types', []),
            help="Select preferred cuisine types"
        )
        st.session_state.selected_cuisine_types = selected_cuisine
    
    with col2:
        # Spice levels
        spice_options = ["Mild", "Medium", "Hot", "Very Hot"]
        
        selected_spice = st.multiselect(
            "🌶️ Spice Level",
            options=spice_options,
            default=st.session_state.get('selected_spice_levels', []),
            help="Select preferred spice levels"
        )
        st.session_state.selected_spice_levels = selected_spice
        
        # Meal types
        meal_options = ["Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Beverage"]
        
        selected_meal = st.multiselect(
            "🍽️ Meal Type",
            options=meal_options,
            default=st.session_state.get('selected_meal_types', []),
            help="Select meal types"
        )
        st.session_state.selected_meal_types = selected_meal

def render_advanced_filters():
    """Render advanced filter options"""
    col1, col2 = st.columns(2)
    
    with col1:
        # Cooking methods
        cooking_options = [
            "Grilled", "Fried", "Steamed", "Baked", "Sautéed", "Boiled",
            "Roasted", "Stir-fried", "Deep-fried", "Pan-fried"
        ]
        
        selected_cooking = st.multiselect(
            "🔥 Cooking Methods",
            options=cooking_options,
            default=st.session_state.get('selected_cooking_methods', []),
            help="Select preferred cooking methods"
        )
        st.session_state.selected_cooking_methods = selected_cooking
        
        # Price ranges
        price_options = ["Budget", "Mid-range", "Premium", "Luxury"]
        
        selected_price = st.multiselect(
            "💰 Price Range",
            options=price_options,
            default=st.session_state.get('selected_price_ranges', []),
            help="Select preferred price ranges"
        )
        st.session_state.selected_price_ranges = selected_price
    
    with col2:
        # Allergen-free options
        allergen_options = [
            "Nuts", "Dairy", "Gluten", "Eggs", "Soy", "Shellfish",
            "Fish", "Sesame", "Sulfites"
        ]
        
        selected_allergen_free = st.multiselect(
            "🚫 Allergen-Free",
            options=allergen_options,
            default=st.session_state.get('selected_allergen_free', []),
            help="Select allergens to avoid"
        )
        st.session_state.selected_allergen_free = selected_allergen_free
        
        # Custom ingredients
        ingredient_input = st.text_input(
            "🥕 Preferred Ingredients",
            value=", ".join(st.session_state.get('selected_ingredient_preferences', [])),
            placeholder="e.g., tomato, cheese, chicken",
            help="Enter ingredients you want (comma-separated)"
        )
        
        if ingredient_input:
            ingredients = [ing.strip() for ing in ingredient_input.split(',') if ing.strip()]
            st.session_state.selected_ingredient_preferences = ingredients
        else:
            st.session_state.selected_ingredient_preferences = []

def perform_search():
    """Perform visual search with all filters"""
    if 'uploaded_image' not in st.session_state:
        st.error("❌ Please upload an image first!")
        return
    
    # Create filter dictionary for backward compatibility
    custom_filters = {
        'dietary_preferences': st.session_state.get('selected_dietary_preferences', []),
        'cuisine_types': st.session_state.get('selected_cuisine_types', []),
        'spice_levels': st.session_state.get('selected_spice_levels', []),
        'price_ranges': st.session_state.get('selected_price_ranges', []),
        'cooking_methods': st.session_state.get('selected_cooking_methods', []),
        'meal_types': st.session_state.get('selected_meal_types', []),
        'allergen_free': st.session_state.get('selected_allergen_free', []),
        'nutritional_focus': st.session_state.get('selected_nutritional_focus', []),
        'ingredient_preferences': st.session_state.get('selected_ingredient_preferences', []),
        'texture_preferences': st.session_state.get('selected_texture_preferences', [])
    }
    
    with st.spinner("🔍 Searching with filters..."):
        results = search_similar_dishes(st.session_state.uploaded_image, custom_filters, 15)
        
        if results:
            st.session_state.visual_search_results = results
            st.success(f"✅ Found {len(results)} matching dishes!")
            st.rerun()
        else:
            st.warning("⚠️ No matching dishes found. Try adjusting your filters.")

def render_results_section():
    """Render search results with detailed scoring"""
    st.markdown("### 🎯 Search Results")
    
    results = st.session_state.get('visual_search_results', [])
    
    if not results:
        return
    
    # Results summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Results", len(results))
    
    with col2:
        avg_score = sum(r.get('match_score', 0) for r in results) / len(results)
        st.metric("Avg Match Score", f"{avg_score:.1%}")
    
    with col3:
        high_confidence = len([r for r in results if r.get('match_score', 0) > 0.7])
        st.metric("High Confidence", high_confidence)
    
    # Display results
    for i, dish in enumerate(results):
        render_result_card(dish, i)

def render_result_card(dish: Dict, index: int):
    """Render result card with detailed information"""
    match_score = dish.get('match_score', 0)
    score_breakdown = dish.get('score_breakdown', {})
    
    # Color coding based on match score
    if match_score >= 0.8:
        border_color = "🟢"
    elif match_score >= 0.6:
        border_color = "🟡"
    else:
        border_color = "🔴"
    
    with st.container():
        st.markdown(f"#### {border_color} {dish.get('name', 'Unknown Dish')}")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.write(f"**Description:** {dish.get('description', 'No description available')}")
            st.write(f"**Cuisine:** {dish.get('cuisine', 'Unknown')}")
            
            ingredients = dish.get('ingredients', [])
            if isinstance(ingredients, list):
                ingredients_str = ', '.join(str(ing) for ing in ingredients[:5])
                if len(ingredients) > 5:
                    ingredients_str += f" (+{len(ingredients) - 5} more)"
            else:
                ingredients_str = str(ingredients)
            
            st.write(f"**Ingredients:** {ingredients_str}")
        
        with col2:
            analysis = dish.get('analysis_match', {})
            
            st.write(f"**Spice Level:** {analysis.get('spice_level', 'Unknown')}")
            st.write(f"**Cooking Method:** {analysis.get('cooking_method', 'Unknown')}")
            st.write(f"**Meal Type:** {analysis.get('meal_type', 'Unknown')}")
            
            dietary_info = analysis.get('dietary_info', [])
            if dietary_info:
                st.write(f"**Dietary:** {', '.join(dietary_info)}")
        
        with col3:
            # Match score display
            st.metric("Match Score", f"{match_score:.1%}")
            
            # Score breakdown in expander
            if score_breakdown:
                with st.expander("📊 Details"):
                    for category, score in score_breakdown.items():
                        st.write(f"**{category.title()}:** {score:.1%}")
        
        st.markdown("---")

def clear_all_filters():
    """Clear all selected filters"""
    filter_keys = [
        'selected_dietary_preferences', 'selected_cuisine_types', 'selected_spice_levels',
        'selected_price_ranges', 'selected_cooking_methods', 'selected_meal_types',
        'selected_allergen_free', 'selected_nutritional_focus', 'selected_ingredient_preferences',
        'selected_texture_preferences'
    ]
    
    for key in filter_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    st.success("✅ All filters cleared!")
    st.rerun()
