import streamlit as st
st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")

from ui.components import (
  leftover_input_csv, leftover_input_manual, leftover_input_firebase
)
from ui.components import (
  render_auth_ui, initialize_session_state, auth_required, get_current_user, is_user_role
)
from ui.components import (
  display_user_stats_sidebar, render_cooking_quiz, display_gamification_dashboard,
  award_recipe_generation_xp, display_daily_challenge, show_xp_notification
)
from modules.leftover import suggest_recipes
from modules.leftover import get_user_stats, award_recipe_xp
from firebase_init import init_firebase

from app_integration import integrate_event_planner, check_event_firebase_config
from dashboard import render_dashboard, get_feature_description

init_firebase()

import logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(levelname)s - %(message)s')

# Ingredient Management Functions (embedded directly)
import firebase_admin
from firebase_admin import firestore
import google.generativeai as genai
import os
import uuid
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple

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
        logging.error(f"Error getting event Firestore client: {str(e)}")
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
        logging.error(f"Error getting events: {str(e)}")
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
        logging.error(f"Error getting ingredients: {str(e)}")
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
        logging.error(f"Error getting ingredient types: {str(e)}")
        return []

def add_ingredient(event_id: str, ingredient_name: str, quantity: float, ingredient_type: str, 
                  expiry_date: str, alternatives: str = "") -> Tuple[bool, str]:
    """Add a new ingredient to inventory"""
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
        
        logging.info(f"Added ingredient: {ingredient_name} to event {event_id}")
        return True, f"Successfully added {ingredient_name}"
        
    except Exception as e:
        logging.error(f"Error adding ingredient: {str(e)}")
        return False, f"Error adding ingredient: {str(e)}"

def update_ingredient(doc_id: str, ingredient_name: str, quantity: float, ingredient_type: str,
                     expiry_date: str, alternatives: str = "") -> Tuple[bool, str]:
    """Update an existing ingredient"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        # Validate inputs
        if not all([ingredient_name, quantity > 0, ingredient_type, expiry_date]):
            return False, "All fields are required"
        
        if not validate_date_format(expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy"
        
        if not is_future_date(expiry_date):
            return False, "Expiry date must be in the future"
        
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
        
        logging.info(f"Updated ingredient: {ingredient_name}")
        return True, f"Successfully updated {ingredient_name}"
        
    except Exception as e:
        logging.error(f"Error updating ingredient: {str(e)}")
        return False, f"Error updating ingredient: {str(e)}"

def delete_ingredient(doc_id: str, ingredient_name: str) -> Tuple[bool, str]:
    """Delete an ingredient from inventory"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        inventory_ref = db.collection('ingredient_inventory').document(doc_id)
        inventory_ref.delete()
        
        logging.info(f"Deleted ingredient: {ingredient_name}")
        return True, f"Successfully deleted {ingredient_name}"
        
    except Exception as e:
        logging.error(f"Error deleting ingredient: {str(e)}")
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
        
        logging.info(f"Bulk deleted {len(doc_ids)} ingredients")
        return True, f"Successfully deleted {len(doc_ids)} ingredients"
        
    except Exception as e:
        logging.error(f"Error bulk deleting ingredients: {str(e)}")
        return False, f"Error bulk deleting ingredients: {str(e)}"

def bulk_update_expiry(doc_ids: List[str], new_expiry_date: str) -> Tuple[bool, str]:
    """Update expiry date for multiple ingredients"""
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
        
        logging.info(f"Bulk updated expiry for {len(doc_ids)} ingredients")
        return True, f"Successfully updated expiry date for {len(doc_ids)} ingredients"
        
    except Exception as e:
        logging.error(f"Error bulk updating expiry: {str(e)}")
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
        logging.error(f"Error getting AI alternatives: {str(e)}")
        return ["Similar ingredient", "Substitute ingredient"]

