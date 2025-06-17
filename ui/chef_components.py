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
import plotly.express as px

logger = logging.getLogger(__name__)

def get_firestore_client():
    try:
        if firebase_admin._apps:
            return firestore.client()
        else:
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client: {str(e)}")
        return None

def render_chef_recipe_suggestions():
    st.title("Chef Recipe Suggestions")
    
    db = get_firestore_client()
    if not db:
        st.error("Database connection failed. Please try again later.")
        return
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to access chef features.")
        return
    
    user_role = user.get('role', 'user')
    
    if user_role == 'admin':
        tabs = st.tabs(["Menu Generator", "Chef Submission", "My Submissions", "Chef Leaderboard", "Analytics Dashboard"])
        with tabs[0]:
            render_menu_generator(db)
        with tabs[1]:
            render_chef_submission(db)
        with tabs[2]:
            render_chef_submissions_history(db)
        with tabs[3]:
            render_chef_leaderboard(db)
        with tabs[4]:
            render_analytics_dashboard(db)
    elif user_role == 'chef':
        tabs = st.tabs(["Chef Submission", "My Submissions", "Chef Leaderboard", "Personal Analytics"])
        with tabs[0]:
            render_chef_submission(db)
        with tabs[1]:
            render_chef_submissions_history(db)
        with tabs[2]:
            render_chef_leaderboard(db)
        with tabs[3]:
            render_chef_analytics(db)
    else:
        st.warning("You don't have access to Chef Recipe Suggestions. This feature is available for Chefs and Administrators only.")
        return

def render_menu_generator(db):
    """Render the menu generator component using old logic"""
    st.markdown("### 🍽️ Weekly Menu Generator")
    st.markdown("Generate weekly restaurant menus using available ingredients and AI")
    
    # Ingredient Analysis
    st.markdown("#### 📦 Ingredient Analysis")
    
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        with st.spinner("Loading ingredients..."):
            ingredient_data = parse_ingredients(db)

    with col2:
        if ingredient_data:
            st.metric("Total Ingredients", len(ingredient_data))

    with col3:
        if ingredient_data:
            expiring_soon = len([i for i in ingredient_data if i["days_to_expiry"] <= 3])
            st.metric("Expiring Soon", expiring_soon)

    if not ingredient_data:
        st.error("No ingredients found. Please check your inventory database connection.")
        return
    else:
        st.success(f"✓ Loaded {len(ingredient_data)} ingredients")

    # Priority ingredient selection
    sorted_ingredients = sorted(ingredient_data, key=lambda x: (x["days_to_expiry"], -x["quantity"]))
    top_labels = [f"{i['name']} (Exp: {i['expiry_date']})" for i in sorted_ingredients[:4]]
    label_map = {f"{i['name']} (Exp: {i['expiry_date']})": i['name'] for i in sorted_ingredients}

    st.markdown("#### 🌟 Priority Ingredients")
    st.info("Select up to 4 ingredients to prioritize in menu generation. Pre-sorted by expiry date.")

    selected_labels = st.multiselect(
        "Choose priority ingredients:",
        options=list(label_map.keys()),
        default=top_labels,
        max_selections=4
    )
    priority_ingredients = [label_map[label] for label in selected_labels]

    if selected_labels:
        st.write("**Selected ingredients:**")
        cols = st.columns(min(len(selected_labels), 4))
        for i, ingredient in enumerate(selected_labels):
            with cols[i % 4]:
                st.info(f"**{ingredient.split(' (')[0]}**\n{ingredient.split('(')[1].replace(')', '')}")

    # Menu Generation
    st.markdown("#### 🚀 Generate Menu")
    
    # Check existing menu status
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    st.info(f"📅 Current week: {start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')}")
    
    # Check for existing menu items
    try:
        existing_query = db.collection("menu").where("created_at", ">=", start_of_week.isoformat()).limit(10)
        existing_docs = list(existing_query.stream())
        
        if existing_docs:
            st.warning(f"⚠️ Found {len(existing_docs)} menu items for this week")
            
            with st.expander("View Existing Menu Items"):
                for i, doc in enumerate(existing_docs[:3]):
                    data = doc.to_dict()
                    st.write(f"**{i+1}. {data.get('name', 'Unknown')}**")
                    st.write(f"   - Created: {data.get('created_at', 'Unknown')}")
                    st.write(f"   - Source: {data.get('source', 'Unknown')}")
                    st.write(f"   - Category: {data.get('category', 'Unknown')}")
                if len(existing_docs) > 3:
                    st.write(f"... and {len(existing_docs) - 3} more items")
            
            st.markdown("#### 🔄 Menu Regeneration")
            st.error("⚠️ **WARNING**: This will delete ALL current menu items and generate a completely new menu.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Delete Current Menu & Generate New", type="primary", key="regenerate_menu"):
                    delete_and_regenerate_menu(db, sorted_ingredients, priority_ingredients)
            
            with col2:
                if st.button("❌ Keep Current Menu", key="keep_menu"):
                    st.info("✅ Current menu preserved")
        else:
            st.success("✅ No existing menu found for this week")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("Generate a comprehensive weekly menu with starters, mains, desserts, and beverages.")

            with col2:
                if st.button("🚀 Generate New Menu", type="primary", use_container_width=True):
                    generate_new_menu(db, sorted_ingredients, priority_ingredients)
                    
    except Exception as e:
        logger.error(f"Error checking existing menu: {str(e)}")
        st.error(f"Error checking existing menu: {str(e)}")
        
        if st.button("🚀 Generate Menu (Fallback)", type="secondary"):
            generate_new_menu(db, sorted_ingredients, priority_ingredients)

    # Display generated menu if exists
    if "generated_menu" in st.session_state:
        display_generated_menu(db)

