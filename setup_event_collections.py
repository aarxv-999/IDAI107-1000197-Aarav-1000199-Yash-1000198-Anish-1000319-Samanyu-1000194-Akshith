"""
Setup script for Event Planning Chatbot collections in Firestore
This script creates and populates the necessary collections for the event planning system
"""

import firebase_admin
from firebase_admin import credentials, firestore
import json
import datetime
import uuid
import os

# Sample data for menu items
menu_items = [
    {
        "name": "Grilled Salmon with Lemon Butter",
        "category": "Main Course",
        "cuisine": "Seafood",
        "description": "Fresh salmon fillet grilled to perfection, served with lemon butter sauce",
        "diet": ["pescatarian", "gluten-free"],
        "ingredients": ["salmon", "butter", "lemon", "garlic", "herbs"],
        "cook_time": 25,
        "rating_comment": "Customer favorite"
    },
    {
        "name": "Vegetable Risotto",
        "category": "Main Course",
        "cuisine": "Italian",
        "description": "Creamy arborio rice cooked with seasonal vegetables and parmesan",
        "diet": ["vegetarian"],
        "ingredients": ["arborio rice", "vegetable stock", "onion", "garlic", "parmesan", "seasonal vegetables"],
        "cook_time": 35,
        "rating_comment": "Staff pick"
    },
    {
        "name": "Chocolate Lava Cake",
        "category": "Dessert",
        "cuisine": "French",
        "description": "Warm chocolate cake with a molten chocolate center",
        "diet": ["vegetarian"],
        "ingredients": ["chocolate", "butter", "eggs", "flour", "sugar"],
        "cook_time": 20,
        "rating_comment": "Most ordered dessert"
    },
    {
        "name": "Vegan Buddha Bowl",
        "category": "Main Course",
        "cuisine": "International",
        "description": "Nutritious bowl with quinoa, roasted vegetables, avocado and tahini dressing",
        "diet": ["vegan", "gluten-free"],
        "ingredients": ["quinoa", "sweet potato", "chickpeas", "avocado", "kale", "tahini"],
        "cook_time": 30,
        "rating_comment": "Healthy option"
    },
    {
        "name": "Beef Wellington",
        "category": "Main Course",
        "cuisine": "British",
        "description": "Tender beef fillet wrapped in puff pastry with mushroom duxelles",
        "diet": [],
        "ingredients": ["beef fillet", "puff pastry", "mushrooms", "prosciutto", "herbs"],
        "cook_time": 60,
        "rating_comment": "Premium dish"
    },
    {
        "name": "Caesar Salad",
        "category": "Starter",
        "cuisine": "American",
        "description": "Crisp romaine lettuce with Caesar dressing, croutons and parmesan",
        "diet": ["vegetarian"],
        "ingredients": ["romaine lettuce", "parmesan", "croutons", "caesar dressing"],
        "cook_time": 15,
        "rating_comment": "Classic favorite"
    },
    {
        "name": "Mushroom Risotto",
        "category": "Main Course",
        "cuisine": "Italian",
        "description": "Creamy arborio rice with wild mushrooms and truffle oil",
        "diet": ["vegetarian", "gluten-free"],
        "ingredients": ["arborio rice", "mushrooms", "onion", "white wine", "parmesan", "truffle oil"],
        "cook_time": 35,
        "rating_comment": "Rich and flavorful"
    },
    {
        "name": "Gluten-Free Pasta Primavera",
        "category": "Main Course",
        "cuisine": "Italian",
        "description": "Gluten-free pasta with fresh spring vegetables in a light cream sauce",
        "diet": ["vegetarian", "gluten-free"],
        "ingredients": ["gluten-free pasta", "zucchini", "bell peppers", "cherry tomatoes", "cream", "parmesan"],
        "cook_time": 25,
        "rating_comment": "Light and fresh"
    },
    {
        "name": "Spicy Tofu Stir-Fry",
        "category": "Main Course",
        "cuisine": "Asian",
        "description": "Crispy tofu with vegetables in a spicy sauce, served with rice",
        "diet": ["vegan", "vegetarian"],
        "ingredients": ["tofu", "bell peppers", "broccoli", "carrots", "soy sauce", "chili"],
        "cook_time": 20,
        "rating_comment": "Popular vegan option"
    },
    {
        "name": "Tiramisu",
        "category": "Dessert",
        "cuisine": "Italian",
        "description": "Classic Italian dessert with layers of coffee-soaked ladyfingers and mascarpone cream",
        "diet": ["vegetarian"],
        "ingredients": ["ladyfingers", "mascarpone", "coffee", "cocoa", "eggs", "sugar"],
        "cook_time": 30,
        "rating_comment": "Authentic recipe"
    }
]

