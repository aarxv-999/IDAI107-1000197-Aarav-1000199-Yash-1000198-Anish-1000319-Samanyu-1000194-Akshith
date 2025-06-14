"""
Event Planning Chatbot for Smart Restaurant Management App
Simplified version with clean UI and maintained functionality
"""

import streamlit as st
import google.generativeai as genai
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import firebase_admin
from firebase_admin import firestore, credentials
import logging
import pandas as pd
from fpdf import FPDF
import base64
import random

from modules.leftover import (
    get_user_stats, calculate_level, get_firestore_db,
    generate_dynamic_quiz_questions, calculate_quiz_score
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('event_planner')

def init_event_firebase():
    """Initialize the Firebase Admin SDK for event data"""
    if not firebase_admin._apps or 'event_app' not in [app.name for app in firebase_admin._apps.values()]:
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
            logger.info("Event Firebase initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Event Firebase: {str(e)}")
            st.error(f"Failed to initialize Event Firebase")
            return False
    return True

def get_event_db():
    """Get Firestore client for event data"""
    if init_event_firebase():
        return firestore.client(app=firebase_admin.get_app(name='event_app'))
    return None

def configure_ai_model():
    """Configure and return the Gemini AI model"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            api_key = st.secrets.get("GEMINI_API_KEY")
            
        if not api_key:
            st.error("GEMINI_API_KEY not found!")
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        logger.error(f"Error configuring AI model: {str(e)}")
        st.error(f"Failed to configure AI model: {str(e)}")
        return None

def generate_event_plan(query: str, user_id: str, user_role: str) -> Dict:
    """Generate event plan with simplified JSON parsing"""
    model = configure_ai_model()
    if not model:
        return {'error': 'AI model configuration failed', 'success': False}

    # Extract guest count
    guest_count = 20
    guest_matches = re.findall(r'(\d+)\s+(?:people|guests|persons)', query)
    if guest_matches:
        guest_count = int(guest_matches[0])

    # Calculate costs
    food_cost_per_person = 500
    total_food_cost = food_cost_per_person * guest_count
    decoration_cost = min(5000, guest_count * 200)
    venue_setup_cost = 3000
    service_charges = int(total_food_cost * 0.15)
    total_cost = total_food_cost + decoration_cost + venue_setup_cost + service_charges
    cost_per_person = int(total_cost / guest_count)

    prompt = f'''Create an event plan for: "{query}"

Guest count: {guest_count}

Return ONLY valid JSON:

{{
  "theme": {{
    "name": "Event Theme Name",
    "description": "Theme description"
  }},
  "seating": {{
    "layout": "Seating description",
    "tables": [
      {{"table_number": 1, "shape": "round", "seats": 8, "location": "center"}}
    ]
  }},
  "decor": [
    "Decoration 1",
    "Decoration 2",
    "Decoration 3"
  ],
  "recipe_suggestions": [
    "Recipe 1",
    "Recipe 2", 
    "Recipe 3"
  ],
  "budget": {{
    "food_cost_per_person": {food_cost_per_person},
    "total_food_cost": {total_food_cost},
    "decoration_cost": {decoration_cost},
    "venue_setup_cost": {venue_setup_cost},
    "service_charges": {service_charges},
    "total_cost": {total_cost},
    "cost_per_person": {cost_per_person},
    "breakdown": [
      {{"item": "Food and Beverages", "cost": {total_food_cost}}},
      {{"item": "Decorations", "cost": {decoration_cost}}},
      {{"item": "Venue Setup", "cost": {venue_setup_cost}}},
      {{"item": "Service Charges", "cost": {service_charges}}}
    ]
  }},
  "invitation": "Invitation text here"
}}'''

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        response_text = response_text.replace('\`\`\`json', '').replace('\`\`\`', '').strip()
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No valid JSON found")
        
        json_text = response_text[start_idx:end_idx + 1]
        event_plan = json.loads(json_text)
        
        event_plan['date'] = datetime.now().strftime("%Y-%m-%d")
        event_plan['guest_count'] = guest_count
        
        logger.info(f"Successfully generated event plan for {guest_count} guests")
        return {'plan': event_plan, 'success': True}
        
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        return {'error': str(e), 'success': False}

def create_event_pdf(event_plan: Dict) -> bytes:
    """Create PDF with simplified formatting"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"EVENT PLAN: {event_plan['theme']['name'].upper()}", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.cell(0, 8, f"Guests: {event_plan.get('guest_count', 'Not specified')}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "THEME", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, event_plan['theme']['description'])
        pdf.ln(3)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "BUDGET (INR)", ln=True)
        pdf.set_font("Arial", "", 11)
        
        budget = event_plan.get('budget', {})
        if budget:
            pdf.cell(0, 6, f"Total: Rs. {budget.get('total_cost', 0):,}", ln=True)
            pdf.cell(0, 6, f"Per Person: Rs. {budget.get('cost_per_person', 0):,}", ln=True)
            pdf.ln(2)
            
            for item in budget.get('breakdown', []):
                pdf.cell(0, 5, f"• {item.get('item', '')}: Rs. {item.get('cost', 0):,}", ln=True)
            pdf.ln(3)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "SEATING", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, event_plan['seating']['layout'])
        pdf.ln(3)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "DECORATION", ln=True)
        pdf.set_font("Arial", "", 11)
        for item in event_plan['decor']:
            pdf.cell(0, 5, f"• {item}", ln=True)
        pdf.ln(3)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "MENU", ln=True)
        pdf.set_font("Arial", "", 11)
        for item in event_plan['recipe_suggestions']:
            pdf.cell(0, 5, f"• {item}", ln=True)
        pdf.ln(3)
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "INVITATION", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6, event_plan['invitation'])
        
        return pdf.output(dest="S").encode("latin1")
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        return b""

