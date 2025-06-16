"""
Chef Components Module for Smart Restaurant Menu Management System
Handles chef recipe submissions, AI rating generation, XP rewards, and chef leaderboards
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
import os
import json
import google.generativeai as genai
from firebase_admin import firestore
import firebase_admin
from typing import List, Dict, Tuple, Optional
import pandas as pd

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONNECTION FUNCTIONS
# ============================================================================

def get_firestore_client():
    """Get Firestore client for chef submissions"""
    try:
        # Use the main Firebase app (default) for chef submissions
        if firebase_admin._apps:
            return firestore.client()
        else:
            # Initialize main Firebase if not already done
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client: {str(e)}")
        return None

# ============================================================================
# MAIN RENDER FUNCTIONS
# ============================================================================

def render_chef_recipe_suggestions():
    """Main function to render chef recipe suggestions interface"""
    st.title("👨‍🍳 Chef Recipe Submissions")
    st.markdown("Submit your original recipes and get AI feedback with XP rewards!")
    
    # Get database connection
    db = get_firestore_client()
    if not db:
        st.error("Database connection failed. Please try again later.")
        return
    
    # Check user authentication
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to access chef features.")
        return
    
    # Create tabs for different chef functions
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Submit Recipe", "📊 My Submissions", "🏆 Chef Leaderboard", "📈 Analytics"])
    
    with tab1:
        render_chef_submission(db)
    
    with tab2:
        render_chef_submissions_history(db)
    
    with tab3:
        render_chef_leaderboard(db)
    
    with tab4:
        render_chef_analytics(db)

def render_chef_submission(db):
    """Render the chef recipe submission form"""
    st.subheader("Submit Your Recipe")
    
    # Get current user
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to submit recipes.")
        return
    
    # Check if user is a chef (allow all roles for now, but show different messaging)
    user_role = user.get('role', 'user')
    if user_role != 'chef':
        st.info(f"You're logged in as '{user_role}'. Anyone can submit recipes, but chefs get special recognition!")
    
    # Show XP information
    with st.expander("💎 XP Rewards System", expanded=False):
        st.markdown("""
        **Earn XP based on AI recipe ratings:**
        - ⭐ 1 Star: 5 XP
        - ⭐⭐ 2 Stars: 10 XP  
        - ⭐⭐⭐ 3 Stars: 15 XP
        - ⭐⭐⭐⭐ 4 Stars: 30 XP (20 base + 10 bonus)
        - ⭐⭐⭐⭐⭐ 5 Stars: 45 XP (25 base + 20 bonus)
        
        **AI evaluates recipes based on:**
        - Creativity and uniqueness (25%)
        - Ingredient quality and combination (25%)
        - Cooking technique and method (25%)
        - Overall appeal and feasibility (25%)
        """)
    
    with st.form("chef_recipe_submission"):
        st.markdown("### Recipe Details")
        
        # Basic recipe information
        col1, col2 = st.columns(2)
        
        with col1:
            dish_name = st.text_input(
                "Recipe Name *",
                placeholder="e.g., Spicy Garlic Butter Shrimp",
                help="Give your recipe an appetizing name"
            )
            
            cook_time = st.selectbox(
                "Cooking Time *",
                ["Under 15 minutes", "15-30 minutes", "30-45 minutes", "45 minutes - 1 hour", "1-2 hours", "2+ hours"],
                help="Estimated total cooking time"
            )
            
            cuisine = st.selectbox(
                "Cuisine Type *",
                ["Italian", "Indian", "Chinese", "Mexican", "American", "French", "Thai", "Mediterranean", "Japanese", "Korean", "Vietnamese", "Middle Eastern", "African", "Fusion", "Other"],
                help="Primary cuisine style"
            )
            
            difficulty = st.selectbox(
                "Difficulty Level *",
                ["Beginner", "Intermediate", "Advanced", "Expert"],
                help="Cooking skill level required"
            )
        
        with col2:
            category = st.selectbox(
                "Category *",
                ["Appetizer", "Main Course", "Dessert", "Side Dish", "Soup", "Salad", "Beverage", "Snack", "Breakfast", "Lunch", "Dinner"],
                help="Type of dish"
            )
            
            servings = st.number_input(
                "Servings *",
                min_value=1,
                max_value=20,
                value=4,
                help="Number of people this recipe serves"
            )
            
            diet = st.multiselect(
                "Dietary Options",
                ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Keto", "Low-Carb", "High-Protein", "Paleo", "Nut-Free"],
                help="Select all applicable dietary restrictions"
            )
            
            chef_name = st.text_input(
                "Chef Name *",
                value=user.get('full_name', user.get('username', '')),
                help="Your name as it will appear on the recipe"
            )
        
        # Recipe description
        description = st.text_area(
            "Recipe Description *",
            placeholder="Describe your dish, its flavors, inspiration, and what makes it special. Include any background story or cultural significance...",
            height=120,
            help="Provide a detailed description of your recipe"
        )
        
        # Ingredients
        st.markdown("### Ingredients")
        ingredients = st.text_area(
            "Ingredients List *",
            placeholder="List ingredients with precise measurements, one per line:\n• 2 cups basmati rice, rinsed\n• 1 lb large shrimp, peeled and deveined\n• 4 cloves garlic, minced\n• 2 tbsp unsalted butter\n• 1 tsp paprika\n• Salt and pepper to taste",
            height=180,
            help="List all ingredients with exact quantities and preparation notes"
        )
        
        # Cooking instructions
        st.markdown("### Instructions")
        instructions = st.text_area(
            "Step-by-Step Instructions *",
            placeholder="Provide detailed cooking instructions:\n\n1. Preparation (5 mins):\n   - Rinse rice until water runs clear\n   - Pat shrimp dry and season with salt and pepper\n\n2. Cooking (20 mins):\n   - Heat butter in large skillet over medium-high heat\n   - Add garlic and cook until fragrant, about 30 seconds\n   - Add shrimp and cook 2-3 minutes per side until pink\n\n3. Finishing:\n   - Sprinkle with paprika and serve immediately",
            height=250,
            help="Detailed step-by-step cooking instructions with timing"
        )
        
        # Additional information
        col1, col2 = st.columns(2)
        
        with col1:
            prep_time = st.text_input(
                "Prep Time",
                placeholder="e.g., 15 minutes",
                help="Time needed for preparation"
            )
            
            equipment = st.text_area(
                "Required Equipment",
                placeholder="e.g., Large skillet, wooden spoon, measuring cups",
                height=80,
                help="List any special equipment needed"
            )
        
        with col2:
            storage_tips = st.text_area(
                "Storage & Reheating Tips",
                placeholder="e.g., Store in refrigerator for up to 3 days. Reheat gently in microwave.",
                height=80,
                help="How to store and reheat leftovers"
            )
            
            variations = st.text_area(
                "Recipe Variations",
                placeholder="e.g., Substitute chicken for shrimp, add vegetables like bell peppers",
                height=80,
                help="Suggest possible variations or substitutions"
            )
        
        # Chef's notes
        notes = st.text_area(
            "Chef's Notes & Tips (Optional)",
            placeholder="Share any professional tips, tricks, or personal insights that make this recipe special...",
            height=100,
            help="Additional tips and insights from your experience"
        )
        
        # Submit button
        submitted = st.form_submit_button("🚀 Submit Recipe for AI Review", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            required_fields = {
                'Recipe Name': dish_name,
                'Description': description,
                'Ingredients': ingredients,
                'Instructions': instructions,
                'Chef Name': chef_name,
                'Cook Time': cook_time,
                'Cuisine': cuisine,
                'Category': category
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value or not value.strip()]
            
            if missing_fields:
                st.error(f"Please fill in the following required fields: {', '.join(missing_fields)}")
            else:
                # Process the submission
                with st.spinner("Submitting recipe and generating AI rating..."):
                    process_chef_submission(db, chef_name, dish_name, description, ingredients, cook_time, cuisine, diet, category)

def process_chef_submission(db, chef_name, dish_name, description, ingredients, cook_time, cuisine, diet, category):
    """
    Processes the chef's recipe submission, including saving the recipe,
    generating AI rating, awarding XP, and displaying notifications.
    """
    # Get current user
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("User session error. Please log in again.")
        return

    # Get additional form data from session state or form
    instructions = st.session_state.get('instructions', '')
    notes = st.session_state.get('notes', '')
    difficulty = st.session_state.get('difficulty', 'Intermediate')
    servings = st.session_state.get('servings', 4)
    prep_time = st.session_state.get('prep_time', '')
    equipment = st.session_state.get('equipment', '')
    storage_tips = st.session_state.get('storage_tips', '')
    variations = st.session_state.get('variations', '')

    try:
        # Prepare recipe data for database
        recipe_data = {
            'name': dish_name,
            'description': description,
            'ingredients': ingredients.split('\n') if isinstance(ingredients, str) else ingredients,
            'instructions': instructions,
            'cook_time': cook_time,
            'prep_time': prep_time,
            'cuisine': cuisine,
            'diet': diet if isinstance(diet, list) else [diet] if diet else [],
            'category': category,
            'difficulty': difficulty,
            'servings': servings,
            'equipment': equipment,
            'storage_tips': storage_tips,
            'variations': variations,
            'chef_name': chef_name,
            'chef_user_id': user['user_id'],
            'chef_role': user.get('role', 'user'),
            'submitted_at': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.now().isoformat(),
            'status': 'submitted',
            'source': 'Chef Submission',
            'notes': notes,
            'rating': None,  # Will be set after AI evaluation
            'ai_feedback': None,
            'views': 0,
            'likes': 0,
            'featured': False
        }
        
        # Save to recipes collection
        doc_ref = db.collection('recipes').add(recipe_data)
        recipe_id = doc_ref[1].id
        
        logger.info(f"Recipe '{dish_name}' saved to database with ID: {recipe_id}")
        
        # Generate AI rating and feedback for the recipe
        try:
            rating, feedback, detailed_scores = generate_ai_recipe_rating_and_feedback(
                dish_name, description, ingredients, instructions, cook_time, cuisine, category, difficulty
            )
            
            # Update the recipe with the rating and feedback
            db.collection('recipes').document(recipe_id).update({
                'rating': rating,
                'ai_feedback': feedback,
                'ai_detailed_scores': detailed_scores,
                'evaluation_date': firestore.SERVER_TIMESTAMP
            })
            
            # Display results
            st.success(f"✅ Recipe '{dish_name}' submitted successfully!")
            
            # Show AI rating with stars
            star_display = "⭐" * rating + "☆" * (5 - rating)
            st.info(f"🤖 **AI Rating:** {rating}/5 {star_display}")
            
            # Show detailed scores
            if detailed_scores:
                st.markdown("### 📊 Detailed AI Evaluation")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Creativity", f"{detailed_scores.get('creativity', 0)}/5")
                with col2:
                    st.metric("Ingredients", f"{detailed_scores.get('ingredients', 0)}/5")
                with col3:
                    st.metric("Technique", f"{detailed_scores.get('technique', 0)}/5")
                with col4:
                    st.metric("Appeal", f"{detailed_scores.get('appeal', 0)}/5")
            
            # Show AI feedback
            if feedback:
                st.markdown("### 📝 AI Feedback & Suggestions")
                st.write(feedback)
            
            # Award XP based on rating
            award_chef_submission_xp(user['user_id'], rating, chef_name, dish_name)
            
        except Exception as e:
            logger.error(f"Error generating AI rating: {str(e)}")
            st.success(f"✅ Recipe '{dish_name}' submitted successfully!")
            st.warning("Recipe saved, but AI rating could not be generated at this time.")

    except Exception as e:
        st.error(f"Error saving recipe to database: {str(e)}")
        logger.exception("Error during recipe database save")

# ============================================================================
# AI RATING AND FEEDBACK FUNCTIONS
# ============================================================================

def generate_ai_recipe_rating_and_feedback(dish_name, description, ingredients, instructions, cook_time, cuisine, category, difficulty):
    """Generate AI rating and detailed feedback for the submitted recipe"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found, using default rating")
            return 3, "AI rating unavailable - API key not configured.", {}
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        ingredients_text = ingredients if isinstance(ingredients, str) else '\n'.join(ingredients)
        
        prompt = f"""As a professional chef and food critic, evaluate this recipe submission comprehensively.

RECIPE DETAILS:
Name: {dish_name}
Category: {category}
Cuisine: {cuisine}
Difficulty: {difficulty}
Cook Time: {cook_time}
Description: {description}

INGREDIENTS:
{ingredients_text}

INSTRUCTIONS:
{instructions}

EVALUATION CRITERIA:
Rate each aspect from 1-5 and provide an overall rating:

1. CREATIVITY & UNIQUENESS (25%):
   - How original and innovative is this recipe?
   - Does it offer something new or interesting?
   - Creative use of ingredients or techniques?

2. INGREDIENT QUALITY & COMBINATION (25%):
   - Are ingredients well-chosen and complementary?
   - Appropriate quantities and balance?
   - Quality of ingredient selection?

3. COOKING TECHNIQUE & METHOD (25%):
   - Are cooking methods appropriate and well-explained?
   - Clear, logical step-by-step instructions?
   - Proper cooking techniques for the dish?

4. OVERALL APPEAL & FEASIBILITY (25%):
   - How appealing does this dish sound?
   - Is it practical for home cooks?
   - Good balance of flavor, texture, and presentation?

RESPONSE FORMAT:
CREATIVITY: [1-5]
INGREDIENTS: [1-5]
TECHNIQUE: [1-5]
APPEAL: [1-5]
OVERALL_RATING: [1-5]

FEEDBACK:
[Provide detailed, constructive feedback covering:]
- What works exceptionally well
- Areas for improvement with specific suggestions
- Technical cooking advice
- Flavor profile analysis
- Presentation suggestions
- Variations or modifications to consider

Be professional, encouraging, and constructive while providing honest assessment."""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse rating and feedback
        try:
            lines = response_text.split('\n')
            detailed_scores = {}
            overall_rating = 3  # default
            feedback = "No feedback available."
            
            # Parse individual scores
            for line in lines:
                line = line.strip()
                if line.startswith('CREATIVITY:'):
                    try:
                        detailed_scores['creativity'] = int(line.split(':')[1].strip())
                    except:
                        detailed_scores['creativity'] = 3
                elif line.startswith('INGREDIENTS:'):
                    try:
                        detailed_scores['ingredients'] = int(line.split(':')[1].strip())
                    except:
                        detailed_scores['ingredients'] = 3
                elif line.startswith('TECHNIQUE:'):
                    try:
                        detailed_scores['technique'] = int(line.split(':')[1].strip())
                    except:
                        detailed_scores['technique'] = 3
                elif line.startswith('APPEAL:'):
                    try:
                        detailed_scores['appeal'] = int(line.split(':')[1].strip())
                    except:
                        detailed_scores['appeal'] = 3
                elif line.startswith('OVERALL_RATING:'):
                    try:
                        overall_rating = int(line.split(':')[1].strip())
                        if not (1 <= overall_rating <= 5):
                            overall_rating = 3
                    except:
                        overall_rating = 3
                elif line.startswith('FEEDBACK:'):
                    feedback_start_idx = lines.index(line)
                    if feedback_start_idx < len(lines) - 1:
                        feedback_lines = lines[feedback_start_idx + 1:]
                        feedback = '\n'.join(feedback_lines).strip()
                        if not feedback:
                            feedback = "No detailed feedback provided."
            
            # Validate scores
            for key in ['creativity', 'ingredients', 'technique', 'appeal']:
                if key not in detailed_scores:
                    detailed_scores[key] = 3
                elif not (1 <= detailed_scores[key] <= 5):
                    detailed_scores[key] = 3
            
            return overall_rating, feedback, detailed_scores
            
        except Exception as parse_error:
            logger.warning(f"Could not parse AI response: {parse_error}")
            return 3, "AI feedback parsing error occurred.", {'creativity': 3, 'ingredients': 3, 'technique': 3, 'appeal': 3}
            
    except Exception as e:
        logger.error(f"Error generating AI rating and feedback: {str(e)}")
        return 3, "AI rating and feedback unavailable due to technical error.", {'creativity': 3, 'ingredients': 3, 'technique': 3, 'appeal': 3}

