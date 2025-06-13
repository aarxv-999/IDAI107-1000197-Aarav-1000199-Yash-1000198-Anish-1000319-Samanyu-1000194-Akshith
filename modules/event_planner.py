"""
Simplified Event Planning Chatbot
This streamlined version focuses on the AI-powered event planning experience
without actual Firebase integration or dashboard functionality.
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from datetime import datetime
import uuid
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Stub Firebase functions to maintain compatibility
def init_event_firebase():
    """Stub function that simulates Firebase initialization but doesn't actually connect"""
    logger.info("Using stub Firebase initialization")
    return True

def get_event_db():
    """Stub function that returns None instead of a Firestore client"""
    logger.info("Using stub Firestore client")
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

# Sample data (replacing Firebase data)
def get_recipe_items(dietary_restrictions: Optional[str] = None) -> List[Dict]:
    """
    Return sample recipe items, optionally filtered by dietary restrictions
    
    Args:
        dietary_restrictions: Optional filter for dietary needs
        
    Returns:
        List of recipe items as dictionaries
    """
    recipes = [
        {"id": "1", "name": "Grilled Salmon with Lemon Butter", "diet": []},
        {"id": "2", "name": "Vegetable Risotto", "diet": ["vegetarian"]},
        {"id": "3", "name": "Beef Wellington", "diet": []},
        {"id": "4", "name": "Mushroom Ravioli", "diet": ["vegetarian"]},
        {"id": "5", "name": "Chicken Tikka Masala", "diet": []},
        {"id": "6", "name": "Vegan Buddha Bowl", "diet": ["vegan", "vegetarian", "gluten-free"]},
        {"id": "7", "name": "Chocolate Soufflé", "diet": ["vegetarian"]},
        {"id": "8", "name": "Mediterranean Mezze Platter", "diet": ["vegetarian"]},
        {"id": "9", "name": "Sushi Platter", "diet": []},
        {"id": "10", "name": "Beef Bourguignon", "diet": []},
        {"id": "11", "name": "Ratatouille", "diet": ["vegan", "vegetarian", "gluten-free"]},
        {"id": "12", "name": "Lobster Thermidor", "diet": []},
        {"id": "13", "name": "Gluten-Free Pizza", "diet": ["gluten-free"]},
        {"id": "14", "name": "Vegan Lasagna", "diet": ["vegan", "vegetarian"]},
        {"id": "15", "name": "Keto-Friendly Cauliflower Steak", "diet": ["keto", "vegetarian"]}
    ]
    
    if dietary_restrictions and dietary_restrictions.lower() != "none":
        return [r for r in recipes if dietary_restrictions.lower() in r["diet"]]
    return recipes

def get_available_ingredients() -> List[Dict]:
    """
    Return sample ingredients
    
    Returns:
        List of ingredients as dictionaries
    """
    return [
        {"id": "1", "Ingredient": "Salmon", "Quantity": "10 kg"},
        {"id": "2", "Ingredient": "Arborio Rice", "Quantity": "5 kg"},
        {"id": "3", "Ingredient": "Beef Tenderloin", "Quantity": "8 kg"},
        {"id": "4", "Ingredient": "Mushrooms", "Quantity": "3 kg"},
        {"id": "5", "Ingredient": "Chicken Breast", "Quantity": "12 kg"},
        {"id": "6", "Ingredient": "Chickpeas", "Quantity": "4 kg"},
        {"id": "7", "Ingredient": "Chocolate", "Quantity": "2 kg"},
        {"id": "8", "Ingredient": "Hummus", "Quantity": "3 kg"},
        {"id": "9", "Ingredient": "Sushi Rice", "Quantity": "6 kg"},
        {"id": "10", "Ingredient": "Red Wine", "Quantity": "10 bottles"},
        {"id": "11", "Ingredient": "Eggplant", "Quantity": "5 kg"},
        {"id": "12", "Ingredient": "Lobster", "Quantity": "8 units"},
        {"id": "13", "Ingredient": "Cauliflower", "Quantity": "6 kg"},
        {"id": "14", "Ingredient": "Tofu", "Quantity": "4 kg"},
        {"id": "15", "Ingredient": "Almond Flour", "Quantity": "2 kg"}
    ]

def save_event_to_firestore(event_data: Dict) -> bool:
    """
    Stub function that simulates saving event data to Firestore
    
    Args:
        event_data: Dictionary containing event details
        
    Returns:
        Boolean indicating success
    """
    logger.info(f"Simulating save of event: {event_data.get('theme', 'Unknown event')}")
    return True

