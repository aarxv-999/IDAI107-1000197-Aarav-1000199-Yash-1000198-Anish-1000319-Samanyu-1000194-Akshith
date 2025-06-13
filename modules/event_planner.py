import datetime
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
import time
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Initialize Firebase for event data
def init_event_firebase():
    """Initialize the Firebase Admin SDK for event data"""
    if not firebase_admin._apps or 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
        try:
            # Use environment variables with EVENT_ prefix or Streamlit secrets
            cred = credentials.Certificate({
                "type": os.getenv("EVENT_FIREBASE_TYPE", st.secrets.get("event_firebase_type")),
                "project_id": os.getenv("EVENT_FIREBASE_PROJECT_ID", st.secrets.get("event_firebase_project_id")),
                "private_key_id": os.getenv("EVENT_FIREBASE_PRIVATE_KEY_ID", st.secrets.get("event_firebase_private_key_id")),
                "private_key": os.getenv("EVENT_FIREBASE_PRIVATE_KEY", st.secrets.get("event_firebase_private_key", "")).replace("\\n", "\n"),
                "client_email": os.getenv("EVENT_FIREBASE_CLIENT_EMAIL", st.secrets.get("event_firebase_client_email")),
                "client_id": os.getenv("EVENT_FIREBASE_CLIENT_ID", st.secrets.get("event_firebase_client_id")),
                "auth_uri": os.getenv("EVENT_FIREBASE_AUTH_URI", st.secrets.get("event_firebase_auth_uri")),
                "token_uri": os.getenv("EVENT_FIREBASE_TOKEN_URI", st.secrets.get("event_firebase_token_uri")),
                "auth_provider_x509_cert_url": os.getenv("EVENT_FIREBASE_AUTH_PROVIDER_X509_CERT_URL", st.secrets.get("event_firebase_auth_provider_x509_cert_url")),
                "client_x509_cert_url": os.getenv("EVENT_FIREBASE_CLIENT_X509_CERT_URL", st.secrets.get("event_firebase_client_x509_cert_url")),
            })
            firebase_admin.initialize_app(cred, name='event_app')
            logger.info("Event Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            logger.error(traceback.format_exc())
            st.error(f"Failed to initialize Event Firebase. Please check your credentials: {str(e)}")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

def test_firestore_connection():
    """
    Test function to verify Firestore connectivity and write permissions.
    """
    try:
        # Get Firestore client
        db = get_event_db()
        if not db:
            return False, "Failed to get database connection"
        
        # Create a test document
        test_id = f"test_{uuid.uuid4()}"
        test_data = {
            'id': test_id,
            'test': True,
            'timestamp': datetime.utcnow(),
            'message': 'This is a test document'
        }
        
        # Try to write to Firestore
        db.collection('test_collection').document(test_id).set(test_data)
        
        # Verify the write
        test_doc = db.collection('test_collection').document(test_id).get()
        
        if test_doc.exists:
            # Clean up
            db.collection('test_collection').document(test_id).delete()
            return True, "Firestore connection and write permissions verified"
        else:
            return False, "Failed to verify document creation"
            
    except Exception as e:
        return False, f"Error testing Firestore: {str(e)}\n{traceback.format_exc()}"

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

def save_event_to_firestore(event_data: Dict) -> Tuple[bool, str]:
    """
    Save event data to Firestore with enhanced error handling and debugging.
    
    Args:
        event_data: Dictionary containing event details
        
    Returns:
        Tuple of (success_boolean, event_id_or_error_message)
    """
    try:
        # Get Firestore client
        db = get_event_db()
        if not db:
            logger.error("Failed to get database connection")
            return False, "Database connection failed"
            
        # Generate a unique ID if not provided
        event_id = event_data.get('id', str(uuid.uuid4()))
        
        # Log the event ID
        logger.info(f"Generated event ID: {event_id}")
        
        # Format the data for Firestore
        firestore_data = {
            'id': event_id,
            'theme': event_data.get('theme', 'Untitled Event'),
            'description': event_data.get('description', ''),
            'decor': event_data.get('decor', []),
            'invitation': event_data.get('invitation', ''),
            'created_by': event_data.get('created_by', 'unknown'),
            'created_at': datetime.utcnow(),
            'seating': {
                'layout': event_data.get('seating', {}).get('layout', ''),
                'tables': event_data.get('seating', {}).get('tables', [])
            },
            'menu': event_data.get('recipes', [])
        }
        
        # Log the data being saved
        logger.info(f"Attempting to save event with ID: {event_id}")
        logger.info(f"Event data: {str(firestore_data)}")
        
        # DIRECT APPROACH: Use the collection reference directly
        events_collection = db.collection('events')
        
        # Set the document with the event ID
        events_collection.document(event_id).set(firestore_data)
        
        # Verify the save was successful
        logger.info(f"Checking if document {event_id} was saved...")
        saved_doc = events_collection.document(event_id).get()
        
        if saved_doc.exists:
            logger.info(f"✅ Event saved successfully with ID: {event_id}")
            return True, event_id
        else:
            logger.error(f"❌ Document {event_id} not found after save operation")
            return False, "Event was not saved - document does not exist after save"
            
    except Exception as e:
        error_msg = f"Error saving event: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False, error_msg

def get_all_events() -> List[Dict]:
    """
    Fetch all events from Firestore

    Returns:
        List of events as dictionaries
    """
    try:
        db = get_event_db()
        if not db:
            logger.error("Failed to get database connection")
            return []
            
        events_ref = db.collection('events')
        events_docs = events_ref.get()  # Get all events
        
        events = []
        for doc in events_docs:
            event = doc.to_dict()
            event['doc_id'] = doc.id
            # Handle Firestore timestamp for created_at
            if 'created_at' in event and isinstance(event['created_at'], datetime):
                event['created_at'] = event['created_at'].strftime('%d %B %Y at %H:%M:%S UTC')
            elif 'created_at' not in event:
                event['created_at'] = "Unknown date"
            events.append(event)
        
        # Sort by created_at (newest first)
        events.sort(key=lambda x: datetime.strptime(x.get('created_at', '01 January 1970 at 00:00:00 UTC').split(' at ')[0], '%d %B %Y'), reverse=True)
        logger.info(f"Retrieved {len(events)} events from Firestore")
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
        # Try to use the main Firebase app for user data, fallback to event app
        try:
            db = firestore.client()
        except:
            db = get_event_db()
            
        if not db:
            return []
            
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
    Send invites to selected customers

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
                'sent_at': firestore.SERVER_TIMESTAMP,
                'status': 'sent'
            }
            invites_ref.document(invite_id).set(invite_data)
            
        # Update event with invited customers
        event_ref.update({
            'invited_customers': firestore.ArrayUnion(customer_ids),
            'last_invite_sent': firestore.SERVER_TIMESTAMP
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
        json_match = re.search(r'\`\`\`json\s*(.*?)\s*\`\`\`', response_text, re.DOTALL)
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
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("💾 Save Event Plan", type="primary", key="save_event_btn_chatbot"):
                            with st.spinner("Saving event to Firestore..."):
                                try:
                                    # Generate a unique ID for this event
                                    new_event_id = str(uuid.uuid4())
                                    
                                    # Prepare the event data
                                    event_data = {
                                        'id': new_event_id,
                                        'theme': event_plan['theme']['name'],
                                        'description': event_plan['theme']['description'],
                                        'decor': event_plan['decor'],
                                        'recipes': event_plan['recipe_suggestions'],
                                        'invitation': event_plan['invitation'],
                                        'seating': event_plan['seating'],
                                        'created_by': st.session_state.user['user_id'] if 'user' in st.session_state else 'unknown'
                                    }
                                    
                                    # Log the data we're about to save
                                    st.write("Saving event data:", event_data)
                                    logger.info(f"Attempting to save event with ID {new_event_id}")
                                    
                                    # Call the save function
                                    success, result = save_event_to_firestore(event_data)
                                    
                                    if success:
                                        st.success(f"✅ Event plan saved successfully! Event ID: {result}")
                                        st.balloons()
                                        
                                        # Clear the current plan but avoid immediate rerun
                                        st.session_state.current_event_plan = None
                                        time.sleep(1)  # Small delay to ensure save
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to save event plan: {result}")
                                        st.error("Please try again or contact support.")
                                        
                                        # Add debug information
                                        with st.expander("Debug Information"):
                                            st.code(f"Error: {result}")
                                            st.write("Event Data:", event_data)
                                            
                                except Exception as e:
                                    st.error(f"❌ An error occurred: {str(e)}")
                                    with st.expander("Error Details"):
                                        st.code(traceback.format_exc())
                    
                    with col2:
                        if st.button("🔄 Generate New Plan", key="new_plan_btn_chatbot"):
                            st.session_state.current_event_plan = None
                            st.rerun()
                    
                    # Add assistant message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I've created an event plan for '{event_plan['theme']['name']}'. You can view the details above and save it when ready."
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
    
    # Add diagnostic section
    with st.expander("🔧 Diagnostics"):
        if st.button("Test Firestore Connection", key="test_connection_dashboard"):
            with st.spinner("Testing Firestore connection..."):
                success, message = test_firestore_connection()
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
                    
        # Add a direct save test
        if st.button("Test Direct Save", key="test_direct_save_dashboard"):
            with st.spinner("Testing direct save to Firestore..."):
                try:
                    test_id = f"manual_test_{uuid.uuid4()}"
                    test_data = {
                        'id': test_id,
                        'theme': 'Test Event',
                        'description': 'This is a test event',
                        'created_at': datetime.utcnow(),
                        'created_by': 'admin_test'
                    }
                    
                    db = get_event_db()
                    if db:
                        # Direct save to Firestore
                        db.collection('events').document(test_id).set(test_data)
                        st.success(f"✅ Test event saved with ID: {test_id}")
                    else:
                        st.error("❌ Failed to get database connection")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Dashboard", key="refresh_dashboard_btn"):
            st.rerun()

    # Fetch events
    with st.spinner("Loading events..."):
        events = get_all_events()

    if not events:
        st.info("📝 No events found. Use the Event Planner tab to create your first event!")
        return
    
    st.success(f"📋 Found {len(events)} events")

    # Display events in an expandable format
    for i, event in enumerate(events):
        event_title = f"🎭 {event.get('theme', 'Untitled Event')}"
        event_date = event.get('created_at', 'Unknown date')
        
        with st.expander(f"{event_title} - Created: {event_date}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Event ID:** `{event.get('id', 'N/A')}`")
                st.markdown(f"**Description:** {event.get('description', 'No description')}")
                st.markdown(f"**Created by:** {event.get('created_by', 'Unknown')}")
                
                st.markdown("##### 💺 Seating")
                seating = event.get('seating', {})
                if isinstance(seating, dict):
                    st.markdown(seating.get('layout', 'No seating information'))
                    
                    if 'tables' in seating and seating['tables']:
                        st.markdown("**Tables:**")
                        for table in seating['tables']:
                            st.markdown(f"- {table}")
                else:
                    st.markdown("No seating information")
                
                st.markdown("##### 🎭 Decor")
                decor_items = event.get('decor', [])
                if decor_items:
                    for item in decor_items:
                        st.markdown(f"- {item}")
                else:
                    st.markdown("No decor information")
                
                st.markdown("##### 🍽️ Menu")
                # Use 'menu' instead of 'recipes' to match Firestore structure
                menu_items = event.get('menu', [])
                if menu_items:
                    for item in menu_items:
                        st.markdown(f"- {item}")
                else:
                    st.markdown("No menu information")
            
            with col2:
                st.markdown("##### ✉️ Invitation")
                invitation_text = event.get('invitation', 'No invitation template')
                st.info(invitation_text)
                
                # Invite customers section
                st.markdown("##### 👥 Invite Customers")
                
                # Check if invites were already sent
                invited_customers = event.get('invited_customers', [])
                if invited_customers:
                    st.success(f"✅ Invites sent to {len(invited_customers)} customers")
                    if event.get('last_invite_sent'):
                        st.caption(f"Last sent: {event.get('last_invite_sent')}")
                else:
                    # Get customers
                    customers = get_customers()
                    
                    if not customers:
                        st.warning("⚠️ No customers found in the system")
                    else:
                        # Multi-select for customers
                        selected_customers = st.multiselect(
                            "Select customers to invite:",
                            options=[c['user_id'] for c in customers],
                            format_func=lambda x: next((f"{c['username']} ({c['email']})" for c in customers if c['user_id'] == x), x),
                            key=f"customer_select_{event.get('id', i)}"
                        )
                        
                        if selected_customers:
                            if st.button("📧 Send Invites", key=f"send_invite_{event.get('id', i)}"):
                                if send_invites(event.get('id', ''), selected_customers):
                                    st.success(f"✅ Invites sent to {len(selected_customers)} customers!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to send invites. Please try again.")

def render_user_invites():
    """Render the user's event invites UI"""
    st.markdown("### 📬 My Event Invites")

    # Get current user
    user = st.session_state.get('user')
    if not user:
        st.warning("⚠️ Please log in to view your invites")
        return

    user_id = user.get('user_id')

    try:
        # Fetch user's invites
        db = get_event_db()
        if not db:
            st.error("❌ Failed to connect to database")
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
            st.info("📭 You don't have any event invites yet.")
            return
        
        st.success(f"📧 You have {len(invites)} event invites")
        
        # Display invites
        for i, invite in enumerate(invites):
            event = invite.get('event', {})
            
            with st.expander(f"🎉 {event.get('theme', 'Event')} - Status: {invite.get('status', 'Unknown').title()}"):
                st.markdown(f"**Description:** {event.get('description', 'No description')}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### 🍽️ Menu")
                    menu_items = event.get('menu', [])
                    if menu_items:
                        for item in menu_items:
                            st.markdown(f"- {item}")
                    else:
                        st.markdown("No menu information")
                
                with col2:
                    st.markdown("##### ✉️ Invitation")
                    st.info(event.get('invitation', 'No invitation template'))
                
                # RSVP buttons - only show if not already responded
                current_status = invite.get('status', 'sent')
                if current_status == 'sent':
                    st.markdown("##### 📝 RSVP")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Accept", key=f"accept_invite_{invite.get('event_id', '')}_{i}"):
                            # Update invite status
                            invite_id = f"{invite.get('event_id', '')}_{user_id}"
                            db.collection('invites').document(invite_id).update({
                                'status': 'accepted',
                                'responded_at': firestore.SERVER_TIMESTAMP
                            })
                            st.success("✅ You've accepted the invitation!")
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Decline", key=f"decline_invite_{invite.get('event_id', '')}_{i}"):
                            # Update invite status
                            invite_id = f"{invite.get('event_id', '')}_{user_id}"
                            db.collection('invites').document(invite_id).update({
                                'status': 'declined',
                                'responded_at': firestore.SERVER_TIMESTAMP
                            })
                            st.success("❌ You've declined the invitation.")
                            st.rerun()
                else:
                    st.info(f"✅ You have {current_status} this invitation.")

    except Exception as e:
        logger.error(f"Error fetching invites: {str(e)}")
        st.error(f"❌ Failed to load invites: {str(e)}")

# Main Event Planner Function
def event_planner():
    """Main function to render the event planner UI based on user role"""
    st.title("🎉 Event Planning System")

    # Check if user is logged in
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("⚠️ Please log in to access the Event Planning System")
        return

    # Get user role
    user_role = st.session_state.user.get('role', 'user')

    # Add a diagnostic section for admins
    if user_role == 'admin':
        with st.expander("🔧 Firebase Diagnostics"):
            if st.button("Test Firestore Connection", key="test_connection_admin"):
                with st.spinner("Testing Firestore connection..."):
                    success, message = test_firestore_connection()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
                        
            # Add a direct save test
            if st.button("Test Direct Save", key="test_direct_save_admin"):
                with st.spinner("Testing direct save to Firestore..."):
                    try:
                        test_id = f"manual_test_{uuid.uuid4()}"
                        test_data = {
                            'id': test_id,
                            'theme': 'Test Event',
                            'description': 'This is a test event',
                            'created_at': datetime.utcnow(),
                            'created_by': 'admin_test'
                        }
                        
                        db = get_event_db()
                        if db:
                            # Direct save to Firestore
                            db.collection('events').document(test_id).set(test_data)
                            st.success(f"✅ Test event saved with ID: {test_id}")
                        else:
                            st.error("❌ Failed to get database connection")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

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