def parse_ingredients(db):
    """Parse ingredients from Firebase inventory using old logic"""
    if not db:
        return []
        
    try:
        ingredients_ref = db.collection("ingredient_inventory")
        ingredients = []

        for doc in ingredients_ref.stream():
            data = doc.to_dict()

            name = data.get("Ingredient", "").strip()
            expiry_str = data.get("Expiry Date", "").strip()
            quantity_raw = data.get("Quantity", "").strip()

            # Parse quantity: extract number from string like "4 kg"
            try:
                quantity = float("".join(c for c in quantity_raw if c.isdigit() or c == '.'))
            except:
                quantity = 0

            if not name or not expiry_str:
                continue

            try:
                from dateutil import parser
                expiry_date = parser.parse(expiry_str)
                days_to_expiry = (expiry_date - datetime.now()).days
            except Exception:
                continue

            ingredients.append({
                "name": name,
                "expiry_date": expiry_str,
                "quantity": quantity,
                "days_to_expiry": days_to_expiry
            })

        logger.info(f"Parsed {len(ingredients)} ingredients from inventory")
        return ingredients
        
    except Exception as e:
        logger.error(f"Error parsing ingredients: {str(e)}")
        return []

def delete_and_regenerate_menu(db, sorted_ingredients, priority_ingredients):
    """Delete existing menu and generate new one"""
    try:
        with st.spinner("🗑️ Deleting existing menu items..."):
            all_menu_docs = db.collection("menu").stream()
            deleted_count = 0
            
            for doc in all_menu_docs:
                try:
                    doc_data = doc.to_dict()
                    logger.info(f"Deleting menu item: {doc_data.get('name', 'Unknown')} (ID: {doc.id})")
                    doc.reference.delete()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting document {doc.id}: {str(e)}")
            
            logger.info(f"Successfully deleted {deleted_count} menu items")
            st.success(f"✅ Deleted {deleted_count} existing menu items")
            
        if "generated_menu" in st.session_state:
            del st.session_state.generated_menu
            
        st.info("🚀 Generating new menu...")
        generate_new_menu(db, sorted_ingredients, priority_ingredients)
        
    except Exception as e:
        logger.error(f"Error during menu deletion and regeneration: {str(e)}")
        st.error(f"❌ Error during menu regeneration: {str(e)}")

