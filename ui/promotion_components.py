import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from modules.promotion_services import (
    get_promotion_firebase_db, filter_valid_ingredients, find_possible_dishes,
    generate_campaign, save_campaign, get_existing_campaign, get_campaigns_for_month,
    award_promotion_xp, delete_campaign, get_user_stats_promotion, get_all_campaigns,
    like_campaign, dislike_campaign, get_user_by_id
)
from ui.components import show_xp_notification
import logging

logger = logging.getLogger(__name__)

def render_promotion_generator():
    st.title("AI Marketing Campaign Generator")
    
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    staff_name = user.get('username', 'Unknown User')
    user_id = user.get('user_id')
    
    if user_role not in ['staff', 'admin']:
        st.warning("You don't have access to the Marketing Campaign Generator. This feature is available for Staff and Administrators only.")
        return
    
    db = get_promotion_firebase_db()
    if not db:
        st.error("Database connection failed. Please check your configuration.")
        return
    
    if user_id:
        render_clean_gamification_header(user_id)
    
    tabs = st.tabs(["Create Campaign", "Campaign History", "All Campaigns"])
    
    with tabs[0]:
        render_campaign_creation(db, staff_name, user_id)
    with tabs[1]:
        render_campaign_history(db, staff_name)
    with tabs[2]:
        render_all_campaigns(db, user_id)

def render_clean_gamification_header(user_id):
    try:
        user_stats = get_user_stats_promotion(user_id)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Level", user_stats.get('level', 1))
        
        with col2:
            current_xp = user_stats.get('total_xp', 0)
            st.metric("Total XP", f"{current_xp:,}")
        
        with col3:
            level = user_stats.get('level', 1)
            progress = (current_xp % 100) / 100
            st.metric("Next Level", f"{progress*100:.0f}%")
        
        st.progress(progress, text=f"Level {level} → {level + 1}")
        
    except Exception as e:
        logger.error(f"Error rendering gamification header: {str(e)}")

def render_campaign_creation(db, staff_name, user_id):
    st.markdown("### Create Marketing Campaign")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    st.info("XP Rewards: Basic (20 XP) • Good (30 XP) • Excellent (50 XP) • Likes (+10 XP) • Dislikes (+2 XP)")
    
    existing_campaign = get_existing_campaign(db, staff_name)
    
    if existing_campaign:
        st.warning(f"Campaign Already Created for {month_name}")
        
        with st.expander("View Your Current Campaign", expanded=True):
            campaign_text = existing_campaign.get('campaign', 'No campaign content found')
            st.write("**Campaign Content:**")
            st.write(campaign_text)
            
            campaign_length = len(campaign_text)
            if campaign_length >= 300:
                xp_earned = "50 XP (Excellent)"
            elif campaign_length >= 200:
                xp_earned = "30 XP (Good)"
            else:
                xp_earned = "20 XP (Basic)"
            
            likes = existing_campaign.get('likes', 0)
            dislikes = existing_campaign.get('dislikes', 0)
            engagement_xp = (likes * 10) + (dislikes * 2)
            
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"Creation XP: {xp_earned}")
                st.caption(f"Engagement XP: +{engagement_xp} XP ({likes} likes, {dislikes} dislikes)")
            with col2:
                st.write(f"**Type:** {existing_campaign.get('promotion_type', 'N/A')}")
                st.write(f"**Goal:** {existing_campaign.get('goal', 'N/A')}")
        
        st.markdown("#### Campaign Management")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Delete & Create New", type="primary", key="delete_campaign"):
                delete_and_regenerate_campaign(db, staff_name, user_id)
        
        with col2:
            if st.button("Keep Current Campaign", key="keep_campaign"):
                st.success("Current campaign preserved")
        
        return
    
    st.success("Ready to create a new campaign and earn XP!")
    render_campaign_form(db, staff_name, user_id, month_name)

def delete_and_regenerate_campaign(db, staff_name, user_id):
    try:
        with st.spinner("Deleting existing campaign..."):
            success = delete_campaign(db, staff_name)
            
            if success:
                st.success("Campaign deleted successfully!")
                
                if "campaign_created" in st.session_state:
                    del st.session_state.campaign_created
                
                month_name = datetime.now().strftime("%B %Y")
                render_campaign_form(db, staff_name, user_id, month_name)
            else:
                st.error("Failed to delete campaign. Please try again.")
                
    except Exception as e:
        logger.error(f"Error during campaign deletion: {str(e)}")
        st.error(f"Error during campaign deletion: {str(e)}")