def render_ingredient_management():
    """Main ingredient management interface"""
    st.title("🥬 Ingredient Management")
    
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
        render_add_ingredient()
    
    with tab3:
        render_edit_ingredient()
    
    with tab4:
        render_bulk_operations()

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

def render_add_ingredient():
    """Render the add ingredient interface"""
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
                if st.form_submit_button("🤖 AI Suggest", use_container_width=True):
                    if ingredient_name:
                        with st.spinner("Getting AI suggestions..."):
                            ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                            st.session_state.suggested_alternatives = ", ".join(ai_alternatives)
                    else:
                        st.warning("Enter ingredient name first")
        
        # Show AI suggestions if available
        if 'suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.suggested_alternatives}")
            if st.checkbox("Use AI suggestions"):
                alternatives = st.session_state.suggested_alternatives
        
        submitted = st.form_submit_button("➕ Add Ingredient", type="primary", use_container_width=True)
        
        if submitted:
            # Validate quantity
            is_valid_qty, quantity = validate_quantity(quantity_str)
            
            if not all([event_id, ingredient_name, is_valid_qty, ingredient_type]):
                st.error("❌ Please fill all required fields with valid values")
            else:
                success, message = add_ingredient(event_id, ingredient_name, quantity, 
                                                ingredient_type, expiry_date, alternatives)
                if success:
                    st.success(f"✅ {message}")
                    # Clear AI suggestions
                    if 'suggested_alternatives' in st.session_state:
                        del st.session_state.suggested_alternatives
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def render_edit_ingredient():
    """Render the edit ingredient interface"""
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
            
            # Parse current expiry date
            current_expiry = current_ingredient.get('Expiry Date', '')
            try:
                current_expiry_date = datetime.strptime(current_expiry, "%d/%m/%Y").date()
            except:
                current_expiry_date = date.today() + timedelta(days=7)
            
            expiry_date_input = st.date_input("📅 Expiry Date*", 
                                            value=current_expiry_date,
                                            min_value=date.today() + timedelta(days=1))
            expiry_date = expiry_date_input.strftime("%d/%m/%Y")
        
        # Alternatives with AI suggestion
        col2a, col2b = st.columns([3, 1])
        with col2a:
            alternatives = st.text_input("🔄 Alternatives", 
                                       value=current_ingredient.get('Alternatives', ''))
        with col2b:
            st.write("")  # Spacing
            if st.form_submit_button("🤖 AI Suggest"):
                if ingredient_name:
                    with st.spinner("Getting AI suggestions..."):
                        ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                        st.session_state.edit_suggested_alternatives = ", ".join(ai_alternatives)
                else:
                    st.warning("Enter ingredient name first")
        
        # Show AI suggestions if available
        if 'edit_suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.edit_suggested_alternatives}")
            if st.checkbox("Use AI suggestions"):
                alternatives = st.session_state.edit_suggested_alternatives
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            update_submitted = st.form_submit_button("💾 Update Ingredient", type="primary", use_container_width=True)
        
        with col2:
            if st.form_submit_button("🗑️ Delete Ingredient", use_container_width=True):
                st.session_state.confirm_delete = edit_id
        
        with col3:
            if st.form_submit_button("← Back to View", use_container_width=True):
                del st.session_state.edit_ingredient_id
                if 'edit_suggested_alternatives' in st.session_state:
                    del st.session_state.edit_suggested_alternatives
                st.rerun()
        
        if update_submitted:
            # Validate quantity
            is_valid_qty, quantity = validate_quantity(quantity_str)
            
            if not all([ingredient_name, is_valid_qty, ingredient_type]):
                st.error("❌ Please fill all required fields with valid values")
            else:
                success, message = update_ingredient(edit_id, ingredient_name, quantity, 
                                                   ingredient_type, expiry_date, alternatives)
                if success:
                    st.success(f"✅ {message}")
                    del st.session_state.edit_ingredient_id
                    if 'edit_suggested_alternatives' in st.session_state:
                        del st.session_state.edit_suggested_alternatives
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
    
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

