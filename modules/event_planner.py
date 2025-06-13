"""
Event Planning Chatbot for Smart Restaurant Management App
Created by: v0

This module provides:
1. AI-powered event planning chatbot using Gemini API
2. Event dashboard for viewing and managing events
3. Integration with Firestore for recipe and ingredient data
4. Role-based access control for different user types
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import firebase_admin
from firebase_admin import firestore, credentials
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Initialize Firebase for event data
def init_event_firebase():
    """Initialize the Firebase Admin SDK for event data"""
    if not firebase_admin._apps or 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
        try:
            # Use environment variables with EVENT_ prefix
            cred = credentials.Certificate({
                "type": st.secrets["event_firebase_type"],
                "project_id": st.secrets["event_firebase_project_id"],
                "private_key_id": st.secrets["event_firebase_private_key_id"],
                "private_key": st.secrets["event_firebase_private_key"].replace("\\n", "\n"),
                "client_email": st.secrets["event_firebase_client_email"],
                "client_id": st.secrets["event_firebase_client_id"],
                "auth_uri": st.secrets["event_firebase_auth_uri"],
                "token_uri": st.secrets["event_firebase_token_uri"],
                "auth_provider_x509_cert_url": st.secrets["event_firebase_auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["event_firebase_client_x509_cert_url"],
            })
            firebase_admin.initialize_app(cred, name='event_app')
            logger.info("Event Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            # Fallback to display error in UI
            st.error(f"Failed to initialize Event Firebase. Please check your credentials.")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

# AI Model Configuration
def configure_ai_model():
    """Configure and return the Gemini AI model"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            api_key = st.secrets.get("GEMINI_API_KEY")
            
        if not api_key:
            st.error("GEMINI_API_KEY not found in environment variables or secrets!")
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        logger.error(f"Error configuring AI model: {str(e)}")
        st.error(f"Failed to configure AI model: {str(e)}")
        return None

# Firestore Data Functions
def get_recipe_items(dietary_restrictions: Optional[str] = None) -> List[Dict]:
    """
    Fetch recipe items from Firestore, optionally filtered by dietary restrictions

    Args:
        dietary_restrictions: Optional filter for dietary needs (e.g., "vegan", "gluten-free")
        
    Returns:
        List of recipe items as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            return []
            
        recipe_ref = db.collection('recipe_archive')
        
        # Apply dietary filter if provided
        if dietary_restrictions and dietary_restrictions.lower() != "none":
            query = recipe_ref.where('diet', 'array_contains', dietary_restrictions.lower())
            recipe_docs = query.get()
        else:
            recipe_docs = recipe_ref.get()
            
        recipe_items = []
        for doc in recipe_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            recipe_items.append(item)
            
        return recipe_items
    except Exception as e:
        logger.error(f"Error fetching recipe items: {str(e)}")
        return []

def get_available_ingredients() -> List[Dict]:
    """
    Fetch available ingredients from Firestore inventory

    Returns:
        List of ingredients as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            return []
            
        inventory_ref = db.collection('ingredients_inventory')
        inventory_docs = inventory_ref.get()
        
        ingredients = []
        for doc in inventory_docs:
            item = doc.to_dict()
            item['id'] = doc.id
            ingredients.append(item)
            
        return ingredients
    except Exception as e:
        logger.error(f"Error fetching ingredients: {str(e)}")
        return []

def save_event_to_firestore(event_data: Dict) -> bool:
    """
    Save event data to Firestore

    Args:
        event_data: Dictionary containing event details
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        db = get_event_db()
        if not db:
            return False
            
        # Generate a unique ID if not provided
        if 'id' not in event_data:
            event_data['id'] = str(uuid.uuid4())
            
        # Add timestamp
        event_data['created_at'] = datetime.now()
        
        # Save to Firestore
        events_ref = db.collection('events')
        events_ref.document(event_data['id']).set(event_data)
        
        logger.info(f"Event saved successfully with ID: {event_data['id']}")
        return True
    except Exception as e:
        logger.error(f"Error saving event: {str(e)}")
        return False

def get_all_events() -> List[Dict]:
    """
    Fetch all events from Firestore

    Returns:
        List of events as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            return []
            
        events_ref = db.collection('events')
        events_docs = events_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        
        events = []
        for doc in events_docs:
            event = doc.to_dict()
            # Convert Firestore timestamp to datetime for display
            if 'created_at' in event and isinstance(event['created_at'], datetime):
                event['created_at'] = event['created_at'].strftime("%Y-%m-%d %H:%M")
            events.append(event)
            
        return events
    except Exception as e:
        logger.error(f"Error fetching events: {str(e)}")
        return []

