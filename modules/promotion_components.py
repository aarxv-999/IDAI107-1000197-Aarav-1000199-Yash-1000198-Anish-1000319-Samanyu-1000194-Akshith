import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import streamlit as st
import os
from datetime import datetime

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)

db = firestore.client()

def generate_promotion_content(campaign_name, target_audience, campaign_type, product_details, special_offers):
    """
    Generates promotional content based on the provided parameters.
    This is a placeholder function; replace with actual content generation logic.
    """
    content = f"Campaign Name: {campaign_name}\n"
    content += f"Target Audience: {target_audience}\n"
    content += f"Campaign Type: {campaign_type}\n"
    content += f"Product Details: {product_details}\n"
    content += f"Special Offers: {special_offers}\n"
    content += "This is a sample promotional content. Please replace with your actual content generation logic."
    return content

def calculate_campaign_score(target_audience, campaign_type, special_offers):
    """
    Calculates a score for the campaign based on the provided parameters.
    This is a placeholder function; replace with actual scoring logic.
    """
    score = 0
    if "discount" in special_offers.lower():
        score += 5
    if target_audience == "new customers":
        score += 3
    if campaign_type == "email":
        score += 2
    return score

def save_campaign(campaign_name, target_audience, campaign_type, generated_content, special_offers, score, user):
    """
    Saves the campaign data to Firestore in staff_campaigns collection with XP tracking fields.
    """
    campaign_data = {
        'campaign_name': campaign_name,
        'target_audience': target_audience,
        'campaign_type': campaign_type,
        'campaign_content': generated_content,
        'special_offers': special_offers,
        'campaign_score': score,
        'created_by_user_id': user['user_id'],
        'created_by_username': user['username'],
        'created_at': firestore.SERVER_TIMESTAMP,
        'likes_count': 0,  # Initialize likes count
        'dislikes_count': 0,  # Initialize dislikes count
        'last_feedback_at': None  # Track when last feedback was received
    }

    # Add the campaign data to staff_campaigns collection
    doc_ref = db.collection('staff_campaigns').add(campaign_data)
    return True

