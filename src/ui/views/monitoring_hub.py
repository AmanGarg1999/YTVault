import streamlit as st
import json
import logging
from src.ui.components import (
    page_header,
    section_header,
    glass_card,
    info_card,
    success_card,
    spacer
)
from src.intelligence.live_monitor import LiveMonitor

logger = logging.getLogger(__name__)

def render(db):
    """Render the Monitoring Hub for channel subscriptions and briefs."""
    page_header(
        "Monitoring Hub",
        "Strategic channel follows and automated intelligence briefings."
    )

    monitor = LiveMonitor(db)

    # Tabs: Subscriptions, Weekly Briefs
    tab_subs, tab_briefs = st.tabs(["Followed Channels", "Intelligence Briefs"])

    with tab_subs:
        render_subscriptions(db, monitor)

    with tab_briefs:
        render_briefs(db, monitor)

def render_subscriptions(db, monitor):
    section_header("Active Subscriptions", icon="📡")
    
    # Add new subscription
    with glass_card():
        col1, col2 = st.columns([3, 1])
        new_url = col1.text_input("Follow New Channel URL", placeholder="https://youtube.com/@channel...")
        if col2.button("Follow", type="primary", use_container_width=True):
            if new_url:
                with st.spinner("Subscribing..."):
                    if monitor.follow_channel(new_url):
                        st.success(f"Now following {new_url}")
                        st.rerun()
                    else:
                        st.error("Failed to follow channel. Ensure it is a valid YouTube channel URL.")

    spacer("2rem")
    
    monitored = db.get_monitored_channels()
    if not monitored:
        info_card("No Subscriptions", "Follow a channel to begin receiving automated briefings.")
        return

    for m in monitored:
        channel = db.get_channel(m.channel_id)
        channel_name = channel.name if channel else m.channel_id
        
        with glass_card():
            cols = st.columns([1, 4, 1])
            if channel and channel.thumbnail_url:
                cols[0].image(channel.thumbnail_url, width=60)
            
            with cols[1]:
                st.markdown(f"**{channel_name}**")
                st.caption(f"Last Brief: {m.last_brief_at or 'Never'}")
            
            if cols[2].button("Unfollow", key=f"unsub_{m.channel_id}"):
                monitor.unfollow_channel(m.channel_id)
                st.toast(f"Unfollowed {channel_name}")
                st.rerun()

def render_briefs(db, monitor):
    section_header("Weekly Intelligence Briefs", icon="◈")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Generate Brief Now", type="primary", use_container_width=True):
            with st.spinner("Scanning for new content..."):
                brief = monitor.run_subscriptions_check()
                if brief:
                    st.success("New Weekly Brief generated!")
                    st.rerun()
                else:
                    st.info("No new content found to brief Since last check.")

    briefs = db.get_weekly_briefs()
    if not briefs:
        info_card("No Briefs Yet", "Generated briefs will appear here after new content is discovered.")
        return

    for brief in briefs:
        with st.expander(f"Intelligence Brief - {brief.created_at}", expanded=brief == briefs[0]):
            st.markdown(brief.content)
            
            try:
                channel_ids = json.loads(brief.channel_ids_json)
                st.divider()
                st.caption(f"Sources: {', '.join(channel_ids)}")
            except:
                pass
