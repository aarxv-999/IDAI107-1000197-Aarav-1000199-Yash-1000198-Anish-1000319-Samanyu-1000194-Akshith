import logging
from firebase_admin import firestore
from modules.xp_utils import calculate_level_from_xp

logger = logging.getLogger(__name__)

def get_firestore_client():
    """Get Firestore client - reuse from components if available"""
    try:
        from ui.components import get_firestore_client as get_client
        return get_client()
    except ImportError:
        # Fallback implementation
        return firestore.client()

def update_user_stats(user_id, xp_gained, recipes_generated=0, quizzes_completed=0):
    """Update user stats with XP and calculate new level using progressive system"""
    try:
        db = get_firestore_client()
        if not db:
            logger.error("Failed to get Firestore client")
            return False
        
        user_stats_ref = db.collection('user_stats').document(user_id)
        user_stats_doc = user_stats_ref.get()
        
        if user_stats_doc.exists:
            current_stats = user_stats_doc.to_dict()
            current_xp = current_stats.get('total_xp', 0)
            current_recipes = current_stats.get('recipes_generated', 0)
            current_quizzes = current_stats.get('quizzes_completed', 0)
        else:
            current_xp = 0
            current_recipes = 0
            current_quizzes = 0
        
        # Calculate new totals
        new_total_xp = current_xp + xp_gained
        new_recipes = current_recipes + recipes_generated
        new_quizzes = current_quizzes + quizzes_completed
        
        # Calculate new level using progressive system
        new_level = calculate_level_from_xp(new_total_xp)
        
        # Update stats
        updated_stats = {
            'total_xp': new_total_xp,
            'level': new_level,
            'recipes_generated': new_recipes,
            'quizzes_completed': new_quizzes,
            'last_activity': firestore.SERVER_TIMESTAMP
        }
        
        user_stats_ref.set(updated_stats, merge=True)
        
        logger.info(f"Updated user {user_id} stats: +{xp_gained} XP (Total: {new_total_xp}), Level {new_level}, Recipes: {new_recipes}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating user stats: {str(e)}")
        return False

def get_user_stats(user_id):
    """Get user stats from Firebase"""
    try:
        db = get_firestore_client()
        if not db:
            return {}
        
        user_stats_ref = db.collection('user_stats').document(user_id)
        user_stats_doc = user_stats_ref.get()
        
        if user_stats_doc.exists:
            stats = user_stats_doc.to_dict()
            # Ensure level is calculated correctly based on current XP
            total_xp = stats.get('total_xp', 0)
            calculated_level = calculate_level_from_xp(total_xp)
            stats['level'] = calculated_level
            return stats
        else:
            # Return default stats for new users
            return {
                'total_xp': 0,
                'level': 1,
                'recipes_generated': 0,
                'quizzes_completed': 0
            }
            
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {}

def get_leaderboard(limit=10):
    """Get leaderboard data"""
    try:
        db = get_firestore_client()
        if not db:
            return []
        
        # Query top users by total XP
        users_query = db.collection('user_stats').order_by('total_xp', direction=firestore.Query.DESCENDING).limit(limit)
        users = users_query.stream()
        
        leaderboard = []
        for user_doc in users:
            user_data = user_doc.to_dict()
            # Recalculate level to ensure consistency
            total_xp = user_data.get('total_xp', 0)
            calculated_level = calculate_level_from_xp(total_xp)
            
            leaderboard.append({
                'Username': user_data.get('username', 'Unknown'),
                'Level': calculated_level,
                'Total XP': f"{total_xp:,}",
                'Recipes': user_data.get('recipes_generated', 0),
                'Quizzes': user_data.get('quizzes_completed', 0)
            })
        
        return leaderboard
        
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        return []

# Remove the old award_recipe_xp function to prevent confusion
# All XP awarding should go through update_user_stats now

def generate_dynamic_quiz_questions(ingredients, num_questions=5):
    """Generate dynamic quiz questions - placeholder implementation"""
    # This would contain your existing quiz generation logic
    # Returning empty list as placeholder
    logger.info(f"Generating {num_questions} quiz questions for ingredients: {ingredients}")
    return []
