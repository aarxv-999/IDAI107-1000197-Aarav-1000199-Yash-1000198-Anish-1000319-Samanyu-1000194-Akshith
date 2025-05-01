'''
MAIN APP FILE for the Smart Restaurant Menu Management App
This combines all UI components and logic functions from all modules to create a complete working Streamlit interface
'''
import streamlit as st
from ui.components import ( # importing all ui functions from the folder
    leftover_input_csv, leftover_input_manual,
)
from modules.leftover import suggest_recipes # importing all logic functions from the module folder
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# main function
def main():
    st.set_page_config(page_title="Smart Restaurant Menu Management", layout="wide")
    st.title("🍽️ Smart Restaurant Menu Management System")
    st.markdown("""
    Welcome to the AI-powered smart restaurant system!
    Please select a feature from the sidebar to begin.
    """)
    
    feature = st.sidebar.selectbox( # feature selection
        "Choose a Feature",
        options=[
            "Leftover Management",
            "Event Planning ChatBot",
            "Promotion Generator",
            "Chef Recipe Suggestions",
            "Visual Menu Search"
        ]
    )
    
    st.divider()
    
    if feature == "Leftover Management":
        st.subheader("♻️ Leftover Management")
        
        # Debug UI state
        leftovers_csv = leftover_input_csv() # inputting leftovers from csv
        logging.info(f"Leftovers from CSV: {leftovers_csv}")
        
        leftovers_manual = leftover_input_manual() # inputting leftovers manually
        logging.info(f"Leftovers from manual entry: {leftovers_manual}")
        
        # Use the leftovers from either source
        leftovers = leftovers_csv or leftovers_manual # main leftovers based on what the user picks
        logging.info(f"Final leftovers list: {leftovers}")
        
        if leftovers:
            st.success(f"Working with these ingredients: {', '.join(leftovers)}")
            
            max_suggestions = st.slider("How many recipes do you want?", 1, 5, 3)
            logging.info(f"User requested {max_suggestions} recipes")
            
            if st.button("Generate Recipes"):
                with st.spinner("Generating recipe suggestions..."):
                    try:
                        logging.info("Calling suggest_recipes function...")
                        suggestions = suggest_recipes(leftovers, max_suggestions)
                        logging.info(f"Received suggestions: {suggestions}")
                        
                        if suggestions and len(suggestions) > 0:
                            st.markdown("### Recipe Suggestions:")
                            for i, recipe in enumerate(suggestions, 1):
                                st.write(f"{i}. {recipe}")
                        else:
                            st.warning("No recipes could be generated. Try different ingredients.")
                            logging.warning(f"No recipes returned for ingredients: {leftovers}")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        logging.error(f"Error in recipe generation: {str(e)}")
        else:
            st.info("Please upload or enter some leftover ingredients to continue.")
            
if __name__ == "__main__":
    main()
