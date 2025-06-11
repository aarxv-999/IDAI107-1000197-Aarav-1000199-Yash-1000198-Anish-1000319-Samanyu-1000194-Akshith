# UI component for the smart restaurant menu management app
import streamlit as st
from typing import List, Dict, Any, Tuple, Optional

# importing all logic functions from the modules
from modules.leftover import load_leftovers, parse_manual_leftovers, suggest_recipes

def leftover_input_csv() -> List[str]:
    """
    Renders clean UI for uploading a CSV file containing leftover ingredients.
    
    Returns:
        List[str]: List of leftover ingredients
    """
    st.sidebar.subheader("CSV Upload")
    use_csv = st.sidebar.checkbox("Upload from CSV file")
    
    leftovers = []    
    if use_csv:
        uploaded_file = st.sidebar.file_uploader( 
            "Choose CSV file", 
            type=["csv"],
            help="CSV should contain a column with ingredient names"
        )
        if uploaded_file is not None:
            try:
                leftovers = load_leftovers(uploaded_file)
                st.sidebar.success(f"Loaded {len(leftovers)} ingredients")
            except Exception as err:
                st.sidebar.error(f"Error loading CSV: {str(err)}")
                st.sidebar.info("Please check your CSV format")
    return leftovers

def leftover_input_manual() -> List[str]:
    """
    Creates clean UI for manually inputting leftover ingredients.
    
    Returns:
        List[str]: List of manually entered leftover ingredients
    """
    st.sidebar.subheader("Manual Entry")
    ingredients_text = st.sidebar.text_area(
        "Enter ingredients (comma-separated)",
        placeholder="tomatoes, onions, chicken, rice",
        help="Separate ingredients with commas"
    )
    
    leftovers = []
    if ingredients_text:
        try:
            leftovers = parse_manual_leftovers(ingredients_text)
            st.sidebar.success(f"Added {len(leftovers)} ingredients")
        except Exception as err:
            st.sidebar.error(f"Error: {str(err)}")
    return leftovers

def display_leftover_summary(leftovers: List[str]):
    """
    Display current leftovers in a clean format.
    
    Args:
        leftovers (List[str]): List of leftover ingredients
    """
    if leftovers:
        st.subheader("Current Ingredients")
        
        # Display as columns for better layout
        cols = st.columns(min(len(leftovers), 3))
        for i, ingredient in enumerate(leftovers):
            col_idx = i % 3
            with cols[col_idx]:
                st.info(ingredient.title())
    else:
        st.info("No ingredients added yet")

def display_recipe_suggestions(recipes: List[Dict], leftovers: List[str]):
    """
    Display recipe suggestions in a clean, organized format.
    
    Args:
        recipes (List[Dict]): List of recipe suggestions
        leftovers (List[str]): List of available ingredients
    """
    if not recipes:
        st.warning("No recipe suggestions found")
        return
    
    st.subheader("Recipe Suggestions")
    
    for i, recipe in enumerate(recipes):
        with st.expander(f"{recipe.get('name', f'Recipe {i+1}')}", expanded=i==0):
            
            # Recipe overview
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if 'description' in recipe:
                    st.write(recipe['description'])
                
                if 'cooking_time' in recipe:
                    st.caption(f"Cooking Time: {recipe['cooking_time']}")
                
                if 'difficulty' in recipe:
                    st.caption(f"Difficulty: {recipe['difficulty']}")
            
            with col2:
                if 'servings' in recipe:
                    st.metric("Servings", recipe['servings'])
            
            # Ingredients section
            if 'ingredients' in recipe:
                st.write("**Ingredients:**")
                for ingredient in recipe['ingredients']:
                    # Highlight ingredients we have
                    if any(leftover.lower() in ingredient.lower() for leftover in leftovers):
                        st.write(f"✓ {ingredient}")
                    else:
                        st.write(f"• {ingredient}")
            
            # Instructions section
            if 'instructions' in recipe:
                st.write("**Instructions:**")
                for j, instruction in enumerate(recipe['instructions'], 1):
                    st.write(f"{j}. {instruction}")
            
            # Additional info
            if 'nutrition' in recipe:
                st.write("**Nutrition Info:**")
                nutrition = recipe['nutrition']
                cols = st.columns(len(nutrition))
                for k, (key, value) in enumerate(nutrition.items()):
                    with cols[k]:
                        st.metric(key.title(), value)

