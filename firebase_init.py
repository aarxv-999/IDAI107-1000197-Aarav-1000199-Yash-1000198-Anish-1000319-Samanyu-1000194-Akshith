import firebase_admin
from firebase_admin import credentials
import streamlit as st
import json

def init_firebase():
    if not firebase_admin._apps:
        try:
            with open("firebase_cred.json") as f:
                config_dict = json.load(f)
            cred = credentials.Certificate(config_dict)
            firebase_admin.initialize_app(cred)
            return True
        except Exception as e:
            st.error(f"Couldn't initialize Main firebase {str(e)}")
            return False
    return True