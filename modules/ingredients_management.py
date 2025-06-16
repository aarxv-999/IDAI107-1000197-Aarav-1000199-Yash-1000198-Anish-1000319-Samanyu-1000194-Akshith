"""
Comprehensive Ingredient Management System for Smart Restaurant Menu Management App.
Handles CRUD operations for ingredient inventory with AI-powered suggestions.
Enhanced with gamification integration.
"""

import streamlit as st
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
import os
import uuid
import re

# Import gamification system
from modules.gamification_core import award_xp

logger = logging.getLogger(__name__)

def get_event_firestore_db():
    """Get the event Firestore client for ingredient management"""
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            if init_event_firebase():
                return firestore.client(app=firebase_admin.get_app(name='event_app'))
            return None
    except Exception as e:
        logger.error(f"Error getting event Firestore client: {str(e)}")
        return None

def validate_date_format(date_string: str) -> bool:
    """Validate date format dd/mm/yyyy"""
    try:
        datetime.strptime(date_string, "%d/%m/%Y")
        return True
    except ValueError:
        return False

def is_future_date(date_string: str) -> bool:
    """Check if date is in the future"""
    try:
        input_date = datetime.strptime(date_string, "%d/%m/%Y").date()
        return input_date > date.today()
    except ValueError:
        return False

def validate_quantity(quantity_str: str) -> Tuple[bool, float]:
    """Validate quantity is positive number"""
    try:
        quantity = float(quantity_str)
        return quantity > 0, quantity
    except ValueError:
        return False, 0

def get_all_events() -> List[Dict]:
    """Get all unique event IDs from ingredient inventory"""
    try:
        db = get_event_firestore_db()
        if not db:
            return []
        
        inventory_ref = db.collection('ingredient_inventory')
        docs = inventory_ref.get()
        
        events = set()
        for doc in docs:
            data = doc.to_dict()
            event_id = data.get('Event ID', '')
            if event_id:
                events.add(event_id)
        
        return [{'id': event_id, 'name': f"Event {event_id}"} for event_id in sorted(events)]
        
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        return []

def create_new_event() -> str:
    """Create a new event ID"""
    return f"EVT_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"

def get_all_ingredients(search_term: str = "", expiry_filter: str = "all", type_filter: str = "all") -> List[Dict]:
    """Get all ingredients with optional filtering"""
    try:
        db = get_event_firestore_db()
        if not db:
            return []
        
        inventory_ref = db.collection('ingredient_inventory')
        docs = inventory_ref.get()
        
        ingredients = []
        current_date = date.today()
        
        for doc in docs:
            data = doc.to_dict()
            data['doc_id'] = doc.id
            
            # Calculate days until expiry
            expiry_str = data.get('Expiry Date', '')
            try:
                expiry_date = datetime.strptime(expiry_str, "%d/%m/%Y").date()
                days_until_expiry = (expiry_date - current_date).days
                data['days_until_expiry'] = days_until_expiry
                data['expiry_status'] = get_expiry_status(days_until_expiry)
            except:
                data['days_until_expiry'] = -999
                data['expiry_status'] = 'invalid'
            
            ingredients.append(data)
        
        # Apply filters
        filtered_ingredients = []
        
        for ingredient in ingredients:
            # Search filter
            if search_term:
                ingredient_name = ingredient.get('Ingredient', '').lower()
                if search_term.lower() not in ingredient_name:
                    continue
            
            # Expiry filter
            if expiry_filter != "all":
                if expiry_filter == "expired" and ingredient['days_until_expiry'] >= 0:
                    continue
                elif expiry_filter == "expiring_soon" and not (0 <= ingredient['days_until_expiry'] <= 7):
                    continue
                elif expiry_filter == "fresh" and ingredient['days_until_expiry'] <= 7:
                    continue
            
            # Type filter
            if type_filter != "all":
                ingredient_type = ingredient.get('Type', '').lower()
                if type_filter.lower() != ingredient_type.lower():
                    continue
            
            filtered_ingredients.append(ingredient)
        
        # Sort by expiry date (soonest first)
        filtered_ingredients.sort(key=lambda x: x['days_until_expiry'])
        
        return filtered_ingredients
        
    except Exception as e:
        logger.error(f"Error getting ingredients: {str(e)}")
        return []

