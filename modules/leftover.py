'''
MADE BY: Aarav Agarwal, IBCP CRS: AI, WACP ID: 1000197
This file will serve as the functionality for the leftovermanagement feature

Packages used: 
- pandas: to read CSV files
- google.generativeai to add gemini APi
'''

import pandas as pd  
from typing import List, Optional 
import random 
import os
import google.generativeai as genai
import logging

# Set up logging to help with debugging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# primarily used exception handling in this code ! 

def load_leftovers(csv_path: str) -> List[str]:
    '''
    ARGUMENT - loading all leftover ingredients from a csv file (if it exists)
    csv_path (str) is the path to the csv file containing the ingredients & should have a column named "ingredients"
    
    RETURN -  List[str]: a list of names of all leftover ingredients
    
    RAISES -  if FileNotFoundError occurs then it means that the csv file does not exist. if "ValueError" occurs then that means thtat the CSV file doesnt have ingredients column
    '''
    logging.info(f"Attempting to load leftovers from: {csv_path}")
    try:
        df = pd.read_csv(csv_path) # reading the Csv file
        logging.info(f"CSV columns: {df.columns.tolist()}")
        
        # Check for both 'ingredient' and 'ingredients' columns (common mistake)
        if 'ingredient' in df.columns:
            column_name = 'ingredient'
        elif 'ingredients' in df.columns:
            column_name = 'ingredients'
            logging.info("Using 'ingredients' column instead of 'ingredient'")
        else:
            raise ValueError("CSV file must have an 'ingredient' column") 
            
        ingredients = df[column_name].tolist() # getting all values in the "ingredient" column in list format if it is there 
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)] # imputing empty values and white space in every value of the list
        logging.info(f"Successfully loaded {len(ingredients)} ingredients: {ingredients}")
        return ingredients
    except FileNotFoundError: # as previously mentioned in the first comment, considering the case where the csv file is not there at the path 
        logging.error(f"CSV file unavailable at: {csv_path}")
        raise FileNotFoundError(f"CSV file unavailable at: {csv_path}")
    except Exception as e: # consider any other exceptions in loading the csv file. this is a general exception handler in case any other errors are found
        logging.error(f"Faced error in loading leftovers from CSV: {str(e)}")
        raise Exception(f"Faced error in loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]: 
    '''
    parses the manually entered list 
    
    ARGUMENT - input_text (str), which is the manually entered ingredients with each being separated by a , 
    RETURN - List[str], a list of leftover ingredient names where it is properly organized 
    '''
    logging.info(f"Parsing manual leftover input: {input_text}")
    ingredients = input_text.split(',') #splittingall input texts by a comma. 
    ingredients = [ing.strip() for ing in ingredients if ing.strip()] # imputing empty values and white space in every ingredient of the list
    logging.info(f"Parsed {len(ingredients)} ingredients: {ingredients}")
    return ingredients

def suggest_recipes(leftovers: List[str], max_suggestions: int = 3) -> List[str]:
    '''
    this function will suggest recipes based on the leftover ingredients which we got previously
    
    ARGUMENT - 
    leftovers (List[str]), list of the leftover ingredients (whether via the csv file or manually entered)
    max_suggestions (int, optional): maximum number of recipe suggestions to output
    
    RETURN - List[str] of all recipes
    '''
    logging.info(f"Suggesting recipes for leftovers: {leftovers}, max_suggestions: {max_suggestions}")
    
    #first checking if we have any leftovers to work with, if there are no leftovers then an empty list will be returned
    if not leftovers:
        logging.warning("No leftovers provided to generate recipes")
        return []
    
    # Default to basic recipes if no API is available or fails
    basic_recipes = [
        f"Simple {leftovers[0].capitalize()} Dish" if leftovers else "Simple Dish",
        "Quick Stir Fry",
        "Leftover Soup",
        "Mixed Ingredient Salad",
        "One-Pot Casserole"
    ]
    
    # implementing gemini api for the recipe suggestions
    try:
        api_key = os.environ.get("GEMINI_API_KEY") # searching the environment set by the user to find the variable for the api key 
        
        # Debug: Check if API key exists
        if api_key:
            logging.info("Found Gemini API key")
        else:
            logging.warning("GEMINI_API_KEY environment variable not found - using fallback recipes")
            return basic_recipes[:max_suggestions]
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro') # initializing gemini 1.5 pro as required by the capstone brief.
        
        ingredients_list = ", ".join(leftovers) 
        prompt = f'''
        Here are the leftover ingredients I have: {ingredients_list}.
        
        I need you to suggest {max_suggestions} creative and unique recipe ideas that use these ingredients to avoid any food waste

        For each recipe, provide just the recipe name. Don't include ingredients list or instructions, just keep it very simple and minimalistic in the output
        Format each recipe as "Recipe Name"
        Keep the recipes simple and focused on using the leftover ingredients
        ''' 
        # used chatgpt to generate prompt, made some changes afterwards as required.
        
        logging.info("Sending request to Gemini API")
        response = model.generate_content(prompt) # getting gemini's response from the prompt
        
        response_text = response.text # extracting recipes from list
        logging.info(f"Received response from Gemini API: {response_text}")
        
        recipe_lines = [line.strip() for line in response_text.split('\n') if line.strip()] # splitting the response into cleaning it 
        logging.info(f"Extracted recipe lines: {recipe_lines}")
        
        # this part of the code is required to turn geminis responses into a proper list which can later be used to properly display it 
        recipes = [] 
        for line in recipe_lines:
            # Handle various formatting patterns from Gemini
            if line.startswith('"') and line.endswith('"'):
                # Handle quoted recipe names
                line = line.strip('"')
                recipes.append(line)
            elif line[0].isdigit() and len(line) > 2:
                # Handle numbered lists (1. Recipe, 2. Recipe, etc.)
                if line[1:].startswith('. ') or line[1:].startswith(') ') or line[1:].startswith('- '):
                    line = line[3:].strip()
                    recipes.append(line)
                else:
                    # Just a recipe that starts with a number
                    recipes.append(line)
            else:
                # Just add the recipe as is
                recipes.append(line)
        
        logging.info(f"Processed recipes before limiting: {recipes}")
        
        # ensuring that only the required number of suggestions are included in the list 
        recipes = recipes[:max_suggestions]
        logging.info(f"Final recipes to return: {recipes}")
        
        # Use basic recipes if API returned nothing
        if not recipes:
            logging.warning("No recipes extracted from API response, using fallback recipes")
            return basic_recipes[:max_suggestions]
            
        # Return the recipes list
        return recipes
        
    except Exception as e:
        # If there's an error with the API, fall back to basic recipes
        logging.error(f"Error using Gemini API: {str(e)}")
        
        # Always return something useful, even in error cases
        return basic_recipes[:max_suggestions]

'''
How to use this module:

1. Activate a Python virtual environment:
   - On Windows: venv\Scripts\activate
   - On macOS/Linux: source venv/bin/activate

2. Install required packages:
   pip install pandas google-generativeai

3. Set up your Gemini API key as an environment variable:
   - On Windows: set GEMINI_API_KEY=your_api_key_here
   - On macOS/Linux: export GEMINI_API_KEY=your_api_key_here

4. Import and use in your code:
   from modules.leftover import load_leftovers, suggest_recipes
'''
