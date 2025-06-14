"""
Event Planning Chatbot for Smart Restaurant Management App
Created by: v0

This module provides:
1. AI-powered event planning chatbot using Gemini API
2. Integration with Firestore for recipe and ingredient data (read-only)
3. Role-based access control for different user types
4. User-friendly display of event plans
5. PDF export functionality
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import firebase_admin
from firebase_admin import firestore, credentials
import logging
import pandas as pd
from fpdf import FPDF
import base64
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

# Initialize Firebase for event data (read-only)
def init_event_firebase():
    """Initialize Firebase for event data"""
    if 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
        try:
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
            logger.error(f"Event Firebase init failed: {str(e)}")
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

# Firestore Data Functions (Read-Only)
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
            "tables": [
                {{"table_number": 1, "shape": "round", "seats": 8, "location": "near window"}},
                {{"table_number": 2, "shape": "rectangular", "seats": 10, "location": "center"}}
            ]
        }},
        "decor": [List of decoration ideas],
        "recipe_suggestions": [List of recipe names],
        "invitation": "Invitation text"
    }}

    Make sure the JSON is valid and properly formatted. For the tables, include table number, shape, number of seats, and location.
    '''

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
        
        # Add event date (current date)
        event_plan['date'] = datetime.now().strftime("%Y-%m-%d")
        
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

# PDF Generation Functions
def create_event_pdf(event_plan: Dict) -> bytes:
    """
    Create a PDF document of the event plan
    
    Args:
        event_plan: Dictionary containing event plan details
        
    Returns:
        PDF document as bytes
    """
    try:
        # Create PDF object
        pdf = FPDF()
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", "B", 16)
        
        # Title
        pdf.cell(0, 10, f"Event Plan: {event_plan['theme']['name']}", ln=True, align="C")
        pdf.ln(5)
        
        # Date
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.ln(5)
        
        # Theme description
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Theme", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['theme']['description'])
        pdf.ln(5)
        
        # Seating arrangement
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Seating Arrangement", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['seating']['layout'])
        
        # Table details
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Tables:", ln=True)
        
        # Create table for seating
        pdf.set_font("Arial", "", 10)
        col_width = 45
        row_height = 10
        
        # Table headers
        pdf.cell(col_width, row_height, "Table Number", border=1)
        pdf.cell(col_width, row_height, "Shape", border=1)
        pdf.cell(col_width, row_height, "Seats", border=1)
        pdf.cell(col_width, row_height, "Location", border=1)
        pdf.ln(row_height)
        
        # Table data
        for table in event_plan['seating']['tables']:
            if isinstance(table, dict):
                # New format
                pdf.cell(col_width, row_height, str(table.get('table_number', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('shape', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('seats', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('location', '')), border=1)
            else:
                # Old format (string)
                pdf.cell(0, row_height, str(table), border=1, ln=True)
            pdf.ln(row_height)
        
        pdf.ln(5)
        
        # Decoration
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Decoration Ideas", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['decor']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Recipe suggestions
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Recipe Suggestions", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['recipe_suggestions']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Invitation
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Invitation Template", ln=True)
        pdf.set_font("Arial", "I", 12)
        pdf.multi_cell(0, 10, event_plan['invitation'])
        
        # Return PDF as bytes
        return pdf.output(dest="S").encode("latin1", errors="replace")
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        return b""

def create_unicode_pdf(event_plan: Dict) -> bytes:
    """
    Create a PDF document with Unicode support using BytesIO
    
    Args:
        event_plan: Dictionary containing event plan details
        
    Returns:
        PDF document as bytes
    """
    try:
        from fpdf import FPDF
        
        class UnicodePDF(FPDF):
            def __init__(self):
                super().__init__()
                self.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
                self.add_font('DejaVu', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)
                self.add_font('DejaVu', 'I', 'DejaVuSansCondensed-Oblique.ttf', uni=True)
        
        # If we can't use DejaVu fonts, fall back to standard method
        try:
            pdf = UnicodePDF()
            use_unicode = True
        except:
            pdf = FPDF()
            use_unicode = False
        
        pdf.add_page()
        
        # Set font based on availability
        if use_unicode:
            pdf.set_font("DejaVu", "B", 16)
        else:
            pdf.set_font("Arial", "B", 16)
        
        # Title
        pdf.cell(0, 10, f"Event Plan: {event_plan['theme']['name']}", ln=True, align="C")
        pdf.ln(5)
        
        # Rest of PDF generation...
        # (Similar to create_event_pdf but with Unicode awareness)
        
        # Date
        pdf.set_font("Arial", "I", 12)
        pdf.cell(0, 10, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.ln(5)
        
        # Theme description
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Theme", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['theme']['description'])
        pdf.ln(5)
        
        # Seating arrangement
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Seating Arrangement", ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.multi_cell(0, 10, event_plan['seating']['layout'])
        
        # Table details
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Tables:", ln=True)
        
        # Create table for seating
        pdf.set_font("Arial", "", 10)
        col_width = 45
        row_height = 10
        
        # Table headers
        pdf.cell(col_width, row_height, "Table Number", border=1)
        pdf.cell(col_width, row_height, "Shape", border=1)
        pdf.cell(col_width, row_height, "Seats", border=1)
        pdf.cell(col_width, row_height, "Location", border=1)
        pdf.ln(row_height)
        
        # Table data
        for table in event_plan['seating']['tables']:
            if isinstance(table, dict):
                # New format
                pdf.cell(col_width, row_height, str(table.get('table_number', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('shape', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('seats', '')), border=1)
                pdf.cell(col_width, row_height, str(table.get('location', '')), border=1)
            else:
                # Old format (string)
                pdf.cell(0, row_height, str(table), border=1, ln=True)
            pdf.ln(row_height)
        
        pdf.ln(5)
        
        # Decoration
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Decoration Ideas", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['decor']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Recipe suggestions
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Recipe Suggestions", ln=True)
        pdf.set_font("Arial", "", 12)
        for item in event_plan['recipe_suggestions']:
            # Replace bullet point with hyphen to avoid encoding issues
            pdf.cell(0, 10, f"- {item}", ln=True)
        pdf.ln(5)
        
        # Invitation
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Invitation Template", ln=True)
        pdf.set_font("Arial", "I", 12)
        pdf.multi_cell(0, 10, event_plan['invitation'])
        
        # Use BytesIO to avoid encoding issues
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        return pdf_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error creating Unicode PDF: {str(e)}")
        # Fall back to standard method with character replacement
        return create_event_pdf(event_plan)

def get_pdf_download_link(pdf_bytes: bytes, filename: str) -> str:
    """
    Generate a download link for a PDF file
    
    Args:
        pdf_bytes: PDF document as bytes
        filename: Name of the file to download
        
    Returns:
        HTML string with download link
    """
    b64 = base64.b64encode(pdf_bytes).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download Event Plan PDF</a>'
    return href

# Streamlit UI Components
def render_seating_visualization(tables: List):
    """
    Render a visual representation of the seating arrangement
    
    Args:
        tables: List of table dictionaries or strings
    """
    # Convert tables to dataframe for better display
    table_data = []
    
    for i, table in enumerate(tables):
        if isinstance(table, dict):
            # New format
            table_data.append({
                "Table Number": table.get("table_number", i+1),
                "Shape": table.get("shape", "Round"),
                "Seats": table.get("seats", 0),
                "Location": table.get("location", "")
            })
        else:
            # Old format (string) - try to parse
            try:
                # Try to extract information from string format
                table_info = eval(table) if isinstance(table, str) else {"table_number": i+1, "guest_count": 0}
                table_data.append({
                    "Table Number": table_info.get("table_number", i+1),
                    "Shape": "Not specified",
                    "Seats": table_info.get("guest_count", 0),
                    "Location": "Not specified"
                })
            except:
                # Fallback if parsing fails
                table_data.append({
                    "Table Number": i+1,
                    "Shape": "Not specified",
                    "Seats": 0,
                    "Location": "Not specified"
                })
    
    # Create dataframe
    df = pd.DataFrame(table_data)
    
    # Display as a styled table
    st.dataframe(
        df,
        column_config={
            "Table Number": st.column_config.NumberColumn(
                "Table #",
                help="Table number",
                format="%d"
            ),
            "Seats": st.column_config.NumberColumn(
                "Seats",
                help="Number of seats at this table",
                format="%d"
            )
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Calculate total seats
    total_seats = sum(table.get("seats", 0) if isinstance(table, dict) else 0 for table in tables)
    st.caption(f"Total capacity: {total_seats} guests")

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
                    tabs = st.tabs(["💺 Seating", "🎭 Decor", "🍽️ Recipes", "✉️ Invitation", "📄 Export"])
                    
                    with tabs[0]:
                        st.markdown("#### Seating Arrangement")
                        st.markdown(event_plan['seating']['layout'])
                        
                        # Display tables in a user-friendly format
                        st.markdown("##### Tables:")
                        render_seating_visualization(event_plan['seating']['tables'])
                    
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
                    
                    with tabs[4]:
                        st.markdown("#### Export Event Plan")
                        
                        # Generate PDF
                        try:
                            # Try Unicode PDF first
                            pdf_bytes = create_unicode_pdf(event_plan)
                        except:
                            # Fall back to standard PDF with character replacement
                            pdf_bytes = create_event_pdf(event_plan)
                        
                        if pdf_bytes:
                            # Create download button
                            st.download_button(
                                label="Download Event Plan as PDF",
                                data=pdf_bytes,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="download_pdf"
                            )
                        else:
                            st.error("Failed to generate PDF. Please try again.")
                            
                            # Provide plain text alternative
                            st.markdown("### Plain Text Export")
                            text_export = f"""
                            # Event Plan: {event_plan['theme']['name']}
                            Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}
                            
                            ## Theme
                            {event_plan['theme']['description']}
                            
                            ## Seating Arrangement
                            {event_plan['seating']['layout']}
                            
                            ### Tables:
                            """
                            
                            for i, table in enumerate(event_plan['seating']['tables']):
                                if isinstance(table, dict):
                                    text_export += f"- Table {table.get('table_number', i+1)}: {table.get('shape', 'Round')} table with {table.get('seats', 0)} seats at {table.get('location', 'unspecified location')}\n"
                                else:
                                    text_export += f"- {table}\n"
                            
                            text_export += "\n## Decoration Ideas\n"
                            for item in event_plan['decor']:
                                text_export += f"- {item}\n"
                                
                            text_export += "\n## Recipe Suggestions\n"
                            for item in event_plan['recipe_suggestions']:
                                text_export += f"- {item}\n"
                                
                            text_export += f"\n## Invitation Template\n{event_plan['invitation']}\n"
                            
                            st.download_button(
                                label="Download as Text File",
                                data=text_export,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d')}.txt",
                                mime="text/plain",
                                key="download_txt"
                            )
                    
                    # Add assistant message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I've created an event plan for '{event_plan['theme']['name']}'. You can view the details above and download it as a PDF."
                    })
                else:
                    st.error(f"Failed to generate event plan: {response.get('error', 'Unknown error')}")
                    
                    # Add error message to chat history
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"I'm sorry, I couldn't generate an event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_user_invites():
    """Render the user's event invites UI"""
    st.markdown("### 📬 My Event Invites")
    st.info("Event invites feature has been disabled.")

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
        # Staff view with only chatbot
        render_chatbot_ui()
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