def get_expiry_status(days_until_expiry: int) -> str:
    """Get expiry status based on days until expiry"""
    if days_until_expiry < 0:
        return "expired"
    elif days_until_expiry <= 3:
        return "critical"
    elif days_until_expiry <= 7:
        return "warning"
    else:
        return "fresh"

def get_ingredient_types() -> List[str]:
    """Get all unique ingredient types"""
    try:
        db = get_event_firestore_db()
        if not db:
            return []
        
        inventory_ref = db.collection('ingredient_inventory')
        docs = inventory_ref.get()
        
        types = set()
        for doc in docs:
            data = doc.to_dict()
            ingredient_type = data.get('Type', '').strip()
            if ingredient_type:
                types.add(ingredient_type)
        
        return sorted(list(types))
        
    except Exception as e:
        logger.error(f"Error getting ingredient types: {str(e)}")
        return []

def add_ingredient(event_id: str, ingredient_name: str, quantity: float, ingredient_type: str, 
                  expiry_date: str, alternatives: str = "", user_id: str = None) -> Tuple[bool, str]:
    """Add a new ingredient to inventory with XP reward"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        # Validate inputs
        if not all([event_id, ingredient_name, quantity > 0, ingredient_type, expiry_date]):
            return False, "All fields are required"
        
        if not validate_date_format(expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy"
        
        if not is_future_date(expiry_date):
            return False, "Expiry date must be in the future"
        
        # Create ingredient document
        ingredient_data = {
            'Event ID': event_id,
            'Ingredient': ingredient_name.strip(),
            'Quantity': str(quantity),
            'Type': ingredient_type.strip(),
            'Expiry Date': expiry_date,
            'Alternatives': alternatives.strip(),
            'Created': datetime.now().strftime("%d/%m/%Y %H:%M"),
            'Last Modified': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        inventory_ref = db.collection('ingredient_inventory')
        inventory_ref.add(ingredient_data)
        
        # Award XP for adding ingredient
        if user_id:
            try:
                xp_awarded, level_up, achievements = award_xp(
                    user_id, 
                    'ingredient_add', 
                    context={'feature': 'ingredients_management', 'ingredient_name': ingredient_name}
                )
                if xp_awarded > 0:
                    st.success(f"✅ Added {ingredient_name} (+{xp_awarded} XP)")
                    if level_up:
                        st.balloons()
                        st.success("🎉 LEVEL UP!")
                    if achievements:
                        for achievement in achievements:
                            st.success(f"🏆 Achievement Unlocked: {achievement}!")
                else:
                    st.success(f"✅ Added {ingredient_name}")
            except Exception as e:
                logger.error(f"Error awarding XP for ingredient add: {str(e)}")
                st.success(f"✅ Added {ingredient_name}")
        
        logger.info(f"Added ingredient: {ingredient_name} to event {event_id}")
        return True, f"Successfully added {ingredient_name}"
        
    except Exception as e:
        logger.error(f"Error adding ingredient: {str(e)}")
        return False, f"Error adding ingredient: {str(e)}"

def update_ingredient(doc_id: str, ingredient_name: str, quantity: float, ingredient_type: str,
                     expiry_date: str, alternatives: str = "", user_id: str = None) -> Tuple[bool, str]:
    """Update an existing ingredient with XP reward"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        # Validate inputs
        if not all([ingredient_name, quantity > 0, ingredient_type, expiry_date]):
            return False, "All fields are required"
        
        if not validate_date_format(expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy"
        
        # Update ingredient document
        update_data = {
            'Ingredient': ingredient_name.strip(),
            'Quantity': str(quantity),
            'Type': ingredient_type.strip(),
            'Expiry Date': expiry_date,
            'Alternatives': alternatives.strip(),
            'Last Modified': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        inventory_ref = db.collection('ingredient_inventory').document(doc_id)
        inventory_ref.update(update_data)
        
        # Award XP for updating ingredient
        if user_id:
            try:
                xp_awarded, level_up, achievements = award_xp(
                    user_id, 
                    'ingredient_update', 
                    context={'feature': 'ingredients_management', 'ingredient_name': ingredient_name}
                )
                if xp_awarded > 0:
                    st.success(f"✅ Updated {ingredient_name} (+{xp_awarded} XP)")
                    if level_up:
                        st.balloons()
                        st.success("🎉 LEVEL UP!")
                    if achievements:
                        for achievement in achievements:
                            st.success(f"🏆 Achievement Unlocked: {achievement}!")
                else:
                    st.success(f"✅ Updated {ingredient_name}")
            except Exception as e:
                logger.error(f"Error awarding XP for ingredient update: {str(e)}")
                st.success(f"✅ Updated {ingredient_name}")
        
        logger.info(f"Updated ingredient: {ingredient_name}")
        return True, f"Successfully updated {ingredient_name}"
        
    except Exception as e:
        logger.error(f"Error updating ingredient: {str(e)}")
        return False, f"Error updating ingredient: {str(e)}"

def delete_ingredient(doc_id: str, ingredient_name: str) -> Tuple[bool, str]:
    """Delete an ingredient from inventory"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        inventory_ref = db.collection('ingredient_inventory').document(doc_id)
        inventory_ref.delete()
        
        logger.info(f"Deleted ingredient: {ingredient_name}")
        return True, f"Successfully deleted {ingredient_name}"
        
    except Exception as e:
        logger.error(f"Error deleting ingredient: {str(e)}")
        return False, f"Error deleting ingredient: {str(e)}"

def bulk_delete_ingredients(doc_ids: List[str]) -> Tuple[bool, str]:
    """Delete multiple ingredients"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        batch = db.batch()
        inventory_ref = db.collection('ingredient_inventory')
        
        for doc_id in doc_ids:
            doc_ref = inventory_ref.document(doc_id)
            batch.delete(doc_ref)
        
        batch.commit()
        
        logger.info(f"Bulk deleted {len(doc_ids)} ingredients")
        return True, f"Successfully deleted {len(doc_ids)} ingredients"
        
    except Exception as e:
        logger.error(f"Error bulk deleting ingredients: {str(e)}")
        return False, f"Error bulk deleting ingredients: {str(e)}"

def bulk_update_expiry(doc_ids: List[str], new_expiry_date: str, user_id: str = None) -> Tuple[bool, str]:
    """Update expiry date for multiple ingredients with XP reward"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        if not validate_date_format(new_expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy"
        
        if not is_future_date(new_expiry_date):
            return False, "Expiry date must be in the future"
        
        batch = db.batch()
        inventory_ref = db.collection('ingredient_inventory')
        
        for doc_id in doc_ids:
            doc_ref = inventory_ref.document(doc_id)
            batch.update(doc_ref, {
                'Expiry Date': new_expiry_date,
                'Last Modified': datetime.now().strftime("%d/%m/%Y %H:%M")
            })
        
        batch.commit()
        
        # Award XP for inventory management
        if user_id:
            try:
                xp_awarded, level_up, achievements = award_xp(
                    user_id, 
                    'inventory_management', 
                    context={'feature': 'ingredients_management', 'items_updated': len(doc_ids)}
                )
                if xp_awarded > 0:
                    st.success(f"✅ Updated {len(doc_ids)} ingredients (+{xp_awarded} XP)")
                    if level_up:
                        st.balloons()
                        st.success("🎉 LEVEL UP!")
                    if achievements:
                        for achievement in achievements:
                            st.success(f"🏆 Achievement Unlocked: {achievement}!")
            except Exception as e:
                logger.error(f"Error awarding XP for bulk update: {str(e)}")
        
        logger.info(f"Bulk updated expiry for {len(doc_ids)} ingredients")
        return True, f"Successfully updated expiry date for {len(doc_ids)} ingredients"
        
    except Exception as e:
        logger.error(f"Error bulk updating expiry: {str(e)}")
        return False, f"Error bulk updating expiry: {str(e)}"

def suggest_alternatives_with_ai(ingredient_name: str) -> List[str]:
    """Use Gemini AI to suggest ingredient alternatives"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return ["AI suggestions unavailable - API key not found"]
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f'''Suggest exactly 2 practical cooking alternatives for the ingredient "{ingredient_name}".

Requirements:
- Provide alternatives that can be used in similar cooking applications
- Consider flavor profile, texture, and cooking properties
- Make suggestions practical for restaurant use
- Keep suggestions concise (2-4 words each)

Format your response as exactly 2 alternatives separated by a comma, nothing else.

Example format: "alternative1, alternative2"

Ingredient: {ingredient_name}'''

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse alternatives
        alternatives = [alt.strip() for alt in response_text.split(',')]
        alternatives = [alt for alt in alternatives if alt and len(alt) > 0]
        
        # Ensure we have exactly 2 alternatives
        if len(alternatives) >= 2:
            return alternatives[:2]
        elif len(alternatives) == 1:
            return alternatives + ["Similar ingredient"]
        else:
            return ["Similar ingredient", "Substitute ingredient"]
            
    except Exception as e:
        logger.error(f"Error getting AI alternatives: {str(e)}")
        return ["Similar ingredient", "Substitute ingredient"]

def render_ingredient_management():
    """Main ingredient management interface with gamification"""
    st.title("🥬 Ingredient Management")
    
    # Get current user for XP awarding
    user = st.session_state.get('user', {})
    user_id = user.get('user_id')
    
    # Check database connection
    db = get_event_firestore_db()
    if not db:
        st.error("❌ Cannot connect to ingredient database. Please check your Firebase configuration.")
        return
    
    # Create tabs for different functions
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View Ingredients", "➕ Add Ingredient", "✏️ Edit Ingredient", "🔧 Bulk Operations"])
    
    with tab1:
        render_view_ingredients()
    
    with tab2:
        render_add_ingredient(user_id)
    
    with tab3:
        render_edit_ingredient(user_id)
    
    with tab4:
        render_bulk_operations(user_id)

def render_view_ingredients():
    """Render the ingredient viewing interface with search and filters"""
    st.markdown("### 📋 Current Inventory")
    
    # Search and filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔍 Search Ingredients", placeholder="Enter ingredient name...")
    
    with col2:
        expiry_options = {
            "all": "All Items",
            "expired": "Expired",
            "expiring_soon": "Expiring Soon (≤7 days)",
            "fresh": "Fresh (>7 days)"
        }
        expiry_filter = st.selectbox("📅 Filter by Expiry", options=list(expiry_options.keys()), 
                                   format_func=lambda x: expiry_options[x])
    
    with col3:
        ingredient_types = ["all"] + get_ingredient_types()
        type_filter = st.selectbox("🏷️ Filter by Type", options=ingredient_types,
                                 format_func=lambda x: "All Types" if x == "all" else x)
    
    # Get filtered ingredients
    ingredients = get_all_ingredients(search_term, expiry_filter, type_filter)
    
    if not ingredients:
        st.info("No ingredients found matching your criteria.")
        return
    
    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    expired_count = len([ing for ing in ingredients if ing['days_until_expiry'] < 0])
    expiring_soon_count = len([ing for ing in ingredients if 0 <= ing['days_until_expiry'] <= 7])
    fresh_count = len([ing for ing in ingredients if ing['days_until_expiry'] > 7])
    
    with col1:
        st.metric("Total Items", len(ingredients))
    with col2:
        st.metric("Expired", expired_count, delta=f"-{expired_count}" if expired_count > 0 else None)
    with col3:
        st.metric("Expiring Soon", expiring_soon_count, delta=f"⚠️ {expiring_soon_count}" if expiring_soon_count > 0 else None)
    with col4:
        st.metric("Fresh", fresh_count, delta=f"✅ {fresh_count}" if fresh_count > 0 else None)
    
    st.divider()
    
    # Display ingredients in a table format
    for ingredient in ingredients:
        expiry_status = ingredient['expiry_status']
        days_until_expiry = ingredient['days_until_expiry']
        
        # Choose color based on expiry status
        if expiry_status == "expired":
            status_color = "🔴"
            status_text = f"Expired {abs(days_until_expiry)} days ago"
        elif expiry_status == "critical":
            status_color = "🟠"
            status_text = f"Expires in {days_until_expiry} days"
        elif expiry_status == "warning":
            status_color = "🟡"
            status_text = f"Expires in {days_until_expiry} days"
        else:
            status_color = "🟢"
            status_text = f"Fresh ({days_until_expiry} days left)"
        
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
            
            with col1:
                st.markdown(f"**{ingredient.get('Ingredient', 'Unknown')}**")
                st.caption(f"Event: {ingredient.get('Event ID', 'N/A')}")
            
            with col2:
                st.write(f"**Quantity:** {ingredient.get('Quantity', 'N/A')}")
                st.caption(f"Type: {ingredient.get('Type', 'N/A')}")
            
            with col3:
                st.write(f"**Expiry:** {ingredient.get('Expiry Date', 'N/A')}")
                st.caption(f"{status_color} {status_text}")
            
            with col4:
                alternatives = ingredient.get('Alternatives', '')
                if alternatives:
                    st.write(f"**Alternatives:**")
                    st.caption(alternatives)
                else:
                    st.write("**Alternatives:**")
                    st.caption("None specified")
            
            with col5:
                if st.button("✏️ Edit", key=f"edit_{ingredient['doc_id']}", use_container_width=True):
                    st.session_state.edit_ingredient_id = ingredient['doc_id']
                    st.session_state.selected_tab = 2  # Switch to edit tab
                    st.rerun()
        
        st.divider()

def render_add_ingredient(user_id: str):
    """Render the add ingredient interface with gamification"""
    st.markdown("### ➕ Add New Ingredient")
    
    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Event selection or creation
            events = get_all_events()
            event_options = ["Create New Event"] + [f"{event['name']} ({event['id']})" for event in events]
            
            selected_event_option = st.selectbox("📅 Select Event", options=event_options)
            
            if selected_event_option == "Create New Event":
                event_name = st.text_input("Event Name", placeholder="Enter event name...")
                if event_name:
                    event_id = create_new_event()
                    st.info(f"New Event ID: {event_id}")
                else:
                    event_id = ""
            else:
                # Extract event ID from selection
                event_id = selected_event_option.split("(")[-1].rstrip(")")
            
            ingredient_name = st.text_input("🥬 Ingredient Name*", placeholder="e.g., Tomatoes")
            
            quantity_str = st.text_input("📊 Quantity*", placeholder="e.g., 5.5")
            
        with col2:
            ingredient_types = get_ingredient_types()
            if ingredient_types:
                ingredient_type = st.selectbox("🏷️ Type*", options=[""] + ingredient_types)
                if not ingredient_type:
                    ingredient_type = st.text_input("Or enter new type:", placeholder="e.g., Vegetable")
            else:
                ingredient_type = st.text_input("🏷️ Type*", placeholder="e.g., Vegetable")
            
            # Date input with proper format
            expiry_date_input = st.date_input("📅 Expiry Date*", 
                                            min_value=date.today() + timedelta(days=1),
                                            value=date.today() + timedelta(days=7))
            expiry_date = expiry_date_input.strftime("%d/%m/%Y")
            
            # Alternatives with AI suggestion
            col2a, col2b = st.columns([3, 1])
            with col2a:
                alternatives = st.text_input("🔄 Alternatives", placeholder="Optional alternatives...")
            with col2b:
                st.write("")  # Spacing
                ai_suggest_button = st.form_submit_button("🤖 AI Suggest", use_container_width=True)
        
        # Show AI suggestions if available
        if 'suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.suggested_alternatives}")
            if st.checkbox("Use AI suggestions"):
                alternatives = st.session_state.suggested_alternatives
        
        # Handle AI suggestion button
        if ai_suggest_button:
            if ingredient_name:
                with st.spinner("Getting AI suggestions..."):
                    ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                    st.session_state.suggested_alternatives = ", ".join(ai_alternatives)
                    st.rerun()
            else:
                st.warning("Enter ingredient name first")
        
        submitted = st.form_submit_button("➕ Add Ingredient", type="primary", use_container_width=True)
        
        if submitted:
            # Validate quantity
            is_valid_qty, quantity = validate_quantity(quantity_str)
            
            if not all([event_id, ingredient_name, is_valid_qty, ingredient_type]):
                st.error("❌ Please fill all required fields with valid values")
            else:
                success, message = add_ingredient(event_id, ingredient_name, quantity, 
                                                ingredient_type, expiry_date, alternatives, user_id)
                if success:
                    # Clear AI suggestions
                    if 'suggested_alternatives' in st.session_state:
                        del st.session_state.suggested_alternatives
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def render_edit_ingredient(user_id: str):
    """Render the edit ingredient interface with gamification"""
    st.markdown("### ✏️ Edit Ingredient")
    
    # Get ingredient to edit
    edit_id = st.session_state.get('edit_ingredient_id', '')
    
    if not edit_id:
        st.info("Select an ingredient from the 'View Ingredients' tab to edit.")
        return
    
    # Get current ingredient data
    ingredients = get_all_ingredients()
    current_ingredient = None
    
    for ingredient in ingredients:
        if ingredient['doc_id'] == edit_id:
            current_ingredient = ingredient
            break
    
    if not current_ingredient:
        st.error("Ingredient not found.")
        if st.button("← Back to View"):
            del st.session_state.edit_ingredient_id
            st.rerun()
        return
    
    st.info(f"Editing: **{current_ingredient.get('Ingredient', 'Unknown')}**")
    
    with st.form("edit_ingredient_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            ingredient_name = st.text_input("🥬 Ingredient Name*", 
                                          value=current_ingredient.get('Ingredient', ''))
            
            quantity_str = st.text_input("📊 Quantity*", 
                                       value=current_ingredient.get('Quantity', ''))
            
        with col2:
            ingredient_types = get_ingredient_types()
            current_type = current_ingredient.get('Type', '')
            
            if current_type in ingredient_types:
                type_index = ingredient_types.index(current_type)
                ingredient_type = st.selectbox("🏷️ Type*", options=ingredient_types, index=type_index)
            else:
                ingredient_type = st.text_input("🏷️ Type*", value=current_type)
            
            # Parse current expiry date with better error handling
            current_expiry = current_ingredient.get('Expiry Date', '')
            try:
                current_expiry_date = datetime.strptime(current_expiry, "%d/%m/%Y").date()
            except:
                current_expiry_date = date.today() + timedelta(days=7)
            
            # For editing, allow past dates (ingredients might already be expired)
            # Set min_value to a reasonable past date instead of future only
            min_date = date.today() - timedelta(days=365)  # Allow up to 1 year in the past
            max_date = date.today() + timedelta(days=365*10)  # Allow up to 10 years in the future
            
            # Ensure current_expiry_date is within bounds
            if current_expiry_date < min_date:
                current_expiry_date = min_date
            elif current_expiry_date > max_date:
                current_expiry_date = max_date
            
            expiry_date_input = st.date_input("📅 Expiry Date*", 
                                            value=current_expiry_date,
                                            min_value=min_date,
                                            max_value=max_date)
            expiry_date = expiry_date_input.strftime("%d/%m/%Y")
        
        # Alternatives with AI suggestion
        col2a, col2b = st.columns([3, 1])
        with col2a:
            alternatives = st.text_input("🔄 Alternatives", 
                                       value=current_ingredient.get('Alternatives', ''))
        with col2b:
            st.write("")  # Spacing
            ai_suggest_edit_button = st.form_submit_button("🤖 AI Suggest")
        
        # Show AI suggestions if available
        if 'edit_suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.edit_suggested_alternatives}")
            if st.checkbox("Use AI suggestions"):
                alternatives = st.session_state.edit_suggested_alternatives
        
        # Handle AI suggestion button
        if ai_suggest_edit_button:
            if ingredient_name:
                with st.spinner("Getting AI suggestions..."):
                    ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                    st.session_state.edit_suggested_alternatives = ", ".join(ai_alternatives)
                    st.rerun()
            else:
                st.warning("Enter ingredient name first")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            update_submitted = st.form_submit_button("💾 Update Ingredient", type="primary", use_container_width=True)
        
        with col2:
            delete_submitted = st.form_submit_button("🗑️ Delete Ingredient", use_container_width=True)
        
        with col3:
            back_submitted = st.form_submit_button("← Back to View", use_container_width=True)
        
        if update_submitted:
            # Validate quantity
            is_valid_qty, quantity = validate_quantity(quantity_str)
            
            if not all([ingredient_name, is_valid_qty, ingredient_type]):
                st.error("❌ Please fill all required fields with valid values")
            else:
                success, message = update_ingredient(edit_id, ingredient_name, quantity, 
                                                   ingredient_type, expiry_date, alternatives, user_id)
                if success:
                    del st.session_state.edit_ingredient_id
                    if 'edit_suggested_alternatives' in st.session_state:
                        del st.session_state.edit_suggested_alternatives
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        if delete_submitted:
            st.session_state.confirm_delete = edit_id
            st.rerun()
        
        if back_submitted:
            del st.session_state.edit_ingredient_id
            if 'edit_suggested_alternatives' in st.session_state:
                del st.session_state.edit_suggested_alternatives
            st.rerun()
    
    # Handle delete confirmation
    if st.session_state.get('confirm_delete') == edit_id:
        st.warning("⚠️ Are you sure you want to delete this ingredient?")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Yes, Delete", type="primary", use_container_width=True):
                success, message = delete_ingredient(edit_id, current_ingredient.get('Ingredient', 'Unknown'))
                if success:
                    st.success(f"✅ {message}")
                    del st.session_state.edit_ingredient_id
                    del st.session_state.confirm_delete
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                del st.session_state.confirm_delete
                st.rerun()

def render_bulk_operations(user_id: str):
    """Render bulk operations interface with gamification"""
    st.markdown("### 🔧 Bulk Operations")
    
    ingredients = get_all_ingredients()
    
    if not ingredients:
        st.info("No ingredients available for bulk operations.")
        return
    
    st.markdown("#### Select Ingredients for Bulk Operations")
    
    # Select all checkbox
    select_all = st.checkbox("Select All Ingredients")
    
    selected_ingredients = []
    
    # Create ingredient selection interface
    for ingredient in ingredients:
        col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
        
        with col1:
            is_selected = st.checkbox("Select", key=f"bulk_select_{ingredient['doc_id']}", value=select_all, label_visibility="hidden")
            if is_selected:
                selected_ingredients.append(ingredient)
        
        with col2:
            st.write(f"**{ingredient.get('Ingredient', 'Unknown')}**")
        
        with col3:
            st.write(f"Qty: {ingredient.get('Quantity', 'N/A')}")
        
        with col4:
            expiry_status = ingredient['expiry_status']
            status_icons = {"expired": "🔴", "critical": "🟠", "warning": "🟡", "fresh": "🟢"}
            st.write(f"{status_icons.get(expiry_status, '⚪')} {ingredient.get('Expiry Date', 'N/A')}")
    
    if not selected_ingredients:
        st.info("Select ingredients to perform bulk operations.")
        return
    
    st.divider()
    st.markdown(f"#### Bulk Operations ({len(selected_ingredients)} selected)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 🗑️ Bulk Delete")
        st.warning(f"This will permanently delete {len(selected_ingredients)} ingredients.")
        
        if st.button("🗑️ Delete Selected Ingredients", type="primary", use_container_width=True):
            st.session_state.confirm_bulk_delete = [ing['doc_id'] for ing in selected_ingredients]
    
    with col2:
        st.markdown("##### 📅 Bulk Update Expiry Date")
        
        new_expiry_date = st.date_input("New Expiry Date", 
                                      min_value=date.today() + timedelta(days=1),
                                      value=date.today() + timedelta(days=7),
                                      key="bulk_expiry_date")
        
        if st.button("📅 Update Expiry Dates", type="primary", use_container_width=True):
            doc_ids = [ing['doc_id'] for ing in selected_ingredients]
            expiry_str = new_expiry_date.strftime("%d/%m/%Y")
            
            success, message = bulk_update_expiry(doc_ids, expiry_str, user_id)
            if success:
                st.rerun()
            else:
                st.error(f"❌ {message}")
    
    # Handle bulk delete confirmation
    if 'confirm_bulk_delete' in st.session_state:
        st.divider()
        st.error("⚠️ **CONFIRM BULK DELETE**")
        st.write(f"You are about to delete {len(st.session_state.confirm_bulk_delete)} ingredients. This action cannot be undone.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Confirm Delete", type="primary", use_container_width=True):
                success, message = bulk_delete_ingredients(st.session_state.confirm_bulk_delete)
                if success:
                    st.success(f"✅ {message}")
                    del st.session_state.confirm_bulk_delete
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
        
        with col2:
            if st.button("❌ Cancel Delete", use_container_width=True):
                del st.session_state.confirm_bulk_delete
                st.rerun()