# ============================================================================
# XP AND GAMIFICATION FUNCTIONS
# ============================================================================

def award_chef_submission_xp(user_id, rating, chef_name, dish_name):
    """Award XP based on the AI rating received"""
    try:
        # Calculate XP based on rating: 1 star = 5 XP, 2 stars = 10 XP, etc.
        base_xp_per_star = 5
        rating_xp = rating * base_xp_per_star
        
        # Bonus XP for high ratings
        bonus_xp = 0
        if rating >= 4:
            bonus_xp = 10  # Bonus for 4-5 star recipes
        if rating == 5:
            bonus_xp = 20  # Extra bonus for perfect 5-star recipes
        
        total_xp = rating_xp + bonus_xp
        
        # Update user stats with XP
        from modules.leftover import update_user_stats
        update_user_stats(user_id=user_id, xp_gained=total_xp, recipes_generated=1)
        
        # Show XP notification
        from modules.components import show_xp_notification
        show_xp_notification(total_xp, f"chef recipe submission ({rating}⭐)")
        
        # Show detailed XP breakdown
        if bonus_xp > 0:
            st.success(f"🎉 **XP Earned:** {total_xp} total ({rating_xp} base + {bonus_xp} bonus for {rating}⭐ rating)")
        else:
            st.success(f"🎉 **XP Earned:** {total_xp} XP for {rating}⭐ rating")
        
        # Show achievement notifications
        check_chef_achievements(user_id, rating)
            
        logger.info(f"Awarded {total_xp} XP to chef {chef_name} (ID: {user_id}) for {rating}-star recipe '{dish_name}'")
        
    except Exception as e:
        logger.error(f"Error awarding XP for chef submission: {str(e)}")
        st.warning("Recipe saved successfully, but there was an issue awarding XP.")

