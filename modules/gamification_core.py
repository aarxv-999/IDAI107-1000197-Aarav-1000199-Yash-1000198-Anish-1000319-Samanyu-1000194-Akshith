"""
Centralized Gamification System for Restaurant Management App
Handles XP, levels, achievements, tasks, and leaderboards across all features
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger(__name__)

def get_gamification_firestore_db():
    """Get the gamification Firestore client"""
    try:
        # Use the main Firebase app for gamification data
        if not firebase_admin._apps:
            from firebase_init import init_firebase
            init_firebase()
        
        return firestore.client()
    except Exception as e:
        logger.error(f"Error getting gamification Firestore client: {str(e)}")
        return None

# XP and Level Configuration
XP_REWARDS = {
    # Recipe and cooking activities
    'recipe_generation': 15,
    'recipe_rating': 5,
    'recipe_sharing': 10,
    
    # Quiz activities
    'quiz_completion': 20,
    'quiz_perfect_score': 50,
    'quiz_attempt': 10,
    
    # Visual menu activities
    'dish_detection': 25,
    'dish_like': 5,
    'challenge_submission': 30,
    'challenge_vote': 10,
    'personalized_recommendations': 15,
    
    # Promotion activities
    'campaign_creation_basic': 20,
    'campaign_creation_good': 30,
    'campaign_creation_excellent': 50,
    
    # Chef activities
    'chef_recipe_submission': 40,
    'menu_generation': 35,
    'signature_dish_rating': 10,
    
    # General activities
    'daily_login': 10,
    'feature_exploration': 5,
    'task_completion': 25,
    'achievement_unlock': 0,  # Achievements give their own XP
    
    # Leftover management
    'leftover_recipe_generation': 15,
    'ingredient_optimization': 20,
    
    # Event planning
    'event_creation': 30,
    'event_participation': 15,
    
    # Ingredient management
    'ingredient_tracking': 10,
    'inventory_update': 5,
}

# Achievement definitions
ACHIEVEMENTS = {
    'first_recipe': {
        'name': 'First Recipe',
        'description': 'Generated your first recipe',
        'xp_reward': 25,
        'condition': lambda stats: stats.get('recipes_generated', 0) >= 1
    },
    'recipe_master': {
        'name': 'Recipe Master',
        'description': 'Generated 50 recipes',
        'xp_reward': 100,
        'condition': lambda stats: stats.get('recipes_generated', 0) >= 50
    },
    'quiz_champion': {
        'name': 'Quiz Champion',
        'description': 'Completed 10 quizzes',
        'xp_reward': 75,
        'condition': lambda stats: stats.get('quizzes_completed', 0) >= 10
    },
    'perfect_scorer': {
        'name': 'Perfect Scorer',
        'description': 'Got 100% on a quiz',
        'xp_reward': 50,
        'condition': lambda stats: stats.get('perfect_quiz_scores', 0) >= 1
    },
    'dish_detective': {
        'name': 'Dish Detective',
        'description': 'Detected 25 dishes using AI',
        'xp_reward': 60,
        'condition': lambda stats: stats.get('dishes_detected', 0) >= 25
    },
    'campaign_creator': {
        'name': 'Campaign Creator',
        'description': 'Created 5 marketing campaigns',
        'xp_reward': 80,
        'condition': lambda stats: stats.get('campaigns_created', 0) >= 5
    },
    'chef_extraordinaire': {
        'name': 'Chef Extraordinaire',
        'description': 'Submitted 10 signature dishes',
        'xp_reward': 120,
        'condition': lambda stats: stats.get('signature_dishes_submitted', 0) >= 10
    },
    'daily_warrior': {
        'name': 'Daily Warrior',
        'description': 'Maintained a 7-day login streak',
        'xp_reward': 100,
        'condition': lambda stats: stats.get('daily_streak', 0) >= 7
    },
    'level_10': {
        'name': 'Rising Star',
        'description': 'Reached level 10',
        'xp_reward': 150,
        'condition': lambda stats: stats.get('level', 1) >= 10
    },
    'level_25': {
        'name': 'Culinary Expert',
        'description': 'Reached level 25',
        'xp_reward': 300,
        'condition': lambda stats: stats.get('level', 1) >= 25
    },
    'feature_explorer': {
        'name': 'Feature Explorer',
        'description': 'Used all 5 main features',
        'xp_reward': 100,
        'condition': lambda stats: len(stats.get('features_used', [])) >= 5
    }
}

def calculate_level_from_xp(total_xp: int) -> int:
    """Calculate user level based on total XP"""
    # Level 1: 0-99 XP, Level 2: 100-199 XP, etc.
    return max(1, (total_xp // 100) + 1)

def get_user_stats(user_id: str) -> Dict:
    """Get comprehensive user statistics"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return _get_default_user_stats(user_id)
        
        # Get user document
        user_ref = db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            stats = user_doc.to_dict()
            
            # Calculate level from XP
            total_xp = stats.get('total_xp', 0)
            stats['level'] = calculate_level_from_xp(total_xp)
            
            # Count achievements
            achievements = stats.get('achievements', [])
            stats['achievement_count'] = len(achievements)
            
            return stats
        else:
            # Create new user stats
            default_stats = _get_default_user_stats(user_id)
            user_ref.set(default_stats)
            return default_stats
    
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return _get_default_user_stats(user_id)