def render_bulk_operations():
    """Render bulk operations interface"""
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
            is_selected = st.checkbox("", key=f"bulk_select_{ingredient['doc_id']}", value=select_all)
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
            
            success, message = bulk_update_expiry(doc_ids, expiry_str)
            if success:
                st.success(f"✅ {message}")
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

# End of Ingredient Management Functions

def check_feature_access(feature_name):
  """Check if the current user has access to a specific feature"""
  user = get_current_user()

  public_features = ["Event Planning ChatBot", "Gamification Hub", "Cooking Quiz"]
  staff_features = ["Leftover Management", "Promotion Generator"]
  chef_features = ["Chef Recipe Suggestions", "Ingredient Management"]  # Added Ingredient Management
  admin_features = ["Visual Menu Search", "Ingredient Management"]  # Added Ingredient Management

  if feature_name in public_features:
      return True

  if not user:
      return False
      
  if feature_name in staff_features and user['role'] in ['staff', 'manager', 'chef', 'admin']:
      return True
      
  if feature_name in chef_features and user['role'] in ['chef', 'admin']:
      return True
      
  if feature_name in admin_features and user['role'] in ['admin']:
      return True
      
  return False

@auth_required
def leftover_management():
  """Combined leftover management and cooking quiz interface"""
  st.title("♻️ Leftover Management")
  
  user = get_current_user()
  user_id = user.get('user_id', '') if user else ''
  
  # Create tabs for different functions
  tab1, tab2 = st.tabs(["♻️ Leftover Recipes", "🧠 Cooking Quiz"])
  
  with tab1:
      render_leftover_management(user_id)
  
  with tab2:
      render_cooking_quiz_tab(user_id)

