"""
Enhanced Event Planning Chatbot with Firebase integration and XP rewards
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
    generate_dynamic_quiz_questions, calculate_quiz_score, update_user_stats
)
from modules.firebase_data import (
    fetch_recipe_archive, fetch_menu_items, get_popular_recipes,
    format_recipe_for_display, format_menu_item_for_display
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

def analyze_prompt_quality(prompt: str) -> Dict[str, Any]:
    """
    Analyze the quality and detail level of the user's event planning prompt.
    Returns a dictionary with quality metrics and XP calculation.
    """
    quality_score = 0
    details_found = []
    
    # Convert to lowercase for analysis
    prompt_lower = prompt.lower()
    
    # Base points for submitting any prompt
    base_xp = 8
    
    # Length analysis (more detailed prompts get more points)
    word_count = len(prompt.split())
    if word_count >= 50:
        quality_score += 15
        details_found.append("Very detailed description")
    elif word_count >= 30:
        quality_score += 10
        details_found.append("Detailed description")
    elif word_count >= 15:
        quality_score += 5
        details_found.append("Good description length")
    
    # Specific details mentioned
    detail_keywords = {
        'guest_count': ['guests', 'people', 'persons', 'attendees', 'participants'],
        'event_type': ['birthday', 'wedding', 'corporate', 'anniversary', 'graduation', 'party', 'celebration'],
        'preferences': ['vegetarian', 'vegan', 'spicy', 'mild', 'traditional', 'modern', 'fusion'],
        'budget': ['budget', 'cost', 'expensive', 'affordable', 'cheap', 'premium', 'luxury'],
        'timing': ['morning', 'afternoon', 'evening', 'lunch', 'dinner', 'brunch'],
        'venue': ['indoor', 'outdoor', 'garden', 'hall', 'restaurant', 'home'],
        'theme': ['theme', 'color', 'decoration', 'style', 'elegant', 'casual', 'formal'],
        'special_requirements': ['allergies', 'dietary', 'wheelchair', 'kids', 'children', 'elderly']
    }
    
    for category, keywords in detail_keywords.items():
        if any(keyword in prompt_lower for keyword in keywords):
            quality_score += 3
            details_found.append(f"Specified {category.replace('_', ' ')}")
    
    # Bonus for specific numbers (guest count, budget, etc.)
    numbers_found = re.findall(r'\d+', prompt)
    if numbers_found:
        quality_score += 5
        details_found.append("Included specific numbers")
    
    # Bonus for questions or considerations
    question_words = ['how', 'what', 'when', 'where', 'should', 'would', 'could', 'can']
    if any(word in prompt_lower for word in question_words):
        quality_score += 3
        details_found.append("Asked thoughtful questions")
    
    # Bonus for mentioning multiple aspects
    aspects = ['menu', 'decoration', 'seating', 'entertainment', 'music', 'photography']
    mentioned_aspects = [aspect for aspect in aspects if aspect in prompt_lower]
    if len(mentioned_aspects) >= 3:
        quality_score += 8
        details_found.append("Considered multiple event aspects")
    elif len(mentioned_aspects) >= 2:
        quality_score += 5
        details_found.append("Considered multiple aspects")
    
    # Calculate total XP
    total_xp = base_xp + quality_score
    
    # Cap the maximum XP to prevent exploitation
    total_xp = min(total_xp, 50)
    
    # Determine quality level
    if total_xp >= 35:
        quality_level = "Exceptional"
    elif total_xp >= 25:
        quality_level = "Excellent"
    elif total_xp >= 18:
        quality_level = "Good"
    elif total_xp >= 12:
        quality_level = "Fair"
    else:
        quality_level = "Basic"
    
    return {
        'total_xp': total_xp,
        'base_xp': base_xp,
        'quality_bonus': quality_score,
        'quality_level': quality_level,
        'details_found': details_found,
        'word_count': word_count
    }

def award_event_planning_xp(user_id: str, prompt: str, event_plan_success: bool = True):
    """Award XP for event planning based on prompt quality"""
    try:
        # Analyze prompt quality
        quality_analysis = analyze_prompt_quality(prompt)
        
        # Reduce XP if event plan generation failed
        if not event_plan_success:
            quality_analysis['total_xp'] = max(5, quality_analysis['total_xp'] // 2)
            quality_analysis['quality_level'] = "Partial (generation failed)"
        
        # Award XP using the existing system
        update_user_stats(user_id, quality_analysis['total_xp'])
        
        # Show detailed XP notification
        show_event_xp_notification(quality_analysis)
        
        logger.info(f"Awarded {quality_analysis['total_xp']} XP to user {user_id} for {quality_analysis['quality_level']} event planning prompt")
        
        return quality_analysis
        
    except Exception as e:
        logger.error(f"Error awarding event planning XP: {str(e)}")
        return None

def show_event_xp_notification(quality_analysis: Dict[str, Any]):
    """Show detailed XP notification for event planning"""
    total_xp = quality_analysis['total_xp']
    quality_level = quality_analysis['quality_level']
    details_found = quality_analysis['details_found']
    
    # Create expandable notification
    with st.expander(f"🎉 +{total_xp} XP Earned! ({quality_level} Event Planning)", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total XP", total_xp)
            st.metric("Quality Level", quality_level)
        
        with col2:
            st.metric("Base XP", quality_analysis['base_xp'])
            st.metric("Quality Bonus", quality_analysis['quality_bonus'])
        
        if details_found:
            st.markdown("**Details Recognized:**")
            for detail in details_found:
                st.write(f"✅ {detail}")
        
        # XP improvement tips
        if quality_analysis['quality_level'] in ['Basic', 'Fair']:
            st.info("""
            💡 **Tips for more XP:**
            - Include specific guest count
            - Mention event type and theme
            - Add dietary preferences or special requirements
            - Describe venue or timing preferences
            - Consider multiple aspects (menu, decoration, seating)
            """)

def clean_text_for_pdf(text: str) -> str:
    """Clean text to remove Unicode characters that can't be encoded in latin-1"""
    if not text:
        return ""
    
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2022': '-',  # bullet point
        '\u2013': '-',  # en dash
        '\u2014': '--', # em dash
        '\u2018': "'",  # left single quotation mark
        '\u2019': "'",  # right single quotation mark
        '\u201c': '"',  # left double quotation mark
        '\u201d': '"',  # right double quotation mark
        '\u2026': '...', # horizontal ellipsis
        '\u00a0': ' ',  # non-breaking space
        '\u00b0': ' degrees', # degree symbol
        '\u20b9': 'Rs. ', # Indian Rupee symbol
        '\u00ae': '(R)', # registered trademark
        '\u00a9': '(C)', # copyright
        '\u2122': '(TM)', # trademark
    }
    
    # Apply replacements
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # Remove any remaining non-ASCII characters
    try:
        # Try to encode as latin-1, replace problematic characters
        text = text.encode('latin-1', errors='replace').decode('latin-1')
    except Exception:
        # If that fails, keep only ASCII characters
        text = ''.join(char for char in text if ord(char) < 128)
    
    return text