def display_ingredient_filter():
    """
    Display ingredient filtering options with clean interface.
    
    Returns:
        Dict: Filter options selected by user
    """
    st.sidebar.divider()
    st.sidebar.subheader("Filters")
    
    # Dietary restrictions
    dietary_options = st.sidebar.multiselect(
        "Dietary Restrictions",
        ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Paleo"],
        help="Filter recipes by dietary needs"
    )
    
    # Cuisine type
    cuisine_type = st.sidebar.selectbox(
        "Cuisine Type",
        ["Any", "Italian", "Asian", "Mexican", "American", "Mediterranean", "Indian"],
        help="Choose preferred cuisine style"
    )
    
    # Cooking time
    max_time = st.sidebar.slider(
        "Max Cooking Time (minutes)",
        min_value=15,
        max_value=120,
        value=60,
        step=15,
        help="Maximum time you want to spend cooking"
    )
    
    # Difficulty level
    difficulty = st.sidebar.selectbox(
        "Max Difficulty",
        ["Any", "Easy", "Medium", "Hard"],
        help="Choose maximum difficulty level"
    )
    
    return {
        "dietary": dietary_options,
        "cuisine": cuisine_type if cuisine_type != "Any" else None,
        "max_time": max_time,
        "difficulty": difficulty if difficulty != "Any" else None
    }

def display_recipe_stats(recipes: List[Dict]):
    """
    Display statistics about the recipe suggestions.
    
    Args:
        recipes (List[Dict]): List of recipes to analyze
    """
    if not recipes:
        return
    
    st.sidebar.divider()
    st.sidebar.subheader("Recipe Stats")
    
    # Basic stats
    total_recipes = len(recipes)
    st.sidebar.metric("Total Recipes", total_recipes)
    
    # Average cooking time
    cooking_times = []
    for recipe in recipes:
        if 'cooking_time' in recipe:
            # Extract numeric value from cooking time string
            time_str = recipe['cooking_time']
            try:
                # Simple extraction of numbers from string
                import re
                numbers = re.findall(r'\d+', time_str)
                if numbers:
                    cooking_times.append(int(numbers[0]))
            except:
                pass
    
    if cooking_times:
        avg_time = sum(cooking_times) / len(cooking_times)
        st.sidebar.metric("Avg. Cooking Time", f"{avg_time:.0f} min")
    
    # Difficulty distribution
    difficulties = {}
    for recipe in recipes:
        if 'difficulty' in recipe:
            diff = recipe['difficulty']
            difficulties[diff] = difficulties.get(diff, 0) + 1
    
    if difficulties:
        st.sidebar.write("**Difficulty Breakdown:**")
        for diff, count in difficulties.items():
            st.sidebar.write(f"• {diff}: {count}")

def display_shopping_list(recipes: List[Dict], available_ingredients: List[str]):
    """
    Generate and display a shopping list for selected recipes.
    
    Args:
        recipes (List[Dict]): Selected recipes
        available_ingredients (List[str]): Ingredients already available
    """
    if not recipes:
        return
    
    st.subheader("Shopping List")
    
    # Collect all ingredients from selected recipes
    all_ingredients = set()
    for recipe in recipes:
        if 'ingredients' in recipe:
            for ingredient in recipe['ingredients']:
                # Clean ingredient text (remove quantities, etc.)
                clean_ingredient = ingredient.lower().strip()
                all_ingredients.add(clean_ingredient)
    
    # Filter out ingredients we already have
    available_lower = [ing.lower().strip() for ing in available_ingredients]
    missing_ingredients = []
    
    for ingredient in all_ingredients:
        if not any(avail in ingredient or ingredient in avail for avail in available_lower):
            missing_ingredients.append(ingredient)
    
    if missing_ingredients:
        st.write("**Items to buy:**")
        for ingredient in sorted(missing_ingredients):
            st.write(f"• {ingredient.title()}")
    else:
        st.success("You have all ingredients needed!")