def render_leftover_management(user_id: str):
  """Clean step-by-step leftover management section"""
  st.markdown("### ♻️ Generate New Recipes from Leftovers")
  
  # Initialize session state
  if 'leftover_step' not in st.session_state:
      st.session_state.leftover_step = 'select_method'
  if 'selected_method' not in st.session_state:
      st.session_state.selected_method = None
  if 'max_ingredients' not in st.session_state:
      st.session_state.max_ingredients = 8
  if 'all_leftovers' not in st.session_state:
      st.session_state.all_leftovers = []
  if 'detailed_ingredient_info' not in st.session_state:
      st.session_state.detailed_ingredient_info = []
  if 'recipes' not in st.session_state:
      st.session_state.recipes = []
  if 'recipe_generation_error' not in st.session_state:
      st.session_state.recipe_generation_error = None

  # Step 1: Method Selection
  if st.session_state.leftover_step == 'select_method':
      st.markdown("#### Step 1: Choose Your Ingredient Input Method")
      
      col1, col2, col3 = st.columns(3)
      
      with col1:
          if st.button("📁 Upload CSV File", use_container_width=True, type="primary", key="csv_method"):
              st.session_state.selected_method = 'csv'
              st.session_state.leftover_step = 'input_ingredients'
              st.rerun()
          st.caption("Upload a CSV file with ingredient list")
      
      with col2:
          if st.button("✏️ Manual Entry", use_container_width=True, type="primary", key="manual_method"):
              st.session_state.selected_method = 'manual'
              st.session_state.leftover_step = 'input_ingredients'
              st.rerun()
          st.caption("Type ingredients manually")
      
      with col3:
          if st.button("🔥 Current Inventory", use_container_width=True, type="primary", key="firebase_method"):
              st.session_state.selected_method = 'firebase'
              st.session_state.leftover_step = 'firebase_config'  # New step for Firebase
              st.rerun()
          st.caption("Fetch from restaurant database")

  # Step 2: Firebase Configuration (only for Firebase method)
  elif st.session_state.leftover_step == 'firebase_config':
      st.markdown("#### Step 2: Configure Inventory Fetch")
      
      # Back button
      if st.button("← Back to Method Selection", key="back_to_method"):
          st.session_state.leftover_step = 'select_method'
          st.session_state.selected_method = None
          st.rerun()
      
      st.info("Configure how many ingredients to fetch from your restaurant inventory")
      
      max_ingredients = st.slider(
          "Maximum ingredients to fetch", 
          min_value=3, 
          max_value=20, 
          value=st.session_state.max_ingredients,
          help="Select how many ingredients you want to work with"
      )
      st.session_state.max_ingredients = max_ingredients
      
      if st.button("Continue to Fetch Ingredients →", type="primary", use_container_width=True, key="continue_firebase"):
          st.session_state.leftover_step = 'input_ingredients'
          st.rerun()

  # Step 3: Input Ingredients
  elif st.session_state.leftover_step == 'input_ingredients':
      method_names = {
          'csv': '📁 CSV Upload',
          'manual': '✏️ Manual Entry', 
          'firebase': '🔥 Current Inventory'
      }
      
      st.markdown(f"#### Step {'3' if st.session_state.selected_method == 'firebase' else '2'}: {method_names[st.session_state.selected_method]}")
      
      # Back button - different logic for Firebase vs others
      if st.session_state.selected_method == 'firebase':
          if st.button("← Back to Configuration", key="back_to_config"):
              st.session_state.leftover_step = 'firebase_config'
              st.rerun()
      else:
          if st.button("← Back to Method Selection", key="back_to_method_from_input"):
              st.session_state.leftover_step = 'select_method'
              st.session_state.selected_method = None
              st.session_state.all_leftovers = []
              st.session_state.detailed_ingredient_info = []
              st.rerun()
      
      # Handle different input methods
      leftovers = []
      detailed_info = []
      
      if st.session_state.selected_method == 'csv':
          leftovers = leftover_input_csv()
          
      elif st.session_state.selected_method == 'manual':
          leftovers = leftover_input_manual()
          
      elif st.session_state.selected_method == 'firebase':
          # Pass the max_ingredients parameter
          leftovers, detailed_info = leftover_input_firebase_with_limit(st.session_state.max_ingredients)
      
      # Update session state
      st.session_state.all_leftovers = leftovers
      st.session_state.detailed_ingredient_info = detailed_info
      
      # Show ingredients if found and move to next step
      if leftovers:
          st.session_state.leftover_step = 'review_ingredients'
          st.rerun()

  # Step 4: Review Ingredients
  elif st.session_state.leftover_step == 'review_ingredients':
      step_number = '4' if st.session_state.selected_method == 'firebase' else '3'
      st.markdown(f"#### Step {step_number}: Review Your Ingredients")
      
      # Back button
      if st.button("← Back to Input", key="back_to_input"):
          st.session_state.leftover_step = 'input_ingredients'
          # Clear ingredients when going back
          st.session_state.all_leftovers = []
          st.session_state.detailed_ingredient_info = []
          st.rerun()
      
      all_leftovers = st.session_state.all_leftovers
      firebase_detailed_info = st.session_state.detailed_ingredient_info
      
      # Display ingredient summary
      col1, col2 = st.columns([2, 1])
      with col1:
          st.success(f"✅ **{len(all_leftovers)} ingredients found**")
      with col2:
          if firebase_detailed_info:
              urgent_count = len([item for item in firebase_detailed_info if item['days_until_expiry'] <= 3])
              if urgent_count > 0:
                  st.warning(f"⚠️ {urgent_count} expire soon")
      
      # Show ingredient details
      if firebase_detailed_info:
          st.markdown("**Ingredient Details:**")
          for item in firebase_detailed_info:
              days_left = item['days_until_expiry']
              if days_left <= 1:
                  st.error(f"🔴 {item['name']} - expires in {days_left} days")
              elif days_left <= 3:
                  st.warning(f"🟡 {item['name']} - expires in {days_left} days")
              else:
                  st.info(f"🟢 {item['name']} - expires in {days_left} days")
      else:
          st.markdown("**Your Ingredients:**")
          st.write(", ".join(all_leftovers))
      
      # Continue to recipe generation
      if st.button("Continue to Recipe Generation →", type="primary", use_container_width=True, key="continue_to_recipes"):
          st.session_state.leftover_step = 'generate_recipes'
          st.rerun()

  # Step 5: Generate Recipes
  elif st.session_state.leftover_step == 'generate_recipes':
      step_number = '5' if st.session_state.selected_method == 'firebase' else '4'
      st.markdown(f"#### Step {step_number}: Generate Creative Recipes")
      
      # Back button
      if st.button("← Back to Review", key="back_to_review"):
          st.session_state.leftover_step = 'review_ingredients'
          st.rerun()
      
      all_leftovers = st.session_state.all_leftovers
      firebase_detailed_info = st.session_state.detailed_ingredient_info
      
      # Quick ingredient summary
      st.info(f"Using {len(all_leftovers)} ingredients: {', '.join(all_leftovers[:5])}" + 
              (f" and {len(all_leftovers) - 5} more..." if len(all_leftovers) > 5 else ""))
      
      # Recipe generation controls
      col1, col2 = st.columns([2, 1])
      with col1:
          notes = st.text_input("Special Requirements (optional)", 
                              placeholder="e.g., vegetarian, quick meals, spicy",
                              key="recipe_notes")
      with col2:
          num_suggestions = st.selectbox("Number of Recipes", [1, 2, 3, 4, 5], index=2, key="num_recipes")
      
      if st.button("🆕 Generate Creative Recipes", type="primary", use_container_width=True, key="generate_recipes_btn"):
          try:
              with st.spinner("Creating new recipes from your leftovers..."):
                  recipes = suggest_recipes(
                      all_leftovers, 
                      num_suggestions, 
                      notes, 
                      priority_ingredients=firebase_detailed_info
                  )
                  st.session_state.recipes = recipes
                  st.session_state.recipe_generation_error = None
                  
                  # Award XP for recipe generation
                  if user_id:
                      award_recipe_generation_xp(user_id, len(recipes))
          except Exception as e:
              st.session_state.recipe_generation_error = str(e)
      
      # Display results
      if st.session_state.recipe_generation_error:
          st.error(f"❌ Error: {st.session_state.recipe_generation_error}")
          
      elif st.session_state.recipes:
          st.success("✨ **New Creative Recipe Suggestions**")
          for i, recipe in enumerate(st.session_state.recipes, 1):
              st.write(f"**{i}.** {recipe}")
          
          st.divider()
          
          # Action buttons
          col1, col2 = st.columns(2)
          with col1:
              if st.button("🔄 Generate More Recipes", use_container_width=True, key="more_recipes"):
                  st.session_state.recipes = []
                  st.rerun()
          with col2:
              if st.button("🆕 Start Over", use_container_width=True, key="start_over"):
                  # Reset everything
                  st.session_state.leftover_step = 'select_method'
                  st.session_state.selected_method = None
                  st.session_state.max_ingredients = 8
                  st.session_state.all_leftovers = []
                  st.session_state.detailed_ingredient_info = []
                  st.session_state.recipes = []
                  st.session_state.recipe_generation_error = None
                  st.rerun()