def check_chef_achievements(user_id, rating):
    """Check and display chef-specific achievements"""
    try:
        db = get_firestore_client()
        if not db:
            return
        
        # Get user's recipe submissions - simpler query
        user_recipes_ref = db.collection('recipes').where('chef_user_id', '==', user_id)
        all_user_recipes = list(user_recipes_ref.stream())
        
        # Filter for chef submissions after fetching
        user_recipes = [doc for doc in all_user_recipes if doc.to_dict().get('source') == 'Chef Submission']
        
        total_submissions = len(user_recipes)
        five_star_count = sum(1 for doc in user_recipes if doc.to_dict().get('rating') == 5)
        four_plus_star_count = sum(1 for doc in user_recipes if doc.to_dict().get('rating', 0) >= 4)
        
        # Check for achievements
        achievements = []
        
        if total_submissions == 1:
            achievements.append("🍳 First Recipe - Welcome to the kitchen!")
        elif total_submissions == 5:
            achievements.append("👨‍🍳 Recipe Enthusiast - 5 recipes submitted!")
        elif total_submissions == 10:
            achievements.append("🏆 Prolific Chef - 10 recipes and counting!")
        
        if rating == 5 and five_star_count == 1:
            achievements.append("⭐ Perfect Recipe - Your first 5-star dish!")
        elif five_star_count == 3:
            achievements.append("🌟 Master Chef - 3 perfect recipes!")
        elif five_star_count == 5:
            achievements.append("💎 Culinary Genius - 5 perfect recipes!")
        
        if four_plus_star_count >= 5:
            achievements.append("🎖️ Consistent Excellence - 5+ high-rated recipes!")
        
        # Display achievements
        for achievement in achievements:
            st.balloons()
            st.success(f"🏆 **Achievement Unlocked:** {achievement}")
        
    except Exception as e:
        logger.error(f"Error checking chef achievements: {str(e)}")

