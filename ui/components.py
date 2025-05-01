# UI component for the smart restaurant menu management app which will have all required widges and components which is required in the project

import streamlit as st
from typing import List, Dict, Any, Tuple, Optional

# importing all logic functions from the modules
from modules.leftover import load_leftovers, parse_manual_leftovers, suggest_recipes

def leftover_input_csv() -> List[str]:
    """
    Renders UI for uploading a CSV file containing leftover ingredients.
    adding the ui to upload csv file with all leftover ingredients 
    RETURN - List[str]: a list of leftover ingredients in the list format 
    """
    st.sidebar.header("Leftover Management - CSV Upload")
    use_csv = st.sidebar.checkbox("Upload leftovers from CSV", value=False,
                                 help="Enable to upload a CSV file with leftover ingredients")
    
    leftovers = []    
    if use_csv:
        uploaded_file = st.sidebar.file_uploader( # <- this is to have file uploader for leftover csv file.
            "Upload leftover ingredient CSV file", 
            type=["csv"],
            help="CSV needs to  have a column with ingredient names"
        )

        if uploaded_file is not None:
            try:
                leftovers = load_leftovers(uploaded_file) # Using the load leftover function from the module to turn the csv into a list 
                st.sidebar.success(f"Successfully loaded {len(leftovers)} ingredients")
            except Exception as err: # error handling 
                st.sidebar.error(f"Faced an error loading CSV: {str(err)}")
                st.sidebar.info("Please make sure your CSV has the correct format!")
    return leftovers


def leftover_input_manual() -> List[str]:
    """
    creating the UI to manually input leftover ingredients
    RETURN - List[str]: a list of leftover ingredients whic h were entered by the user
    """
    st.sidebar.header("Leftover Management - Manual Entry")
    ingredients_text = st.sidebar.text_area( # <-- Text area to manusally input the ingredients
        "Enter leftover ingredients (comma-separated)",
        placeholder="tomatoes, onions, chicken, rice",
        help="Type your ingredients separated by commas"
    )
    
    leftovers = []
    if ingredients_text:
        try:
            leftovers = parse_manual_leftovers(ingredients_text) # calling manual leftover parsing function
            st.sidebar.success(f"Parsed {len(leftovers)} ingredients")
        except Exception as err:
            st.sidebar.error(f"Error parsing ingredients: {str(err)}")
    return leftovers