def generate_new_menu(db, sorted_ingredients, priority_ingredients):
    """Generate new menu using AI with old logic"""
    logger.info("Starting menu generation...")
    
    with st.spinner("Generating menu with AI..."):
        progress_bar = st.progress(0)

        ingredient_names = [i['name'] for i in sorted_ingredients[:50]]
        logger.info(f"Using {len(ingredient_names)} ingredients for menu generation")
        logger.info(f"Priority ingredients: {priority_ingredients}")
        
        prompt = f"""
You are an AI chef. Generate a full weekly restaurant menu (at least 35 dishes).
Include:
- Starters (8-10 dishes)
- Main Course (15-18 dishes) 
- Desserts (6-8 dishes)
- Beverages (6-8 dishes)
- Special dishes using: {', '.join(priority_ingredients)}
- Seasonal dishes based on the current month and available ingredients: {', '.join(ingredient_names)}
- Normal dishes based on the same available ingredients

Use this EXACT structure for each dish:
{{
    "name": "Dish Name",
    "description": "Detailed description",
    "ingredients": ["ingredient1", "ingredient2"],
    "cook_time": "30 minutes",
    "cuisine": "Italian",
    "diet": ["Vegetarian"],
    "category": "Main Course",
    "types": ["Seasonal Items"],
    "source": "Gemini",
    "rating": null,
    "rating_comment": "",
    "timestamp": "{datetime.now().isoformat()}"
}}

Return ONLY a JSON array of dishes. No explanation or additional text.
"""
        progress_bar.progress(50)
        logger.info("Sending request to Gemini AI...")
        
        response = generate_dish(prompt)
        progress_bar.progress(100)

        if not isinstance(response, list):
            logger.error(f"Invalid response type: {type(response)}")
            st.error("❌ Invalid menu format generated")
            if response:
                st.json(response)
            return

        logger.info(f"Successfully generated {len(response)} dishes")
        st.session_state.generated_menu = response
        st.success(f"✅ Generated {len(response)} dishes successfully!")