def render_promotion_generator(user):
    """
    Renders the promotion generator interface for staff and admin users.
    """
    st.title("📢 Promotion Generator")
    st.markdown("Create AI-powered marketing campaigns with automatic scoring and analytics!")
    
    # Check user permissions
    if user['role'] not in ['admin', 'staff']:
        st.error("Access denied. Only admin and staff users can access the Promotion Generator.")
        return
    
    # Campaign creation form
    st.subheader("Create New Campaign")
    
    with st.form("campaign_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            campaign_name = st.text_input(
                "Campaign Name *",
                placeholder="Enter campaign name",
                help="A catchy name for your marketing campaign"
            )
            
            target_audience = st.selectbox(
                "Target Audience *",
                ["new customers", "existing customers", "families", "young adults", "seniors", "business clients"],
                help="Select the primary audience for this campaign"
            )
            
            campaign_type = st.selectbox(
                "Campaign Type *",
                ["email", "social media", "print", "radio", "tv", "online ads"],
                help="Choose the medium for your campaign"
            )
        
        with col2:
            product_details = st.text_area(
                "Product/Service Details *",
                placeholder="Describe the products or services being promoted",
                help="Provide details about what you're promoting",
                height=100
            )
            
            special_offers = st.text_area(
                "Special Offers *",
                placeholder="Describe any discounts, deals, or special offers",
                help="Include any promotional offers or incentives",
                height=100
            )
        
        # Additional campaign options
        st.markdown("### Additional Options")
        
        col1, col2 = st.columns(2)
        with col1:
            campaign_duration = st.selectbox(
                "Campaign Duration",
                ["1 week", "2 weeks", "1 month", "2 months", "3 months", "ongoing"],
                help="How long will this campaign run?"
            )
        
        with col2:
            budget_range = st.selectbox(
                "Budget Range",
                ["Under $500", "$500-$1000", "$1000-$5000", "$5000-$10000", "Over $10000"],
                help="Estimated budget for this campaign"
            )
        
        # Submit button
        submitted = st.form_submit_button("Generate Campaign", type="primary", use_container_width=True)
        
        if submitted:
            # Validation
            if not all([campaign_name, target_audience, campaign_type, product_details, special_offers]):
                st.error("Please fill in all required fields marked with *")
            else:
                with st.spinner("Generating your marketing campaign..."):
                    try:
                        # Generate campaign content
                        generated_content = generate_promotion_content(
                            campaign_name, target_audience, campaign_type, 
                            product_details, special_offers
                        )
                        
                        # Calculate campaign score
                        score = calculate_campaign_score(target_audience, campaign_type, special_offers)
                        
                        # Save campaign to database
                        success = save_campaign(
                            campaign_name, target_audience, campaign_type,
                            generated_content, special_offers, score, user
                        )
                        
                        if success:
                            st.success("Campaign generated and saved successfully!")
                            
                            # Display generated campaign
                            st.subheader("Generated Campaign")
                            
                            # Campaign metrics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Campaign Score", f"{score}/10")
                            with col2:
                                st.metric("Target Audience", target_audience.title())
                            with col3:
                                st.metric("Campaign Type", campaign_type.title())
                            
                            # Campaign content
                            with st.expander("Campaign Content", expanded=True):
                                st.markdown("**Generated Content:**")
                                st.write(generated_content)
                                
                                st.markdown("**Campaign Details:**")
                                st.write(f"**Duration:** {campaign_duration}")
                                st.write(f"**Budget:** {budget_range}")
                                st.write(f"**Created by:** {user['username']}")
                                st.write(f"**Created on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            # Campaign tips
                            st.markdown("### Campaign Tips")
                            if score < 5:
                                st.warning("**Low Score Campaign** - Consider adding more compelling offers or targeting a more specific audience.")
                            elif score < 8:
                                st.info("**Good Campaign** - This campaign has potential. Consider A/B testing different versions.")
                            else:
                                st.success("**Excellent Campaign** - This campaign is well-targeted and should perform well!")
                            
                        else:
                            st.error("Failed to save campaign. Please try again.")
                            
                    except Exception as e:
                        st.error(f"Error generating campaign: {str(e)}")
    
    # Campaign history section
    st.markdown("---")
    st.subheader("Your Campaign History")
    
    try:
        # Fetch user's campaigns from staff_campaigns collection
        campaigns_ref = db.collection('staff_campaigns').where('created_by_user_id', '==', user['user_id'])
        campaigns = campaigns_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(10).stream()
        
        campaign_list = []
        for doc in campaigns:
            campaign_data = doc.to_dict()
            campaign_data['id'] = doc.id
            campaign_list.append(campaign_data)
        
        if campaign_list:
            for i, campaign in enumerate(campaign_list):
                with st.expander(f"{campaign.get('campaign_name', 'Untitled')} - Score: {campaign.get('campaign_score', 0)}/10"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Target Audience:** {campaign.get('target_audience', 'N/A')}")
                        st.write(f"**Campaign Type:** {campaign.get('campaign_type', 'N/A')}")
                        st.write(f"**Score:** {campaign.get('campaign_score', 0)}/10")
                    
                    with col2:
                        # Display feedback metrics
                        likes_count = campaign.get('likes_count', 0)
                        dislikes_count = campaign.get('dislikes_count', 0)
                        total_feedback = likes_count + dislikes_count
                        
                        st.metric("👍 Likes", likes_count)
                        st.metric("👎 Dislikes", dislikes_count)
                        st.metric("Total Feedback", total_feedback)
                    
                    if campaign.get('campaign_content'):
                        st.markdown("**Content:**")
                        st.text(campaign['campaign_content'])
                    
                    # Show creation date
                    created_at = campaign.get('created_at')
                    if created_at:
                        if hasattr(created_at, 'strftime'):
                            date_str = created_at.strftime("%B %d, %Y at %I:%M %p")
                        else:
                            date_str = str(created_at)
                        st.caption(f"Created: {date_str}")
        else:
            st.info("No campaigns created yet. Create your first campaign above!")
            
    except Exception as e:
        st.error(f"Error loading campaign history: {str(e)}")
    
    # Campaign analytics section
    st.markdown("---")
    st.subheader("Campaign Analytics")
    
    if campaign_list:
        # Calculate analytics
        total_campaigns = len(campaign_list)
        avg_score = sum(c.get('campaign_score', 0) for c in campaign_list) / total_campaigns if total_campaigns > 0 else 0
        total_likes = sum(c.get('likes_count', 0) for c in campaign_list)
        total_dislikes = sum(c.get('dislikes_count', 0) for c in campaign_list)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Campaigns", total_campaigns)
        with col2:
            st.metric("Average Score", f"{avg_score:.1f}/10")
        with col3:
            st.metric("Total Likes", total_likes)
        with col4:
            st.metric("Total Dislikes", total_dislikes)
        
        # Performance insights
        st.markdown("### Performance Insights")
        
        if avg_score >= 7:
            st.success("🎉 Excellent performance! Your campaigns are well-targeted and engaging.")
        elif avg_score >= 5:
            st.info("📈 Good performance! Consider experimenting with different offers and targeting.")
        else:
            st.warning("📊 Room for improvement. Focus on more specific targeting and compelling offers.")
        
        # Feedback ratio
        if total_likes + total_dislikes > 0:
            like_ratio = (total_likes / (total_likes + total_dislikes)) * 100
            st.write(f"**Feedback Ratio:** {like_ratio:.1f}% positive feedback")
            
            if like_ratio >= 70:
                st.success("Great job! Your campaigns are well-received by the community.")
            elif like_ratio >= 50:
                st.info("Your campaigns have mixed reception. Consider gathering more specific feedback.")
            else:
                st.warning("Your campaigns need improvement. Focus on audience needs and value proposition.")
    else:
        st.info("Create some campaigns to see analytics!")