# Sample data for ingredients inventory
ingredients_inventory = [
    {
        "Ingredient": "salmon",
        "Quantity": 20,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
        "Alternatives": ["trout", "cod"],
        "Type": "protein"
    },
    {
        "Ingredient": "chicken breast",
        "Quantity": 30,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
        "Alternatives": ["turkey breast", "tofu"],
        "Type": "protein"
    },
    {
        "Ingredient": "beef fillet",
        "Quantity": 15,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=4)).strftime("%Y-%m-%d"),
        "Alternatives": ["pork tenderloin"],
        "Type": "protein"
    },
    {
        "Ingredient": "arborio rice",
        "Quantity": 5000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
        "Alternatives": ["carnaroli rice"],
        "Type": "grain"
    },
    {
        "Ingredient": "quinoa",
        "Quantity": 3000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
        "Alternatives": ["couscous", "bulgur"],
        "Type": "grain"
    },
    {
        "Ingredient": "gluten-free pasta",
        "Quantity": 2000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
        "Alternatives": ["rice noodles"],
        "Type": "pasta"
    },
    {
        "Ingredient": "tofu",
        "Quantity": 10,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
        "Alternatives": ["tempeh", "seitan"],
        "Type": "protein"
    },
    {
        "Ingredient": "avocado",
        "Quantity": 15,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        "Alternatives": [],
        "Type": "fruit"
    },
    {
        "Ingredient": "bell peppers",
        "Quantity": 25,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
        "Alternatives": [],
        "Type": "vegetable"
    },
    {
        "Ingredient": "mushrooms",
        "Quantity": 2000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        "Alternatives": [],
        "Type": "vegetable"
    },
    {
        "Ingredient": "chocolate",
        "Quantity": 5000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
        "Alternatives": ["cocoa powder"],
        "Type": "baking"
    },
    {
        "Ingredient": "parmesan",
        "Quantity": 2000,
        "Expiry date": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        "Alternatives": ["pecorino"],
        "Type": "dairy"
    }
]

# Sample event data
sample_events = [
    {
        "id": str(uuid.uuid4()),
        "theme": "Summer Garden Party",
        "description": "A refreshing outdoor celebration with seasonal flavors and natural decor",
        "seating": {
            "layout": "Outdoor garden setting with scattered tables under string lights",
            "tables": ["2 long tables with 10 guests each", "5 small round tables with 4 guests each"]
        },
        "decor": [
            "String lights hanging from trees",
            "Wildflower centerpieces",
            "Linen tablecloths in pastel colors",
            "Mason jar candles",
            "Wooden signage"
        ],
        "menu": [
            "Grilled Salmon with Lemon Butter",
            "Vegetable Risotto",
            "Caesar Salad",
            "Gluten-Free Pasta Primavera",
            "Tiramisu"
        ],
        "invitation": "Join us for a delightful Summer Garden Party under the stars. Enjoy fresh seasonal cuisine in our beautiful garden setting. Dress code: Garden casual.",
        "created_at": datetime.datetime.now() - datetime.timedelta(days=5),
        "created_by": "admin"
    }
]

# Initialize Firebase
def init_event_firebase():
    """Initialize Firebase for event data"""
    try:
        # Check if already initialized
        if firebase_admin._apps and 'event_app' in [app.name for app in firebase_admin._apps.values()]:
            return firestore.client(app=firebase_admin.get_app(name='event_app'))
            
        # Use environment variables with EVENT_ prefix if available
        if os.environ.get("EVENT_FIREBASE_PROJECT_ID"):
            cred = credentials.Certificate({
                "type": os.environ.get("EVENT_FIREBASE_TYPE"),
                "project_id": os.environ.get("EVENT_FIREBASE_PROJECT_ID"),
                "private_key_id": os.environ.get("EVENT_FIREBASE_PRIVATE_KEY_ID"),
                "private_key": os.environ.get("EVENT_FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
                "client_email": os.environ.get("EVENT_FIREBASE_CLIENT_EMAIL"),
                "client_id": os.environ.get("EVENT_FIREBASE_CLIENT_ID"),
                "auth_uri": os.environ.get("EVENT_FIREBASE_AUTH_URI"),
                "token_uri": os.environ.get("EVENT_FIREBASE_TOKEN_URI"),
                "auth_provider_x509_cert_url": os.environ.get("EVENT_FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
                "client_x509_cert_url": os.environ.get("EVENT_FIREBASE_CLIENT_X509_CERT_URL")
            })
        else:
            # For local testing, use a service account file
            cred = credentials.Certificate("path/to/serviceAccountKey.json")
            
        app = firebase_admin.initialize_app(cred, name='event_app')
        return firestore.client(app=app)
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

def setup_collections():
    """Set up and populate Firestore collections for event planning"""
    db = init_event_firebase()
    if not db:
        print("Failed to initialize Firebase")
        return False
        
    try:
        # Create menu collection
        menu_ref = db.collection('menu')
        for item in menu_items:
            menu_ref.add(item)
        print(f"Added {len(menu_items)} menu items")
        
        # Create ingredients inventory collection
        inventory_ref = db.collection('ingredients_inventory')
        for item in ingredients_inventory:
            inventory_ref.add(item)
        print(f"Added {len(ingredients_inventory)} inventory items")
        
        # Create events collection with sample data
        events_ref = db.collection('events')
        for event in sample_events:
            events_ref.document(event['id']).set(event)
        print(f"Added {len(sample_events)} sample events")
        
        # Create empty invites collection
        db.collection('invites')
        print("Created invites collection")
        
        return True
    except Exception as e:
        print(f"Error setting up collections: {e}")
        return False

if __name__ == "__main__":
    success = setup_collections()
    if success:
        print("Successfully set up all collections for event planning system")
    else:
        print("Failed to set up collections")