def generate_dish(prompt):
    """Generate dish using old logic"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found")
            return []
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content(prompt)
        
        try:
            import re
            match = re.search(r"\[.*\]", response.text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                logger.warning("No JSON array found in response")
                return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            return []
            
    except Exception as e:
        logger.error(f"Error generating dish: {str(e)}")
        return []

def display_generated_menu(db):
    """Display and save generated menu using old logic"""
    st.markdown("#### 📋 Generated Menu")

    menu_stats = st.session_state.generated_menu
    categories = {}
    for dish in menu_stats:
        cat = dish.get('category', 'Other')
        categories[cat] = categories.get(cat, 0) + 1

    if categories:
        stat_cols = st.columns(len(categories))
        for i, (cat, count) in enumerate(categories.items()):
            with stat_cols[i]:
                st.metric(cat, f"{count} dishes")

    df = pd.DataFrame(st.session_state.generated_menu)
    st.dataframe(df, use_container_width=True, height=300)

    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("Save all generated dishes to Firebase and create backups.")

    with col2:
        if st.button("💾 Save to Database", type="primary", use_container_width=True):
            save_menu_to_database(db)

def save_menu_to_database(db):
    """Save generated menu to database using old logic"""
    logger.info("Starting menu save to database...")
    
    with st.spinner("Saving menu..."):
        progress = st.progress(0)
        created_count = 0
        error_count = 0
        total_dishes = len(st.session_state.generated_menu)

        required_fields = ["name", "description", "ingredients", "cook_time", "cuisine", "diet", "category"]

        for i, dish in enumerate(st.session_state.generated_menu):
            progress.progress((i + 1) / total_dishes)

            missing = [f for f in required_fields if f not in dish or not dish[f]]
            if missing:
                logger.warning(f"Skipping dish '{dish.get('name', 'Unknown')}' due to missing fields: {missing}")
                error_count += 1
                continue

            dish["source"] = "Gemini"
            dish["created_at"] = datetime.now().isoformat()
            dish["rating"] = None

            try:
                menu_ref = db.collection("menu").add(dish)
                logger.info(f"Added dish '{dish.get('name')}' to menu collection with ID: {menu_ref[1].id}")
                
                archive_ref = db.collection("recipe_archive").add(dish)
                logger.info(f"Added dish '{dish.get('name')}' to recipe archive with ID: {archive_ref[1].id}")
                
                created_count += 1
            except Exception as e:
                logger.error(f"Error saving dish '{dish.get('name', 'Unnamed')}': {e}")
                error_count += 1

        logger.info(f"Menu save completed: {created_count} saved, {error_count} errors")

        if created_count:
            st.success(f"✅ Menu saved successfully! {created_count} dishes added to restaurant menu.")
            if error_count > 0:
                st.warning(f"⚠️ {error_count} dishes had errors and were not saved.")
            
            del st.session_state.generated_menu
            st.rerun()
        else:
            st.error("❌ No dishes saved. All dishes had validation errors.")

def render_chef_submission(db):
    st.subheader("Submit Your Recipe")
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to submit recipes.")
        return
    
    user_role = user.get('role', 'user')
    if user_role != 'chef':
        st.info(f"You're logged in as '{user_role}'. Anyone can submit recipes, but chefs get special recognition!")
    
    with st.expander("XP Rewards System", expanded=False):
        st.markdown("""
        **Earn XP based on AI recipe ratings:**
        - 1 Star: 5 XP
        - 2 Stars: 10 XP  
        - 3 Stars: 15 XP
        - 4 Stars: 30 XP (20 base + 10 bonus)
        - 5 Stars: 45 XP (25 base + 20 bonus)
        
        **AI evaluates recipes based on:**
        - Creativity and uniqueness (25%)
        - Ingredient quality and combination (25%)
        - Cooking technique and method (25%)
        - Overall appeal and feasibility (25%)
        """)
    
    create_chef_sub_ratings_collection(db)
    
    with st.form("chef_recipe_submission"):
        st.markdown("### Recipe Details")
        
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
        
        description = st.text_area(
            "Recipe Description *",
            placeholder="Describe your dish, its flavors, inspiration, and what makes it special. Include any background story or cultural significance...",
            height=120,
            help="Provide a detailed description of your recipe"
        )
        
        st.markdown("### Ingredients")
        ingredients = st.text_area(
            "Ingredients List *",
            placeholder="List ingredients with precise measurements, one per line:\n• 2 cups basmati rice, rinsed\n• 1 lb large shrimp, peeled and deveined\n• 4 cloves garlic, minced\n• 2 tbsp unsalted butter\n• 1 tsp paprika\n• Salt and pepper to taste",
            height=180,
            help="List all ingredients with exact quantities and preparation notes"
        )
        
        st.markdown("### Instructions")
        instructions = st.text_area(
            "Step-by-Step Instructions *",
            placeholder="Provide detailed cooking instructions:\n\n1. Preparation (5 mins):\n   - Rinse rice until water runs clear\n   - Pat shrimp dry and season with salt and pepper\n\n2. Cooking (20 mins):\n   - Heat butter in large skillet over medium-high heat\n   - Add garlic and cook until fragrant, about 30 seconds\n   - Add shrimp and cook 2-3 minutes per side until pink\n\n3. Finishing:\n   - Sprinkle with paprika and serve immediately",
            height=250,
            help="Detailed step-by-step cooking instructions with timing"
        )
        
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
        
        notes = st.text_area(
            "Chef's Notes & Tips (Optional)",
            placeholder="Share any professional tips, tricks, or personal insights that make this recipe special...",
            height=100,
            help="Additional tips and insights from your experience"
        )
        
        submitted = st.form_submit_button("Submit Recipe for AI Review", type="primary", use_container_width=True)
        
        if submitted:
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
                with st.spinner("Submitting recipe and generating AI rating..."):
                    process_chef_submission_detailed(db, {
                        'chef_name': chef_name,
                        'dish_name': dish_name,
                        'description': description,
                        'ingredients': ingredients,
                        'instructions': instructions,
                        'cook_time': cook_time,
                        'prep_time': prep_time,
                        'cuisine': cuisine,
                        'diet': diet,
                        'category': category,
                        'difficulty': difficulty,
                        'servings': servings,
                        'equipment': equipment,
                        'storage_tips': storage_tips,
                        'variations': variations,
                        'notes': notes
                    })

def create_chef_sub_ratings_collection(db):
    try:
        test_doc = db.collection("chef_sub_ratings").limit(1).get()
        if not test_doc:
            db.collection("chef_sub_ratings").add({
                "test": True,
                "created_at": datetime.now().isoformat()
            })
    except Exception as e:
        logger.error(f"Error creating chef_sub_ratings collection: {str(e)}")

def process_chef_submission_detailed(db, recipe_data):
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("User session error. Please log in again.")
        return

    try:
        full_recipe_data = {
            'name': recipe_data['dish_name'],
            'description': recipe_data['description'],
            'ingredients': recipe_data['ingredients'].split('\n') if isinstance(recipe_data['ingredients'], str) else recipe_data['ingredients'],
            'instructions': recipe_data['instructions'],
            'cook_time': recipe_data['cook_time'],
            'prep_time': recipe_data['prep_time'],
            'cuisine': recipe_data['cuisine'],
            'diet': recipe_data['diet'] if isinstance(recipe_data['diet'], list) else [recipe_data['diet']] if recipe_data['diet'] else [],
            'category': recipe_data['category'],
            'difficulty': recipe_data['difficulty'],
            'servings': recipe_data['servings'],
            'equipment': recipe_data['equipment'],
            'storage_tips': recipe_data['storage_tips'],
            'variations': recipe_data['variations'],
            'chef_name': recipe_data['chef_name'],
            'chef_user_id': user['user_id'],
            'chef_role': user.get('role', 'user'),
            'submitted_at': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.now().isoformat(),
            'status': 'submitted',
            'source': 'Chef Submission',
            'notes': recipe_data['notes'],
            'rating': None,
            'ai_feedback': None,
            'views': 0,
            'likes': 0,
            'featured': False
        }
        
        doc_ref = db.collection('recipes').add(full_recipe_data)
        recipe_id = doc_ref[1].id
        
        logger.info(f"Recipe '{recipe_data['dish_name']}' saved to database with ID: {recipe_id}")
        
        try:
            rating, feedback, detailed_scores = generate_ai_recipe_rating_and_feedback(
                recipe_data['dish_name'], recipe_data['description'], recipe_data['ingredients'], 
                recipe_data['instructions'], recipe_data['cook_time'], recipe_data['cuisine'], 
                recipe_data['category'], recipe_data['difficulty']
            )
            
            db.collection('recipes').document(recipe_id).update({
                'rating': rating,
                'ai_feedback': feedback,
                'ai_detailed_scores': detailed_scores,
                'evaluation_date': firestore.SERVER_TIMESTAMP
            })
            
            st.success(f"Recipe '{recipe_data['dish_name']}' submitted successfully!")
            
            star_display = "⭐" * rating + "☆" * (5 - rating)
            st.info(f"AI Rating: {rating}/5 {star_display}")
            
            if detailed_scores:
                st.markdown("### Detailed AI Evaluation")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Creativity", f"{detailed_scores.get('creativity', 0)}/5")
                with col2:
                    st.metric("Ingredients", f"{detailed_scores.get('ingredients', 0)}/5")
                with col3:
                    st.metric("Technique", f"{detailed_scores.get('technique', 0)}/5")
                with col4:
                    st.metric("Appeal", f"{detailed_scores.get('appeal', 0)}/5")
            
            if feedback:
                st.markdown("### AI Feedback & Suggestions")
                st.write(feedback)
            
            award_chef_submission_xp(user['user_id'], rating, recipe_data['chef_name'], recipe_data['dish_name'])
            
        except Exception as e:
            logger.error(f"Error generating AI rating: {str(e)}")
            st.success(f"Recipe '{recipe_data['dish_name']}' submitted successfully!")
            st.warning("Recipe saved, but AI rating could not be generated at this time.")

    except Exception as e:
        st.error(f"Error saving recipe to database: {str(e)}")
        logger.exception("Error during recipe database save")

def generate_ai_recipe_rating_and_feedback(dish_name, description, ingredients, instructions, cook_time, cuisine, category, difficulty):
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
        
        try:
            lines = response_text.split('\n')
            detailed_scores = {}
            overall_rating = 3
            feedback = "No feedback available."
            
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

def award_chef_submission_xp(user_id, rating, chef_name, dish_name):
    try:
        base_xp_per_star = 5
        rating_xp = rating * base_xp_per_star
        
        bonus_xp = 0
        if rating >= 4:
            bonus_xp = 10
        if rating == 5:
            bonus_xp = 20
        
        total_xp = rating_xp + bonus_xp
        
        from modules.leftover import update_user_stats
        update_user_stats(user_id=user_id, xp_gained=total_xp, recipes_generated=1)
        
        from ui.components import show_xp_notification
        show_xp_notification(total_xp, f"chef recipe submission ({rating}⭐)")
        
        if bonus_xp > 0:
            st.success(f"XP Earned: {total_xp} total ({rating_xp} base + {bonus_xp} bonus for {rating}⭐ rating)")
        else:
            st.success(f"XP Earned: {total_xp} XP for {rating}⭐ rating")
        
        check_chef_achievements(user_id, rating)
            
        logger.info(f"Awarded {total_xp} XP to chef {chef_name} (ID: {user_id}) for {rating}-star recipe '{dish_name}'")
        
    except Exception as e:
        logger.error(f"Error awarding XP for chef submission: {str(e)}")
        st.warning("Recipe saved successfully, but there was an issue awarding XP.")

def check_chef_achievements(user_id, rating):
    try:
        db = get_firestore_client()
        if not db:
            return
        
        user_recipes_ref = db.collection('recipes').where('chef_user_id', '==', user_id)
        all_user_recipes = list(user_recipes_ref.stream())
        
        user_recipes = [doc for doc in all_user_recipes if doc.to_dict().get('source') == 'Chef Submission']
        
        total_submissions = len(user_recipes)
        five_star_count = sum(1 for doc in user_recipes if doc.to_dict().get('rating') == 5)
        four_plus_star_count = sum(1 for doc in user_recipes if doc.to_dict().get('rating', 0) >= 4)
        
        achievements = []
        
        if total_submissions == 1:
            achievements.append("First Recipe - Welcome to the kitchen!")
        elif total_submissions == 5:
            achievements.append("Recipe Enthusiast - 5 recipes submitted!")
        elif total_submissions == 10:
            achievements.append("Prolific Chef - 10 recipes and counting!")
        
        if rating == 5 and five_star_count == 1:
            achievements.append("Perfect Recipe - Your first 5-star dish!")
        elif five_star_count == 3:
            achievements.append("Master Chef - 3 perfect recipes!")
        elif five_star_count == 5:
            achievements.append("Culinary Genius - 5 perfect recipes!")
        
        if four_plus_star_count >= 5:
            achievements.append("Consistent Excellence - 5+ high-rated recipes!")
        
        for achievement in achievements:
            st.balloons()
            st.success(f"Achievement Unlocked: {achievement}")
        
    except Exception as e:
        logger.error(f"Error checking chef achievements: {str(e)}")

def render_chef_submissions_history(db):
    st.subheader("Your Recipe Submissions")
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to view your submissions.")
        return
    
    try:
        submissions_ref = db.collection('recipes').where('chef_user_id', '==', user['user_id'])
        submissions = list(submissions_ref.stream())
        
        submissions = [doc for doc in submissions if doc.to_dict().get('source') == 'Chef Submission']
        
        submissions.sort(key=lambda x: x.to_dict().get('submitted_at', datetime.min), reverse=True)
        
        if not submissions:
            st.info("You haven't submitted any recipes yet. Use the 'Submit Recipe' tab to get started!")
            return
        
        total_submissions = len(submissions)
        ratings = [doc.to_dict().get('rating', 0) for doc in submissions if doc.to_dict().get('rating')]
        total_rating = sum(ratings)
        avg_rating = total_rating / len(ratings) if ratings else 0
        five_star_count = sum(1 for rating in ratings if rating == 5)
        four_plus_count = sum(1 for rating in ratings if rating >= 4)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Submissions", total_submissions)
        with col2:
            st.metric("Average Rating", f"{avg_rating:.1f}⭐")
        with col3:
            st.metric("5⭐ Recipes", five_star_count)
        with col4:
            st.metric("4+ ⭐ Recipes", four_plus_count)
        
        st.markdown("### Filter & Sort")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            rating_filter = st.selectbox("Filter by Rating", ["All", "5⭐", "4⭐", "3⭐", "2⭐", "1⭐"])
        with col2:
            category_filter = st.selectbox("Filter by Category", ["All"] + list(set(doc.to_dict().get('category', 'Unknown') for doc in submissions)))
        with col3:
            sort_by = st.selectbox("Sort by", ["Newest First", "Oldest First", "Highest Rated", "Lowest Rated"])
        
        filtered_submissions = submissions.copy()
        
        if rating_filter != "All":
            target_rating = int(rating_filter[0])
            filtered_submissions = [doc for doc in filtered_submissions if doc.to_dict().get('rating') == target_rating]
        
        if category_filter != "All":
            filtered_submissions = [doc for doc in filtered_submissions if doc.to_dict().get('category') == category_filter]
        
        if sort_by == "Oldest First":
            filtered_submissions.reverse()
        elif sort_by == "Highest Rated":
            filtered_submissions.sort(key=lambda x: x.to_dict().get('rating', 0), reverse=True)
        elif sort_by == "Lowest Rated":
            filtered_submissions.sort(key=lambda x: x.to_dict().get('rating', 0))
        
        st.markdown(f"### Your Recipes ({len(filtered_submissions)} shown)")
        
        for doc in filtered_submissions:
            recipe = doc.to_dict()
            
            recipe_title = f"{recipe.get('name', 'Unnamed Recipe')} - {recipe.get('rating', 'No rating')}⭐"
            
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
                    
                    if recipe.get('ai_feedback'):
                        st.markdown("**AI Feedback:**")
                        st.write(recipe['ai_feedback'])
                
                with col2:
                    rating = recipe.get('rating', 0)
                    if rating:
                        star_display = "⭐" * rating + "☆" * (5 - rating)
                        st.write(f"**Rating:** {rating}/5")
                        st.write(star_display)
                        
                        detailed_scores = recipe.get('ai_detailed_scores', {})
                        if detailed_scores:
                            st.write("**Detailed Scores:**")
                            for aspect, score in detailed_scores.items():
                                st.write(f"• {aspect.title()}: {score}/5")
                    
                    submitted_at = recipe.get('submitted_at')
                    if submitted_at:
                        st.write(f"**Submitted:** {submitted_at.strftime('%Y-%m-%d %H:%M')}")
                    
                    if st.button(f"View Full Recipe", key=f"view_{doc.id}"):
                        show_full_recipe_modal(recipe)
                
                st.markdown("---")
        
    except Exception as e:
        logger.error(f"Error loading chef submissions: {str(e)}")
        st.error("Error loading your submissions. Please try again later.")

def show_full_recipe_modal(recipe):
    st.markdown("---")
    st.markdown(f"# {recipe.get('name', 'Recipe')}")
    
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
    st.subheader("Chef Leaderboard")
    
    try:
        recipes_ref = db.collection('recipes')
        all_recipes = list(recipes_ref.stream())
        
        recipes = [doc for doc in all_recipes if doc.to_dict().get('source') == 'Chef Submission']
        
        if not recipes:
            st.info("No chef submissions found yet.")
            return
        
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
            
            chef_stats[chef_name]['recent_recipes'].append({
                'name': recipe.get('name', 'Unknown'),
                'rating': rating,
                'date': recipe.get('submitted_at')
            })
        
        for chef in chef_stats:
            if chef_stats[chef]['total_recipes'] > 0:
                chef_stats[chef]['avg_rating'] = chef_stats[chef]['total_rating'] / chef_stats[chef]['total_recipes']
            
            chef_stats[chef]['recent_recipes'].sort(key=lambda x: x['date'] or datetime.min, reverse=True)
            chef_stats[chef]['recent_recipes'] = chef_stats[chef]['recent_recipes'][:3]
        
        tab1, tab2, tab3 = st.tabs(["Top Rated", "Most Active", "Perfect Scores"])
        
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
    for i, (chef_name, stats) in enumerate(sorted_chefs):
        if stats['total_recipes'] == 0:
            continue
            
        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                st.write(f"**{rank_emoji}**")
            
            with col2:
                st.write(f"**{chef_name}**")
                if stats['recent_recipes']:
                    recent = stats['recent_recipes'][0]
                    st.caption(f"Latest: {recent['name']} ({recent['rating']}⭐)")
            
            with col3:
                if metric_type == "avg_rating":
                    st.metric("Avg Rating", f"{stats['avg_rating']:.1f}⭐")
                elif metric_type == "total_recipes":
                    st.metric("Total Recipes", stats['total_recipes'])
                elif metric_type == "five_star_count":
                    st.metric("5⭐ Recipes", stats['five_star_count'])
            
            with col4:
                st.write(f"{stats['total_recipes']} recipes")
                st.write(f"{stats['four_plus_count']} high-rated")

def render_chef_analytics(db):
    st.subheader("Chef Analytics")
    
    user = st.session_state.get('user', {})
    if not user or not user.get('user_id'):
        st.error("Please log in to view analytics.")
        return
    
    try:
        submissions_ref = db.collection('recipes').where('chef_user_id', '==', user['user_id'])
        all_submissions = list(submissions_ref.stream())
        
        submissions = [doc for doc in all_submissions if doc.to_dict().get('source') == 'Chef Submission']
        
        if not submissions:
            st.info("Submit some recipes to see your analytics!")
            return
        
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
                
                st.write(f"Focus on: {lowest_skill} (your lowest score)")
                st.write(f"Strength: {highest_skill} (your highest score)")
                
                if avg_scores[lowest_skill] < 3:
                    st.write(f"Tip: Consider taking cooking classes or watching tutorials focused on {lowest_skill.lower()}")
        
        if len(df) >= 5:
            st.markdown("### Recent Performance Trend")
            df_sorted = df.sort_values('submitted_at') if 'submitted_at' in df.columns else df
            recent_ratings = df_sorted.tail(10)['rating'].tolist()
            
            st.line_chart(pd.DataFrame({'Rating': recent_ratings}))
            
            if len(recent_ratings) >= 5:
                recent_avg = sum(recent_ratings[-5:]) / 5
                earlier_avg = sum(recent_ratings[-10:-5]) / 5 if len(recent_ratings) >= 10 else recent_avg
                
                if recent_avg > earlier_avg:
                    st.success("Your recent recipes are improving! Keep up the great work!")
                elif recent_avg < earlier_avg:
                    st.info("Consider reviewing your recent recipes and applying lessons from your higher-rated dishes.")
                else:
                    st.info("Your performance is consistent. Try experimenting with new techniques to reach the next level!")
        
    except Exception as e:
        logger.error(f"Error loading chef analytics: {str(e)}")
        st.error("Error loading analytics. Please try again later.")

def render_analytics_dashboard(db):
    st.markdown("### Menu Analytics Dashboard")
    st.markdown("Insights into menu performance, chef ratings, and category distribution")

    @st.cache_data(ttl=300)
    def load_menu_data():
        try:
            menu_docs = db.collection("menu").stream()
            return [doc.to_dict() for doc in menu_docs]
        except Exception as e:
            st.error(f"Failed to load menu items: {e}")
            return []

    menu_items = load_menu_data()

    if not menu_items:
        st.error("No menu data available. Please generate a menu first.")
        return

    st.markdown("#### Overview")

    total_dishes = len(menu_items)
    categories = list(set(item.get("category", "Uncategorized") for item in menu_items))
    chef_specials = [item for item in menu_items if "Chef" in item.get("source", "")]
    
    rated_items = [item for item in menu_items if isinstance(item.get("rating"), (int, float))]
    avg_rating = sum(item.get("rating", 0) for item in rated_items) / max(len(rated_items), 1)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Dishes", total_dishes)
    with col2:
        st.metric("Categories", len(categories))
    with col3:
        st.metric("Chef Specials", len(chef_specials))
    with col4:
        st.metric("Avg Rating", f"{avg_rating:.1f}")

    st.markdown("#### Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_category = st.selectbox("Category", ["All"] + sorted(categories))

    with col2:
        cuisine_types = sorted(set(item.get("cuisine", "Unknown") for item in menu_items if item.get("cuisine")))
        selected_cuisine = st.selectbox("Cuisine", ["All"] + cuisine_types)

    with col3:
        source_types = sorted(set(item.get("source", "Unknown") for item in menu_items if item.get("source")))
        selected_source = st.selectbox("Source", ["All"] + source_types)

    filtered_items = menu_items

    if selected_category != "All":
        filtered_items = [item for item in filtered_items if item.get("category") == selected_category]

    if selected_cuisine != "All":
        filtered_items = [item for item in filtered_items if item.get("cuisine") == selected_cuisine]

    if selected_source != "All":
        filtered_items = [item for item in filtered_items if item.get("source") == selected_source]

    st.markdown("#### Menu Items")

    if filtered_items:
        st.write(f"Showing {len(filtered_items)} of {total_dishes} dishes")
        df = pd.DataFrame(filtered_items)
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.info("No dishes match the selected filters.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Chef Ratings")

        chef_specials_rated = [
            item for item in menu_items
            if "Chef" in item.get("source", "") and isinstance(item.get("rating"), (int, float))
        ]

        if chef_specials_rated:
            ratings_df = pd.DataFrame(chef_specials_rated).sort_values(by="rating", ascending=True)

            fig = px.bar(
                ratings_df.tail(10),
                x="rating",
                y="name",
                orientation='h',
                height=400,
                title="Top 10 Chef Dishes by Rating"
            )

            fig.update_layout(
                xaxis_title="Rating",
                yaxis_title="",
                showlegend=False,
                margin=dict(l=0, r=0, t=30, b=0)
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No rated chef specials available.")

    with col2:
        st.markdown("#### Category Distribution")

        category_counts = pd.Series([item.get("category", "Uncategorized") for item in menu_items]).value_counts()

        fig_pie = px.pie(
            values=category_counts.values,
            names=category_counts.index,
            height=400,
            title="Menu Items by Category"
        )

        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("#### Recent Chef Ratings")

    @st.cache_data(ttl=300)
    def load_recent_ratings():
        try:
            rating_docs = db.collection("chef_sub_ratings") \
                .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                .limit(5).stream()
            return [doc.to_dict() for doc in rating_docs]
        except Exception as e:
            logger.error(f"Error loading recent ratings: {str(e)}")
            return []

    recent_ratings = load_recent_ratings()

    if recent_ratings:
        ratings_df = pd.DataFrame(recent_ratings)
        st.dataframe(ratings_df, use_container_width=True, height=200)
    else:
        st.info("No recent ratings available.")

    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

if __name__ == "__main__":
    logger.info("Chef Components module loaded successfully")