def leftover_input_firebase_with_limit(max_ingredients: int):
  """Firebase input with ingredient limit"""
  from ui.components import leftover_input_firebase
  
  # Store the max_ingredients in session state for the component to use
  st.session_state.firebase_max_ingredients = max_ingredients
  
  # Call the original function
  return leftover_input_firebase()

def render_cooking_quiz_tab(user_id: str):
  """Cooking quiz section"""
  st.markdown("### 🧠 Test Your Culinary Knowledge")
  
  if not user_id:
      st.warning("Please log in to take quizzes")
      return
  
  # Display daily challenge
  display_daily_challenge(user_id)
  
  # Sample ingredients for quiz context
  sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
  
  # Render the quiz
  render_cooking_quiz(sample_ingredients, user_id)

@auth_required
def gamification_hub():
  """Simplified gamification interface"""
  user = get_current_user()
  if user and user.get('user_id'):
      display_gamification_dashboard(user['user_id'])
  else:
      st.warning("Please log in to view stats")

@auth_required
def cooking_quiz():
  """Simplified quiz interface"""
  st.title("🧠 Cooking Quiz")

  user = get_current_user()
  if not user or not user.get('user_id'):
      st.warning("Please log in to take quizzes")
      return
      
  sample_ingredients = ["chicken", "rice", "tomatoes", "onions", "garlic", "olive oil"]
  display_daily_challenge(user['user_id'])
  render_cooking_quiz(sample_ingredients, user['user_id'])