def event_planner():
    """Simplified main event planner function"""
    st.title("🎉 Event Planning Assistant")
    
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("Please log in to access Event Planning")
        return
    
    user = st.session_state.user
    user_role = user.get('role', 'user')
    user_id = user.get('user_id', '')
    
    if user_role in ['admin', 'staff', 'chef']:
        # Staff interface with chatbot
        render_chatbot_ui(user_id, user_role)
    else:
        # User interface with quiz
        render_user_interface(user_id)

def render_chatbot_ui(user_id: str, user_role: str):
    """Simplified chatbot interface"""
    st.markdown("### 🤖 AI Assistant")
    
    if 'event_chat_history' not in st.session_state:
        st.session_state.event_chat_history = []
        
    if 'current_event_plan' not in st.session_state:
        st.session_state.current_event_plan = None

    # Display chat history
    for message in st.session_state.event_chat_history:
        if message['role'] == 'user':
            st.chat_message('user').write(message['content'])
        else:
            st.chat_message('assistant').write(message['content'])

    # Quick suggestions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎂 Birthday Party", use_container_width=True):
            st.session_state.suggested_query = "Plan a birthday party for 50 guests"
    
    with col2:
        if st.button("💼 Corporate Event", use_container_width=True):
            st.session_state.suggested_query = "Plan a corporate event for 100 guests"
    
    with col3:
        if st.button("💒 Wedding Reception", use_container_width=True):
            st.session_state.suggested_query = "Plan a wedding reception for 200 guests"

    # Chat input
    user_query = st.chat_input("Describe your event...")
    
    if 'suggested_query' in st.session_state:
        user_query = st.session_state.suggested_query
        del st.session_state.suggested_query

    if user_query:
        st.session_state.event_chat_history.append({
            'role': 'user',
            'content': user_query
        })
        
        st.chat_message('user').write(user_query)
        
        with st.chat_message('assistant'):
            with st.spinner("Creating event plan..."):
                response = generate_event_plan(user_query, user_id, user_role)
                
                if response['success']:
                    event_plan = response['plan']
                    st.session_state.current_event_plan = event_plan
                    
                    st.markdown(f"### 🎉 {event_plan['theme']['name']}")
                    st.markdown(f"*{event_plan['theme']['description']}*")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Guests", event_plan.get('guest_count', 'N/A'))
                    with col2:
                        st.metric("Total Cost", f"₹{event_plan.get('budget', {}).get('total_cost', 0):,}")
                    with col3:
                        st.metric("Per Person", f"₹{event_plan.get('budget', {}).get('cost_per_person', 0):,}")
                    
                    tabs = st.tabs(["Seating", "Budget", "Decor", "Menu", "Export"])
                    
                    with tabs[0]:
                        st.write("**Seating Arrangement**")
                        st.write(event_plan['seating']['layout'])
                    
                    with tabs[1]:
                        st.write("**Budget Breakdown**")
                        budget = event_plan.get('budget', {})
                        for item in budget.get('breakdown', []):
                            st.write(f"• {item.get('item', '')}: ₹{item.get('cost', 0):,}")
                    
                    with tabs[2]:
                        st.write("**Decoration**")
                        for item in event_plan['decor']:
                            st.write(f"• {item}")
                    
                    with tabs[3]:
                        st.write("**Menu Suggestions**")
                        for item in event_plan['recipe_suggestions']:
                            st.write(f"• {item}")
                    
                    with tabs[4]:
                        st.write("**Export Options**")
                        
                        pdf_bytes = create_event_pdf(event_plan)
                        
                        if pdf_bytes:
                            st.download_button(
                                label="📄 Download PDF",
                                data=pdf_bytes,
                                file_name=f"event_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        
                        text_export = f"""EVENT PLAN: {event_plan['theme']['name']}
Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}
Guests: {event_plan.get('guest_count', 'Not specified')}

THEME: {event_plan['theme']['description']}

BUDGET: ₹{event_plan.get('budget', {}).get('total_cost', 0):,}

SEATING: {event_plan['seating']['layout']}

DECORATION: {chr(10).join([f"• {item}" for item in event_plan['decor']])}

MENU: {chr(10).join([f"• {item}" for item in event_plan['recipe_suggestions']])}

INVITATION: {event_plan['invitation']}"""
                        
                        st.download_button(
                            label="📝 Download Text",
                            data=text_export,
                            file_name=f"event_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"Created event plan for '{event_plan['theme']['name']}' with budget of ₹{event_plan.get('budget', {}).get('total_cost', 0):,}"
                    })
                else:
                    st.error(f"Failed to generate event plan: {response.get('error', 'Unknown error')}")
                    
                    st.session_state.event_chat_history.append({
                        'role': 'assistant',
                        'content': f"Sorry, couldn't generate event plan. Error: {response.get('error', 'Unknown error')}"
                    })

def render_user_interface(user_id: str):
    """Simplified user interface with quiz"""
    st.markdown("### 🎉 Event Planning Quiz")
    
    stats = get_user_stats(user_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Level", stats.get('level', 1))
    with col2:
        st.metric("Quizzes", stats.get('quizzes_taken', 0))
    with col3:
        st.metric("XP", stats.get('total_xp', 0))
    
    st.info("🎯 Take quizzes to learn about event planning!")
    
    # Simple quiz interface
    if st.button("Start Event Quiz", type="primary", use_container_width=True):
        st.info("Quiz feature coming soon!")
