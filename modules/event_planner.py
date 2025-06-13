"""
Simplified Event Planning Chatbot
This streamlined version focuses on the AI-powered event planning experience
without Firebase integration or dashboard functionality.
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

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
def get_sample_recipes() -> List[str]:
    """Return sample recipe names"""
    return [
        "Grilled Salmon with Lemon Butter", 
        "Vegetable Risotto", 
        "Beef Wellington", 
        "Mushroom Ravioli",
        "Chicken Tikka Masala", 
        "Vegan Buddha Bowl", 
        "Chocolate Soufflé", 
        "Mediterranean Mezze Platter",
        "Sushi Platter", 
        "Beef Bourguignon", 
        "Ratatouille", 
        "Lobster Thermidor",
        "Gluten-Free Pizza", 
        "Vegan Lasagna", 
        "Keto-Friendly Cauliflower Steak"
    ]

def get_sample_ingredients() -> List[str]:
    """Return sample ingredient names"""
    return [
        "Salmon", "Arborio Rice", "Beef Tenderloin", "Mushrooms", "Chicken Breast",
        "Chickpeas", "Chocolate", "Hummus", "Sushi Rice", "Red Wine",
        "Eggplant", "Lobster", "Cauliflower", "Tofu", "Almond Flour",
        "Olive Oil", "Butter", "Garlic", "Onions", "Fresh Herbs",
        "Lemons", "Tomatoes", "Avocados", "Bell Peppers", "Spices"
    ]

# AI Event Planning Function
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

    # Get sample recipe items and ingredients for context
    recipe_names = get_sample_recipes()
    ingredient_names = get_sample_ingredients()

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

    Available recipes at our restaurant: {', '.join(recipe_names)}
    Available ingredients: {', '.join(ingredient_names)}

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
        
        # Filter recipe suggestions based on dietary restrictions if needed
        if dietary_restrictions:
            # In the simplified version, we'll just note the restrictions
            event_plan['dietary_restrictions'] = dietary_restrictions
        
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
    st.markdown("## 🎉 Event Planning Assistant")
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

# Main Event Planner Function
def event_planner():
    """Main function to render the simplified event planner UI"""
    st.set_page_config(
        page_title="Restaurant Event Planner",
        page_icon="🎉",
        layout="wide"
    )
    
    # Add some custom CSS for better styling
    st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    h1, h2, h3 {
        color: #1e88e5;
    }
    .stButton button {
        background-color: #1e88e5;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header with logo and title
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("# 🎉")
    with col2:
        st.title("Restaurant Event Planner")
    
    st.markdown("---")
    
    # Introduction
    with st.expander("ℹ️ About this app", expanded=True):
        st.markdown("""
        This AI-powered event planner helps you create custom event plans for your restaurant.
        
        **How to use:**
        1. Describe the event you want to plan in the chat box below
        2. Include details like number of guests, theme preferences, and dietary restrictions
        3. The AI will generate a complete event plan with theme, seating, decor, recipes, and invitation text
        4. You can download the plan as a JSON file for your records
        
        **Example prompts:**
        - "Plan a corporate dinner for 30 people with a Mediterranean theme"
        - "I need a wedding reception for 50 guests with vegan options"
        - "Create a birthday party for 15 people with gluten-free menu options"
        """)
    
    # Main chatbot UI
    render_chatbot_ui()
    
    # Footer
    st.markdown("---")
    st.markdown("*Powered by Gemini AI*")

# For testing the module independently
if __name__ == "__main__":
    event_planner()
