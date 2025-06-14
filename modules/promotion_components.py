"""
Promotion Campaign UI Components for the Smart Restaurant Menu Management App.
Integrated with the main gamification system - minimalistic design.
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
from modules.leftover import get_user_stats
import logging

logger = logging.getLogger(__name__)

def render_promotion_generator():
    """Main function to render Promotion Generator with clean gamification"""
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
    
    # Show clean gamification stats at the top
    if user_id:
        render_clean_gamification_header(user_id)
    
    # Create tabs
    tabs = st.tabs(["📝 Create Campaign", "📊 Campaign History"])
    
    with tabs[0]:
        render_campaign_creation(db, staff_name, user_id)
    with tabs[1]:
        render_campaign_history(db, staff_name)

def render_clean_gamification_header(user_id):
    """Render clean, minimal gamification stats"""
    try:
        user_stats = get_user_stats(user_id)
        
        # Simple XP info box
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Level", user_stats.get('level', 1))
        
        with col2:
            current_xp = user_stats.get('total_xp', 0)
            st.metric("Total XP", f"{current_xp:,}")
        
        with col3:
            # Next level progress
            level = user_stats.get('level', 1)
            progress = (current_xp % 100) / 100
            st.metric("Next Level", f"{progress*100:.0f}%")
        
        # Simple progress bar
        st.progress(progress, text=f"Level {level} → {level + 1}")
        
    except Exception as e:
        logger.error(f"Error rendering gamification header: {str(e)}")

def render_campaign_creation(db, staff_name, user_id):
    """Render the campaign creation form with clean XP display"""
    st.markdown("### 📝 Create Marketing Campaign")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    # Simple XP info
    st.info("💡 **XP Rewards:** Basic (20 XP) • Good (30 XP) • Excellent (50 XP)")
    
    # Check if user already submitted this month
    existing_campaign = get_existing_campaign(db, staff_name)
    
    if existing_campaign:
        st.warning(f"⚠️ **Campaign Already Created for {month_name}**")
        
        # Show existing campaign
        with st.expander("👀 View Your Current Campaign", expanded=True):
            campaign_text = existing_campaign.get('campaign', 'No campaign content found')
            st.write("**Campaign Content:**")
            st.write(campaign_text)
            
            # Show XP earned (simple)
            campaign_length = len(campaign_text)
            if campaign_length >= 300:
                xp_earned = "50 XP (Excellent)"
            elif campaign_length >= 200:
                xp_earned = "30 XP (Good)"
            else:
                xp_earned = "20 XP (Basic)"
            
            st.caption(f"XP Earned: {xp_earned}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Type:** {existing_campaign.get('promotion_type', 'N/A')}")
                st.write(f"**Goal:** {existing_campaign.get('goal', 'N/A')}")
            with col2:
                st.write(f"**Target:** {existing_campaign.get('target_audience', 'N/A')}")
                st.write(f"**Duration:** {existing_campaign.get('campaign_duration', 'N/A')}")
        
        # Campaign management
        st.markdown("#### 🔄 Campaign Management")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete & Create New", type="primary", key="delete_campaign"):
                delete_and_regenerate_campaign(db, staff_name, user_id)
        
        with col2:
            if st.button("✅ Keep Current Campaign", key="keep_campaign"):
                st.success("✅ Current campaign preserved")
        
        return
    
    # No existing campaign - show creation form
    st.success("✅ Ready to create a new campaign and earn XP!")
    render_campaign_form(db, staff_name, user_id, month_name)

def delete_and_regenerate_campaign(db, staff_name, user_id):
    """Delete existing campaign and allow creation of new one"""
    try:
        with st.spinner("🗑️ Deleting existing campaign..."):
            success = delete_campaign(db, staff_name)
            
            if success:
                st.success("✅ Campaign deleted successfully!")
                
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
    """Create campaign and award XP with clean notifications"""
    with st.spinner('🤖 AI is crafting your campaign...'):
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
                # Calculate XP based on campaign quality
                campaign_length = len(campaign)
                if campaign_length >= 300:
                    campaign_quality = "excellent"
                    xp_earned = 50
                    quality_msg = "Excellent"
                elif campaign_length >= 200:
                    campaign_quality = "good"
                    xp_earned = 30
                    quality_msg = "Good"
                else:
                    campaign_quality = "basic"
                    xp_earned = 20
                    quality_msg = "Basic"
                
                # Award XP
                if user_id:
                    actual_xp = award_promotion_xp(user_id, campaign_quality)
                    xp_earned = actual_xp if actual_xp > 0 else xp_earned
                
                # Clean success message
                st.success(f"✅ **Campaign Created Successfully!** +{xp_earned} XP ({quality_msg})")
                
                # Show XP notification
                if xp_earned > 0:
                    show_xp_notification(xp_earned, "Creating Marketing Campaign")
                
                # Display generated campaign
                st.markdown("#### 📢 Your Generated Campaign")
                st.write(f"**Campaign by:** {staff_name}")
                st.write(f"**Type:** {promotion_type} | **Goal:** {promotion_goal}")
                st.markdown("---")
                st.write(campaign)
                
                # Show campaign in code block
                with st.expander("📋 Campaign Text (Copy/Paste Ready)"):
                    st.code(campaign, language=None)
                
                # Force sidebar update by clearing cache and rerunning
                if hasattr(st, 'cache_data'):
                    st.cache_data.clear()
                
                # Force a rerun to refresh the campaign status and sidebar
                st.rerun()
            else:
                st.error("❌ Failed to save campaign. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in campaign generation: {str(e)}")
            st.error(f"❌ Failed to generate campaign: {str(e)}")

def render_campaign_history(db, staff_name):
    """Render campaign history with minimal XP tracking"""
    st.markdown("### 📊 Campaign History")
    
    # Load all campaigns for this user
    try:
        all_user_campaigns = []
        total_estimated_xp = 0
        
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
            st.info("📝 No campaigns created yet. Create your first campaign to start earning XP!")
            return
        
        # Calculate XP for each campaign
        for campaign in all_user_campaigns:
            campaign_length = len(campaign.get('campaign', ''))
            if campaign_length >= 300:
                total_estimated_xp += 50
                campaign['estimated_xp'] = 50
                campaign['quality'] = 'Excellent'
            elif campaign_length >= 200:
                total_estimated_xp += 30
                campaign['estimated_xp'] = 30
                campaign['quality'] = 'Good'
            else:
                total_estimated_xp += 20
                campaign['estimated_xp'] = 20
                campaign['quality'] = 'Basic'
        
        # Display simple statistics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Campaigns", len(all_user_campaigns))
        
        with col2:
            st.metric("Estimated XP Earned", f"{total_estimated_xp} XP")
        
        with col3:
            # Average XP per campaign
            avg_xp = total_estimated_xp / len(all_user_campaigns) if all_user_campaigns else 0
            st.metric("Avg XP/Campaign", f"{avg_xp:.0f} XP")
        
        # Campaign timeline
        st.markdown("#### 📅 Recent Campaigns")
        
        for i, campaign in enumerate(reversed(all_user_campaigns[-5:])):  # Show last 5
            month = campaign.get('month', 'Unknown')
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
            xp = campaign.get('estimated_xp', 0)
            quality = campaign.get('quality', 'Unknown')
            
            with st.expander(f"{month_name} - {campaign.get('promotion_type', 'Unknown')} (+{xp} XP)", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Goal:** {campaign.get('goal', 'N/A')}")
                    st.write(f"**Target:** {campaign.get('target_audience', 'N/A')}")
                    st.write(f"**Duration:** {campaign.get('campaign_duration', 'N/A')}")
                
                with col2:
                    st.metric("XP", f"{xp}")
                    st.caption(f"Quality: {quality}")
                
                st.markdown("**Campaign:**")
                st.write(campaign.get('campaign', 'No content available'))
        
        # Simple tips
        st.markdown("#### 💡 Tips")
        st.info("Create longer, more detailed campaigns to earn more XP (up to 50 XP for excellent campaigns)")
        
    except Exception as e:
        logger.error(f"Error loading campaign history: {str(e)}")
        st.error("❌ Failed to load campaign history.")
