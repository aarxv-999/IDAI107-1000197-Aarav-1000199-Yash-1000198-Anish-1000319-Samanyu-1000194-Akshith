import streamlit as st
from modules.event_planner import event_planner, init_event_firebase

def integrate_event_planner():
    init_event_firebase()
    event_planner()

def check_event_firebase_config():
    if "event_firebase" not in st.secrets:
        st.error("Missing event firebase configuration.")
        return False
    return True