def render_campaign_form(db, staff_name, user_id, month_name):
    st.markdown(f"#### New Campaign for {month_name}")
    
    with st.form("campaign_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            promotion_type = st.selectbox(
                "Promotion Type",
                ["Buy 1 Get 1", "Percentage Discount", "Fixed Amount Off", "Combo Offer", 
                 "Happy Hour", "Bundle Deal", "Free Item", "Loyalty Reward"],
                help="Select the type of promotion you want to create"
            )
            
            target_audience = st.selectbox(
                "Target Audience",
                ["All Customers", "Regular Customers", "New Customers", "Families", 
                 "Young Adults", "Office Workers", "Weekend Diners"],
                help="Who should this campaign target?"
            )
        
        with col2:
            promotion_goal = st.selectbox(
                "Campaign Goal",
                ["Reduce Food Wastage", "Increase Daily Orders", "Launch New Dish", 
                 "Clear Excess Inventory", "Boost Weekend Sales", "Attract New Customers", 
                 "Increase Average Order Value"],
                help="What do you want to achieve with this campaign?"
            )
            
            campaign_duration = st.selectbox(
                "Campaign Duration",
                ["Today Only", "This Week", "Weekend Special", "Limited Time (3 days)", 
                 "Extended (1 week)"],
                help="How long should this promotion run?"
            )
        
        submitted = st.form_submit_button("Generate Campaign", type="primary")
        
        if submitted:
            create_campaign_with_xp(
                db, staff_name, user_id, promotion_type, promotion_goal, 
                target_audience, campaign_duration
            )

def create_campaign_with_xp(db, staff_name, user_id, promotion_type, promotion_goal, target_audience, campaign_duration):
    with st.spinner('AI is crafting your campaign...'):
        try:
            available_ingredients = filter_valid_ingredients(db)
            if not available_ingredients:
                st.error("No valid ingredients found in inventory. Please check your inventory database.")
                return
            
            possible_dishes = find_possible_dishes(db, available_ingredients)
            if not possible_dishes:
                st.error("No dishes can be prepared today based on current inventory. Please contact the kitchen manager.")
                return
            
            campaign = generate_campaign(
                staff_name, promotion_type, promotion_goal, 
                target_audience, campaign_duration, possible_dishes
            )
            
            if not campaign:
                st.error("Failed to generate campaign. Please try again.")
                return
            
            campaign_data = {
                "name": staff_name,
                "campaign": campaign,
                "promotion_type": promotion_type,
                "goal": promotion_goal,
                "target_audience": target_audience,
                "campaign_duration": campaign_duration
            }
            
            success = save_campaign(db, staff_name, campaign_data, user_id)
            
            if success:
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
                
                if user_id:
                    actual_xp = award_promotion_xp(user_id, campaign_quality)
                    xp_earned = actual_xp if actual_xp > 0 else xp_earned
                
                st.success(f"Campaign Created Successfully! +{xp_earned} XP ({quality_msg})")
                
                if xp_earned > 0:
                    show_xp_notification(xp_earned, "Creating Marketing Campaign")
                
                st.markdown("#### Your Generated Campaign")
                st.write(f"**Campaign by:** {staff_name}")
                st.write(f"**Type:** {promotion_type} | **Goal:** {promotion_goal}")
                st.markdown("---")
                st.write(campaign)
                
                with st.expander("Campaign Text (Copy/Paste Ready)"):
                    st.code(campaign, language=None)
                
                if hasattr(st, 'cache_data'):
                    st.cache_data.clear()
                
                if 'user_stats_updated' not in st.session_state:
                    st.session_state.user_stats_updated = 0
                st.session_state.user_stats_updated += 1
                
                st.rerun()
            else:
                st.error("Failed to save campaign. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in campaign generation: {str(e)}")
            st.error(f"Failed to generate campaign: {str(e)}")