@auth_required
def event_planning():
  """Event planning interface"""
  integrate_event_planner()

@auth_required
def ingredient_management():
  """Ingredient management interface"""
  render_ingredient_management()

def promotion_generator():
  """Simplified placeholder"""
  st.title("📣 Promotion Generator")
  st.info("Feature coming soon")

def chef_recipe_suggestions():
  """Simplified placeholder"""
  st.title("👨‍🍳 Chef Recipe Suggestions")
  st.info("Feature coming soon")

def visual_menu_search():
  """Simplified placeholder"""
  st.title("🔍 Visual Menu Search")
  st.info("Feature coming soon")

@auth_required
def dashboard():
  """Simplified dashboard"""
  render_dashboard()

def main():
  initialize_session_state()

  if 'show_quiz' not in st.session_state:
      st.session_state.show_quiz = False
  if 'show_general_quiz' not in st.session_state:
      st.session_state.show_general_quiz = False
  if 'show_achievements' not in st.session_state:
      st.session_state.show_achievements = False

  if 'selected_feature' not in st.session_state:
      st.session_state.selected_feature = "Dashboard"

  check_event_firebase_config()

  # Simplified sidebar
  with st.sidebar:
      st.title("🔐 Login")
      auth_status = render_auth_ui()

  if not st.session_state.is_authenticated:
      # Clean welcome screen
      st.title("🍽️ Smart Restaurant Management")
      st.markdown("""
      **AI-powered restaurant system with:**
      - Smart recipe generation from leftovers
      - Gamification with quizzes and achievements  
      - Event planning assistance
      - Ingredient inventory management
      - Progress tracking and leaderboards
      
      Please log in to access features.
      """)
      return

  # Simplified feature navigation
  with st.sidebar:
      st.divider()
      st.header("Features")

      features = [
          "Dashboard",
          "Leftover Management",
          "Gamification Hub", 
          "Cooking Quiz",
          "Event Planning ChatBot",
          "Ingredient Management",  # Added new feature
          "Promotion Generator", 
          "Chef Recipe Suggestions",
          "Visual Menu Search"
      ]

      available_features = ["Dashboard"] + [f for f in features[1:] if check_feature_access(f)]

      user = get_current_user()
      if user and user.get('user_id'):
          display_user_stats_sidebar(user['user_id'])

      selected_feature = st.selectbox(
          "Choose Feature",
          options=available_features,
          index=available_features.index(st.session_state.selected_feature) if st.session_state.selected_feature in available_features else 0
      )

      st.session_state.selected_feature = selected_feature

  # Feature routing
  if selected_feature == "Dashboard":
      dashboard()
  elif selected_feature == "Leftover Management":
      leftover_management()
  elif selected_feature == "Gamification Hub":
      gamification_hub()
  elif selected_feature == "Cooking Quiz":
      cooking_quiz()
  elif selected_feature == "Event Planning ChatBot":
      event_planning()
  elif selected_feature == "Ingredient Management":  # Added new route
      ingredient_management()
  elif selected_feature == "Promotion Generator":
      promotion_generator()
  elif selected_feature == "Chef Recipe Suggestions":
      chef_recipe_suggestions()
  elif selected_feature == "Visual Menu Search":
      visual_menu_search()

if __name__ == "__main__":
  main()
