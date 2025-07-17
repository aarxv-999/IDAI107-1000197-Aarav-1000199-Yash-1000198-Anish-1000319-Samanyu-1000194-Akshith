"""
Comprehensive Ingredient Management System for Smart Restaurant Menu Management App.
Handles CRUD operations for ingredient inventory with AI-powered suggestions.
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

logger = logging.getLogger(__name__)

def get_event_firestore_db():
    """Get the Firestore client for ingredient management"""
    try:
        if 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            logger.info("Using existing event_app Firestore client")
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
        else:
            from modules.event_planner import init_event_firebase
            if init_event_firebase():
                logger.info("Initialized new event_app Firestore client")
                return firestore.client(app=firebase_admin.get_app(name='event_app'))
            logger.error("init_event_firebase returned False")
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
        if not quantity_str:
            return False, 0
        quantity = float(quantity_str)
        return quantity > 0, quantity
    except ValueError:
        return False, 0

def get_all_ingredients(search_term: str = "", expiry_filter: str = "all", type_filter: str = "all") -> List[Dict]:
    """Get all ingredients with optional filtering"""
    try:
        db = get_event_firestore_db()
        if not db:
            logger.error("No Firestore client available for get_all_ingredients")
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
            
            # Handle missing Unit field
            data['Unit'] = data.get('Unit', 'N/A')
            
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

def add_ingredient(ingredient_name: str, quantity: float, ingredient_type: str, 
                  expiry_date: str, unit: str, alternatives: str = "") -> Tuple[bool, str, Optional[str]]:
    """Add a new ingredient to inventory with a unique document ID"""
    try:
        db = get_event_firestore_db()
        if not db:
            logger.error("Database connection failed in add_ingredient")
            return False, "Database connection failed", None
        
        # Log Firebase project ID to confirm correct instance
        project_id = firebase_admin.get_app(name='event_app').project_id
        logger.info(f"Using Firebase project: {project_id}")
        
        # Validate inputs
        if not all([ingredient_name, quantity > 0, ingredient_type, expiry_date, unit]):
            return False, "All fields are required", None
        
        if not validate_date_format(expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy", None
        
        if not is_future_date(expiry_date):
            return False, "Expiry date must be in the future", None
        
        ingredient_data = {
            'Alternatives': alternatives.strip(),
            'Expiry Date': expiry_date,
            'Ingredient': ingredient_name.strip(),
            'Quantity': str(quantity),
            'Type': ingredient_type.strip(),
            'Unit': unit.strip(),
            'Created At': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        inventory_ref = db.collection('ingredient_inventory')
        logger.info(f"Adding ingredient {ingredient_name} to collection: ingredient_inventory")
        
        # Generate a unique document ID using uuid4
        doc_id = str(uuid.uuid4())
        doc_ref = inventory_ref.document(doc_id)
        
        # Check if document already exists (extra safety)
        if doc_ref.get().exists:
            logger.warning(f"Document ID {doc_id} already exists, generating new ID")
            doc_id = str(uuid.uuid4())
            doc_ref = inventory_ref.document(doc_id)
        
        # Write the new document
        doc_ref.set(ingredient_data)
        
        logger.info(f"Successfully added ingredient: {ingredient_name} with document ID: {doc_id}")
        return True, f"Successfully added {ingredient_name} with document ID: {doc_id}", doc_id
        
    except Exception as e:
        if "409" in str(e) or "Document already exists" in str(e):
            logger.error(f"Firestore 409 error adding ingredient {ingredient_name} with doc_id {doc_id}: {str(e)}", exc_info=True)
            return False, f"Error: Document creation failed due to conflict (ID: {doc_id}). Please try again or contact support.", None
        logger.error(f"Error adding ingredient {ingredient_name}: {str(e)}", exc_info=True)
        return False, f"Error adding ingredient: {str(e)}", None

def update_ingredient(doc_id: str, ingredient_name: str, quantity: float, ingredient_type: str,
                     expiry_date: str, unit: str, alternatives: str = "") -> Tuple[bool, str]:
    """Update an existing ingredient"""
    try:
        db = get_event_firestore_db()
        if not db:
            return False, "Database connection failed"
        
        # Validate inputs
        if not all([ingredient_name, quantity > 0, ingredient_type, expiry_date, unit]):
            return False, "All fields are required"
        
        if not validate_date_format(expiry_date):
            return False, "Invalid date format. Use dd/mm/yyyy"
        
        update_data = {
            'Ingredient': ingredient_name.strip(),
            'Quantity': str(quantity),
            'Type': ingredient_type.strip(),
            'Expiry Date': expiry_date,
            'Unit': unit.strip(),
            'Alternatives': alternatives.strip(),
            'Last Modified': datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        
        inventory_ref = db.collection('ingredient_inventory').document(doc_id)
        inventory_ref.update(update_data)
        
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
        
        alternatives = [alt.strip() for alt in response_text.split(',')]
        alternatives = [alt for alt in alternatives if alt and len(alt) > 0]
        
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
    """Main ingredient management interface"""
    st.title("🥬 Ingredient Management")
    
    db = get_event_firestore_db()
    if not db:
        st.error("❌ Cannot connect to ingredient database. Please check your Firebase configuration.")
        return
    
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
    
    ingredients = get_all_ingredients(search_term, expiry_filter, type_filter)
    
    if not ingredients:
        st.info("No ingredients found matching your criteria.")
        return
    
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
    
    for ingredient in ingredients:
        expiry_status = ingredient['expiry_status']
        days_until_expiry = ingredient['days_until_expiry']
        
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
            
            with col2:
                quantity = ingredient.get('Quantity', 'N/A')
                unit = ingredient.get('Unit', 'N/A')
                st.write(f"**Quantity:** {quantity} {unit}")
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
                    st.session_state.selected_tab = 2
                    st.rerun()
        
        st.divider()

def render_add_ingredient():
    """Render the add ingredient interface"""
    st.markdown("### ➕ Add New Ingredient")
    
    if 'add_form_data' not in st.session_state:
        st.session_state.add_form_data = {
            'ingredient_name': '',
            'quantity': '',
            'ingredient_type': '',
            'expiry_date': (date.today() + timedelta(days=7)).strftime("%d/%m/%Y"),
            'unit': 'KG',
            'alternatives': ''
        }
    
    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            ingredient_name = st.text_input(
                "🥬 Ingredient Name*",
                value=st.session_state.add_form_data['ingredient_name'],
                placeholder="e.g., Tomatoes",
                key="add_ingredient_name"
            )
            
            quantity_str = st.text_input(
                "📊 Quantity*",
                value=st.session_state.add_form_data['quantity'],
                placeholder="e.g., 5.5",
                key="add_quantity"
            )
            
            unit = st.selectbox(
                "📏 Unit*",
                options=["KG", "LITRE", "GRAMS", "ML", "UNITS"],
                index=["KG", "LITRE", "GRAMS", "ML", "UNITS"].index(st.session_state.add_form_data['unit']),
                key="add_unit"
            )
            
        with col2:
            ingredient_types = get_ingredient_types() or ["Vegetable"]
            ingredient_type = st.selectbox(
                "🏷️ Type*",
                options=ingredient_types,
                index=ingredient_types.index(st.session_state.add_form_data['ingredient_type']) if st.session_state.add_form_data['ingredient_type'] in ingredient_types else 0,
                key="add_ingredient_type_select"
            )
            new_type = st.text_input(
                "Or enter new type:",
                value='',
                placeholder="e.g., Vegetable",
                key="add_ingredient_type_input"
            )
            ingredient_type = new_type if new_type else ingredient_type
            
            try:
                default_expiry = datetime.strptime(st.session_state.add_form_data['expiry_date'], "%d/%m/%Y").date()
            except:
                default_expiry = date.today() + timedelta(days=7)
                
            expiry_date_input = st.date_input(
                "📅 Expiry Date*",
                min_value=date.today() + timedelta(days=1),
                value=default_expiry,
                key="add_expiry_date"
            )
            expiry_date = expiry_date_input.strftime("%d/%m/%Y")
            
            col2a, col2b = st.columns([3, 1])
            with col2a:
                alternatives = st.text_input(
                    "🔄 Alternatives",
                    value=st.session_state.add_form_data['alternatives'],
                    placeholder="Optional: e.g., Bell peppers, Zucchini",
                    key="add_alternatives"
                )
            with col2b:
                st.write("")
                ai_suggest_button = st.form_submit_button("🤖 AI Suggest", use_container_width=True)
        
        if 'suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.suggested_alternatives}")
        
        if ai_suggest_button:
            if not ingredient_name:
                st.error("❌ Please enter an ingredient name before requesting AI suggestions")
            else:
                st.session_state.add_form_data = {
                    'ingredient_name': ingredient_name,
                    'quantity': quantity_str,
                    'ingredient_type': ingredient_type,
                    'expiry_date': expiry_date,
                    'unit': unit,
                    'alternatives': alternatives
                }
                with st.spinner("Getting AI suggestions..."):
                    ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                    st.session_state.suggested_alternatives = ", ".join(ai_alternatives)
                    st.rerun()
        
        submitted = st.form_submit_button("➕ Add Ingredient", type="primary", use_container_width=True)
        
        if submitted:
            is_valid_qty, quantity = validate_quantity(quantity_str)
            errors = []
            if not ingredient_name.strip():
                errors.append("Ingredient name is required")
            if not is_valid_qty:
                errors.append("Quantity must be a positive number")
            if not ingredient_type.strip():
                errors.append("Ingredient type is required")
            if not unit:
                errors.append("Unit is required")
            
            if errors:
                st.error("❌ " + "; ".join(errors))
            else:
                success, message, doc_id = add_ingredient(ingredient_name, quantity, 
                                                       ingredient_type, expiry_date, unit, alternatives)
                if success:
                    st.success(f"✅ {message}")
                    if 'suggested_alternatives' in st.session_state:
                        del st.session_state.suggested_alternatives
                    st.session_state.add_form_data = {
                        'ingredient_name': '',
                        'quantity': '',
                        'ingredient_type': '',
                        'expiry_date': (date.today() + timedelta(days=7)).strftime("%d/%m/%Y"),
                        'unit': 'KG',
                        'alternatives': ''
                    }
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def render_edit_ingredient():
    """Render the edit ingredient interface"""
    st.markdown("### ✏️ Edit Ingredient")
    
    edit_id = st.session_state.get('edit_ingredient_id', '')
    
    if not edit_id:
        st.info("Select an ingredient from the 'View Ingredients' tab to edit.")
        return
    
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
    
    if 'edit_form_data' not in st.session_state:
        st.session_state.edit_form_data = {
            'ingredient_name': current_ingredient.get('Ingredient', ''),
            'quantity': current_ingredient.get('Quantity', ''),
            'ingredient_type': current_ingredient.get('Type', 'Vegetable'),
            'expiry_date': current_ingredient.get('Expiry Date', (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")),
            'unit': current_ingredient.get('Unit', 'KG'),
            'alternatives': current_ingredient.get('Alternatives', '')
        }
    
    st.info(f"Editing: **{current_ingredient.get('Ingredient', 'Unknown')}**")
    
    with st.form("edit_ingredient_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            ingredient_name = st.text_input(
                "🥬 Ingredient Name*",
                value=st.session_state.edit_form_data['ingredient_name'],
                key="edit_ingredient_name"
            )
            
            quantity_str = st.text_input(
                "📊 Quantity*",
                value=st.session_state.edit_form_data['quantity'],
                key="edit_quantity"
            )
            
            unit = st.selectbox(
                "📏 Unit*",
                options=["KG", "LITRE", "GRAMS", "ML", "UNITS"],
                index=["KG", "LITRE", "GRAMS", "ML", "UNITS"].index(st.session_state.edit_form_data['unit']) if st.session_state.edit_form_data['unit'] in ["KG", "LITRE", "GRAMS", "ML", "UNITS"] else 0,
                key="edit_unit"
            )
            
        with col2:
            ingredient_types = get_ingredient_types() or ["Vegetable"]
            current_type = st.session_state.edit_form_data['ingredient_type']
            
            ingredient_type = st.selectbox(
                "🏷️ Type*",
                options=ingredient_types,
                index=ingredient_types.index(current_type) if current_type in ingredient_types else 0,
                key="edit_ingredient_type_select"
            )
            new_type = st.text_input(
                "Or enter new type:",
                value='',
                placeholder="e.g., Vegetable",
                key="edit_ingredient_type_input"
            )
            ingredient_type = new_type if new_type else ingredient_type
            
            try:
                current_expiry_date = datetime.strptime(st.session_state.edit_form_data['expiry_date'], "%d/%m/%Y").date()
            except:
                current_expiry_date = date.today() + timedelta(days=7)
            
            min_date = date.today() - timedelta(days=365)
            max_date = date.today() + timedelta(days=365*10)
            
            if current_expiry_date < min_date:
                current_expiry_date = min_date
            elif current_expiry_date > max_date:
                current_expiry_date = max_date
            
            expiry_date_input = st.date_input(
                "📅 Expiry Date*",
                value=current_expiry_date,
                min_value=min_date,
                max_value=max_date,
                key="edit_expiry_date"
            )
            expiry_date = expiry_date_input.strftime("%d/%m/%Y")
        
        col2a, col2b = st.columns([3, 1])
        with col2a:
            alternatives = st.text_input(
                "🔄 Alternatives",
                value=st.session_state.edit_form_data['alternatives'],
                placeholder="Optional: e.g., Bell peppers, Zucchini",
                key="edit_alternatives"
            )
        with col2b:
            st.write("")
            ai_suggest_edit_button = st.form_submit_button("🤖 AI Suggest")
        
        if 'edit_suggested_alternatives' in st.session_state:
            st.info(f"🤖 AI Suggestions: {st.session_state.edit_suggested_alternatives}")
        
        if ai_suggest_edit_button:
            if not ingredient_name:
                st.error("❌ Please enter an ingredient name before requesting AI suggestions")
            else:
                st.session_state.edit_form_data = {
                    'ingredient_name': ingredient_name,
                    'quantity': quantity_str,
                    'ingredient_type': ingredient_type,
                    'expiry_date': expiry_date,
                    'unit': unit,
                    'alternatives': alternatives
                }
                with st.spinner("Getting AI suggestions..."):
                    ai_alternatives = suggest_alternatives_with_ai(ingredient_name)
                    st.session_state.edit_suggested_alternatives = ", ".join(ai_alternatives)
                    st.rerun()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            update_submitted = st.form_submit_button("💾 Update Ingredient", type="primary", use_container_width=True)
        
        with col2:
            delete_submitted = st.form_submit_button("🗑️ Delete Ingredient", use_container_width=True)
        
        with col3:
            back_submitted = st.form_submit_button("← Back to View", use_container_width=True)
        
        if update_submitted:
            is_valid_qty, quantity = validate_quantity(quantity_str)
            errors = []
            if not ingredient_name.strip():
                errors.append("Ingredient name is required")
            if not is_valid_qty:
                errors.append("Quantity must be a positive number")
            if not ingredient_type.strip():
                errors.append("Ingredient type is required")
            if not unit:
                errors.append("Unit is required")
            
            if errors:
                st.error("❌ " + "; ".join(errors))
            else:
                success, message = update_ingredient(edit_id, ingredient_name, quantity, 
                                                   ingredient_type, expiry_date, unit, alternatives)
                if success:
                    st.success(f"✅ {message}")
                    del st.session_state.edit_ingredient_id
                    if 'edit_suggested_alternatives' in st.session_state:
                        del st.session_state.edit_suggested_alternatives
                    if 'edit_form_data' in st.session_state:
                        del st.session_state.edit_form_data
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
            if 'edit_form_data' in st.session_state:
                del st.session_state.edit_form_data
            st.rerun()
    
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
                    if 'edit_form_data' in st.session_state:
                        del st.session_state.edit_form_data
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
    
    select_all = st.checkbox("Select All Ingredients")
    
    selected_ingredients = []
    
    for ingredient in ingredients:
        col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
        
        with col1:
            is_selected = st.checkbox("Select", key=f"bulk_select_{ingredient['doc_id']}", value=select_all, label_visibility="hidden")
            if is_selected:
                selected_ingredients.append(ingredient)
        
        with col2:
            st.write(f"**{ingredient.get('Ingredient', 'Unknown')}**")
        
        with col3:
            quantity = ingredient.get('Quantity', 'N/A')
            unit = ingredient.get('Unit', 'N/A')
            st.write(f"Qty: {quantity} {unit}")
        
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