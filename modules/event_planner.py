"""
Event Planning Chatbot for Smart Restaurant Management App - Fixed Version
This script fixes the issue with saving AI-generated event plans to Firebase
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import uuid
from datetime import datetime
import firebase_admin
from firebase_admin import firestore, credentials
import logging
import re
import traceback
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# AI Event Planning Functions - FIXED VERSION
def generate_event_plan(query: str) -> Dict:
    """
    Generate an event plan using AI based on user query with improved Firebase storage structure
    
    Args:
        query: User's natural language query about event planning
        
    Returns:
        Dictionary containing generated event plan details and structured data for storage
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
        
        # Create a Firebase-friendly structure for storage
        firebase_event_data = {
            'id': str(uuid.uuid4()),
            'theme': event_plan['theme']['name'],
            'description': event_plan['theme']['description'],
            'created_at': datetime.utcnow(),
            'created_by': st.session_state.user['user_id'] if 'user' in st.session_state else 'unknown',
            'invitation': event_plan['invitation'],
            'decor': event_plan['decor'],
            'recipes': event_plan['recipe_suggestions'],
            'seating': {
                'layout': event_plan['seating']['layout'],
                'tables': event_plan['seating']['tables']
            },
            'query': query
        }
        
        return {
            'plan': event_plan,  # Original plan for display
            'firebase_data': firebase_event_data,  # Structured data for Firebase
            'success': True
        }
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'success': False
        }

# Modified render_chatbot_ui function to use the new firebase_data structure
def render_chatbot_ui():
    """Render the event planning chatbot UI with improved Firebase storage"""
    st.markdown("### 🤖 Event Planning Assistant")

    # Initialize chat history
    if 'event_chat_history' not in st.session_state:
        st.session_state.event_chat_history = []
        
    # Initialize current plan
    if 'current_event_plan' not in st.session_state:
        st.session_state.current_event_plan = None
        
    # Initialize firebase data
    if 'current_firebase_data' not in st.session_state:
        st.session_state.current_firebase_data = None

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
                    
                    # Store Firebase-structured data in session state
                    st.session_state.current_firebase_data = response['firebase_data']
                    
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
                        # Use the pre-structured Firebase data
                        firebase_data = st.session_state.current_firebase_data
                        
                        # Save to Firestore
                        if save_event_to_firestore(firebase_data):
                            st.success(f"Event plan saved successfully with ID: {firebase_data['id']}!")
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

# Add a debug function to test the Firebase data structure
def debug_firebase_structure():
    """Debug function to test Firebase data structure"""
    st.subheader("Debug: Firebase Data Structure")
    
    if st.button("Generate Test Event Structure"):
        test_id = f"test-{uuid.uuid4()}"
        current_time = datetime.utcnow()
        
        # Create a test Firebase data structure
        test_data = {
            'id': test_id,
            'theme': f"Test Event {current_time.strftime('%H:%M:%S')}",
            'description': "This is a test event structure for Firebase.",
            'created_at': current_time,
            'created_by': st.session_state.user['user_id'] if 'user' in st.session_state else 'unknown',
            'invitation': "You are invited to our test event!",
            'decor': [
                "Elegant centerpieces",
                "Ambient lighting",
                "Floral arrangements"
            ],
            'recipes': [
                "Spaghetti Carbonara",
                "Chicken Stir Fry", 
                "Chocolate Chip Cookies"
            ],
            'seating': {
                'layout': "Test layout with round tables",
                'tables': [
                    "Table 1: 6 guests",
                    "Table 2: 6 guests",
                    "Table 3: 4 guests"
                ]
            },
            'query': "Test query for event planning"
        }
        
        st.json(test_data)
        
        if st.button("Save Test Structure to Firebase"):
            if save_event_to_firestore(test_data):
                st.success(f"Test structure saved successfully with ID: {test_id}!")
            else:
                st.error("Failed to save test structure. Please check Firebase connection.")

# Add this to your main function to include the debug option for admins
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
        # Staff view with tabs for chatbot, dashboard, and debug (for admins)
        if user_role == 'admin':
            tab1, tab2, tab3 = st.tabs(["🤖 Event Planner", "📊 Event Dashboard", "🔧 Debug"])
            
            with tab1:
                render_chatbot_ui()
                
            with tab2:
                render_event_dashboard()
                
            with tab3:
                debug_firebase_structure()
        else:
            # Regular staff view
            tab1, tab2 = st.tabs(["🤖 Event Planner", "📊 Event Dashboard"])
            
            with tab1:
                render_chatbot_ui()
                
            with tab2:
                render_event_dashboard()
    else:
        # Customer view - only shows their invites
        render_user_invites()

# The rest of your functions remain unchanged


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
