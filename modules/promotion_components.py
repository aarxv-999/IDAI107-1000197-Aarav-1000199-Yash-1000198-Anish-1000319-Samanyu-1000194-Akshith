"""
Promotion Campaign UI Components for the Smart Restaurant Menu Management App.
Integrated with the main gamification system.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from modules.promotion_services import (
    get_promotion_firebase_db, filter_valid_ingredients, find_possible_dishes,
    generate_campaign, save_campaign, get_existing_campaign, get_campaigns_for_month,
    award_promotion_xp, delete_campaign
)
from ui.components import show_xp_notification
import logging

logger = logging.getLogger(__name__)

def render_promotion_generator():
    """Main function to render Promotion Generator"""
    st.title("📣 AI Marketing Campaign Generator")
    
    # Get current user for role-based access
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    staff_name = user.get('username', 'Unknown User')
    user_id = user.get('user_id')
    
    # Check access permissions - ONLY Admin and Staff
    if user_role not in ['staff', 'admin']:
        st.warning("⚠️ You don't have access to the Marketing Campaign Generator. This feature is available for Staff and Administrators only.")
        return
    
    # Initialize database connection
    db = get_promotion_firebase_db()
    if not db:
        st.error("❌ Database connection failed. Please check your configuration.")
        return
    
    # Create tabs
    tabs = st.tabs(["📝 Create Campaign", "📊 Campaign History"])
    
    with tabs[0]:
        render_campaign_creation(db, staff_name, user_id)
    with tabs[1]:
        render_campaign_history(db, staff_name)

def render_campaign_creation(db, staff_name, user_id):
    """Render the campaign creation form"""
    st.markdown("### 📝 Create Marketing Campaign")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    # Information box
    st.info("""
    **How it works:**
    1. Enter your campaign preferences below
    2. AI will generate a personalized campaign based on available inventory
    3. Earn XP for creating effective marketing campaigns!
    """)
    
    # Check if user already submitted this month
    existing_campaign = get_existing_campaign(db, staff_name)
    
    if existing_campaign:
        st.warning(f"⚠️ **Campaign Already Created for {month_name}**")
        
        # Show existing campaign
        with st.expander("👀 View Your Current Campaign", expanded=True):
            st.write("**Campaign Content:**")
            st.write(existing_campaign.get('campaign', 'No campaign content found'))
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Type:** {existing_campaign.get('promotion_type', 'N/A')}")
                st.write(f"**Goal:** {existing_campaign.get('goal', 'N/A')}")
            with col2:
                st.write(f"**Target:** {existing_campaign.get('target_audience', 'N/A')}")
                st.write(f"**Duration:** {existing_campaign.get('campaign_duration', 'N/A')}")
        
        # Campaign regeneration section
        st.markdown("#### 🔄 Campaign Management")
        st.info("You can delete your current campaign and create a new one if needed.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete Current Campaign & Create New", type="primary", key="delete_campaign"):
                delete_and_regenerate_campaign(db, staff_name, user_id)
        
        with col2:
            if st.button("✅ Keep Current Campaign", key="keep_campaign"):
                st.success("✅ Current campaign preserved")
        
        return
    
    # No existing campaign - show creation form
    st.success("✅ No existing campaign found for this month")
    render_campaign_form(db, staff_name, user_id, month_name)

def delete_and_regenerate_campaign(db, staff_name, user_id):
    """Delete existing campaign and allow creation of new one"""
    try:
        with st.spinner("🗑️ Deleting existing campaign..."):
            success = delete_campaign(db, staff_name)
            
            if success:
                st.success("✅ Campaign deleted successfully!")
                st.info("🚀 You can now create a new campaign below.")
                
                # Clear any session state related to campaigns
                if "campaign_created" in st.session_state:
                    del st.session_state.campaign_created
                
                # Show the creation form
                month_name = datetime.now().strftime("%B %Y")
                render_campaign_form(db, staff_name, user_id, month_name)
            else:
                st.error("❌ Failed to delete campaign. Please try again.")
                
    except Exception as e:
        logger.error(f"Error during campaign deletion: {str(e)}")
        st.error(f"❌ Error during campaign deletion: {str(e)}")

def render_campaign_form(db, staff_name, user_id, month_name):
    """Render the campaign creation form"""
    st.markdown(f"#### 📅 New Campaign for {month_name}")
    
    with st.form("campaign_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            promotion_type = st.selectbox(
                "🎯 Promotion Type",
                ["Buy 1 Get 1", "Percentage Discount", "Fixed Amount Off", "Combo Offer", 
                 "Happy Hour", "Bundle Deal", "Free Item", "Loyalty Reward"],
                help="Select the type of promotion you want to create"
            )
            
            target_audience = st.selectbox(
                "👥 Target Audience",
                ["All Customers", "Regular Customers", "New Customers", "Families", 
                 "Young Adults", "Office Workers", "Weekend Diners"],
                help="Who should this campaign target?"
            )
        
        with col2:
            promotion_goal = st.selectbox(
                "🎪 Campaign Goal",
                ["Reduce Food Wastage", "Increase Daily Orders", "Launch New Dish", 
                 "Clear Excess Inventory", "Boost Weekend Sales", "Attract New Customers", 
                 "Increase Average Order Value"],
                help="What do you want to achieve with this campaign?"
            )
            
            campaign_duration = st.selectbox(
                "⏰ Campaign Duration",
                ["Today Only", "This Week", "Weekend Special", "Limited Time (3 days)", 
                 "Extended (1 week)"],
                help="How long should this promotion run?"
            )
        
        submitted = st.form_submit_button("🚀 Generate Campaign", type="primary")
        
        if submitted:
            create_campaign_with_xp(
                db, staff_name, user_id, promotion_type, promotion_goal, 
                target_audience, campaign_duration
            )

def create_campaign_with_xp(db, staff_name, user_id, promotion_type, promotion_goal, target_audience, campaign_duration):
    """Create campaign and award XP"""
    with st.spinner('🤖 AI is crafting your perfect campaign...'):
        try:
            # Get available ingredients and possible dishes
            available_ingredients = filter_valid_ingredients(db)
            if not available_ingredients:
                st.error("❌ No valid ingredients found in inventory. Please check your inventory database.")
                return
            
            possible_dishes = find_possible_dishes(db, available_ingredients)
            if not possible_dishes:
                st.error("❌ No dishes can be prepared today based on current inventory. Please contact the kitchen manager.")
                return
            
            # Generate campaign
            campaign = generate_campaign(
                staff_name, promotion_type, promotion_goal, 
                target_audience, campaign_duration, possible_dishes
            )
            
            if not campaign:
                st.error("❌ Failed to generate campaign. Please try again.")
                return
            
            # Save campaign data
            campaign_data = {
                "name": staff_name,
                "campaign": campaign,
                "promotion_type": promotion_type,
                "goal": promotion_goal,
                "target_audience": target_audience,
                "campaign_duration": campaign_duration
            }
            
            success = save_campaign(db, staff_name, campaign_data)
            
            if success:
                # Award XP based on campaign quality (simple heuristic)
                campaign_quality = "excellent" if len(campaign) > 200 else "good" if len(campaign) > 100 else "basic"
                xp_earned = award_promotion_xp(user_id, campaign_quality) if user_id else 0
                
                # Success message
                st.success("🎉 **Campaign Created Successfully!**")
                
                # Show XP notification
                if xp_earned > 0:
                    show_xp_notification(xp_earned, "Creating Marketing Campaign")
                
                # Display generated campaign
                st.markdown("#### 📢 Your Generated Campaign")
                st.write(f"**Campaign by:** {staff_name}")
                st.write(f"**Type:** {promotion_type} | **Goal:** {promotion_goal}")
                st.markdown("---")
                st.write(campaign)
                
                # Show campaign in a nice format
                st.code(campaign, language=None)
                
                st.info("💡 **Tip:** Your campaign has been saved and you've earned XP! Check your profile to see your progress.")
                
                # Force a rerun to refresh the campaign status
                st.rerun()
            else:
                st.error("❌ Failed to save campaign. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in campaign generation: {str(e)}")
            st.error(f"❌ Failed to generate campaign: {str(e)}")

def render_campaign_history(db, staff_name):
    """Render campaign history and statistics"""
    st.markdown("### 📊 Campaign History")
    
    # Load all campaigns for this user
    try:
        all_user_campaigns = []
        # Get campaigns from multiple months
        for month_offset in range(6):  # Last 6 months
            check_date = datetime.now().replace(day=1)
            if month_offset > 0:
                # Go back months
                year = check_date.year
                month = check_date.month - month_offset
                if month <= 0:
                    month += 12
                    year -= 1
                check_month = f"{year}-{month:02d}"
            else:
                check_month = check_date.strftime("%Y-%m")
            
            month_campaigns = get_campaigns_for_month(db, check_month)
            user_campaigns = [c for c in month_campaigns if c.get('name') == staff_name]
            all_user_campaigns.extend(user_campaigns)
        
        if not all_user_campaigns:
            st.info("📝 No campaigns created yet. Create your first campaign in the 'Create Campaign' tab!")
            return
        
        # Display statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Campaigns", len(all_user_campaigns))
        
        with col2:
            # Most used promotion type
            promo_types = [c.get('promotion_type', 'Unknown') for c in all_user_campaigns]
            most_common = max(set(promo_types), key=promo_types.count) if promo_types else "None"
            st.metric("Favorite Type", most_common)
        
        with col3:
            # Most targeted goal
            goals = [c.get('goal', 'Unknown') for c in all_user_campaigns]
            most_common_goal = max(set(goals), key=goals.count) if goals else "None"
            st.metric("Main Focus", most_common_goal.split()[0] + "...")  # Truncate for display
        
        # Campaign timeline
        st.markdown("#### 📅 Your Campaign Timeline")
        
        # Create a simple timeline
        for i, campaign in enumerate(reversed(all_user_campaigns[-5:])):  # Show last 5
            month = campaign.get('month', 'Unknown')
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
            
            with st.expander(f"📋 {month_name} - {campaign.get('promotion_type', 'Unknown Type')}", expanded=False):
                st.write(f"**Goal:** {campaign.get('goal', 'N/A')}")
                st.write(f"**Target Audience:** {campaign.get('target_audience', 'N/A')}")
                st.write(f"**Duration:** {campaign.get('campaign_duration', 'N/A')}")
                st.markdown("**Campaign Content:**")
                st.write(campaign.get('campaign', 'No content available'))
        
        # Tips for improvement
        st.markdown("#### 💡 Tips for Better Campaigns")
        st.info("""
        - **Vary your promotion types** to reach different customer segments
        - **Focus on seasonal ingredients** to reduce waste and costs
        - **Target specific audiences** for more effective campaigns
        - **Track which goals work best** for your restaurant
        """)
        
    except Exception as e:
        logger.error(f"Error loading campaign history: {str(e)}")
        st.error("❌ Failed to load campaign history.")
