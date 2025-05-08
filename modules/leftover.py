'''
MADE BY: Aarav Agarwal, IBCP CRS: AI, WACP ID: 1000197
This file will serve as the functionality for the leftovermanagement feature

Packages used: 
- pandas: to read CSV files
- google.generativeai to add gemini APi
'''

import pandas as pd  
from typing import List, Optional  
import os
import google.generativeai as genai  
import logging # adding on may 8 for debugging. constantly facing issues w code
import openai

# primarily used exception handling in this code ! 

def load_leftovers(csv_path: str) -> List[str]:
    '''
    ARGUMENT - loading all leftover ingredients from a csv file (if it exists)
    csv_path (str) is the path to the csv file containing the ingredients & should have a column named "ingredients"
    
    RETURN -  List[str]: a list of names of all leftover ingredients
    
    RAISES -  if FileNotFoundError occurs then it means that the csv file does not exist. if "ValueError" occurs then that means thtat the CSV file doesnt have ingredients column
    '''
    try:
        df = pd.read_csv(csv_path) # reading the Csv file
        if 'ingredient' not in df.columns: # checking if ingredient column is oresent in the csv
            raise ValueError("CSV file must have an 'ingredient' column") # if column not there , raising a ValueError, which is a exception type for errors which depends on the value of the argument
        ingredients = df['ingredient'].tolist() # getting all values in the "ingredient" column in list format if it is there 
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)] # imputing empty values and white space in every value of the list 
        return ingredients
    except FileNotFoundError: # as previously mentioned in the first comment, considering the case where the csv file is not there at the path 
        raise FileNotFoundError(f" CSV file unavailable at: {csv_path}")
    except Exception as e: # consider any other exceptions in loading the csv file. this is a general exception handler in case any other errors are found
        raise Exception(f"Faced error in loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]: 
    '''
    parses the manually entered list 
    
    ARGUMENT - input_text (str), which is the manually entered ingredients with each being separated by a , 
    RETURN - List[str], a list of leftover ingredient names where it is properly organized 
    '''
    ingredients = input_text.split(',') #splittingall input texts by a comma. 
    ingredients = [ing.strip() for ing in ingredients if ing.strip()] # imputing empty values and white space in every ingredient of the list 
    return ingredients

logger = logging.getLogger()
def suggest_recipes(leftovers: List[str], max_suggestions: int = 3) -> List[str]:
    '''
    this function will suggest recipes based on the leftover ingredients which we got previously
    
    ARGUMENT - 
    leftovers (List[str]), list of the leftover ingredients (whether via the csv file or manually entered)
    max_suggestions (int, optional): maximum number of recipe suggestions to output
    
    RETURN - List[str] of all recipes
    '''
    #first checking if we have any leftovers to work with, if there are no leftovers then anempty list will be returned
    if not leftovers:
        return []
    
    # implementing openai api for the recipe suggestions
    try:
        api_key = os.environ.get("OPENAI_API_KEY") # searching the environment set by the user to find the variable for the api key 
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable was not found!")
        openai.api_key = api_key

        ingredients_list = ", ".join(leftovers) 
        prompt = f'''
        Here are the leftover ingredients I have: {ingredients_list}.
        
        I need you to suggest {max_suggestions} creative and unique recipe ideas that use these ingredients to avoid any food waste

        For each recipe, provide just the recipe name. Don't include ingredients list or instructions, just keep it very simple and minimalistic in the output
        Format each recipe as "Recipe Name"
        Keep the recipes simple and focused on using the leftover ingredients
        ''' 
        # used chatgpt to generate prompt, made some changes afterwards as required.
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}])

        response_text = response['choices'][0]['message']['content']

        recipe_lines = [line.strip() for line in response_text.split('\n') if line.strip()] # splitting the response into cleaning it 
        
        # this part of the code is required to turn geminis responses into a proper list which can later be used to properly display it 
        recipes = [] 
        for line in recipe_lines:
            if line[0].isdigit() and line[1:3] in ['. ', '- ', ') ']: # <- this part will remove any kind of numbers from the response. e.g. 1) Recipe-A --> RecipeA
                line = line[3:].strip()
            line = line.strip('"\'') # <_ in case there aer any quotes in the response, then that will be stripped. e.g. "RecipeA" --> RecipeA
            if line and len(recipes) < max_suggestions: # making sure that max suggestions threshold is met 
                recipes.append(line)
        # ensuring that only the required number of suggestions are included in the list 
        recipes = recipes[:max_suggestions]
        logger.info(f"Got the following recipes from Chatgpt: {recipes}")
    
        if not recipes:
            logger.warning(f"Got no recipes for the ingredients: {ingredients_list}!!")
            return []
        return recipes

    except Exception as e:
            logger.error(f"Error using OpenAI API: {str(e)}")
            return []

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