def render_campaign_history(db, staff_name):
    st.markdown("### Campaign History")
    
    try:
        all_user_campaigns = []
        total_estimated_xp = 0
        
        for month_offset in range(6):
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
            all_user_campaigns.extend(user_campaigns)
        
        if not all_user_campaigns:
            st.info("No campaigns created yet. Create your first campaign to start earning XP!")
            return
        
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
            
            likes = campaign.get('likes', 0)
            dislikes = campaign.get('dislikes', 0)
            engagement_xp = (likes * 10) + (dislikes * 2)
            campaign['engagement_xp'] = engagement_xp
            total_estimated_xp += engagement_xp
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Campaigns", len(all_user_campaigns))
        
        with col2:
            st.metric("Estimated XP Earned", f"{total_estimated_xp} XP")
        
        with col3:
            avg_xp = total_estimated_xp / len(all_user_campaigns) if all_user_campaigns else 0
            st.metric("Avg XP/Campaign", f"{avg_xp:.0f} XP")
        
        st.markdown("#### Recent Campaigns")
        
        for i, campaign in enumerate(reversed(all_user_campaigns[-5:])):
            month = campaign.get('month', 'Unknown')
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
            creation_xp = campaign.get('estimated_xp', 0)
            engagement_xp = campaign.get('engagement_xp', 0)
            total_xp = creation_xp + engagement_xp
            quality = campaign.get('quality', 'Unknown')
            likes = campaign.get('likes', 0)
            dislikes = campaign.get('dislikes', 0)
            
            with st.expander(f"{month_name} - {campaign.get('promotion_type', 'Unknown')} (+{total_xp} XP)", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Goal:** {campaign.get('goal', 'N/A')}")
                    st.write(f"**Target:** {campaign.get('target_audience', 'N/A')}")
                    st.write(f"**Duration:** {campaign.get('campaign_duration', 'N/A')}")
                
                with col2:
                    st.metric("Creation XP", f"{creation_xp}")
                    st.metric("Engagement XP", f"{engagement_xp}")
                    st.caption(f"Quality: {quality}")
                    st.caption(f"Likes: {likes} | Dislikes: {dislikes}")
                
                st.markdown("**Campaign:**")
                st.write(campaign.get('campaign', 'No content available'))
        
        st.markdown("#### Tips")
        st.info("Create longer, more detailed campaigns to earn more XP (up to 50 XP for excellent campaigns). Get likes from colleagues to earn bonus XP!")
        
    except Exception as e:
        logger.error(f"Error loading campaign history: {str(e)}")
        st.error("Failed to load campaign history.")

def render_all_campaigns(db, current_user_id):
    st.markdown("### All Campaigns")
    st.markdown("*Discover and interact with campaigns from all team members*")
    
    try:
        all_campaigns = get_all_campaigns(db, limit=50)
        
        if not all_campaigns:
            st.info("No campaigns found. Be the first to create one!")
            return
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            promotion_types = list(set([c.get('promotion_type', 'Unknown') for c in all_campaigns]))
            selected_type = st.selectbox("Filter by Type", ["All"] + promotion_types)
        
        with col2:
            months = list(set([c.get('month', 'Unknown') for c in all_campaigns]))
            months.sort(reverse=True)
            selected_month = st.selectbox("Filter by Month", ["All"] + months)
        
        with col3:
            sort_option = st.selectbox("Sort by", ["Newest First", "Most Liked", "Most Engaged"])
        
        filtered_campaigns = all_campaigns.copy()
        
        if selected_type != "All":
            filtered_campaigns = [c for c in filtered_campaigns if c.get('promotion_type') == selected_type]
        
        if selected_month != "All":
            filtered_campaigns = [c for c in filtered_campaigns if c.get('month') == selected_month]
        
        if sort_option == "Most Liked":
            filtered_campaigns.sort(key=lambda x: x.get('likes', 0), reverse=True)
        elif sort_option == "Most Engaged":
            filtered_campaigns.sort(key=lambda x: x.get('likes', 0) + x.get('dislikes', 0), reverse=True)
        
        st.markdown(f"#### Showing {len(filtered_campaigns)} campaigns")
        
        for i, campaign in enumerate(filtered_campaigns):
            render_campaign_card(db, campaign, current_user_id, i)
        
    except Exception as e:
        logger.error(f"Error loading all campaigns: {str(e)}")
        st.error("Failed to load campaigns.")

def render_campaign_card(db, campaign, current_user_id, index):
    try:
        campaign_name = campaign.get('name', 'Unknown')
        campaign_text = campaign.get('campaign', 'No content')
        promotion_type = campaign.get('promotion_type', 'Unknown')
        goal = campaign.get('goal', 'N/A')
        month = campaign.get('month', 'Unknown')
        likes = campaign.get('likes', 0)
        dislikes = campaign.get('dislikes', 0)
        liked_by = campaign.get('liked_by', [])
        disliked_by = campaign.get('disliked_by', [])
        doc_id = campaign.get('doc_id', '')
        campaign_user_id = campaign.get('user_id')
        
        try:
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
        except:
            month_name = month
        
        user_liked = current_user_id in liked_by
        user_disliked = current_user_id in disliked_by
        is_own_campaign = current_user_id == campaign_user_id
        
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{campaign_name}** • {month_name}")
                st.markdown(f"Type: {promotion_type} • Goal: {goal}")
            
            with col2:
                st.metric("Likes", likes)
            
            with col3:
                st.metric("Dislikes", dislikes)
            
            with st.expander("Read Campaign", expanded=False):
                st.write(campaign_text)
            
            if not is_own_campaign:
                col1, col2, col3 = st.columns([1, 1, 4])
                
                with col1:
                    like_button_type = "primary" if user_liked else "secondary"
                    like_disabled = user_liked
                    
                    if st.button(
                        f"Like", 
                        key=f"like_{doc_id}_{index}",
                        type=like_button_type,
                        disabled=like_disabled,
                        use_container_width=True
                    ):
                        success, message = like_campaign(db, doc_id, current_user_id)
                        if success:
                            st.success("Liked!")
                            st.rerun()
                        else:
                            st.error(message)
                
                with col2:
                    dislike_button_type = "primary" if user_disliked else "secondary"
                    dislike_disabled = user_disliked
                    
                    if st.button(
                        f"Dislike", 
                        key=f"dislike_{doc_id}_{index}",
                        type=dislike_button_type,
                        disabled=dislike_disabled,
                        use_container_width=True
                    ):
                        success, message = dislike_campaign(db, doc_id, current_user_id)
                        if success:
                            st.success("Disliked")
                            st.rerun()
                        else:
                            st.error(message)
                
                with col3:
                    if user_liked:
                        st.success("You liked this campaign")
                    elif user_disliked:
                        st.info("You disliked this campaign")
            else:
                st.info("This is your campaign")
            
            st.divider()
    
    except Exception as e:
        logger.error(f"Error rendering campaign card: {str(e)}")
        st.error(f"Error displaying campaign")