# ============================================================================
# HISTORY AND ANALYTICS FUNCTIONS
# ============================================================================

def render_chef_submissions_history(db):
    """Display chef's submission history"""
    st.subheader("📊 Your Recipe Submissions")
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to view your submissions.")
        return
    
    try:
        # Get user's submissions - SIMPLER QUERY WITHOUT ORDERING
        # This avoids the need for a composite index
        submissions_ref = db.collection('recipes').where('chef_user_id', '==', user['user_id'])
        submissions = list(submissions_ref.stream())
        
        # Filter for chef submissions after fetching
        submissions = [doc for doc in submissions if doc.to_dict().get('source') == 'Chef Submission']
        
        # Sort in Python instead of in the query
        submissions.sort(key=lambda x: x.to_dict().get('submitted_at', datetime.min), reverse=True)
        
        if not submissions:
            st.info("You haven't submitted any recipes yet. Use the 'Submit Recipe' tab to get started!")
            return
        
        # Display statistics
        total_submissions = len(submissions)
        ratings = [doc.to_dict().get('rating', 0) for doc in submissions if doc.to_dict().get('rating')]
        total_rating = sum(ratings)
        avg_rating = total_rating / len(ratings) if ratings else 0
        five_star_count = sum(1 for rating in ratings if rating == 5)
        four_plus_count = sum(1 for rating in ratings if rating >= 4)
        
        # Statistics display
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Submissions", total_submissions)
        with col2:
            st.metric("Average Rating", f"{avg_rating:.1f}⭐")
        with col3:
            st.metric("5⭐ Recipes", five_star_count)
        with col4:
            st.metric("4+ ⭐ Recipes", four_plus_count)
        
        # Filter options
        st.markdown("### Filter & Sort")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            rating_filter = st.selectbox("Filter by Rating", ["All", "5⭐", "4⭐", "3⭐", "2⭐", "1⭐"])
        with col2:
            category_filter = st.selectbox("Filter by Category", ["All"] + list(set(doc.to_dict().get('category', 'Unknown') for doc in submissions)))
        with col3:
            sort_by = st.selectbox("Sort by", ["Newest First", "Oldest First", "Highest Rated", "Lowest Rated"])
        
        # Apply filters and sorting
        filtered_submissions = submissions.copy()
        
        # Apply rating filter
        if rating_filter != "All":
            target_rating = int(rating_filter[0])
            filtered_submissions = [doc for doc in filtered_submissions if doc.to_dict().get('rating') == target_rating]
        
        # Apply category filter
        if category_filter != "All":
            filtered_submissions = [doc for doc in filtered_submissions if doc.to_dict().get('category') == category_filter]
        
        # Apply sorting
        if sort_by == "Oldest First":
            filtered_submissions.reverse()
        elif sort_by == "Highest Rated":
            filtered_submissions.sort(key=lambda x: x.to_dict().get('rating', 0), reverse=True)
        elif sort_by == "Lowest Rated":
            filtered_submissions.sort(key=lambda x: x.to_dict().get('rating', 0))
        
        # Display submissions
        st.markdown(f"### Your Recipes ({len(filtered_submissions)} shown)")
        
        for doc in filtered_submissions:
            recipe = doc.to_dict()
            
            # Recipe card - REMOVED NESTED EXPANDERS
            recipe_title = f"🍽️ {recipe.get('name', 'Unnamed Recipe')} - {recipe.get('rating', 'No rating')}⭐"
            
            with st.container():
                st.markdown(f"#### {recipe_title}")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Description:** {recipe.get('description', 'No description')}")
                    st.write(f"**Category:** {recipe.get('category', 'Unknown')} | **Cuisine:** {recipe.get('cuisine', 'Unknown')}")
                    st.write(f"**Cook Time:** {recipe.get('cook_time', 'Unknown')}")
                    st.write(f"**Servings:** {recipe.get('servings', 'Unknown')}")
                    
                    if recipe.get('diet'):
                        st.write(f"**Dietary:** {', '.join(recipe['diet'])}")
                    
                    # Show AI feedback directly without nested expander
                    if recipe.get('ai_feedback'):
                        st.markdown("**AI Feedback:**")
                        st.write(recipe['ai_feedback'])
                
                with col2:
                    rating = recipe.get('rating', 0)
                    if rating:
                        star_display = "⭐" * rating + "☆" * (5 - rating)
                        st.write(f"**Rating:** {rating}/5")
                        st.write(star_display)
                        
                        # Show detailed scores if available
                        detailed_scores = recipe.get('ai_detailed_scores', {})
                        if detailed_scores:
                            st.write("**Detailed Scores:**")
                            for aspect, score in detailed_scores.items():
                                st.write(f"• {aspect.title()}: {score}/5")
                    
                    submitted_at = recipe.get('submitted_at')
                    if submitted_at:
                        st.write(f"**Submitted:** {submitted_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Action buttons
                    if st.button(f"View Full Recipe", key=f"view_{doc.id}"):
                        show_full_recipe_modal(recipe)
                
                st.markdown("---")
        
    except Exception as e:
        logger.error(f"Error loading chef submissions: {str(e)}")
        st.error("Error loading your submissions. Please try again later.")

def show_full_recipe_modal(recipe):
    """Display full recipe details in a modal-like format"""
    st.markdown("---")
    st.markdown(f"# 🍽️ {recipe.get('name', 'Recipe')}")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"**Description:** {recipe.get('description', 'No description')}")
        
        st.markdown("### Ingredients")
        ingredients = recipe.get('ingredients', [])
        if isinstance(ingredients, list):
            for ingredient in ingredients:
                st.write(f"• {ingredient}")
        else:
            st.write(ingredients)
        
        st.markdown("### Instructions")
        st.write(recipe.get('instructions', 'No instructions provided'))
        
        if recipe.get('notes'):
            st.markdown("### Chef's Notes")
            st.write(recipe['notes'])
    
    with col2:
        st.markdown("### Recipe Info")
        st.write(f"**Category:** {recipe.get('category', 'Unknown')}")
        st.write(f"**Cuisine:** {recipe.get('cuisine', 'Unknown')}")
        st.write(f"**Difficulty:** {recipe.get('difficulty', 'Unknown')}")
        st.write(f"**Cook Time:** {recipe.get('cook_time', 'Unknown')}")
        st.write(f"**Prep Time:** {recipe.get('prep_time', 'Not specified')}")
        st.write(f"**Servings:** {recipe.get('servings', 'Unknown')}")
        
        if recipe.get('diet'):
            st.write(f"**Dietary:** {', '.join(recipe['diet'])}")
        
        rating = recipe.get('rating', 0)
        if rating:
            star_display = "⭐" * rating + "☆" * (5 - rating)
            st.write(f"**AI Rating:** {rating}/5 {star_display}")
    
    st.markdown("---")

