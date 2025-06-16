"""
Notifications module for marketing campaign feedback system.
Handles campaign likes/dislikes and XP rewards/penalties.
"""

import streamlit as st
import firebase_admin
from firebase_admin import firestore
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def get_firestore_client():
    """Get Firestore client for notifications"""
    try:
        if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client()
        else:
            from firebase_init import init_firebase
            init_firebase()
            return firestore.client()
    except Exception as e:
        logger.error(f"Error getting Firestore client: {str(e)}")
        return None

def get_recent_campaigns(days_back: int = 7) -> List[Dict]:
    """Get recent marketing campaigns for notifications"""
    try:
        db = get_firestore_client()
        if not db:
            return []
        
        # Calculate date threshold
        threshold_date = datetime.now() - timedelta(days=days_back)
        
        # Query campaigns from staff_campaigns collection
        campaigns_ref = db.collection('staff_campaigns')
        query = campaigns_ref.where('created_at', '>=', threshold_date).order_by('created_at', direction=firestore.Query.DESCENDING)
        
        campaigns = []
        for doc in query.stream():
            campaign_data = doc.to_dict()
            campaign_data['campaign_id'] = doc.id
            campaigns.append(campaign_data)
        
        logger.info(f"Retrieved {len(campaigns)} recent campaigns")
        return campaigns
        
    except Exception as e:
        logger.error(f"Error getting recent campaigns: {str(e)}")
        return []

def get_campaign_feedback(campaign_id: str) -> Dict:
    """Get feedback statistics for a campaign"""
    try:
        db = get_firestore_client()
        if not db:
            return {'likes': 0, 'dislikes': 0, 'total_feedback': 0}
        
        # Get campaign document to check for likes/dislikes count
        campaign_ref = db.collection('staff_campaigns').document(campaign_id)
        campaign_doc = campaign_ref.get()
        
        if campaign_doc.exists:
            campaign_data = campaign_doc.to_dict()
            likes = campaign_data.get('likes_count', 0)
            dislikes = campaign_data.get('dislikes_count', 0)
            
            return {
                'likes': likes,
                'dislikes': dislikes,
                'total_feedback': likes + dislikes
            }
        
        return {'likes': 0, 'dislikes': 0, 'total_feedback': 0}
        
    except Exception as e:
        logger.error(f"Error getting campaign feedback: {str(e)}")
        return {'likes': 0, 'dislikes': 0, 'total_feedback': 0}

def get_user_campaign_feedback(user_id: str, campaign_id: str) -> Optional[str]:
    """Check if user has already given feedback on a campaign"""
    try:
        db = get_firestore_client()
        if not db:
            return None
        
        feedback_ref = db.collection('campaign_feedback').where('user_id', '==', user_id).where('campaign_id', '==', campaign_id)
        feedback_docs = list(feedback_ref.stream())
        
        if feedback_docs:
            return feedback_docs[0].to_dict().get('feedback_type')
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking user feedback: {str(e)}")
        return None