def get_customers() -> List[Dict]:
    """
    Fetch customer data from Firestore

    Returns:
        List of customers as dictionaries
    """
    try:
        # Use the main Firebase app for user data
        db = firestore.client()
        users_ref = db.collection('users')
        
        # Get users with role 'user' (customers)
        users_docs = users_ref.where('role', '==', 'user').get()
        
        customers = []
        for doc in users_docs:
            user = doc.to_dict()
            # Only include necessary fields
            customers.append({
                'user_id': user.get('user_id', ''),
                'username': user.get('username', ''),
                'email': user.get('email', '')
            })
            
        return customers
    except Exception as e:
        logger.error(f"Error fetching customers: {str(e)}")
        return []

def send_invites(event_id: str, customer_ids: List[str]) -> bool:
    """
    Send invites to selected customers (mock function)

    Args:
        event_id: ID of the event
        customer_ids: List of customer IDs to invite
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        db = get_event_db()
        if not db:
            return False
            
        # Get event details
        event_ref = db.collection('events').document(event_id)
        event_doc = event_ref.get()
        
        if not event_doc.exists:
            logger.error(f"Event {event_id} not found")
            return False
            
        event_data = event_doc.to_dict()
        
        # Create invites collection
        invites_ref = db.collection('invites')
        
        # Create an invite for each customer
        for customer_id in customer_ids:
            invite_id = f"{event_id}_{customer_id}"
            invite_data = {
                'event_id': event_id,
                'customer_id': customer_id,
                'event_name': event_data.get('theme', 'Event'),
                'sent_at': datetime.now(),
                'status': 'sent'
            }
            invites_ref.document(invite_id).set(invite_data)
            
        # Update event with invited customers
        event_ref.update({
            'invited_customers': firestore.ArrayUnion(customer_ids),
            'last_invite_sent': datetime.now()
        })
        
        logger.info(f"Invites sent to {len(customer_ids)} customers for event {event_id}")
        return True
    except Exception as e:
        logger.error(f"Error sending invites: {str(e)}")
        return False

# AI Event Planning Functions
def generate_event_plan(query: str) -> Dict:
    """
    Generate an event plan using AI based on user query

    Args:
        query: User's natural language query about event planning
        
    Returns:
        Dictionary containing generated event plan details
    """
    model = configure_ai_model()
    if not model:
        return {
            'error': 'AI model configuration failed',
            'success': False
        }

    # Get available recipe items and ingredients for context
    recipe_items = get_recipe_items()
    recipe_names = [item.get('name', '') for item in recipe_items]

    ingredients = get_available_ingredients()
    ingredient_names = [item.get('Ingredient', '') for item in ingredients]

    # Extract dietary restrictions from query
    dietary_keywords = ['vegan', 'vegetarian', 'gluten-free', 'dairy-free', 'nut-free']
    dietary_restrictions = []

    for keyword in dietary_keywords:
        if keyword in query.lower():
            dietary_restrictions.append(keyword)

    # Extract guest count from query
    import re
    guest_count = 20  # Default
    guest_matches = re.findall(r'(\d+)\s+(?:people|guests|persons)', query)
    if guest_matches:
        guest_count = int(guest_matches[0])

    # Prepare prompt for AI
    prompt = f'''
    You are an expert event planner for a restaurant. Plan an event based on this request:
    "{query}"

    Available recipes at our restaurant: {', '.join(recipe_names[:20])}
    Available ingredients: {', '.join(ingredient_names[:20])}

    Generate a complete event plan with the following sections:
    1. Theme: A creative name and description for the event theme
    2. Seating: A seating plan for {guest_count} guests (specify table arrangement)
    3. Decor: Decoration and ambiance suggestions
    4. Recipes: 5-7 recipe suggestions from our available recipes
    5. Invitation: A short invitation message template

    Format your response as a JSON object with these exact keys:
    {{
        "theme": {{
            "name": "Theme name",
            "description": "Theme description"
        }},
        "seating": {{
            "layout": "Layout description",
            "tables": [List of tables with guest counts]
        }},
        "decor": [List of decoration ideas],
        "recipe_suggestions": [List of recipe names],
        "invitation": "Invitation text"
    }}

    Make sure the JSON is valid and properly formatted.'''

    try:
        # Generate response from AI
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        else:
            # Try to find JSON without code blocks
            json_match = re.search(r'({.*})', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
        
        # Parse JSON response
        event_plan = json.loads(response_text)
        
        # Filter recipe suggestions based on dietary restrictions
        if dietary_restrictions:
            filtered_recipes = get_recipe_items(dietary_restrictions[0])
            filtered_names = [item.get('name', '') for item in filtered_recipes]
            
            # If we have filtered items, use them instead
            if filtered_names:
                event_plan['recipe_suggestions'] = filtered_names[:7]
        
        return {
            'plan': event_plan,
            'success': True
        }
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        return {
            'error': str(e),
            'success': False
        }

# Streamlit UI Components
def render_chatbot_ui():
    """Render the event planning chatbot UI"""
    st.markdown("### 🤖 Event Planning Assistant")

    # Initialize chat history
    if 'event_chat_history' not in st.session_state:
        st.session_state.event_chat_history = []
        
    # Initialize current plan
    if 'current_event_plan' not in st.session_state:
        st.session_state.current_event_plan = None

    # Display chat history
    for message in st.session_state.event_chat_history:
        if message['role'] == 'user':
            st.chat_message('user').write(message['content'])
        else:
            st.chat_message('assistant').write(message['content'])

    # Chat input
    user_query = st.chat_input("Describe the event you want to plan...", key="event_chat_input")

    if user_query:
        # Add user message to chat history
        st.session_state.event_chat_history.append({
            'role': 'user',
            'content': user_query
        })
        
        # Display user message
        st.chat_message('user').write(user_query)
        
        # Generate response
        with st.chat_message('assistant'):
            with st.spinner("Planning your event..."):
                response = generate_event_plan(user_query)
                
                if response['success']:
                    event_plan = response['plan']
                    st.session_state.current_event_plan = event_plan
                    
                    # Display response in a user-friendly format
                    st.markdown(f"### 🎉 {event_plan['theme']['name']}")
                    st.markdown(event_plan['theme']['description'])
                    
                    # Create tabs for different aspects of the plan
                    tabs = st.tabs(["💺 Seating", "🎭 Decor", "🍽️ Recipes", "✉️ Invitation"])
                    
                    with tabs[0]:
                        st.markdown("#### Seating Arrangement")
                        st.markdown(event_plan['seating']['layout'])
                        
                        # Display tables
                        st.markdown("##### Tables:")
                        for i, table in enumerate(event_plan['seating']['tables']):
                            st.markdown(f"- {table}")
                    
                    with tabs[1]:
                        st.markdown("#### Decoration Ideas")
                        for item in event_plan['decor']:
                            st.markdown(f"- {item}")
                    
                    with tabs[2]:
                        st.markdown("#### Recipe Suggestions")
                        for item in event_plan['recipe_suggestions']:
                            st.markdown(f"- {item}")
                    
                    with tabs[3]:
                        st.markdown("#### Invitation Template")
                        st.info(event_plan['invitation'])
                    
                    # Save event button
                    if st.button("💾 Save Event Plan", type="primary"):
                        # Prepare event data
                        event_data = {
                            'id': f"event-{uuid.uuid4()}",
                            'description': event_plan['theme']['description'],
                            'decor': event_plan.get('decor', []),
                            'invitation': event_plan.get('invitation', ''),
                            'recipes': event_plan.get('recipe_suggestions', []),
                            'seating': {
                                'layout': event_plan.get('seating', {}).get('layout', ''),
                                'tables': event_plan.get('seating', {}).get('tables', [])
                            },
                            'created_by': st.session_state.user['user_id'] if 'user' in st.session_state else 'unknown'
                        }

                        
                        # Save to Firestore
                        if save_event_to_firestore(event_data):
                            st.success("Event plan saved successfully!")
                        else:
                            st.error("Failed to save event plan. Please try again.")
                    
                    # Add assistant message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I've created an event plan for '{event_plan['theme']['name']}'. You can view the details above."
                    })
                else:
                    st.error(f"Failed to generate event plan: {response.get('error', 'Unknown error')}")
                    
                    # Add error message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I'm sorry, I couldn't generate an event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_event_dashboard():
    """Render the event dashboard UI"""
    st.markdown("### 📊 Event Dashboard")

    # Fetch events
    events = get_all_events()

    if not events:
        st.info("No events found. Use the chatbot to create your first event!")
        return

    # Display events in an expandable format
    for event in events:
        with st.expander(f"🎭 {event.get('theme', 'Event')} - {event.get('created_at', 'Unknown date')}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Description:** {event.get('description', 'No description')}")
                
                st.markdown("##### 💺 Seating")
                seating = event.get('seating', {})
                st.markdown(seating.get('layout', 'No seating information'))
                
                st.markdown("##### 🎭 Decor")
                for item in event.get('decor', ['No decor information']):
                    st.markdown(f"- {item}")
                
                st.markdown("##### 🍽️ Recipes")
                for item in event.get('recipes', ['No recipe information']):
                    st.markdown(f"- {item}")
            
            with col2:
                st.markdown("##### ✉️ Invitation")
                st.info(event.get('invitation', 'No invitation template'))
                
                # Invite customers section
                st.markdown("##### 👥 Invite Customers")
                
                # Check if invites were already sent
                if event.get('invited_customers'):
                    st.success(f"Invites sent to {len(event.get('invited_customers'))} customers")
                else:
                    # Get customers
                    customers = get_customers()
                    
                    if not customers:
                        st.warning("No customers found in the system")
                    else:
                        # Multi-select for customers
                        selected_customers = st.multiselect(
                            "Select customers to invite:",
                            options=[c['user_id'] for c in customers],
                            format_func=lambda x: next((c['username'] for c in customers if c['user_id'] == x), x)
                        )
                        
                        if selected_customers:
                            if st.button("Send Invites", key=f"send_invite_{event.get('id', '')}"):
                                if send_invites(event.get('id', ''), selected_customers):
                                    st.success(f"Invites sent to {len(selected_customers)} customers!")
                                    st.rerun()
                                else:
                                    st.error("Failed to send invites. Please try again.")

def render_user_invites():
    """Render the user's event invites UI"""
    st.markdown("### 📬 My Event Invites")

    # Get current user
    user = st.session_state.get('user')
    if not user:
        st.warning("Please log in to view your invites")
        return

    user_id = user.get('user_id')

    try:
        # Fetch user's invites
        db = get_event_db()
        if not db:
            st.error("Failed to connect to database")
            return
            
        invites_ref = db.collection('invites')
        invites_docs = invites_ref.where('customer_id', '==', user_id).get()
        
        invites = []
        for doc in invites_docs:
            invite = doc.to_dict()
            # Get event details
            event_ref = db.collection('events').document(invite.get('event_id', ''))
            event_doc = event_ref.get()
            
            if event_doc.exists:
                event_data = event_doc.to_dict()
                invite['event'] = event_data
                
            invites.append(invite)
        
        if not invites:
            st.info("You don't have any event invites yet.")
            return
        
        # Display invites
        for invite in invites:
            event = invite.get('event', {})
            
            with st.expander(f"🎉 {event.get('theme', 'Event')}"):
                st.markdown(f"**Description:** {event.get('description', 'No description')}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### 🍽️ Recipes")
                    for item in event.get('recipes', ['No recipe information']):
                        st.markdown(f"- {item}")
                
                with col2:
                    st.markdown("##### ✉️ Invitation")
                    st.info(event.get('invitation', 'No invitation template'))
                
                # RSVP buttons
                st.markdown("##### RSVP")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Accept", key=f"accept_{invite.get('event_id', '')}"):
                        # Update invite status
                        invite_id = f"{invite.get('event_id', '')}_{user_id}"
                        db.collection('invites').document(invite_id).update({
                            'status': 'accepted',
                            'responded_at': datetime.now()
                        })
                        st.success("You've accepted the invitation!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Decline", key=f"decline_{invite.get('event_id', '')}"):
                        # Update invite status
                        invite_id = f"{invite.get('event_id', '')}_{user_id}"
                        db.collection('invites').document(invite_id).update({
                            'status': 'declined',
                            'responded_at': datetime.now()
                        })
                        st.success("You've declined the invitation.")
                        st.rerun()

    except Exception as e:
        logger.error(f"Error fetching invites: {str(e)}")
        st.error(f"Failed to load invites: {str(e)}")

# Main Event Planner Function
def event_planner():
    """Main function to render the event planner UI based on user role"""
    st.title("🎉 Event Planning System")

    # Check if user is logged in
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("Please log in to access the Event Planning System")
        return

    # Get user role
    user_role = st.session_state.user.get('role', 'user')

    # Different views based on role
    if user_role in ['admin', 'staff', 'chef']:
        # Staff view with tabs for chatbot and dashboard
        tab1, tab2 = st.tabs(["🤖 Event Planner", "📊 Event Dashboard"])
        
        with tab1:
            render_chatbot_ui()
            
        with tab2:
            render_event_dashboard()
    else:
        # Customer view - only shows their invites
        render_user_invites()

# For testing the module independently
if __name__ == "__main__":
    st.set_page_config(page_title="Event Planning System", layout="wide")

    # Mock session state for testing
    if 'user' not in st.session_state:
        st.session_state.user = {
            'user_id': 'test_user',
            'username': 'Test User',
            'role': 'admin'
        }

    event_planner()