def display_recipe_search():
    """
    Display recipe search functionality with clean interface.
    
    Returns:
        str: Search query entered by user
    """
    st.subheader("Recipe Search")
    
    search_query = st.text_input(
        "Search recipes",
        placeholder="Enter dish name, ingredient, or cuisine type...",
        help="Search for specific recipes or ingredients"
    )
    
    return search_query

def display_save_recipe_option(recipe: Dict):
    """
    Display option to save/favorite a recipe.
    
    Args:
        recipe (Dict): Recipe to save
    
    Returns:
        bool: True if recipe was saved
    """
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("Save Recipe", key=f"save_{recipe.get('name', 'recipe')}", type="secondary"):
            # Here you would implement the actual saving logic
            st.success("Recipe saved!")
            return True
    
    return False

def display_nutrition_info(recipe: Dict):
    """
    Display nutrition information in a clean format.
    
    Args:
        recipe (Dict): Recipe with nutrition data
    """
    if 'nutrition' not in recipe:
        return
    
    st.write("**Nutrition Information (per serving):**")
    nutrition = recipe['nutrition']
    
    # Display nutrition in columns
    cols = st.columns(min(len(nutrition), 4))
    for i, (key, value) in enumerate(nutrition.items()):
        col_idx = i % 4
        with cols[col_idx]:
            st.metric(key.replace('_', ' ').title(), value)

def display_recipe_rating(recipe: Dict):
    """
    Display recipe rating and review functionality.
    
    Args:
        recipe (Dict): Recipe to rate
    
    Returns:
        int: Rating given by user (1-5)
    """
    st.write("**Rate this recipe:**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        rating = st.selectbox(
            "Rating",
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: "★" * x + "☆" * (5-x),
            key=f"rating_{recipe.get('name', 'recipe')}"
        )
    
    with col2:
        if st.button("Submit Rating", key=f"submit_rating_{recipe.get('name', 'recipe')}"):
            st.success(f"Rated {rating} stars!")
            return rating
    
    return None

def display_cooking_timer():
    """
    Display a cooking timer widget.
    
    Returns:
        int: Timer duration in minutes
    """
    st.sidebar.divider()
    st.sidebar.subheader("Cooking Timer")
    
    timer_minutes = st.sidebar.number_input(
        "Minutes",
        min_value=1,
        max_value=180,
        value=15,
        step=1
    )
    
    if st.sidebar.button("Start Timer"):
        st.sidebar.success(f"Timer set for {timer_minutes} minutes!")
        # Here you would implement actual timer functionality
    
    return timer_minutes

def display_meal_planner():
    """
    Display meal planning interface.
    
    Returns:
        Dict: Meal plan selections
    """
    st.subheader("Weekly Meal Planner")
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meals = ["Breakfast", "Lunch", "Dinner"]
    
    meal_plan = {}
    
    for day in days:
        with st.expander(day):
            meal_plan[day] = {}
            cols = st.columns(3)
            
            for i, meal in enumerate(meals):
                with cols[i]:
                    meal_plan[day][meal] = st.text_input(
                        meal,
                        key=f"{day}_{meal}",
                        placeholder="Enter recipe name"
                    )
    
    if st.button("Save Meal Plan", type="primary"):
        st.success("Meal plan saved!")
    
    return meal_plan