def submit_campaign_feedback(user_id: str, campaign_id: str, feedback_type: str, campaign_creator_id: str) -> bool:
    """Submit feedback for a campaign and update creator's XP"""
    try:
        db = get_firestore_client()
        if not db:
            return False
        
        # Check if user already gave feedback
        existing_feedback = get_user_campaign_feedback(user_id, campaign_id)
        
        # Get campaign reference
        campaign_ref = db.collection('staff_campaigns').document(campaign_id)
        campaign_doc = campaign_ref.get()
        
        if not campaign_doc.exists:
            return False
        
        campaign_data = campaign_doc.to_dict()
        current_likes = campaign_data.get('likes_count', 0)
        current_dislikes = campaign_data.get('dislikes_count', 0)
        
        if existing_feedback:
            # Update existing feedback
            feedback_ref = db.collection('campaign_feedback').where('user_id', '==', user_id).where('campaign_id', '==', campaign_id)
            feedback_docs = list(feedback_ref.stream())
            
            if feedback_docs:
                # Remove old XP effect and update counts
                if existing_feedback == 'like':
                    update_creator_xp(campaign_creator_id, -3)  # Remove old like XP
                    current_likes = max(0, current_likes - 1)
                else:
                    update_creator_xp(campaign_creator_id, 2)   # Remove old dislike penalty
                    current_dislikes = max(0, current_dislikes - 1)
                
                # Update feedback
                feedback_docs[0].reference.update({
                    'feedback_type': feedback_type,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
        else:
            # Create new feedback
            feedback_data = {
                'user_id': user_id,
                'campaign_id': campaign_id,
                'campaign_creator_id': campaign_creator_id,
                'feedback_type': feedback_type,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('campaign_feedback').add(feedback_data)
        
        # Apply new XP change and update counts
        if feedback_type == 'like':
            update_creator_xp(campaign_creator_id, 3)
            current_likes += 1
        else:
            update_creator_xp(campaign_creator_id, -2)
            current_dislikes += 1
        
        # Update campaign document with new counts
        campaign_ref.update({
            'likes_count': current_likes,
            'dislikes_count': current_dislikes,
            'last_feedback_at': firestore.SERVER_TIMESTAMP
        })
        
        logger.info(f"User {user_id} gave {feedback_type} feedback to campaign {campaign_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error submitting campaign feedback: {str(e)}")
        return False

def update_creator_xp(creator_id: str, xp_change: int):
    """Update campaign creator's XP based on feedback"""
    try:
        from modules.leftover import update_user_stats
        
        # Update user stats with XP change
        update_user_stats(creator_id, xp_change)
        
        logger.info(f"Updated creator {creator_id} XP by {xp_change}")
        
    except Exception as e:
        logger.error(f"Error updating creator XP: {str(e)}")

def get_unread_campaigns_count(user_id: str) -> int:
    """Get count of campaigns user hasn't interacted with"""
    try:
        db = get_firestore_client()
        if not db:
            return 0
        
        # Get recent campaigns
        recent_campaigns = get_recent_campaigns(days_back=7)
        
        # Count campaigns user hasn't given feedback on
        unread_count = 0
        for campaign in recent_campaigns:
            # Skip campaigns created by the user themselves
            if campaign.get('created_by_user_id') == user_id:
                continue
                
            user_feedback = get_user_campaign_feedback(user_id, campaign['campaign_id'])
            if user_feedback is None:
                unread_count += 1
        
        return unread_count
        
    except Exception as e:
        logger.error(f"Error getting unread campaigns count: {str(e)}")
        return 0

def render_notifications_page(user_id: str):
    """Render the notifications page with campaign feedback"""
    st.title("📢 Campaign Notifications")
    st.markdown("Review recent marketing campaigns and provide feedback to help improve future campaigns!")
    
    # Get recent campaigns
    campaigns = get_recent_campaigns(days_back=14)  # Show 2 weeks of campaigns
    
    if not campaigns:
        st.info("No recent marketing campaigns to review.")
        return
    
    # Filter out user's own campaigns
    other_campaigns = [c for c in campaigns if c.get('created_by_user_id') != user_id]
    
    if not other_campaigns:
        st.info("No campaigns from other users to review.")
        return
    
    st.markdown(f"### {len(other_campaigns)} Recent Campaigns")
    st.markdown("**Your feedback helps campaign creators improve and earn XP!**")
    st.markdown("👍 **Like** = +3 XP for creator | 👎 **Dislike** = -2 XP for creator")
    
    # Display campaigns
    for i, campaign in enumerate(other_campaigns):
        campaign_id = campaign['campaign_id']
        
        # Get campaign feedback stats
        feedback_stats = get_campaign_feedback(campaign_id)
        user_feedback = get_user_campaign_feedback(user_id, campaign_id)
        
        # Create campaign card
        with st.container():
            st.markdown("---")
            
            # Campaign header
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{campaign.get('campaign_name', 'Untitled Campaign')}**")
                st.caption(f"Created by: {campaign.get('created_by_username', 'Unknown')} | "
                          f"Score: {campaign.get('campaign_score', 'N/A')}")
            
            with col2:
                st.metric("👍 Likes", feedback_stats['likes'])
            
            with col3:
                st.metric("👎 Dislikes", feedback_stats['dislikes'])
            
            # Campaign content
            with st.expander("View Campaign Details", expanded=False):
                st.markdown(f"**Target Audience:** {campaign.get('target_audience', 'Not specified')}")
                st.markdown(f"**Campaign Type:** {campaign.get('campaign_type', 'Not specified')}")
                
                if campaign.get('campaign_content'):
                    st.markdown("**Campaign Content:**")
                    st.write(campaign['campaign_content'])
                
                if campaign.get('special_offers'):
                    st.markdown("**Special Offers:**")
                    st.write(campaign['special_offers'])
                
                # Show creation date
                created_at = campaign.get('created_at')
                if created_at:
                    if hasattr(created_at, 'strftime'):
                        date_str = created_at.strftime("%B %d, %Y at %I:%M %p")
                    else:
                        date_str = str(created_at)
                    st.caption(f"Created: {date_str}")
            
            # Feedback buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                like_button_type = "primary" if user_feedback == "like" else "secondary"
                if st.button("👍 Like", key=f"like_{campaign_id}", type=like_button_type, use_container_width=True):
                    success = submit_campaign_feedback(
                        user_id, 
                        campaign_id, 
                        'like', 
                        campaign.get('created_by_user_id')
                    )
                    if success:
                        st.success("Thanks for your feedback! Creator earned +3 XP")
                        st.rerun()
                    else:
                        st.error("Error submitting feedback")
            
            with col2:
                dislike_button_type = "primary" if user_feedback == "dislike" else "secondary"
                if st.button("👎 Dislike", key=f"dislike_{campaign_id}", type=dislike_button_type, use_container_width=True):
                    success = submit_campaign_feedback(
                        user_id, 
                        campaign_id, 
                        'dislike', 
                        campaign.get('created_by_user_id')
                    )
                    if success:
                        st.warning("Feedback submitted. Creator lost -2 XP")
                        st.rerun()
                    else:
                        st.error("Error submitting feedback")
            
            with col3:
                if user_feedback:
                    feedback_emoji = "👍" if user_feedback == "like" else "👎"
                    st.info(f"Your feedback: {feedback_emoji} {user_feedback.title()}")
                else:
                    st.info("No feedback given yet")

def render_notification_bell(user_id: str):
    """Render notification bell icon with unread count"""
    try:
        unread_count = get_unread_campaigns_count(user_id)
        
        # Create notification bell button
        if unread_count > 0:
            bell_text = f"🔔 ({unread_count})"
            button_type = "primary"
        else:
            bell_text = "🔔"
            button_type = "secondary"
        
        if st.button(bell_text, key="notification_bell", type=button_type, help="View campaign notifications"):
            st.session_state.show_notifications = True
            st.rerun()
            
    except Exception as e:
        logger.error(f"Error rendering notification bell: {str(e)}")
        # Fallback to simple bell
        if st.button("🔔", key="notification_bell_fallback", type="secondary", help="View notifications"):
            st.session_state.show_notifications = True
            st.rerun()