def get_all_events() -> List[Dict]:
    """
    Stub function that returns an empty list instead of fetching events
    
    Returns:
        Empty list
    """
    logger.info("Simulating fetch of all events")
    return []

def get_customers() -> List[Dict]:
    """
    Stub function that returns sample customers
    
    Returns:
        List of sample customers
    """
    return [
        {"user_id": "user1", "username": "John Doe", "email": "john@example.com"},
        {"user_id": "user2", "username": "Jane Smith", "email": "jane@example.com"},
        {"user_id": "user3", "username": "Bob Johnson", "email": "bob@example.com"}
    ]

def send_invites(event_id: str, customer_ids: List[str]) -> bool:
    """
    Stub function that simulates sending invites
    
    Args:
        event_id: ID of the event
        customer_ids: List of customer IDs to invite
        
    Returns:
        Boolean indicating success
    """
    logger.info(f"Simulating sending invites for event {event_id} to {len(customer_ids)} customers")
    return True

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
    st.markdown("Let me help you plan the perfect event for your restaurant! Just describe what you're looking for.")

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
            with st.chat_message('assistant'):
                if 'plan_html' in message:
                    st.markdown(message['plan_html'], unsafe_allow_html=True)
                else:
                    st.write(message['content'])

    # Chat input with helpful placeholder
    user_query = st.chat_input("Example: Plan a corporate dinner for 30 people with Mediterranean theme...", key="event_chat_input")

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
                    
                    # Create a user-friendly HTML display for the plan
                    plan_html = f"""
                    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                        <h2 style="color: #1e88e5; margin-top: 0;">🎉 {event_plan['theme']['name']}</h2>
                        <p style="font-style: italic;">{event_plan['theme']['description']}</p>
                        
                        <div style="margin-top: 20px;">
                            <h3 style="color: #43a047;">💺 Seating Arrangement</h3>
                            <p>{event_plan['seating']['layout']}</p>
                            <ul>
                    """
                    
                    # Add tables
                    for table in event_plan['seating']['tables']:
                        plan_html += f"<li>{table}</li>"
                    
                    plan_html += """
                            </ul>
                        </div>
                        
                        <div style="margin-top: 20px;">
                            <h3 style="color: #e53935;">🎭 Decoration Ideas</h3>
                            <ul>
                    """
                    
                    # Add decor items
                    for item in event_plan['decor']:
                        plan_html += f"<li>{item}</li>"
                    
                    plan_html += """
                            </ul>
                        </div>
                        
                        <div style="margin-top: 20px;">
                            <h3 style="color: #fb8c00;">🍽️ Recipe Suggestions</h3>
                            <ul>
                    """
                    
                    # Add recipes
                    for item in event_plan['recipe_suggestions']:
                        plan_html += f"<li>{item}</li>"
                    
                    plan_html += """
                            </ul>
                        </div>
                        
                        <div style="margin-top: 20px; background-color: #e3f2fd; padding: 15px; border-radius: 5px;">
                            <h3 style="color: #1565c0; margin-top: 0;">✉️ Invitation Template</h3>
                            <p style="font-style: italic;">{}</p>
                        </div>
                    </div>
                    """.format(event_plan['invitation'])
                    
                    # Display the formatted plan
                    st.markdown(plan_html, unsafe_allow_html=True)
                    
                    # Add a download button for the plan
                    plan_json = json.dumps(event_plan, indent=2)
                    st.download_button(
                        label="📥 Download Event Plan",
                        data=plan_json,
                        file_name="event_plan.json",
                        mime="application/json",
                    )
                    
                    # Add assistant message to chat history with HTML
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I've created an event plan for '{event_plan['theme']['name']}'.",
                        'plan_html': plan_html
                    })
                else:
                    error_msg = f"Failed to generate event plan: {response.get('error', 'Unknown error')}"
                    st.error(error_msg)
                    
                    # Add error message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I'm sorry, I couldn't generate an event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_event_dashboard():
    """Stub function for the event dashboard UI"""
    st.markdown("### 📊 Event Dashboard")
    st.info("The dashboard functionality has been simplified. All events will be displayed directly in the chat.")

def render_user_invites():
    """Stub function for the user's event invites UI"""
    st.markdown("### 📬 My Event Invites")
    st.info("The invitation system has been simplified. Please use the chatbot to plan events.")

# Main Event Planner Function
def event_planner():
    """Main function to render the event planner UI based on user role"""
    st.title("🎉 Event Planning System")

    # Check if user is logged in
    if 'user' not in st.session_state or not st.session_state.user:
        # Create a default user for testing
        st.session_state.user = {
            'user_id': 'default_user',
            'username': 'Default User',
            'role': 'admin'
        }

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