def _get_default_user_stats(user_id: str) -> Dict:
    """Get default user statistics"""
    return {
        'user_id': user_id,
        'total_xp': 0,
        'level': 1,
        'achievements': [],
        'achievement_count': 0,
        'daily_streak': 0,
        'last_login': None,
        'features_used': [],
        'activity_counts': {},
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }

def award_xp(user_id: str, activity: str, amount: Optional[int] = None, context: Dict = None) -> Tuple[int, bool, List[str]]:
    """Award XP to user and check for level ups and achievements"""
    try:
        if context is None:
            context = {}
        
        # Get XP amount
        xp_amount = amount if amount is not None else XP_REWARDS.get(activity, 10)
        
        if xp_amount <= 0:
            return 0, False, []
        
        db = get_gamification_firestore_db()
        if not db:
            logger.warning("Firestore not available, XP not awarded")
            return 0, False, []
        
        # Get current user stats
        user_ref = db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            stats = user_doc.to_dict()
        else:
            stats = _get_default_user_stats(user_id)
        
        # Calculate old and new levels
        old_xp = stats.get('total_xp', 0)
        new_xp = old_xp + xp_amount
        old_level = calculate_level_from_xp(old_xp)
        new_level = calculate_level_from_xp(new_xp)
        level_up = new_level > old_level
        
        # Update stats
        stats['total_xp'] = new_xp
        stats['level'] = new_level
        stats['updated_at'] = datetime.now().isoformat()
        
        # Update activity counts
        activity_counts = stats.get('activity_counts', {})
        activity_counts[activity] = activity_counts.get(activity, 0) + 1
        stats['activity_counts'] = activity_counts
        
        # Track feature usage
        feature = context.get('feature')
        if feature:
            features_used = stats.get('features_used', [])
            if feature not in features_used:
                features_used.append(feature)
                stats['features_used'] = features_used
        
        # Update specific counters based on activity
        _update_activity_specific_stats(stats, activity, context)
        
        # Check for new achievements
        new_achievements = _check_achievements(stats)
        
        # Add achievement XP
        achievement_xp = 0
        for achievement_id in new_achievements:
            achievement = ACHIEVEMENTS.get(achievement_id)
            if achievement:
                achievement_xp += achievement.get('xp_reward', 0)
        
        if achievement_xp > 0:
            stats['total_xp'] += achievement_xp
            stats['level'] = calculate_level_from_xp(stats['total_xp'])
            xp_amount += achievement_xp
        
        # Save updated stats
        user_ref.set(stats)
        
        # Create activity log
        _log_activity(db, user_id, activity, xp_amount, context)
        
        # Update daily challenge progress
        _update_daily_challenge_progress(db, user_id, activity, context)
        
        # Update tasks progress
        _update_task_progress(db, user_id, activity, context)
        
        achievement_names = [ACHIEVEMENTS[aid]['name'] for aid in new_achievements if aid in ACHIEVEMENTS]
        
        return xp_amount, level_up, achievement_names
    
    except Exception as e:
        logger.error(f"Error awarding XP: {str(e)}")
        return 0, False, []