def display_ingredient_substitutions(ingredient: str):
    """
    Display common substitutions for an ingredient.
    
    Args:
        ingredient (str): Ingredient to find substitutions for
    
    Returns:
        List[str]: List of substitution suggestions
    """
    # Common substitutions dictionary
    substitutions = {
        "butter": ["margarine", "vegetable oil", "coconut oil", "applesauce"],
        "eggs": ["flax eggs", "chia eggs", "applesauce", "banana"],
        "milk": ["almond milk", "soy milk", "oat milk", "coconut milk"],
        "flour": ["almond flour", "coconut flour", "oat flour", "rice flour"],
        "sugar": ["honey", "maple syrup", "stevia", "coconut sugar"],
        "cream": ["coconut cream", "cashew cream", "greek yogurt"]
    }
    
    ingredient_lower = ingredient.lower()
    possible_subs = []
    
    for key, subs in substitutions.items():
        if key in ingredient_lower or ingredient_lower in key:
            possible_subs = subs
            break
    
    if possible_subs:
        st.write(f"**Substitutions for {ingredient}:**")
        for sub in possible_subs:
            st.write(f"• {sub}")
    
    return possible_subs

def display_cost_calculator(recipes: List[Dict]):
    """
    Display estimated cost calculator for recipes.
    
    Args:
        recipes (List[Dict]): List of recipes to calculate cost for
    
    Returns:
        float: Estimated total cost
    """
    if not recipes:
        return 0.0
    
    st.subheader("Cost Estimate")
    
    # Simple cost estimation (in a real app, this would use actual price data)
    base_cost_per_serving = 3.50
    total_cost = len(recipes) * base_cost_per_serving
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Recipes", len(recipes))
    
    with col2:
        st.metric("Est. Cost per Recipe", f"${base_cost_per_serving:.2f}")
    
    with col3:
        st.metric("Total Estimated Cost", f"${total_cost:.2f}")
    
    st.caption("*Estimates based on average ingredient costs")
    
    return total_cost

def display_recipe_export_options(recipes: List[Dict]):
    """
    Display options to export recipes in various formats.
    
    Args:
        recipes (List[Dict]): Recipes to export
    """
    if not recipes:
        return
    
    st.subheader("Export Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Export as PDF", use_container_width=True):
            st.info("PDF export feature coming soon!")
    
    with col2:
        if st.button("Email Recipes", use_container_width=True):
            st.info("Email feature coming soon!")
    
    with col3:
        if st.button("Share Link", use_container_width=True):
            st.info("Share feature coming soon!")

def display_quick_actions():
    """
    Display quick action buttons for common tasks.
    
    Returns:
        str: Selected quick action
    """
    st.sidebar.divider()
    st.sidebar.subheader("Quick Actions")
    
    actions = {
        "Random Recipe": "Get a random recipe suggestion",
        "Clear All": "Clear all ingredients and start over",
        "Save Session": "Save current session",
        "Load Favorites": "Load your favorite recipes"
    }
    
    selected_action = None
    
    for action, description in actions.items():
        if st.sidebar.button(action, help=description, use_container_width=True):
            selected_action = action
            break
    
    return selected_action

def display_app_settings():
    """
    Display application settings in sidebar.
    
    Returns:
        Dict: User settings
    """
    st.sidebar.divider()
    st.sidebar.subheader("Settings")
    
    settings = {}
    
    # Theme preference
    settings['theme'] = st.sidebar.selectbox(
        "Theme",
        ["Light", "Dark", "Auto"],
        help="Choose your preferred theme"
    )
    
    # Units preference
    settings['units'] = st.sidebar.selectbox(
        "Units",
        ["Metric", "Imperial"],
        help="Choose measurement units"
    )
    
    # Notifications
    settings['notifications'] = st.sidebar.checkbox(
        "Enable notifications",
        value=True,
        help="Receive cooking tips and reminders"
    )
    
    return settings