def get_firebase_menu_suggestions(guest_count: int, event_type: str = "") -> List[str]:
    """Get menu suggestions from Firebase recipe archive and menu collections"""
    try:
        # Get recipes from archive
        recipes = fetch_recipe_archive()
        menu_items = fetch_menu_items()
        
        suggestions = []
        
        # Add popular recipes
        if recipes:
            popular_recipes = recipes[:5]  # Get first 5 recipes
            for recipe in popular_recipes:
                formatted = format_recipe_for_display(recipe)
                suggestions.append(f"Recipe: {formatted}")
        
        # Add menu items
        if menu_items:
            popular_menu = menu_items[:5]  # Get first 5 menu items
            for item in popular_menu:
                formatted = format_menu_item_for_display(item)
                suggestions.append(f"Menu: {formatted}")
        
        # If we have suggestions, return them
        if suggestions:
            return suggestions[:8]  # Return up to 8 suggestions
        
        # Fallback suggestions if Firebase is empty
        return [
            "Vegetable Biryani with Raita",
            "Paneer Butter Masala with Naan",
            "Mixed Vegetable Curry with Rice",
            "Dal Tadka with Roti",
            "Chole Bhature",
            "Samosa with Chutney"
        ]
        
    except Exception as e:
        logger.error(f"Error getting Firebase menu suggestions: {str(e)}")
        # Return fallback suggestions
        return [
            "Vegetable Biryani with Raita",
            "Paneer Butter Masala with Naan",
            "Mixed Vegetable Curry with Rice",
            "Dal Tadka with Roti"
        ]