def _update_activity_specific_stats(stats: Dict, activity: str, context: Dict):
    """Update specific statistics based on activity type"""
    if activity in ['recipe_generation', 'leftover_recipe_generation']:
        stats['recipes_generated'] = stats.get('recipes_generated', 0) + 1
    elif activity in ['quiz_completion', 'quiz_attempt']:
        stats['quizzes_completed'] = stats.get('quizzes_completed', 0) + 1
    elif activity == 'quiz_perfect_score':
        stats['perfect_quiz_scores'] = stats.get('perfect_quiz_scores', 0) + 1
        stats['quizzes_completed'] = stats.get('quizzes_completed', 0) + 1
    elif activity == 'dish_detection':
        stats['dishes_detected'] = stats.get('dishes_detected', 0) + 1
    elif activity in ['campaign_creation_basic', 'campaign_creation_good', 'campaign_creation_excellent']:
        stats['campaigns_created'] = stats.get('campaigns_created', 0) + 1
    elif activity == 'chef_recipe_submission':
        stats['signature_dishes_submitted'] = stats.get('signature_dishes_submitted', 0) + 1

def _check_achievements(stats: Dict) -> List[str]:
    """Check for newly unlocked achievements"""
    try:
        current_achievements = set(stats.get('achievements', []))
        new_achievements = []
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            if achievement_id not in current_achievements:
                if achievement['condition'](stats):
                    new_achievements.append(achievement_id)
                    current_achievements.add(achievement_id)
        
        # Update achievements in stats
        stats['achievements'] = list(current_achievements)
        
        return new_achievements
    
    except Exception as e:
        logger.error(f"Error checking achievements: {str(e)}")
        return []

