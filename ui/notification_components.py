"""
Notification system components for marketing campaigns.
Handles the notification bell and campaign voting interface.
"""

import streamlit as st
from datetime import datetime
from modules.promotion_services import (
    get_promotion_firebase_db, get_all_campaigns_sorted, 
    has_user_voted, vote_on_campaign, get_campaign_votes_summary
)
import logging

logger = logging.getLogger(__name__)

def render_notification_bell():
    """Render notification bell icon in the top right"""
    # Initialize notification state
    if 'show_notifications' not in st.session_state:
        st.session_state.show_notifications = False
    
    # Create a container for the bell icon
    with st.container():
        col1, col2, col3 = st.columns([8, 1, 1])
        
        with col2:
            if st.button("🔔", help="View Marketing Campaigns", key="notification_bell"):
                st.session_state.show_notifications = not st.session_state.show_notifications
                st.rerun()

def render_notifications_page():
    """Render the notifications page with all campaigns"""
    st.title("🔔 Marketing Campaigns")
    
    # Get current user
    user = st.session_state.get('user', {})
    user_id = user.get('user_id')
    
    if not user_id:
        st.warning("Please log in to view and vote on campaigns.")
        return
    
    # Get database connection
    db = get_promotion_firebase_db()
    if not db:
        st.error("❌ Database connection failed.")
        return
    
    # Get all campaigns sorted by newest first
    campaigns = get_all_campaigns_sorted(db)
    
    if not campaigns:
        st.info("📝 No marketing campaigns available yet.")
        return
    
    st.markdown(f"### 📢 All Marketing Campaigns ({len(campaigns)} total)")
    st.markdown("Vote on campaigns to help creators earn XP! 👍 = +10 XP, 👎 = +2 XP")
    
    # Display campaigns
    for campaign in campaigns:
        render_campaign_card(db, campaign, user_id)

def render_campaign_card(db, campaign, user_id):
    """Render a single campaign card with voting"""
    try:
        campaign_id = campaign.get('campaign_id')
        creator_name = campaign.get('name', 'Unknown')
        creator_user_id = campaign.get('user_id')
        campaign_text = campaign.get('campaign', 'No content available')
        promotion_type = campaign.get('promotion_type', 'Unknown')
        goal = campaign.get('goal', 'Unknown')
        month = campaign.get('month', 'Unknown')
        
        # Format month for display
        try:
            month_name = datetime.strptime(month + "-01", "%Y-%m-%d").strftime("%B %Y") if month != 'Unknown' else 'Unknown'
        except:
            month_name = month
        
        # Get vote counts
        vote_summary = get_campaign_votes_summary(db, campaign_id)
        likes = vote_summary.get('likes', 0)
        dislikes = vote_summary.get('dislikes', 0)
        
        # Check if user has voted
        has_voted, existing_vote = has_user_voted(db, user_id, campaign_id)
        user_vote = existing_vote.get('vote_type') if existing_vote else None
        
        # Check if this is user's own campaign
        is_own_campaign = (creator_user_id == user_id)
        
        with st.container():
            # Campaign header
            col1, col2, col3 = st.columns([6, 2, 2])
            
            with col1:
                st.markdown(f"**{promotion_type}** by **{creator_name}**")
                st.caption(f"{month_name} • Goal: {goal}")
            
            with col2:
                st.metric("👍 Likes", likes)
            
            with col3:
                st.metric("👎 Dislikes", dislikes)
            
            # Campaign content
            with st.expander("📖 Read Campaign", expanded=False):
                st.write(campaign_text)
            
            # Voting section
            if is_own_campaign:
                st.info("👤 This is your campaign - you cannot vote on it")
            elif has_voted:
                vote_emoji = "👍" if user_vote == "like" else "👎"
                st.success(f"✅ You voted: {vote_emoji} {user_vote.title()}")
            else:
                # Show voting buttons
                col1, col2, col3 = st.columns([1, 1, 4])
                
                with col1:
                    if st.button("👍 Like", key=f"like_{campaign_id}", help="Award +10 XP to creator"):
                        vote_and_refresh(db, user_id, campaign_id, "like")
                
                with col2:
                    if st.button("👎 Dislike", key=f"dislike_{campaign_id}", help="Award +2 XP to creator"):
                        vote_and_refresh(db, user_id, campaign_id, "dislike")
            
            st.divider()
            
    except Exception as e:
        logger.error(f"Error rendering campaign card: {str(e)}")
        st.error("Error displaying campaign")

def vote_and_refresh(db, user_id, campaign_id, vote_type):
    """Handle voting and refresh the page"""
    try:
        success, message = vote_on_campaign(db, user_id, campaign_id, vote_type)
        
        if success:
            st.success(message)
            # Force a rerun to refresh the vote counts and status
            st.rerun()
        else:
            st.error(message)
            
    except Exception as e:
        logger.error(f"Error voting: {str(e)}")
        st.error("Error recording vote")

def render_notification_system():
    """Main function to render the complete notification system"""
    # Always show the bell icon
    render_notification_bell()
    
    # Show notifications page if bell was clicked
    if st.session_state.get('show_notifications', False):
        render_notifications_page()
        
        # Add a close button
        if st.button("❌ Close Notifications", key="close_notifications"):
            st.session_state.show_notifications = False
            st.rerun()