def generate_event_plan(query: str, user_id: str, user_role: str) -> Dict:
    """Generate event plan with Firebase integration"""
    model = configure_ai_model()
    if not model:
        return {'error': 'AI model configuration failed', 'success': False}

    # Extract guest count
    guest_count = 20
    guest_matches = re.findall(r'(\d+)\s+(?:people|guests|persons)', query)
    if guest_matches:
        guest_count = int(guest_matches[0])

    # Get menu suggestions from Firebase
    firebase_menu_suggestions = get_firebase_menu_suggestions(guest_count, query)
    menu_context = "\n".join([f"- {item}" for item in firebase_menu_suggestions])

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

Available menu options from restaurant database:
{menu_context}

Use these actual menu items in your recipe suggestions when possible.

Return ONLY valid JSON with simple ASCII text (no special characters):

{{
  "theme": {{
    "name": "Event Theme Name",
    "description": "Theme description"
  }},
  "seating": {{
    "layout": "Seating description for {guest_count} guests",
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
    "Recipe from database or new suggestion 1",
    "Recipe from database or new suggestion 2", 
    "Recipe from database or new suggestion 3"
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
}}

IMPORTANT: 
- Use only simple ASCII characters, no special symbols or Unicode characters
- Prioritize using the actual menu items from the restaurant database
- Make suggestions practical for a restaurant setting'''

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No valid JSON found")
        
        json_text = response_text[start_idx:end_idx + 1]
        event_plan = json.loads(json_text)
        
        # Clean all text fields in the event plan for PDF compatibility
        event_plan = clean_event_plan_text(event_plan)
        
        event_plan['date'] = datetime.now().strftime("%Y-%m-%d")
        event_plan['guest_count'] = guest_count
        event_plan['firebase_menu_used'] = len([item for item in firebase_menu_suggestions if any(
            menu_item.lower() in suggestion.lower() 
            for suggestion in event_plan.get('recipe_suggestions', [])
            for menu_item in [item.split(': ', 1)[-1] if ': ' in item else item]
        )]) > 0
        
        logger.info(f"Successfully generated event plan for {guest_count} guests with Firebase integration")
        return {'plan': event_plan, 'success': True}
        
    except Exception as e:
        logger.error(f"Error generating event plan: {str(e)}")
        return {'error': str(e), 'success': False}

def clean_event_plan_text(event_plan: Dict) -> Dict:
    """Recursively clean all text in the event plan for PDF compatibility"""
    if isinstance(event_plan, dict):
        cleaned = {}
        for key, value in event_plan.items():
            cleaned[key] = clean_event_plan_text(value)
        return cleaned
    elif isinstance(event_plan, list):
        return [clean_event_plan_text(item) for item in event_plan]
    elif isinstance(event_plan, str):
        return clean_text_for_pdf(event_plan)
    else:
        return event_plan

def create_event_pdf(event_plan: Dict) -> bytes:
    """Create PDF with proper Unicode handling and error prevention"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Clean the theme name for the title
        theme_name = clean_text_for_pdf(event_plan.get('theme', {}).get('name', 'Event Plan'))
        
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, f"EVENT PLAN: {theme_name.upper()}", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 8, f"Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}", ln=True)
        pdf.cell(0, 8, f"Guests: {event_plan.get('guest_count', 'Not specified')}", ln=True)
        
        # Add Firebase integration note
        if event_plan.get('firebase_menu_used', False):
            pdf.cell(0, 8, "Menu: Based on restaurant database", ln=True)
        
        pdf.ln(5)
        
        # Theme section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "THEME", ln=True)
        pdf.set_font("Arial", "", 11)
        
        theme_description = clean_text_for_pdf(event_plan.get('theme', {}).get('description', 'No description available'))
        pdf.multi_cell(0, 6, theme_description)
        pdf.ln(3)
        
        # Budget section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "BUDGET (INR)", ln=True)
        pdf.set_font("Arial", "", 11)
        
        budget = event_plan.get('budget', {})
        if budget:
            pdf.cell(0, 6, f"Total: Rs. {budget.get('total_cost', 0):,}", ln=True)
            pdf.cell(0, 6, f"Per Person: Rs. {budget.get('cost_per_person', 0):,}", ln=True)
            pdf.ln(2)
            
            for item in budget.get('breakdown', []):
                item_name = clean_text_for_pdf(item.get('item', 'Unknown Item'))
                pdf.cell(0, 5, f"- {item_name}: Rs. {item.get('cost', 0):,}", ln=True)
            pdf.ln(3)
        
        # Seating section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "SEATING", ln=True)
        pdf.set_font("Arial", "", 11)
        
        seating_layout = clean_text_for_pdf(event_plan.get('seating', {}).get('layout', 'No seating information available'))
        pdf.multi_cell(0, 6, seating_layout)
        pdf.ln(3)
        
        # Decoration section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "DECORATION", ln=True)
        pdf.set_font("Arial", "", 11)
        
        for item in event_plan.get('decor', []):
            clean_item = clean_text_for_pdf(str(item))
            pdf.cell(0, 5, f"- {clean_item}", ln=True)
        pdf.ln(3)
        
        # Menu section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "MENU (FROM RESTAURANT DATABASE)", ln=True)
        pdf.set_font("Arial", "", 11)
        
        for item in event_plan.get('recipe_suggestions', []):
            clean_item = clean_text_for_pdf(str(item))
            pdf.cell(0, 5, f"- {clean_item}", ln=True)
        pdf.ln(3)
        
        # Invitation section
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "INVITATION", ln=True)
        pdf.set_font("Arial", "", 11)
        
        invitation_text = clean_text_for_pdf(event_plan.get('invitation', 'No invitation text available'))
        pdf.multi_cell(0, 6, invitation_text)
        
        # Generate PDF bytes with proper encoding - FIXED SECTION
        pdf_output = pdf.output(dest="S")
        
        # Handle the output based on FPDF version
        if isinstance(pdf_output, str):
            # Older FPDF versions return string
            return pdf_output.encode("latin-1")
        elif isinstance(pdf_output, bytearray):
            # Handle bytearray output
            return bytes(pdf_output)
        else:
            # Newer FPDF versions return bytes
            return pdf_output
            
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}")
        # Return empty bytes if PDF creation fails
        return b""

def event_planner():
    """Enhanced main event planner function with Firebase integration"""
    st.title("🎉 Event Planning Assistant")
    
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("Please log in to access Event Planning")
        return
    
    user = st.session_state.user
    user_role = user.get('role', 'user')
    user_id = user.get('user_id', '')
    
    # Show XP information for event planning
    st.info("""
    🎯 **Earn XP for Event Planning:**
    - Base: +8 XP for any event plan
    - Detailed descriptions: +5-15 XP bonus
    - Specific requirements: +3 XP each
    - Multiple aspects considered: +5-8 XP bonus
    - Maximum: 50 XP per event plan
    """)
    
    # Show Firebase integration status
    try:
        recipes = fetch_recipe_archive()
        menu_items = fetch_menu_items()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📚 Recipe Archive", len(recipes))
        with col2:
            st.metric("🍽️ Menu Items", len(menu_items))
        
        if recipes or menu_items:
            st.success("✅ Connected to restaurant database")
        else:
            st.info("ℹ️ Restaurant database is empty")
            
    except Exception as e:
        st.warning("⚠️ Limited database access - using fallback suggestions")
    
    if user_role in ['admin', 'staff', 'chef']:
        # Staff interface with chatbot
        render_chatbot_ui(user_id, user_role)
    else:
        # User interface with quiz
        render_user_interface(user_id)

def render_chatbot_ui(user_id: str, user_role: str):
    """Enhanced chatbot interface with Firebase integration and XP rewards"""
    st.markdown("### 🤖 AI Assistant (Connected to Restaurant Database)")
    
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

    # Quick suggestions with XP hints
    st.markdown("**💡 Quick Suggestions (More details = More XP):**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎂 Birthday Party", use_container_width=True):
            st.session_state.suggested_query = "Plan a birthday party for 50 guests using our restaurant menu with vegetarian options, colorful decorations, and a fun theme suitable for all ages"
    
    with col2:
        if st.button("💼 Corporate Event", use_container_width=True):
            st.session_state.suggested_query = "Plan a corporate event for 100 guests using our restaurant specialties, formal seating arrangement, professional atmosphere, and dietary accommodations"
    
    with col3:
        if st.button("💒 Wedding Reception", use_container_width=True):
            st.session_state.suggested_query = "Plan a wedding reception for 200 guests with our premium menu items, elegant decorations, traditional and modern fusion cuisine, and special dietary requirements"

    # Chat input
    user_query = st.chat_input("Describe your event in detail (more details = more XP)...")
    
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
            with st.spinner("Creating event plan using restaurant database..."):
                response = generate_event_plan(user_query, user_id, user_role)
                
                # Award XP based on prompt quality
                quality_analysis = award_event_planning_xp(user_id, user_query, response['success'])
                
                if response['success']:
                    event_plan = response['plan']
                    st.session_state.current_event_plan = event_plan
                    
                    st.markdown(f"### 🎉 {event_plan['theme']['name']}")
                    st.markdown(f"*{event_plan['theme']['description']}*")
                    
                    # Show Firebase integration status
                    if event_plan.get('firebase_menu_used', False):
                        st.success("✅ Using items from restaurant database")
                    else:
                        st.info("ℹ️ Using AI-generated suggestions")
                    
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
                        st.write("**Menu (From Restaurant Database)**")
                        for item in event_plan['recipe_suggestions']:
                            st.write(f"• {item}")
                    
                    with tabs[4]:
                        st.write("**Export Options**")
                        
                        # PDF generation with error handling
                        try:
                            pdf_bytes = create_event_pdf(event_plan)
                            
                            if pdf_bytes and len(pdf_bytes) > 0:
                                st.download_button(
                                    label="📄 Download PDF",
                                    data=pdf_bytes,
                                    file_name=f"event_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                                st.success("✅ PDF ready for download!")
                            else:
                                st.error("❌ Failed to generate PDF. Please try the text export instead.")
                        except Exception as e:
                            st.error(f"❌ PDF generation failed: {str(e)}")
                            logger.error(f"PDF generation error: {str(e)}")
                        
                        # Text export as fallback
                        st.markdown("---")
                        st.write("**Alternative: Text Export**")
                        
                        text_export = f"""EVENT PLAN: {event_plan['theme']['name']}
Date: {event_plan.get('date', datetime.now().strftime('%Y-%m-%d'))}
Guests: {event_plan.get('guest_count', 'Not specified')}
Database Integration: {'Yes' if event_plan.get('firebase_menu_used', False) else 'No'}

THEME: {event_plan['theme']['description']}

BUDGET: Rs. {event_plan.get('budget', {}).get('total_cost', 0):,}

SEATING: {event_plan['seating']['layout']}

DECORATION:
{chr(10).join([f"- {item}" for item in event_plan['decor']])}

MENU (FROM RESTAURANT DATABASE):
{chr(10).join([f"- {item}" for item in event_plan['recipe_suggestions']])}

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
                        'content': f"Created event plan for '{event_plan['theme']['name']}' with budget of ₹{event_plan.get('budget', {}).get('total_cost', 0):,} using restaurant database"
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