def render_chef_leaderboard(db):
    """Display chef leaderboard based on recipe ratings"""
    st.subheader("🏆 Chef Leaderboard")
    
    try:
        # Get all recipes first, then filter for chef submissions
        # This avoids the need for a composite index
        recipes_ref = db.collection('recipes')
        all_recipes = list(recipes_ref.stream())
        
        # Filter for chef submissions after fetching
        recipes = [doc for doc in all_recipes if doc.to_dict().get('source') == 'Chef Submission']
        
        if not recipes:
            st.info("No chef submissions found yet.")
            return
        
        # Calculate chef statistics
        chef_stats = {}
        
        for doc in recipes:
            recipe = doc.to_dict()
            chef_name = recipe.get('chef_name', 'Unknown Chef')
            chef_id = recipe.get('chef_user_id', 'unknown')
            rating = recipe.get('rating', 0)
            
            if chef_name not in chef_stats:
                chef_stats[chef_name] = {
                    'chef_id': chef_id,
                    'total_recipes': 0,
                    'total_rating': 0,
                    'five_star_count': 0,
                    'four_plus_count': 0,
                    'avg_rating': 0,
                    'recent_recipes': []
                }
            
            chef_stats[chef_name]['total_recipes'] += 1
            chef_stats[chef_name]['total_rating'] += rating
            if rating == 5:
                chef_stats[chef_name]['five_star_count'] += 1
            if rating >= 4:
                chef_stats[chef_name]['four_plus_count'] += 1
            
            # Track recent recipes
            chef_stats[chef_name]['recent_recipes'].append({
                'name': recipe.get('name', 'Unknown'),
                'rating': rating,
                'date': recipe.get('submitted_at')
            })
        
        # Calculate averages and sort recent recipes
        for chef in chef_stats:
            if chef_stats[chef]['total_recipes'] > 0:
                chef_stats[chef]['avg_rating'] = chef_stats[chef]['total_rating'] / chef_stats[chef]['total_recipes']
            
            # Sort recent recipes by date (most recent first)
            chef_stats[chef]['recent_recipes'].sort(key=lambda x: x['date'] or datetime.min, reverse=True)
            chef_stats[chef]['recent_recipes'] = chef_stats[chef]['recent_recipes'][:3]  # Keep only 3 most recent
        
        # Create different leaderboard views
        tab1, tab2, tab3 = st.tabs(["🏆 Top Rated", "📊 Most Active", "⭐ Perfect Scores"])
        
        with tab1:
            st.markdown("### Top Chefs by Average Rating")
            sorted_by_rating = sorted(
                chef_stats.items(),
                key=lambda x: (x[1]['avg_rating'], x[1]['total_recipes']),
                reverse=True
            )
            
            display_leaderboard(sorted_by_rating[:10], "avg_rating")
        
        with tab2:
            st.markdown("### Most Active Chefs")
            sorted_by_activity = sorted(
                chef_stats.items(),
                key=lambda x: x[1]['total_recipes'],
                reverse=True
            )
            
            display_leaderboard(sorted_by_activity[:10], "total_recipes")
        
        with tab3:
            st.markdown("### Perfect Score Champions")
            sorted_by_perfect = sorted(
                chef_stats.items(),
                key=lambda x: x[1]['five_star_count'],
                reverse=True
            )
            
            display_leaderboard(sorted_by_perfect[:10], "five_star_count")
        
    except Exception as e:
        logger.error(f"Error loading chef leaderboard: {str(e)}")
        st.error("Error loading leaderboard. Please try again later.")

