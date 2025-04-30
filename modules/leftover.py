"""
MADE BY: Aarav Agarwal, IBCP CRS: AI, WACP ID: 1000197
This file will serve as the functionality for the leftovermanagement feature

Packages used: 
- pandas: to read CSV files
"""

import pandas as pd  
from typing import List, Optional 
import random 

# primarily used exception handling in this code ! 

def load_leftovers(csv_path: str) -> List[str]:
    """
    ARGUMENT - loading all leftover ingredients from a csv file (if it exists)
    csv_path (str) is the path to the csv file containing the ingredients & should have a column named "ingredients"
    
    RETURN -  List[str]: a list of names of all leftover ingredients
    
    RAISES -  if FileNotFoundError occurs then it means that the csv file does not exist. if "ValueError" occurs then that means thtat the CSV file doesnt have ingredients column
    """
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
    """
    parses the manually entered list 
    
    ARGUMENT - input_text (str), which is the manually entered ingredients with each being separated by a , 
    RETURN - List[str], a list of leftover ingredient names where it is properly organized 
    """
    ingredients = input_text.split(',') #splittingall input texts by a comma. 
    ingredients = [ing.strip() for ing in ingredients if ing.strip()] # imputing empty values and white space in every ingredient of the list 
    return ingredients
def suggest_recipes(leftovers: List[str], max_suggestions: int = 3) -> List[str]:
    """
    this function will suggest recipes based on the leftover ingredients which we got previously
    
    ARGUMENT - 
    leftovers (List[str]), list of the leftover ingredients (whether via the csv file or manually entered)
    max_suggestions (int, optional): Maximum number of recipe suggestions to return. Defaults to 3.
    
    Returns:
        List[str]: A list of recipe suggestions.
    """
    # Check if we have any leftovers to work with
    if not leftovers:
        # If the leftovers list is empty, return an empty list
        # [] creates an empty list
        return []
    
    # This is a placeholder for the future AI integration
    # In a real implementation, this would call an AI API like OpenAI or Gemini
    # For now, we'll generate some simple suggestions based on the ingredients
    
    # Create some example recipe templates
    # These are f-strings (formatted strings) that allow embedding variables inside strings
    # The {} syntax is used to insert a variable's value into the string
    recipe_templates = [
        "Roasted {0} with {1}",
        "{0} and {1} Stir Fry",
        "Creamy {0} Soup with {1} Garnish",
        "{0} & {1} Salad",
        "Grilled {0} with {1} Sauce",
        "{0} and {1} Pasta",
        "Baked {0} with {1} Topping",
        "{0} & {1} Tacos",
        "{0} and {1} Curry",
        "{0} & {1} Smoothie Bowl"
    ]
    
    suggestions = []
    
    # Generate up to max_suggestions recipes
    # min() returns the smaller of two values - we use it to avoid trying to generate
    # more suggestions than we have templates
    for _ in range(min(max_suggestions, len(recipe_templates))):
        # If we have at least 2 ingredients, randomly select 2 different ones
        if len(leftovers) >= 2:
            # Create a copy of the leftovers list to avoid modifying the original
            # [:] is slice notation that creates a copy of the entire list
            available_ingredients = leftovers[:]
            
            # random.choice() selects a random item from a sequence
            ingredient1 = random.choice(available_ingredients)
            
            # Remove the first selected ingredient to avoid duplicates
            # .remove() removes the first occurrence of a value from a list
            available_ingredients.remove(ingredient1)
            
            ingredient2 = random.choice(available_ingredients)
            
            # Select a random recipe template
            template = random.choice(recipe_templates)
            
            # Format the template with our ingredients
            # .format() replaces the {} placeholders with the provided values
            recipe = template.format(ingredient1.capitalize(), ingredient2.capitalize())
            
        # If we only have 1 ingredient, create a simpler recipe
        elif len(leftovers) == 1:
            ingredient = leftovers[0]
            simple_templates = [
                "Roasted {0}",
                "{0} Soup",
                "Grilled {0}",
                "{0} Salad",
                "Baked {0}"
            ]
            template = random.choice(simple_templates)
            recipe = template.format(ingredient.capitalize())
        
        # Add the recipe to our suggestions list
        # .append() adds an item to the end of a list
        suggestions.append(recipe)
        
        # Remove the used template to avoid duplicates
        # This ensures each suggestion uses a different template
        recipe_templates.remove(template)
        
        # If we've used all templates, break the loop
        if not recipe_templates:
            break
    
    # Add a comment to each suggestion explaining the sustainability aspect
    # This is a list comprehension that adds a sustainability note to each recipe
    suggestions = [
        f"{recipe} - A sustainable dish that reduces food waste by using leftover ingredients."
        for recipe in suggestions
    ]
    
    return suggestions

# This block only executes if this file is run directly (not imported)
# __name__ is a special variable that is set to "__main__" when the file is run directly
if __name__ == "__main__":
    # Example usage of the functions
    print("Example usage of leftover management functions:")
    
    # Try loading from a sample CSV
    try:
        sample_leftovers = load_leftovers("../data/leftover.csv")
        print(f"Loaded leftovers from CSV: {sample_leftovers}")
    except Exception as e:
        print(f"Error loading from CSV: {e}")
    
    # Example of manual entry
    manual_input = "carrots, spinach, quinoa, beets"
    parsed_leftovers = parse_manual_leftovers(manual_input)
    print(f"Parsed manual leftovers: {parsed_leftovers}")
    
    # Generate and print recipe suggestions
    recipes = suggest_recipes(parsed_leftovers, 3)
    print("Recipe suggestions:")
    for i, recipe in enumerate(recipes, 1):
        print(f"{i}. {recipe}")

"""
How to use this module:

1. Activate a Python virtual environment:
   - On Windows: venv\Scripts\activate
   - On macOS/Linux: source venv/bin/activate

2. Install required packages:
   pip install pandas

3. Import and use in your code:
   from modules.leftover import load_leftovers, suggest_recipes
"""