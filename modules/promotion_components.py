"""
Promotion Campaign UI Components for the Smart Restaurant Menu Management App.
Integrated with the main gamification system with prominent XP features.
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
    """Main function to render Promotion Generator with prominent gamification"""
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
    
    # Show prominent gamification stats at the top
    if user_id:
        render_gamification_header(user_id, staff_name)
    
    # Create tabs
    tabs = st.tabs(["📝 Create Campaign", "📊 Campaign History", "🏆 XP & Achievements"])
    
    with tabs[0]:
        render_campaign_creation(db, staff_name, user_id)
    with tabs[1]:
        render_campaign_history(db, staff_name)
    with tabs[2]:
        render_promotion_achievements(db, staff_name, user_id)

def render_gamification_header(user_id, staff_name):
    """Render prominent gamification stats at the top"""
    try:
        user_stats = get_user_stats(user_id)
        
        # Create a prominent gamification banner
        st.markdown("""
        <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h3 style="color: white; margin: 0;">🎮 Marketing Campaign Master</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # XP and level display
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="🌟 Current Level", 
                value=user_stats.get('level', 1),
                help="Your current marketing level"
            )
        
        with col2:
            current_xp = user_stats.get('total_xp', 0)
            st.metric(
                label="⚡ Total XP", 
                value=f"{current_xp:,}",
                help="Total experience points earned"
            )
        
        with col3:
            # Calculate campaigns created (estimate from XP)
            campaign_xp = current_xp // 30  # Rough estimate
            st.metric(
                label="📢 Campaigns Created", 
                value=campaign_xp,
                help="Estimated campaigns created"
            )
        
        with col4:
            # Next level progress
            level = user_stats.get('level', 1)
            xp_for_next = level * 100
            progress = min((current_xp % 100) / 100 * 100, 100)
            st.metric(
                label="📈 Next Level", 
                value=f"{progress:.0f}%",
                help=f"Progress to level {level + 1}"
            )
        
        # XP Progress Bar
        st.markdown("#### 🎯 XP Progress to Next Level")
        progress_bar_value = (current_xp % 100) / 100
        st.progress(progress_bar_value)
        st.caption(f"Need {100 - (current_xp % 100)} more XP to reach Level {level + 1}")
        
    except Exception as e:
        logger.error(f"Error rendering gamification header: {str(e)}")
        st.info("🎮 Gamification stats loading...")

def render_campaign_creation(db, staff_name, user_id):
    """Render the campaign creation form with XP incentives"""
    st.markdown("### 📝 Create Marketing Campaign")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    # XP Reward Information Box
    st.success("""
    🎁 **XP Rewards for Campaign Creation:**
    - 🌟 **Basic Campaign (100-200 chars):** 20 XP
    - ⭐ **Good Campaign (200-300 chars):** 30 XP  
    - 🏆 **Excellent Campaign (300+ chars):** 50 XP
    
    💡 **Tip:** Write detailed, creative campaigns to earn more XP!
    """)
    
    # Check if user already submitted this month
    existing_campaign = get_existing_campaign(db, staff_name)
    
    if existing_campaign:
        st.warning(f"⚠️ **Campaign Already Created for {month_name}**")
        
        # Show existing campaign with XP earned indicator
        with st.expander("👀 View Your Current Campaign", expanded=True):
            campaign_text = existing_campaign.get('campaign', 'No campaign content found')
            st.write("**Campaign Content:**")
            st.write(campaign_text)
            
            # Show estimated XP earned
            campaign_length = len(campaign_text)
            if campaign_length >= 300:
                xp_earned = "🏆 50 XP (Excellent!)"
                quality = "excellent"
            elif campaign_length >= 200:
                xp_earned = "⭐ 30 XP (Good!)"
                quality = "good"
            else:
                xp_earned = "🌟 20 XP (Basic)"
                quality = "basic"
            
            st.info(f"**XP Earned:** {xp_earned} | **Quality:** {quality.title()}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Type:** {existing_campaign.get('promotion_type', 'N/A')}")
                st.write(f"**Goal:** {existing_campaign.get('goal', 'N/A')}")
            with col2:
                st.write(f"**Target:** {existing_campaign.get('target_audience', 'N/A')}")
                st.write(f"**Duration:** {existing_campaign.get('campaign_duration', 'N/A')}")
        
        # Campaign regeneration section with XP warning
        st.markdown("#### 🔄 Campaign Management")
        st.warning("⚠️ **Note:** Deleting and recreating will award XP again, but make sure your new campaign is even better!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete & Create New Campaign (+XP)", type="primary", key="delete_campaign"):
                delete_and_regenerate_campaign(db, staff_name, user_id)
        
        with col2:
            if st.button("✅ Keep Current Campaign", key="keep_campaign"):
                st.success("✅ Current campaign preserved")
        
        return
    
    # No existing campaign - show creation form
    st.success("✅ No existing campaign found for this month - Ready to earn XP!")
    render_campaign_form(db, staff_name, user_id, month_name)