def display_leaderboard(sorted_chefs, metric_type):
    """Display leaderboard with specified metric"""
    for i, (chef_name, stats) in enumerate(sorted_chefs):
        if stats['total_recipes'] == 0:  # Skip chefs with no recipes
            continue
            
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                st.write(f"**{rank_emoji}**")
            
            with col2:
                st.write(f"**{chef_name}**")
                # Show recent recipes
                if stats['recent_recipes']:
                    recent = stats['recent_recipes'][0]  # Most recent
                    st.caption(f"Latest: {recent['name']} ({recent['rating']}⭐)")
            
            with col3:
                if metric_type == "avg_rating":
                    st.metric("Avg Rating", f"{stats['avg_rating']:.1f}⭐")
                elif metric_type == "total_recipes":
                    st.metric("Total Recipes", stats['total_recipes'])
                elif metric_type == "five_star_count":
                    st.metric("5⭐ Recipes", stats['five_star_count'])
            
            with col4:
                st.write(f"📊 {stats['total_recipes']} recipes")
                st.write(f"⭐ {stats['four_plus_count']} high-rated")

def render_chef_analytics(db):
    """Display chef analytics and insights"""
    st.subheader("📈 Chef Analytics")
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to view analytics.")
        return
    
    try:
        # Get user's submissions - simpler query
        submissions_ref = db.collection('recipes').where('chef_user_id', '==', user['user_id'])
        all_submissions = list(submissions_ref.stream())
        
        # Filter for chef submissions after fetching
        submissions = [doc for doc in all_submissions if doc.to_dict().get('source') == 'Chef Submission']
        
        if not submissions:
            st.info("Submit some recipes to see your analytics!")
            return
        
        # Prepare data for analysis
        recipe_data = []
        for doc in submissions:
            recipe = doc.to_dict()
            recipe_data.append({
                'name': recipe.get('name', 'Unknown'),
                'rating': recipe.get('rating', 0),
                'category': recipe.get('category', 'Unknown'),
                'cuisine': recipe.get('cuisine', 'Unknown'),
                'difficulty': recipe.get('difficulty', 'Unknown'),
                'submitted_at': recipe.get('submitted_at'),
                'creativity': recipe.get('ai_detailed_scores', {}).get('creativity', 0),
                'ingredients': recipe.get('ai_detailed_scores', {}).get('ingredients', 0),
                'technique': recipe.get('ai_detailed_scores', {}).get('technique', 0),
                'appeal': recipe.get('ai_detailed_scores', {}).get('appeal', 0)
            })
        
        df = pd.DataFrame(recipe_data)
        
        # Overall performance metrics
        st.markdown("### Performance Overview")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_rating = df['rating'].mean() if not df['rating'].empty else 0
            st.metric("Average Rating", f"{avg_rating:.1f}⭐")
        
        with col2:
            best_rating = df['rating'].max() if not df['rating'].empty else 0
            st.metric("Best Rating", f"{best_rating}⭐")
        
        with col3:
            consistency = df['rating'].std() if len(df) > 1 and not df['rating'].empty else 0
            st.metric("Consistency", f"{consistency:.1f}", help="Lower is more consistent")
        
        with col4:
            improvement_trend = "📈" if len(df) > 1 and df.tail(3)['rating'].mean() > df.head(3)['rating'].mean() else "📊"
            st.metric("Trend", improvement_trend)
        
        # Charts and visualizations
        if not df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Rating Distribution")
                if not df['rating'].empty:
                    rating_counts = df['rating'].value_counts().sort_index()
                    st.bar_chart(rating_counts)
                else:
                    st.info("No ratings available yet")
            
            with col2:
                st.markdown("### Performance by Category")
                if not df['category'].empty and not df['rating'].empty:
                    category_performance = df.groupby('category')['rating'].mean().sort_values(ascending=False)
                    st.bar_chart(category_performance)
                else:
                    st.info("Not enough data for category analysis")
        
        # Detailed scores radar chart (if available)
        if any(df[['creativity', 'ingredients', 'technique', 'appeal']].sum()):
            st.markdown("### Skill Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                avg_scores = {
                    'Creativity': df['creativity'].mean() if not df['creativity'].empty else 0,
                    'Ingredients': df['ingredients'].mean() if not df['ingredients'].empty else 0,
                    'Technique': df['technique'].mean() if not df['technique'].empty else 0,
                    'Appeal': df['appeal'].mean() if not df['appeal'].empty else 0
                }
                
                for skill, score in avg_scores.items():
                    st.metric(skill, f"{score:.1f}/5")
            
            with col2:
                st.markdown("**Recommendations:**")
                lowest_skill = min(avg_scores, key=avg_scores.get)
                highest_skill = max(avg_scores, key=avg_scores.get)
                
                st.write(f"🎯 **Focus on:** {lowest_skill} (your lowest score)")
                st.write(f"⭐ **Strength:** {highest_skill} (your highest score)")
                
                if avg_scores[lowest_skill] < 3:
                    st.write(f"💡 **Tip:** Consider taking cooking classes or watching tutorials focused on {lowest_skill.lower()}")
        
        # Recent performance trend
        if len(df) >= 5:
            st.markdown("### Recent Performance Trend")
            df_sorted = df.sort_values('submitted_at') if 'submitted_at' in df.columns else df
            recent_ratings = df_sorted.tail(10)['rating'].tolist()
            
            st.line_chart(pd.DataFrame({'Rating': recent_ratings}))
            
            # Performance insights
            if len(recent_ratings) >= 5:
                recent_avg = sum(recent_ratings[-5:]) / 5
                earlier_avg = sum(recent_ratings[-10:-5]) / 5 if len(recent_ratings) >= 10 else recent_avg
                
                if recent_avg > earlier_avg:
                    st.success("📈 Your recent recipes are improving! Keep up the great work!")
                elif recent_avg < earlier_avg:
                    st.info("📊 Consider reviewing your recent recipes and applying lessons from your higher-rated dishes.")
                else:
                    st.info("📊 Your performance is consistent. Try experimenting with new techniques to reach the next level!")
        
    except Exception as e:
        logger.error(f"Error loading chef analytics: {str(e)}")
        st.error("Error loading analytics. Please try again later.")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_chef_statistics(db, chef_user_id):
    """Get comprehensive statistics for a specific chef"""
    try:
        submissions_ref = db.collection('recipes').where('chef_user_id', '==', chef_user_id).where('source', '==', 'Chef Submission')
        submissions = list(submissions_ref.stream())
        
        if not submissions:
            return None
        
        ratings = [doc.to_dict().get('rating', 0) for doc in submissions if doc.to_dict().get('rating')]
        
        stats = {
            'total_submissions': len(submissions),
            'total_ratings': len(ratings),
            'average_rating': sum(ratings) / len(ratings) if ratings else 0,
            'highest_rating': max(ratings) if ratings else 0,
            'five_star_count': sum(1 for r in ratings if r == 5),
            'four_plus_count': sum(1 for r in ratings if r >= 4),
            'categories': list(set(doc.to_dict().get('category', 'Unknown') for doc in submissions)),
            'cuisines': list(set(doc.to_dict().get('cuisine', 'Unknown') for doc in submissions)),
            'recent_submission': max(submissions, key=lambda x: x.to_dict().get('submitted_at', datetime.min))
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting chef statistics: {str(e)}")
        return None

def validate_recipe_data(recipe_data):
    """Validate recipe data before submission"""
    required_fields = ['name', 'description', 'ingredients', 'instructions', 'chef_name']
    missing_fields = []
    
    for field in required_fields:
        if not recipe_data.get(field) or not str(recipe_data[field]).strip():
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # This module is meant to be imported, not run directly
    logger.info("Chef Components module loaded successfully")
