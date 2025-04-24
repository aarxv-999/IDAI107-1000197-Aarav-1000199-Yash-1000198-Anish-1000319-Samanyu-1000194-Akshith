# aarav
import streamlit as st

def show_leaderboard(data: dict):
    """TODO: display a leaderboard widget."""
    st.write("Leaderboard placeholder", data)

def upload_image_widget():
    """TODO: image uploader widget."""
    return st.file_uploader("Upload a dish image")
