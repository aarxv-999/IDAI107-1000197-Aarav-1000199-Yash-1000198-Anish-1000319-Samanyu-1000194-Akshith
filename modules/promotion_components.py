"""
Promotion Campaign UI Components for the Smart Restaurant Menu Management App.
Integrated into the existing component structure.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from modules.promotion_services import (
    get_promotion_firebase_db, filter_valid_ingredients, find_possible_dishes,
    generate_campaign, save_campaign, get_existing_campaign, get_campaigns_for_month
)
import logging

logger = logging.getLogger(__name__)

def render_promotion_generator():
    """Main function to render Promotion Generator with tabs"""
    st.title("📣 AI Marketing Campaign Generator")
    
    # Get current user for role-based access
    user = st.session_state.get('user', {})
    user_role = user.get('role', 'user')
    staff_name = user.get('username', 'Unknown User')
    
    # Check access permissions - ONLY Admin and Staff
    if user_role not in ['staff', 'admin']:
        st.warning("⚠️ You don't have access to the Marketing Campaign Generator. This feature is available for Staff and Administrators only.")
        return
    
    # Create tabs - no admin panel needed since scoring is automatic
    tabs = st.tabs(["📝 Submit Campaign", "🏆 Leaderboard"])
    
    # Initialize database connection
    db = get_promotion_firebase_db()
    if not db:
        st.error("❌ Database connection failed. Please check your configuration.")
        return
    
    # Render tabs
    with tabs[0]:
        render_campaign_submission(db, staff_name)
    with tabs[1]:
        render_leaderboard(db)

def render_campaign_submission(db, staff_name):
    """Render the campaign submission form"""
    st.markdown("### 📝 Submit Your Marketing Campaign")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    # Information box
    st.info("""
    **How it works:**
    1. Enter your campaign preferences below
    2. AI will generate a personalized campaign based on available inventory
    3. Your campaign will be automatically submitted and scored
    4. Check the leaderboard to see your AI score!
    """)
    
    # Check if user already submitted
    existing_campaign = get_existing_campaign(db, staff_name)
    
    if existing_campaign:
        st.warning(f"⚠️ **Campaign Already Submitted for {month_name}**")
    
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Submitted on:** {existing_campaign.get('timestamp', 'Unknown date')}")
            st.write(f"**Campaign Type:** {existing_campaign.get('promotion_type', 'N/A')}")
        with col2:
            if 'ai_score' in existing_campaign:
                st.success(f"🎯 **AI Score:** {existing_campaign['ai_score']}/10")
            else:
                st.info("⏳ Score processing...")
    
        # Show existing campaign
        with st.expander("👀 View Your Submitted Campaign"):
            st.write("**Campaign Content:**")
            st.text_area("", existing_campaign.get('campaign', 'No campaign content found'), 
                        height=200, disabled=True, key="existing_campaign_display")
    
        return
    
    # Campaign submission form
    st.markdown(f"#### 📅 Campaign Submission for {month_name}")
    
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
        
        submitted = st.form_submit_button("🚀 Generate and Submit Campaign", type="primary")
        
        if submitted:
            generate_and_submit_campaign(
                db, staff_name, promotion_type, promotion_goal, 
                target_audience, campaign_duration
            )

def generate_and_submit_campaign(db, staff_name, promotion_type, promotion_goal, target_audience, campaign_duration):
    """Generate and submit a new campaign with automatic AI scoring"""
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
            
            # Save campaign data (with automatic scoring)
            campaign_data = {
                "name": staff_name,
                "campaign": campaign,
                "promotion_type": promotion_type,
                "goal": promotion_goal,
                "target_audience": target_audience,
                "campaign_duration": campaign_duration
            }
            
            success, ai_score = save_campaign(db, staff_name, campaign_data)
            
            if success:
                # Success message with automatic score
                st.success("🎉 **Campaign Successfully Submitted & Scored!**")
                if ai_score:
                    st.info(f"🎯 **Your AI Score:** {ai_score}/10")
                
                st.info("""
                **What happened:**
                - Your campaign was generated using available inventory
                - AI automatically scored your campaign
                - Check the leaderboard to see your ranking!
                """)
                
                # Display generated campaign
                st.markdown("#### 📢 Your Generated Campaign")
                st.write(f"**Campaign by:** {staff_name}")
                st.write(f"**Type:** {promotion_type} | **Goal:** {promotion_goal}")
                if ai_score:
                    st.write(f"**AI Score:** {ai_score}/10")
                st.markdown("---")
                st.write(campaign)
                
                # Quick actions (no buttons in form context)
                st.info("💡 **Tip:** Switch to the Leaderboard tab to view current rankings!")
                st.code(campaign, language=None)
            else:
                st.error("❌ Failed to save campaign. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in campaign generation: {str(e)}")
            st.error(f"❌ Failed to generate campaign: {str(e)}")

def render_leaderboard(db):
    """Render the campaign leaderboard"""
    st.markdown("### 🏆 AI Campaign Leaderboard")
    
    current_month = datetime.now().strftime("%Y-%m")
    month_name = datetime.now().strftime("%B %Y")
    
    # Load campaigns with scores
    with st.spinner('Loading campaign data...'):
        all_campaigns = get_campaigns_for_month(db, current_month)
        scored_campaigns = [c for c in all_campaigns if "ai_score" in c]
    
    if not scored_campaigns:
        st.info(f"""
        **📊 No Scored Campaigns**
        
        No campaigns have been scored for {month_name}.
        Submit a campaign to get started!
        """)
        return
    
    # Create DataFrame and sort by score
    df = pd.DataFrame(scored_campaigns)
    df = df.sort_values(by="ai_score", ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Campaigns", len(df))
    with col2:
        st.metric("Average Score", f"{df['ai_score'].mean():.1f}/10")
    with col3:
        st.metric("Top Score", f"{df['ai_score'].max():.1f}/10")
    with col4:
        st.metric("Month", month_name)
    
    # Winner highlight
    top_performer = df.iloc[0]
    st.success(f"""
    **🥇 Top Performer: {top_performer['name']}**
    
    **Score:** {top_performer['ai_score']}/10  
    **Campaign Type:** {top_performer['promotion_type']}
    """)
    
    # Score distribution chart
    st.markdown("#### 📈 Score Distribution")
    fig = px.bar(
        df,
        x='name',
        y='ai_score',
        color='ai_score',
        color_continuous_scale='Blues',
        title="Campaign Scores by Staff Member"
    )
    fig.update_layout(
        xaxis_title="Staff Member",
        yaxis_title="AI Score",
        showlegend=False,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Leaderboard table
    st.markdown("#### 🏅 Detailed Rankings")
    
    # Prepare display dataframe
    display_df = df[["rank", "name", "promotion_type", "goal", "ai_score"]].copy()
    display_df.columns = ["Rank", "Staff Name", "Promotion Type", "Goal", "Score"]
    display_df["Score"] = display_df["Score"].apply(lambda x: f"{x}/10")
    
    # Add rank emojis
    rank_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
    display_df["Rank"] = display_df["Rank"].apply(lambda x: f"{rank_emojis.get(x, '🏅')} {x}")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Export section
    st.markdown("#### 📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📊 Download Full Data (CSV)",
            data=csv,
            file_name=f"campaign_leaderboard_{current_month}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        summary_data = {
            "Month": [month_name],
            "Total Campaigns": [len(df)],
            "Winner": [top_performer['name']],
            "Top Score": [f"{top_performer['ai_score']}/10"],
            "Average Score": [f"{df['ai_score'].mean():.1f}/10"]
        }
        summary_csv = pd.DataFrame(summary_data).to_csv(index=False)
        st.download_button(
            label="📋 Download Summary (CSV)",
            data=summary_csv,
            file_name=f"campaign_summary_{current_month}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # Campaign details section
    st.markdown("#### 📝 Campaign Details")
    selected_staff = st.selectbox(
        "Select staff member to view their campaign:",
        options=df['name'].tolist()
    )
    
    if selected_staff:
        staff_campaign = df[df['name'] == selected_staff].iloc[0]
        
        st.markdown(f"**Campaign by:** {staff_campaign['name']}")
        st.markdown(f"**Score:** {staff_campaign['ai_score']}/10")
        st.markdown(f"**Type:** {staff_campaign['promotion_type']} | **Goal:** {staff_campaign['goal']}")
        st.markdown("---")
        st.write(staff_campaign['campaign'])
