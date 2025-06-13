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
import re
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
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            st.error(f"Failed to initialize Event Firebase. Please check your credentials.")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

def ensure_events_collection_exists():
    """
    Check if the events collection exists and create it if needed
    """
    try:
        db = get_event_db()
        if not db:
            logger.error("Failed to get Firestore database client")
            return False
            
        # Check if the events collection exists
        collections = [collection.id for collection in db.collections()]
        
        if 'events' not in collections:
            logger.warning("Events collection does not exist, creating it")
            
            # Create events collection
            db.collection('events')
            logger.info("Created events collection")
            return True
        else:
            logger.info("Events collection already exists")
            return True
            
    except Exception as e:
        logger.error(f"Error checking/creating events collection: {str(e)}")
        return False

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
    Save event data to Firestore 'events' collection

    Args:
        event_data: Dictionary containing event details
        
    Returns:
        Boolean indicating success or failure
    """
    try:
        db = get_event_db()
        if not db:
            logger.error("Failed to get Firestore database client")
            return False
            
        # Generate a unique ID if not provided
        if 'id' not in event_data:
            event_data['id'] = str(uuid.uuid4())
            
        # Add timestamp
        event_data['created_at'] = datetime.now()
        
        # Log event data being saved
        logger.info(f"Saving event with ID: {event_data['id']} to 'events' collection")
        logger.info(f"Event theme: {event_data.get('theme', 'Unknown')}")
        
        # Save to Firestore events collection
        events_ref = db.collection('events')
        events_ref.document(event_data['id']).set(event_data)
        
        # Clear events cache to force refresh
        if 'events_cache' in st.session_state:
            del st.session_state.events_cache
            
        return True
    except Exception as e:
        logger.error(f"Error saving event to 'events' collection: {str(e)}")
        return False

def get_all_events() -> List[Dict]:
    """
    Fetch all events from Firestore 'events' collection

    Returns:
        List of events as dictionaries
    """
    # Check if we have cached events
    if 'events_cache' in st.session_state:
        return st.session_state.events_cache
        
    try:
        db = get_event_db()
        if not db:
            logger.error("Failed to get Firestore database client")
            return []
            
        logger.info("Fetching events from 'events' collection")
        events_ref = db.collection('events')
        
        # Get all events, ordered by creation time
        events_docs = events_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        
        events = []
        for doc in events_docs:
            event = doc.to_dict()
            # Convert Firestore timestamp to datetime for display
            if 'created_at' in event and isinstance(event['created_at'], datetime):
                event['created_at'] = event['created_at'].strftime("%Y-%m-%d %H:%M")
            events.append(event)
        
        logger.info(f"Retrieved {len(events)} events from 'events' collection")
        
        # Cache the events
        st.session_state.events_cache = events
        return events
    except Exception as e:
        logger.error(f"Error fetching events from 'events' collection: {str(e)}")
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
        
        # Clear events cache to refresh the dashboard
        if 'events_cache' in st.session_state:
            del st.session_state.events_cache
            
        return True
    except Exception as e:
        logger.error(f"Error sending invites: {str(e)}")
        return False

# JSON Repair Functions
def fix_json_string(json_str: str) -> str:
    """
    Attempt to fix common JSON formatting errors
    
    Args:
        json_str: The potentially malformed JSON string
        
    Returns:
        A corrected JSON string
    """
    # Replace single quotes with double quotes (except in strings)
    json_str = re.sub(r"(?<!\\)'([^']*)':", r'"\1":', json_str)
    json_str = re.sub(r":'([^']*)'", r':"\1"', json_str)
    
    # Fix missing quotes around keys
    json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)
    
    # Fix trailing commas in arrays and objects
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Fix missing commas between elements
    json_str = re.sub(r'"\s*{', '", {', json_str)
    json_str = re.sub(r'"\s*\[', '", [', json_str)
    json_str = re.sub(r'}\s*"', '}, "', json_str)
    json_str = re.sub(r']\s*"', '], "', json_str)
    
    # Fix unquoted strings
    def quote_unquoted(match):
        return f'"{match.group(1)}"'
    
    json_str = re.sub(r':\s*([a-zA-Z][a-zA-Z0-9_\s]*[a-zA-Z0-9_])\s*([,}])', r':"\1"\2', json_str)
    
    return json_str

def safe_json_loads(json_str: str) -> Dict:
    """
    Safely parse JSON with multiple fallback strategies
    
    Args:
        json_str: The JSON string to parse
        
    Returns:
        Parsed JSON as a dictionary
        
    Raises:
        ValueError: If all parsing attempts fail
    """
    # Try direct parsing first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parsing failed: {str(e)}")
        
        # Try fixing common JSON errors
        try:
            fixed_json = fix_json_string(json_str)
            return json.loads(fixed_json)
        except json.JSONDecodeError as e:
            logger.warning(f"Fixed JSON parsing failed: {str(e)}")
            
            # Try using a more lenient approach - eval (with safety checks)
            if all(c in json_str for c in ['{', '}']):
                try:
                    # Replace "true", "false", "null" with Python equivalents
                    eval_json = json_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                    # Basic security check - only allow dictionaries
                    if eval_json.strip().startswith('{') and eval_json.strip().endswith('}'):
                        result = eval(eval_json)
                        if isinstance(result, dict):
                            return result
                except Exception as e:
                    logger.warning(f"Eval parsing failed: {str(e)}")
            
            # If all else fails, raise the original error
            raise ValueError(f"Failed to parse JSON: {str(e)}")

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

    # Prepare prompt for AI - explicitly request valid JSON
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

    IMPORTANT: Format your response as a valid JSON object with these exact keys:
    {{
        "theme": {{
            "name": "Theme name",
            "description": "Theme description"
        }},
        "seating": {{
            "layout": "Layout description",
            "tables": ["Table 1: 8 guests", "Table 2: 8 guests"]
        }},
        "decor": ["Decoration 1", "Decoration 2", "Decoration 3"],
        "recipe_suggestions": ["Recipe 1", "Recipe 2", "Recipe 3"],
        "invitation": "Invitation text"
    }}

    Make sure the JSON is valid with proper quotes, commas, and brackets. Do not include any explanations or text outside the JSON object.'''

    try:
        # Generate response from AI
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Log the raw response for debugging
        logger.info(f"Raw AI response received: {response_text[:200]}...")
        
        # Extract JSON from response
        json_match = re.search(r'\`\`\`json\s*(.*?)\s*\`\`\`', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
            logger.info("JSON extracted from code block")
        else:
            # Try to find JSON without code blocks
            json_match = re.search(r'({.*})', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
                logger.info("JSON extracted from text")
            else:
                # If no JSON found, create a structured response manually
                logger.warning("No JSON found in response, creating structured response manually")
                # Create a basic event plan structure
                event_plan = {
                    "theme": {
                        "name": "Custom Event",
                        "description": "An event based on your requirements."
                    },
                    "seating": {
                        "layout": "Standard layout with tables arranged for optimal conversation.",
                        "tables": ["Table 1: 8 guests", "Table 2: 8 guests", "Table 3: 4 guests"]
                    },
                    "decor": ["Elegant centerpieces", "Ambient lighting", "Themed decorations"],
                    "recipe_suggestions": recipe_names[:5] if recipe_names else ["No recipes available"],
                    "invitation": "You are cordially invited to our special event."
                }
            
                return {
                    'plan': event_plan,
                    'success': True
                }
    
        # Parse JSON response with better error handling
        try:
            # Use our enhanced JSON parser
            event_plan = safe_json_loads(response_text)
            logger.info("Successfully parsed JSON response")
        
            # Validate the required fields are present
            required_fields = ["theme", "seating", "decor", "invitation"]
            missing_fields = [field for field in required_fields if field not in event_plan]
        
            # Check for recipe_suggestions or menu_suggestions (for backward compatibility)
            if "recipe_suggestions" not in event_plan and "menu_suggestions" in event_plan:
                event_plan["recipe_suggestions"] = event_plan["menu_suggestions"]
                logger.info("Converted menu_suggestions to recipe_suggestions")
            elif "recipe_suggestions" not in event_plan:
                missing_fields.append("recipe_suggestions")
        
            if missing_fields:
                logger.warning(f"Missing required fields in response: {missing_fields}")
                # Add missing fields with default values
                if "theme" not in event_plan:
                    event_plan["theme"] = {
                        "name": "Custom Event",
                        "description": "An event based on your requirements."
                    }
                if "seating" not in event_plan:
                    event_plan["seating"] = {
                        "layout": "Standard layout with tables arranged for optimal conversation.",
                        "tables": ["Table 1: 8 guests", "Table 2: 8 guests", "Table 3: 4 guests"]
                    }
                if "decor" not in event_plan:
                    event_plan["decor"] = ["Elegant centerpieces", "Ambient lighting", "Themed decorations"]
                if "recipe_suggestions" not in event_plan:
                    event_plan["recipe_suggestions"] = recipe_names[:5] if recipe_names else ["No recipes available"]
                if "invitation" not in event_plan:
                    event_plan["invitation"] = "You are cordially invited to our special event."
        except Exception as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            # Create a fallback event plan
            event_plan = {
                "theme": {
                    "name": "Custom Event",
                    "description": "An event based on your requirements."
                },
                "seating": {
                    "layout": "Standard layout with tables arranged for optimal conversation.",
                    "tables": ["Table 1: 8 guests", "Table 2: 8 guests", "Table 3: 4 guests"]
                },
                "decor": ["Elegant centerpieces", "Ambient lighting", "Themed decorations"],
                "recipe_suggestions": recipe_names[:5] if recipe_names else ["No recipes available"],
                "invitation": "You are cordially invited to our special event."
            }
        
            return {
                'plan': event_plan,
                'success': True
            }
    
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
        logger.error(f"Error generating event plan: {str(e)}", exc_info=True)
        # Create a fallback event plan
        event_plan = {
            "theme": {
                "name": "Custom Event",
                "description": "An event based on your requirements."
            },
            "seating": {
                "layout": "Standard layout with tables arranged for optimal conversation.",
                "tables": ["Table 1: 8 guests", "Table 2: 8 guests", "Table 3: 4 guests"]
            },
            "decor": ["Elegant centerpieces", "Ambient lighting", "Themed decorations"],
            "recipe_suggestions": recipe_names[:5] if recipe_names else ["No recipes available"],
            "invitation": "You are cordially invited to our special event."
        }
    
        return {
            'plan': event_plan,
            'success': True
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
                            'id': str(uuid.uuid4()),  # Explicitly set ID
                            'theme': event_plan['theme']['name'],
                            'description': event_plan['theme']['description'],
                            'seating': event_plan['seating'],
                            'decor': event_plan['decor'],
                            'recipes': event_plan['recipe_suggestions'],
                            'invitation': event_plan['invitation'],
                            'query': user_query,
                            'created_by': st.session_state.user['user_id'] if 'user' in st.session_state else 'unknown',
                            'created_at': datetime.now()  # Explicitly set timestamp
                        }
                        
                        # Save to Firestore
                        if save_event_to_firestore(event_data):
                            st.success("Event plan saved successfully!")
                            
                            # Clear the events cache to force refresh
                            if 'events_cache' in st.session_state:
                                del st.session_state.events_cache
                                
                            # Set a flag to switch to the dashboard tab after saving
                            st.session_state.switch_to_dashboard = True
                            
                            # Force a rerun to refresh the dashboard
                            st.rerun()
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

    # Refresh button
    if st.button("🔄 Refresh Events"):
        if 'events_cache' in st.session_state:
            del st.session_state.events_cache
        st.rerun()

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
                            format_func=lambda x: next((c['username'] for c in customers if c['user_id'] == x), x),
                            key=f"select_customers_{event.get('id', '')}"
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

    # Ensure the events collection exists
    ensure_events_collection_exists()

    # Different views based on role
    if user_role in ['admin', 'staff', 'chef']:
        # Staff view with tabs for chatbot and dashboard
        tab_index = 1 if st.session_state.get('switch_to_dashboard', False) else 0
    
        # Reset the switch flag after using it
        if st.session_state.get('switch_to_dashboard', False):
            st.session_state.switch_to_dashboard = False
    
        tab1, tab2 = st.tabs(["🤖 Event Planner", "📊 Event Dashboard"])
    
        if tab_index == 1:
            with tab2:
                render_event_dashboard()
            with tab1:
                render_chatbot_ui()
        else:
            with tab1:
                render_chatbot_ui()
            with tab2:
                render_event_dashboard()
    else:
        # Customer view - only shows their invites
        render_user_invites()
