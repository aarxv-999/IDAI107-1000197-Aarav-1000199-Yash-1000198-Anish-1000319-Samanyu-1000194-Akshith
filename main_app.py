#aarav
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()
st.set_page_config(page_title="Smart Restaurant")

feature = st.sidebar.selectbox("Feature", [
    "Recipe", "Leftover", "Promotions", "Event", "Visual Search"
])

st.write("Select a feature to get started.")
