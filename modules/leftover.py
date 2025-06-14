'''
Simplified leftover management and gamification module
'''

import pandas as pd
from typing import List, Optional, Dict, Tuple
import os
import google.generativeai as genai
import logging
import random
import json
from datetime import datetime, date

from firebase_admin import firestore
from firebase_init import init_firebase

logger = logging.getLogger('leftover_combined')

def load_leftovers(csv_path: str) -> List[str]:
    '''Load leftover ingredients from CSV file'''
    try:
        df = pd.read_csv(csv_path)
        if 'ingredient' not in df.columns:
            raise ValueError("CSV file must have an 'ingredient' column")
        ingredients = df['ingredient'].tolist()
        ingredients = [ing.strip() for ing in ingredients if ing and isinstance(ing, str)]
        return ingredients
    except FileNotFoundError:
        raise FileNotFoundError(f"CSV file unavailable at: {csv_path}")
    except Exception as e:
        raise Exception(f"Error loading leftovers from CSV: {str(e)}")

def parse_manual_leftovers(input_text: str) -> List[str]:
    '''Parse manually entered ingredients'''
    ingredients = input_text.split(',')
    ingredients = [ing.strip() for ing in ingredients if ing.strip()]
    return ingredients

def parse_expiry_date(expiry_string: str) -> datetime:
    '''Parse expiry date from Firebase format'''
    try:
        if "Expiry date:" in expiry_string:
            date_part = expiry_string.replace("Expiry date:", "").strip()
        else:
            date_part = expiry_string.strip()
        
        return datetime.strptime(date_part, "%d/%m/%Y")
    except Exception as e:
        logger.warning(f"Could not parse expiry date '{expiry_string}': {str(e)}")
        return None

def is_ingredient_valid(expiry_string: str) -> bool:
    '''Check if ingredient is still valid (not expired)'''
    expiry_date = parse_expiry_date(expiry_string)
    if expiry_date is None:
        return False
    
    current_date = datetime.now()
    return expiry_date.date() >= current_date.date()

def filter_valid_ingredients(ingredients: List[Dict]) -> List[Dict]:
    '''Filter out expired ingredients'''
    valid_ingredients = []
    expired_count = 0
    
    for ingredient in ingredients:
        expiry_date_str = ingredient.get('Expiry Date', '')