def delete_and_regenerate_campaign(db, staff_name, user_id):
    """Delete existing campaign and allow creation of new one"""
    try:
        with st.spinner("🗑️ Deleting existing campaign..."):
            success = delete_campaign(db, staff_name)
            
            if success:
                st.success("✅ Campaign deleted successfully!")
                st.balloons()  # Celebration effect
                st.info("🚀 You can now create a new campaign below and earn XP again!")
                
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
    """Render the campaign creation form with XP preview"""
    st.markdown(f"#### 📅 New Campaign for {month_name}")
    
    # Real-time XP preview
    if 'campaign_preview' not in st.session_state:
        st.session_state.campaign_preview = ""
    
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
        
        # XP Motivation
        st.markdown("---")
        st.markdown("### 🎯 XP Earning Opportunity!")
        st.info("The AI will generate a campaign based on your selections. Longer, more detailed campaigns earn more XP!")
        
        submitted = st.form_submit_button("🚀 Generate Campaign & Earn XP!", type="primary")
        
        if submitted:
            create_campaign_with_xp(
                db, staff_name, user_id, promotion_type, promotion_goal, 
                target_audience, campaign_duration
            )

def create_campaign_with_xp(db, staff_name, user_id, promotion_type, promotion_goal, target_audience, campaign_duration):
    """Create campaign and award XP with prominent notifications"""
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
                # Calculate XP based on campaign quality
                campaign_length = len(campaign)
                if campaign_length >= 300:
                    campaign_quality = "excellent"
                    xp_earned = 50
                    quality_msg = "🏆 EXCELLENT Campaign!"
                elif campaign_length >= 200:
                    campaign_quality = "good"
                    xp_earned = 30
                    quality_msg = "⭐ GOOD Campaign!"
                else:
                    campaign_quality = "basic"
                    xp_earned = 20
                    quality_msg = "🌟 Basic Campaign"
                
                # Award XP
                if user_id:
                    actual_xp = award_promotion_xp(user_id, campaign_quality)
                    xp_earned = actual_xp if actual_xp > 0 else xp_earned
                
                # BIG SUCCESS CELEBRATION
                st.success("🎉 **CAMPAIGN CREATED SUCCESSFULLY!** 🎉")
                st.balloons()
                
                # Prominent XP notification
                st.markdown(f"""
                <div style="background: linear-gradient(90deg, #4CAF50 0%, #45a049 100%); 
                            padding: 20px; border-radius: 10px; margin: 20px 0; text-align: center;">
                    <h2 style="color: white; margin: 0;">🎁 +{xp_earned} XP EARNED! 🎁</h2>
                    <p style="color: white; margin: 5px 0; font-size: 18px;">{quality_msg}</p>
                    <p style="color: white; margin: 0;">Campaign Length: {campaign_length} characters</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Show XP notification (additional)
                if xp_earned > 0:
                    show_xp_notification(xp_earned, "Creating Marketing Campaign")
                
                # Display generated campaign
                st.markdown("#### 📢 Your Generated Campaign")
                st.write(f"**Campaign by:** {staff_name}")
                st.write(f"**Type:** {promotion_type} | **Goal:** {promotion_goal}")
                st.write(f"**XP Earned:** {xp_earned} | **Quality:** {campaign_quality.title()}")
                st.markdown("---")
                st.write(campaign)
                
                # Show campaign in a nice format
                st.code(campaign, language=None)
                
                # Motivational message
                st.info("🎮 **Great job!** Your XP has been added to your profile. Keep creating campaigns to level up!")
                
                # Force a rerun to refresh the campaign status
                st.rerun()
            else:
                st.error("❌ Failed to save campaign. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in campaign generation: {str(e)}")
            st.error(f"❌ Failed to generate campaign: {str(e)}")

def render_campaign_history(db, staff_name):
    """Render campaign history with XP tracking"""
    st.markdown("### 📊 Campaign History & XP Tracking")
    
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
        
        # Display XP statistics prominently
        st.markdown("#### 🏆 Your Campaign XP Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Campaigns", len(all_user_campaigns))
        
        with col2:
            st.metric("🎁 Estimated XP Earned", f"{total_estimated_xp} XP")
        
        with col3:
            # Most used promotion type
            promo_types = [c.get('promotion_type', 'Unknown') for c in all_user_campaigns]
            most_common = max(set(promo_types), key=promo_types.count) if promo_types else "None"
            st.metric("Favorite Type", most_common)
        
        with col4:
            # Average XP per campaign
            avg_xp = total_estimated_xp / len(all_user_campaigns) if all_user_campaigns else 0
            st.metric("📈 Avg XP/Campaign", f"{avg_xp:.0f} XP")
        
        # XP breakdown chart
        if len(all_user_campaigns) > 1:
            st.markdown("#### 📊 XP Earned Over Time")
            
            # Create XP timeline
            campaign_df = pd.DataFrame(all_user_campaigns)
            campaign_df['month_name'] = campaign_df['month'].apply(
                lambda x: datetime.strptime(x + "-01", "%Y-%m-%d").strftime("%b %Y") if x != 'Unknown' else 'Unknown'
            )
            
            fig = px.bar(
                campaign_df, 
                x='month_name', 
                y='estimated_xp',
                color='quality',
                title="XP Earned Per Campaign",
                color_discrete_map={
                    'Excellent': '#4CAF50',
                    'Good': '#FF9800', 
                    'Basic': '#2196F3'
                }
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Campaign timeline with XP
        st.markdown("#### 📅 Campaign Timeline with XP")
        
        for i, campaign in enumerate(reversed(all_user_campaigns[-5:])):  # Show last 5
            month = campaign.get('month', 'Unknown')
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
            xp = campaign.get('estimated_xp', 0)
            quality = campaign.get('quality', 'Unknown')
            
            # Color code by quality
            if quality == 'Excellent':
                quality_color = "🏆"
            elif quality == 'Good':
                quality_color = "⭐"
            else:
                quality_color = "🌟"
            
            with st.expander(f"{quality_color} {month_name} - {campaign.get('promotion_type', 'Unknown')} (+{xp} XP)", expanded=False):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Goal:** {campaign.get('goal', 'N/A')}")
                    st.write(f"**Target Audience:** {campaign.get('target_audience', 'N/A')}")
                    st.write(f"**Duration:** {campaign.get('campaign_duration', 'N/A')}")
                
                with col2:
                    st.metric("XP Earned", f"{xp} XP")
                    st.write(f"**Quality:** {quality}")
                
                st.markdown("**Campaign Content:**")
                st.write(campaign.get('campaign', 'No content available'))
        
    except Exception as e:
        logger.error(f"Error loading campaign history: {str(e)}")
        st.error("❌ Failed to load campaign history.")

def render_promotion_achievements(db, staff_name, user_id):
    """Render achievements and XP goals for promotions"""
    st.markdown("### 🏆 Marketing Achievements & XP Goals")
    
    if not user_id:
        st.warning("Please log in to view achievements")
        return
    
    try:
        # Get user stats
        user_stats = get_user_stats(user_id)
        total_xp = user_stats.get('total_xp', 0)
        level = user_stats.get('level', 1)
        
        # Get campaign count
        all_campaigns = []
        for month_offset in range(12):  # Last 12 months
            check_date = datetime.now().replace(day=1)
            if month_offset > 0:
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
            all_campaigns.extend(user_campaigns)
        
        campaign_count = len(all_campaigns)
        
        # Achievement definitions
        achievements = [
            {"name": "First Campaign", "desc": "Create your first marketing campaign", "requirement": 1, "xp_reward": 10, "icon": "🎯"},
            {"name": "Campaign Creator", "desc": "Create 5 marketing campaigns", "requirement": 5, "xp_reward": 25, "icon": "📢"},
            {"name": "Marketing Pro", "desc": "Create 10 marketing campaigns", "requirement": 10, "xp_reward": 50, "icon": "🏆"},
            {"name": "Campaign Master", "desc": "Create 25 marketing campaigns", "requirement": 25, "xp_reward": 100, "icon": "👑"},
            {"name": "XP Hunter", "desc": "Earn 500 total XP", "requirement": 500, "xp_reward": 50, "icon": "⚡"},
            {"name": "Level Up", "desc": "Reach Level 5", "requirement": 5, "xp_reward": 75, "icon": "🌟"},
            {"name": "Marketing Legend", "desc": "Reach Level 10", "requirement": 10, "xp_reward": 150, "icon": "🔥"},
        ]
        
        # Display achievements
        st.markdown("#### 🏅 Achievement Progress")
        
        for achievement in achievements:
            # Determine current progress
            if achievement["name"] in ["XP Hunter"]:
                current_progress = total_xp
            elif achievement["name"] in ["Level Up", "Marketing Legend"]:
                current_progress = level
            else:
                current_progress = campaign_count
            
            # Check if achieved
            is_achieved = current_progress >= achievement["requirement"]
            progress_percent = min(current_progress / achievement["requirement"] * 100, 100)
            
            # Create achievement card
            if is_achieved:
                st.success(f"{achievement['icon']} **{achievement['name']}** - COMPLETED! 🎉")
            else:
                st.info(f"{achievement['icon']} **{achievement['name']}** - {current_progress}/{achievement['requirement']}")
            
            st.write(f"   📝 {achievement['desc']}")
            st.write(f"   🎁 Reward: {achievement['xp_reward']} XP")
            st.progress(progress_percent / 100)
            st.write("")
        
        # XP Goals
        st.markdown("#### 🎯 XP Goals & Milestones")
        
        xp_milestones = [100, 250, 500, 1000, 2500, 5000]
        
        for milestone in xp_milestones:
            if total_xp >= milestone:
                st.success(f"✅ {milestone} XP - ACHIEVED!")
            else:
                remaining = milestone - total_xp
                st.info(f"🎯 {milestone} XP - Need {remaining} more XP")
        
        # Motivational section
        st.markdown("#### 💪 Keep Going!")
        
        next_milestone = next((m for m in xp_milestones if m > total_xp), None)
        if next_milestone:
            campaigns_needed = (next_milestone - total_xp) // 30  # Assuming avg 30 XP per campaign
            st.info(f"""
            🚀 **Next Goal:** {next_milestone} XP
            📢 **Campaigns Needed:** ~{campaigns_needed} more campaigns
            💡 **Tip:** Create detailed, creative campaigns to earn more XP per campaign!
            """)
        else:
            st.success("🏆 **Congratulations!** You've achieved all XP milestones!")
        
    except Exception as e:
        logger.error(f"Error rendering achievements: {str(e)}")
        st.error("❌ Failed to load achievements.")
