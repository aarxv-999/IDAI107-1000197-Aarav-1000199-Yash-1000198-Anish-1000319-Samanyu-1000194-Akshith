"""
Chef Recipe UI Components for the Smart Restaurant Menu Management App.
Integrated into the existing component structure.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from modules.chef_services import (
    get_chef_firebase_db, generate_dish_rating, parse_ingredients, generate_dish,
    DIET_TYPES, MENU_CATEGORIES, REQUIRED_MENU_FIELDS
)
import logging
from google.cloud import firestore

logger = logging.getLogger(__name__)

def render_chef_recipe_suggestions():
    """Main function to render Chef Recipe Suggestions with tabs"""
    st.title("👨‍🍳 Chef Recipe Suggestions")
    
    # Get current user for role-based access
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    
    # Create tabs based on user role
    if user_role == 'admin':
        tabs = st.tabs(["🍽️ Menu Generator", "📝 Chef Submission", "📊 Analytics Dashboard"])
    elif user_role == 'chef':
        tabs = st.tabs(["📝 Chef Submission", "📊 Analytics Dashboard"])
    else:
        st.warning("⚠️ You don't have access to Chef Recipe Suggestions. This feature is available for Chefs and Administrators only.")
        return
    
    # Initialize database connection
    db = get_chef_firebase_db()
    if not db:
        st.error("❌ Database connection failed. Please check your configuration.")
        return
    
    # Render tabs based on user role
    tab_index = 0
    
    if user_role == 'admin':
        with tabs[0]:
            render_menu_generator(db)
        with tabs[1]:
            render_chef_submission(db)
        with tabs[2]:
            render_analytics_dashboard(db)
    elif user_role == 'chef':
        with tabs[0]:
            render_chef_submission(db)
        with tabs[1]:
            render_analytics_dashboard(db)

def render_menu_generator(db):
    """Render the menu generator component (Admin only)"""
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
    logger.info(f"Current date: {today}")
    
    # Get current week's date range for better debugging
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    st.info(f"📅 Current week: {start_of_week.strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')}")
    
    # Check for existing menu items
    try:
        # Query for any menu items from this week
        existing_query = db.collection("menu").where("created_at", ">=", start_of_week.isoformat()).limit(10)
        existing_docs = list(existing_query.stream())
        
        logger.info(f"Found {len(existing_docs)} existing menu items for current week")
        
        if existing_docs:
            # Show existing menu info
            st.warning(f"⚠️ Found {len(existing_docs)} menu items for this week")
            
            # Show some sample existing items for debugging
            with st.expander("View Existing Menu Items (Debug Info)"):
                for i, doc in enumerate(existing_docs[:3]):  # Show first 3
                    data = doc.to_dict()
                    st.write(f"**{i+1}. {data.get('name', 'Unknown')}**")
                    st.write(f"   - Created: {data.get('created_at', 'Unknown')}")
                    st.write(f"   - Source: {data.get('source', 'Unknown')}")
                    st.write(f"   - Category: {data.get('category', 'Unknown')}")
                if len(existing_docs) > 3:
                    st.write(f"... and {len(existing_docs) - 3} more items")
            
            # Regeneration section
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
            # No existing menu - show generate button
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
        
        # Fallback - allow generation anyway
        if st.button("🚀 Generate Menu (Fallback)", type="secondary"):
            generate_new_menu(db, sorted_ingredients, priority_ingredients)

    # Display generated menu if exists
    if "generated_menu" in st.session_state:
        display_generated_menu(db)

def delete_and_regenerate_menu(db, sorted_ingredients, priority_ingredients):
    """Delete existing menu and generate new one"""
    try:
        with st.spinner("🗑️ Deleting existing menu items..."):
            # Get ALL menu items (not just this week) to be thorough
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
            
        # Clear any cached menu data
        if "generated_menu" in st.session_state:
            del st.session_state.generated_menu
            
        # Generate new menu
        st.info("🚀 Generating new menu...")
        generate_new_menu(db, sorted_ingredients, priority_ingredients)
        
    except Exception as e:
        logger.error(f"Error during menu deletion and regeneration: {str(e)}")
        st.error(f"❌ Error during menu regeneration: {str(e)}")

def generate_new_menu(db, sorted_ingredients, priority_ingredients):
    """Generate new menu using AI"""
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

def display_generated_menu(db):
    """Display and save generated menu"""
    st.markdown("#### 📋 Generated Menu")

    menu_stats = st.session_state.generated_menu
    categories = {}
    for dish in menu_stats:
        cat = dish.get('category', 'Other')
        categories[cat] = categories.get(cat, 0) + 1

    # Display category stats
    if categories:
        stat_cols = st.columns(len(categories))
        for i, (cat, count) in enumerate(categories.items()):
            with stat_cols[i]:
                st.metric(cat, f"{count} dishes")

    # Menu table
    df = pd.DataFrame(st.session_state.generated_menu)
    st.dataframe(df, use_container_width=True, height=300)

    # Save section
    col1, col2 = st.columns([2, 1])

    with col1:
        st.write("Save all generated dishes to Firebase and create backups.")

    with col2:
        if st.button("💾 Save to Database", type="primary", use_container_width=True):
            save_menu_to_database(db)

def save_menu_to_database(db):
    """Save generated menu to database"""
    logger.info("Starting menu save to database...")
    
    with st.spinner("Saving menu..."):
        progress = st.progress(0)
        created_count = 0
        error_count = 0
        total_dishes = len(st.session_state.generated_menu)

        for i, dish in enumerate(st.session_state.generated_menu):
            progress.progress((i + 1) / total_dishes)

            # Validate required fields
            missing = [f for f in REQUIRED_MENU_FIELDS if f not in dish or not dish[f]]
            if missing:
                logger.warning(f"Skipping dish '{dish.get('name', 'Unknown')}' due to missing fields: {missing}")
                error_count += 1
                continue

            # Set metadata
            dish["source"] = "Gemini"
            dish["created_at"] = datetime.now().isoformat()
            dish["rating"] = None

            try:
                # Add to menu collection
                menu_ref = db.collection("menu").add(dish)
                logger.info(f"Added dish '{dish.get('name')}' to menu collection with ID: {menu_ref[1].id}")
                
                # Add to recipe archive for backup
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
            
            # Clear the generated menu from session state
            del st.session_state.generated_menu
            
            # Force a rerun to refresh the menu status
            st.rerun()
        else:
            st.error("❌ No dishes saved. All dishes had validation errors.")

def render_chef_submission(db):
    """Render the chef submission form component"""
    st.markdown("### 📝 Chef Recipe Submission")
    st.markdown("Submit your signature dish and receive AI-powered feedback")
    
    # Get current user
    user = st.session_state.get('user', {})
    chef_name = user.get('username', 'Unknown Chef')
    
    # Guidelines
    st.info("""
    **Submission Guidelines:**
    • One recipe per chef per week
    • All dishes automatically rated by AI
    • Approved recipes added to restaurant menu
    """)
    
    # Form
    with st.form("chef_form", clear_on_submit=True):
        st.markdown("**Dish Information**")
        col1, col2 = st.columns(2)

        with col1:
            dish_name = st.text_input("Dish Name", placeholder="e.g., Truffle Risotto")
            cook_time = st.text_input("Cook Time", placeholder="e.g., 30 minutes")
            cuisine = st.text_input("Cuisine Type", placeholder="e.g., Italian, French")

        with col2:
            diet = st.selectbox("Dietary Category", DIET_TYPES)
            category = st.selectbox("Menu Category", MENU_CATEGORIES[:4])

        st.markdown("**Recipe Details**")
        ingredients = st.text_area(
            "Ingredients",
            placeholder="List ingredients separated by commas",
            height=80
        )

        description = st.text_area(
            "Description",
            placeholder="Describe your dish, cooking method, and what makes it special",
            height=100
        )

        submitted = st.form_submit_button("🚀 Submit Recipe", type="primary")

        if submitted:
            # Validation
            if not dish_name or not ingredients:
                st.error("❌ Please fill in Dish Name and Ingredients.")
                return

            # Check weekly limit
            start_of_week = datetime.now() - timedelta(days=datetime.now().weekday())
            existing_query = db.collection("menu") \
                .where("source", "==", f"Chef {chef_name}") \
                .where("timestamp", ">=", start_of_week.isoformat()).limit(1)
            
            existing_docs = list(existing_query.stream())
            if existing_docs:
                st.error("❌ You have already submitted a recipe this week.")
                return

            # Process submission
            process_chef_submission(db, chef_name, dish_name, description, ingredients, cook_time, cuisine, diet, category)

def process_chef_submission(db, chef_name, dish_name, description, ingredients, cook_time, cuisine, diet, category):
    """Process chef recipe submission"""
    logger.info(f"Processing chef submission: {dish_name} by {chef_name}")
    
    with st.spinner("Processing submission and generating AI rating..."):
        progress_bar = st.progress(0)

        try:
            progress_bar.progress(25)
            rating_data = generate_dish_rating(
                dish_name, description, ingredients, cook_time, cuisine
            )
            progress_bar.progress(75)

            rating = rating_data.get("rating", 3)
            comment = rating_data.get("rating_comment", "No feedback available")
            
            logger.info(f"Generated rating for {dish_name}: {rating}/5 - {comment}")

        except Exception as e:
            logger.error(f"Error generating rating: {str(e)}")
            rating = 3
            comment = f"Rating unavailable: {str(e)}"

        progress_bar.progress(90)

        # Save to database
        now = datetime.now().isoformat()
        dish_doc = {
            "name": dish_name,
            "description": description,
            "ingredients": [i.strip() for i in ingredients.split(",")],
            "cook_time": cook_time,
            "cuisine": cuisine,
            "diet": [diet],
            "category": category,
            "types": ["Chef Special Items"],
            "source": f"Chef {chef_name}",
            "rating": rating,
            "rating_comment": comment,
            "timestamp": now,
            "created_at": now
        }

        try:
            # Add to menu and recipe archive
            menu_ref = db.collection("menu").add(dish_doc)
            archive_ref = db.collection("recipe_archive").add(dish_doc)
            
            logger.info(f"Saved chef submission to menu: {menu_ref[1].id}")
            logger.info(f"Saved chef submission to archive: {archive_ref[1].id}")

            # Add to chef ratings
            rating_ref = db.collection("chef_sub_ratings").add({
                "dish_name": dish_name,
                "chef_name": chef_name,
                "rating": rating,
                "comment": comment,
                "timestamp": now
            })
            
            logger.info(f"Saved chef rating: {rating_ref[1].id}")

            progress_bar.progress(100)

            # Success message
            st.success(f"✅ Recipe '{dish_name}' submitted successfully! Rating: {rating}/5")
            
            # AI feedback
            if comment and comment != "No feedback available":
                st.info(f"**AI Feedback:** {comment}")
                
        except Exception as e:
            logger.error(f"Error saving chef submission: {str(e)}")
            st.error(f"❌ Error saving recipe: {str(e)}")

def render_analytics_dashboard(db):
    """Render the analytics dashboard component"""
    st.markdown("### 📊 Menu Analytics Dashboard")
    st.markdown("Insights into menu performance, chef ratings, and category distribution")

    # Load data with caching
    @st.cache_data(ttl=300)
    def load_menu_data():
        try:
            menu_docs = db.collection("menu").stream()
            data = [doc.to_dict() for doc in menu_docs]
            logger.info(f"Loaded {len(data)} menu items for analytics")
            return data
        except Exception as e:
            logger.error(f"Failed to load menu items: {e}")
            st.error(f"Failed to load menu items: {e}")
            return []

    menu_items = load_menu_data()

    if not menu_items:
        st.error("❌ No menu data available. Please generate a menu first.")
        return

    # Key metrics
    st.markdown("#### 📈 Overview")

    total_dishes = len(menu_items)
    categories = list(set(item.get("category", "Uncategorized") for item in menu_items))
    chef_specials = [item for item in menu_items if "Chef" in item.get("source", "")]
    
    # Calculate average rating
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
        st.metric("Avg Rating", f"{avg_rating:.1f}⭐")

    # Filters
    st.markdown("#### 🔍 Filters")

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_category = st.selectbox("Category", ["All"] + sorted(categories))

    with col2:
        cuisine_types = sorted(set(item.get("cuisine", "Unknown") for item in menu_items if item.get("cuisine")))
        selected_cuisine = st.selectbox("Cuisine", ["All"] + cuisine_types)

    with col3:
        source_types = sorted(set(item.get("source", "Unknown") for item in menu_items if item.get("source")))
        selected_source = st.selectbox("Source", ["All"] + source_types)

    # Apply filters
    filtered_items = menu_items

    if selected_category != "All":
        filtered_items = [item for item in filtered_items if item.get("category") == selected_category]

    if selected_cuisine != "All":
        filtered_items = [item for item in filtered_items if item.get("cuisine") == selected_cuisine]

    if selected_source != "All":
        filtered_items = [item for item in filtered_items if item.get("source") == selected_source]

    # Menu table
    st.markdown("#### 📋 Menu Items")

    if filtered_items:
        st.write(f"Showing {len(filtered_items)} of {total_dishes} dishes")
        df = pd.DataFrame(filtered_items)
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.info("No dishes match the selected filters.")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 👨‍🍳 Chef Ratings")

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
        st.markdown("#### 📦 Category Distribution")

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

    # Recent ratings
    st.markdown("#### 📝 Recent Chef Ratings")

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