def _log_activity(db, user_id: str, activity: str, xp_amount: int, context: Dict):
    """Log user activity"""
    try:
        activity_log = {
            'user_id': user_id,
            'activity': activity,
            'xp_awarded': xp_amount,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        db.collection('activity_logs').add(activity_log)
    
    except Exception as e:
        logger.error(f"Error logging activity: {str(e)}")

def get_leaderboard(limit: int = 10) -> List[Dict]:
    """Get top users leaderboard"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return []
        
        # Query top users by total XP
        users_ref = db.collection('user_stats')
        query = users_ref.order_by('total_xp', direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.get()
        
        leaderboard = []
        for i, doc in enumerate(docs, 1):
            data = doc.to_dict()
            
            # Get username from users collection
            try:
                user_doc = db.collection('users').document(doc.id).get()
                username = user_doc.to_dict().get('username', 'Unknown') if user_doc.exists else 'Unknown'
            except:
                username = 'Unknown'
            
            leaderboard.append({
                'rank': i,
                'user_id': doc.id,
                'username': username,
                'total_xp': data.get('total_xp', 0),
                'level': data.get('level', 1)
            })
        
        return leaderboard
    
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        return []

def get_achievements(user_id: str) -> List[Dict]:
    """Get user's unlocked achievements with details"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return []
        
        # Get user stats
        user_ref = db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return []
        
        stats = user_doc.to_dict()
        user_achievements = stats.get('achievements', [])
        
        # Get achievement details
        achievement_details = []
        for achievement_id in user_achievements:
            if achievement_id in ACHIEVEMENTS:
                achievement = ACHIEVEMENTS[achievement_id].copy()
                achievement['id'] = achievement_id
                achievement['earned_date'] = stats.get('updated_at', 'Unknown')
                achievement_details.append(achievement)
        
        return achievement_details
    
    except Exception as e:
        logger.error(f"Error getting achievements: {str(e)}")
        return []

def get_daily_challenge(user_id: str) -> Optional[Dict]:
    """Get today's daily challenge for user"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return None
        
        today = date.today().isoformat()
        
        # Check if user has today's challenge
        challenge_ref = db.collection('daily_challenges').document(f"{user_id}_{today}")
        challenge_doc = challenge_ref.get()
        
        if challenge_doc.exists:
            return challenge_doc.to_dict()
        else:
            # Create today's challenge
            challenge = _generate_daily_challenge(user_id, today)
            challenge_ref.set(challenge)
            return challenge
    
    except Exception as e:
        logger.error(f"Error getting daily challenge: {str(e)}")
        return None

def _generate_daily_challenge(user_id: str, date_str: str) -> Dict:
    """Generate a daily challenge for the user"""
    import random
    
    challenges = [
        {
            'name': 'Recipe Explorer',
            'description': 'Generate 3 recipes today',
            'target': 3,
            'activity_type': 'recipe_generation',
            'xp_reward': 50
        },
        {
            'name': 'Quiz Master',
            'description': 'Complete 2 cooking quizzes',
            'target': 2,
            'activity_type': 'quiz_completion',
            'xp_reward': 40
        },
        {
            'name': 'Dish Detective',
            'description': 'Detect 2 dishes using AI',
            'target': 2,
            'activity_type': 'dish_detection',
            'xp_reward': 60
        },
        {
            'name': 'Campaign Creator',
            'description': 'Create 1 marketing campaign',
            'target': 1,
            'activity_type': 'campaign_creation',
            'xp_reward': 45
        },
        {
            'name': 'Feature Explorer',
            'description': 'Use 3 different features',
            'target': 3,
            'activity_type': 'feature_exploration',
            'xp_reward': 35
        }
    ]
    
    selected_challenge = random.choice(challenges)
    
    return {
        'challenge_id': f"{user_id}_{date_str}",
        'user_id': user_id,
        'date': date_str,
        'name': selected_challenge['name'],
        'description': selected_challenge['description'],
        'target': selected_challenge['target'],
        'progress': 0,
        'completed': False,
        'activity_type': selected_challenge['activity_type'],
        'xp_reward': selected_challenge['xp_reward'],
        'created_at': datetime.now().isoformat()
    }

def complete_daily_challenge(user_id: str, challenge_id: str) -> bool:
    """Complete a daily challenge and award XP"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return False
        
        challenge_ref = db.collection('daily_challenges').document(challenge_id)
        challenge_doc = challenge_ref.get()
        
        if not challenge_doc.exists:
            return False
        
        challenge = challenge_doc.to_dict()
        
        if challenge['completed'] or challenge['progress'] < challenge['target']:
            return False
        
        # Mark as completed
        challenge['completed'] = True
        challenge['completed_at'] = datetime.now().isoformat()
        challenge_ref.set(challenge)
        
        # Award XP
        award_xp(user_id, 'daily_challenge_completion', challenge['xp_reward'])
        
        return True
    
    except Exception as e:
        logger.error(f"Error completing daily challenge: {str(e)}")
        return False

def _update_daily_challenge_progress(db, user_id: str, activity: str, context: Dict):
    """Update daily challenge progress"""
    try:
        today = date.today().isoformat()
        challenge_ref = db.collection('daily_challenges').document(f"{user_id}_{today}")
        challenge_doc = challenge_ref.get()
        
        if challenge_doc.exists:
            challenge = challenge_doc.to_dict()
            
            # Check if activity matches challenge type
            activity_mapping = {
                'recipe_generation': 'recipe_generation',
                'leftover_recipe_generation': 'recipe_generation',
                'quiz_completion': 'quiz_completion',
                'quiz_attempt': 'quiz_completion',
                'dish_detection': 'dish_detection',
                'campaign_creation_basic': 'campaign_creation',
                'campaign_creation_good': 'campaign_creation',
                'campaign_creation_excellent': 'campaign_creation',
                'feature_exploration': 'feature_exploration'
            }
            
            mapped_activity = activity_mapping.get(activity)
            if mapped_activity == challenge.get('activity_type') and not challenge.get('completed', False):
                challenge['progress'] = min(challenge['progress'] + 1, challenge['target'])
                challenge_ref.set(challenge)
    
    except Exception as e:
        logger.error(f"Error updating daily challenge progress: {str(e)}")

def get_user_tasks(user_id: str) -> List[Dict]:
    """Get user's active tasks"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return []
        
        # Get user tasks
        tasks_ref = db.collection('user_tasks').where('user_id', '==', user_id).where('completed', '==', False)
        docs = tasks_ref.get()
        
        tasks = []
        for doc in docs:
            task_data = doc.to_dict()
            task_data['task_id'] = doc.id
            tasks.append(task_data)
        
        # If no tasks, create some default ones
        if not tasks:
            tasks = _create_default_tasks(db, user_id)
        
        return tasks
    
    except Exception as e:
        logger.error(f"Error getting user tasks: {str(e)}")
        return []

def _create_default_tasks(db, user_id: str) -> List[Dict]:
    """Create default tasks for new users"""
    try:
        default_tasks = [
            {
                'user_id': user_id,
                'name': 'Recipe Beginner',
                'description': 'Generate your first 5 recipes',
                'target': 5,
                'progress': 0,
                'completed': False,
                'activity_type': 'recipe_generation',
                'xp_reward': 75,
                'created_at': datetime.now().isoformat()
            },
            {
                'user_id': user_id,
                'name': 'Quiz Starter',
                'description': 'Complete your first 3 quizzes',
                'target': 3,
                'progress': 0,
                'completed': False,
                'activity_type': 'quiz_completion',
                'xp_reward': 60,
                'created_at': datetime.now().isoformat()
            },
            {
                'user_id': user_id,
                'name': 'Feature Explorer',
                'description': 'Try 3 different features',
                'target': 3,
                'progress': 0,
                'completed': False,
                'activity_type': 'feature_exploration',
                'xp_reward': 50,
                'created_at': datetime.now().isoformat()
            }
        ]
        
        created_tasks = []
        for task in default_tasks:
            doc_ref = db.collection('user_tasks').add(task)
            task['task_id'] = doc_ref[1].id
            created_tasks.append(task)
        
        return created_tasks
    
    except Exception as e:
        logger.error(f"Error creating default tasks: {str(e)}")
        return []

def _update_task_progress(db, user_id: str, activity: str, context: Dict):
    """Update task progress"""
    try:
        # Get user's active tasks
        tasks_ref = db.collection('user_tasks').where('user_id', '==', user_id).where('completed', '==', False)
        docs = tasks_ref.get()
        
        activity_mapping = {
            'recipe_generation': 'recipe_generation',
            'leftover_recipe_generation': 'recipe_generation',
            'quiz_completion': 'quiz_completion',
            'quiz_attempt': 'quiz_completion',
            'dish_detection': 'dish_detection',
            'campaign_creation_basic': 'campaign_creation',
            'campaign_creation_good': 'campaign_creation',
            'campaign_creation_excellent': 'campaign_creation',
            'feature_exploration': 'feature_exploration'
        }
        
        mapped_activity = activity_mapping.get(activity)
        
        for doc in docs:
            task = doc.to_dict()
            
            if task.get('activity_type') == mapped_activity:
                task['progress'] = min(task['progress'] + 1, task['target'])
                
                if task['progress'] >= task['target']:
                    task['completed'] = True
                    task['completed_at'] = datetime.now().isoformat()
                
                # Update task
                db.collection('user_tasks').document(doc.id).set(task)
    
    except Exception as e:
        logger.error(f"Error updating task progress: {str(e)}")

def update_daily_streak(user_id: str):
    """Update user's daily login streak"""
    try:
        db = get_gamification_firestore_db()
        if not db:
            return
        
        user_ref = db.collection('user_stats').document(user_id)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            stats = user_doc.to_dict()
        else:
            stats = _get_default_user_stats(user_id)
        
        today = date.today()
        last_login_str = stats.get('last_login')
        
        if last_login_str:
            last_login = datetime.fromisoformat(last_login_str).date()
            
            if last_login == today:
                # Already logged in today
                return
            elif last_login == today - timedelta(days=1):
                # Consecutive day
                stats['daily_streak'] = stats.get('daily_streak', 0) + 1
            else:
                # Streak broken
                stats['daily_streak'] = 1
        else:
            # First login
            stats['daily_streak'] = 1
        
        stats['last_login'] = today.isoformat()
        stats['updated_at'] = datetime.now().isoformat()
        
        user_ref.set(stats)
        
        # Award daily login XP
        award_xp(user_id, 'daily_login', context={'streak': stats['daily_streak']})
    
    except Exception as e:
        logger.error(f"Error updating daily streak: {str(e)}")
