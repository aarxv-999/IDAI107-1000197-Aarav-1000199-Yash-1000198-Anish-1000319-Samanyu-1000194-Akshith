'''
MAIN APP FILE for the Smart Restaurant Menu Management App
This combines all UI components and logic functions from all modules to create a complete working Streamlit interface 
'''

import streamlit as st
from ui.components import ( # importing all ui functions from the folder 
    leftover_input_csv, leftover_input_manual,
)
from modules.leftover import suggest_recipes # importing all logic functions from the module folder

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

        leftovers_csv = leftover_input_csv() # inputting leftovers fromcsv
        leftovers_manual = leftover_input_manual() #inputting leftovers manually
        leftovers = leftovers_csv or leftovers_manual # main leftovers based on what the user picks

        if leftovers:
            max_suggestions = st.slider("How many recipes do you want?", 1, 3, 5)
            if st.button("Generate Recipes"):
                suggestions = suggest_recipes(leftovers, max_suggestions)
                if suggestions:
                    st.markdown("Recipe Suggestions:")
                    for i, recipe in enumerate(suggestions, 1):
                        st.write(f"{i}. {recipe}")
                else:
                    st.warning("No recipes could be generated. Try different ingredients.")
        else:
            st.info("Please upload or enter some leftover ingredients to continue.")

if __name__ == "__main__":
    main()
