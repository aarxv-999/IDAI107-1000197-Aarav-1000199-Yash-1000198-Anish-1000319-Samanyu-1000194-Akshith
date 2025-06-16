"""
Enhanced Gamification Core System for Smart Restaurant Management
Connects all features with unified XP, tasks, achievements, and leaderboards
"""

import streamlit as st
import firebase_admin
from firebase_admin import firestore
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)

# XP Rewards Configuration
XP_REWARDS = {
    # Recipe & Leftover Management
    'recipe_generation': 15,
    'priority_ingredient_use': 10,
    'leftover_recipe_creation': 20,
    
    # Quiz System
    'quiz_completion_base': 10,
    'quiz_perfect_score_bonus': 15,
    'quiz_streak_bonus': 5,
    
    # Visual Menu & Challenges
    'dish_detection': 15,
    'personalized_recommendations': 20,
    'dish_like': 5,
    'challenge_submission': 30,
    'challenge_vote': 5,
    'challenge_like_received': 8,
    'challenge_order_received': 15,
    
    # Promotion & Marketing
    'campaign_creation_basic': 20,
    'campaign_creation_good': 30,
    'campaign_creation_excellent': 50,
    
    # Chef Features
    'chef_recipe_submission': 25,
    'menu_generation': 40,
    
    # Ingredients Management
    'ingredient_add': 5,
    'ingredient_update': 3,
    'inventory_management': 10,
    
    # Event Planning
    'event_plan_creation': 35,
    'event_plan_execution': 25,
    
    # Daily/Weekly Bonuses
    'daily_login': 5,
    'weekly_streak': 25,
    'monthly_achievement': 50
}

# Task Categories
TASK_CATEGORIES = {
    'daily': {
        'name': 'Daily Tasks',
        'reset_period': 'daily',
        'tasks': [
            {'id': 'daily_login', 'name': 'Log in to the system', 'xp': 5, 'target': 1},
            {'id': 'generate_recipe', 'name': 'Generate a recipe from leftovers', 'xp': 15, 'target': 1},
            {'id': 'take_quiz', 'name': 'Complete a cooking quiz', 'xp': 10, 'target': 1},
            {'id': 'use_visual_menu', 'name': 'Use AI dish detection', 'xp': 15, 'target': 1}
        ]
    },
    'weekly': {
        'name': 'Weekly Challenges',
        'reset_period': 'weekly',
        'tasks': [
            {'id': 'recipe_master', 'name': 'Generate 5 recipes', 'xp': 50, 'target': 5},
            {'id': 'quiz_champion', 'name': 'Complete 3 quizzes with 80%+ score', 'xp': 75, 'target': 3},
            {'id': 'social_contributor', 'name': 'Like 10 dishes or vote on challenges', 'xp': 30, 'target': 10},
            {'id': 'feature_explorer', 'name': 'Use 4 different features', 'xp': 40, 'target': 4}
        ]
    },
    'role_specific': {
        'staff': [
            {'id': 'campaign_creator', 'name': 'Create a marketing campaign', 'xp': 30, 'target': 1, 'period': 'monthly'},
            {'id': 'inventory_manager', 'name': 'Update 10 inventory items', 'xp': 25, 'target': 10, 'period': 'weekly'}
        ],
        'chef': [
            {'id': 'signature_dish', 'name': 'Submit a signature dish', 'xp': 25, 'target': 1, 'period': 'weekly'},
            {'id': 'menu_architect', 'name': 'Generate a weekly menu', 'xp': 40, 'target': 1, 'period': 'weekly'}
        ],
        'admin': [
            {'id': 'system_overseer', 'name': 'Use all admin features', 'xp': 60, 'target': 5, 'period': 'weekly'}
        ]
    }
}

# Achievement System
ACHIEVEMENTS = {
    # XP Milestones
    'xp_milestones': [
        {'threshold': 100, 'name': 'Getting Started', 'description': 'Earned your first 100 XP', 'badge': '🌟'},
        {'threshold': 500, 'name': 'Rising Star', 'description': 'Reached 500 XP', 'badge': '⭐'},
        {'threshold': 1000, 'name': 'Kitchen Pro', 'description': 'Achieved 1000 XP', 'badge': '👨‍🍳'},
        {'threshold': 2500, 'name': 'Culinary Expert', 'description': 'Mastered 2500 XP', 'badge': '🏆'},
        {'threshold': 5000, 'name': 'Master Chef', 'description': 'Legendary 5000 XP', 'badge': '👑'}
    ],
    
    # Activity Achievements
    'activity_based': [
        {'id': 'recipe_novice', 'name': 'Recipe Novice', 'description': 'Generated first recipe', 'requirement': {'recipes_generated': 1}, 'badge': '📝'},
        {'id': 'recipe_expert', 'name': 'Recipe Expert', 'description': 'Generated 25 recipes', 'requirement': {'recipes_generated': 25}, 'badge': '📚'},
        {'id': 'quiz_starter', 'name': 'Quiz Starter', 'description': 'Completed first quiz', 'requirement': {'quizzes_completed': 1}, 'badge': '🧠'},
        {'id': 'quiz_master', 'name': 'Quiz Master', 'description': 'Completed 20 quizzes', 'requirement': {'quizzes_completed': 20}, 'badge': '🎓'},
        {'id': 'perfect_scorer', 'name': 'Perfectionist', 'description': 'Got perfect score on quiz', 'requirement': {'perfect_scores': 1}, 'badge': '💯'},
        {'id': 'social_butterfly', 'name': 'Social Butterfly', 'description': 'Liked 50 dishes', 'requirement': {'dishes_liked': 50}, 'badge': '💖'},
        {'id': 'challenge_champion', 'name': 'Challenge Champion', 'description': 'Won a weekly challenge', 'requirement': {'challenges_won': 1}, 'badge': '🏅'}
    ]
}

class GamificationManager:
    """Centralized gamification management system"""
    
    def __init__(self):
        self.main_db = self._get_main_firebase()
        
    def _get_main_firebase(self):
        """Get main Firebase client for gamification data"""
        try:
            if firebase_admin._DEFAULT_APP_NAME in [app.name for app in firebase_admin._apps.values()]:
                return firestore.client()
            else:
                from firebase_init import init_firebase
                init_firebase()
                return firestore.client()
        except Exception as e:
            logger.error(f"Error getting main Firebase: {str(e)}")
            return None
    
    def initialize_user_gamification(self, user_id: str, username: str, role: str) -> bool:
        """Initialize gamification data for new user"""
        try:
            if not self.main_db:
                return False
                
            # Initialize user stats
            user_stats = {
                'user_id': user_id,
                'username': username,
                'role': role,
                'total_xp': 0,
                'level': 1,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_activity': firestore.SERVER_TIMESTAMP,
                
                # Activity counters
                'recipes_generated': 0,
                'quizzes_completed': 0,
                'perfect_scores': 0,
                'dishes_liked': 0,
                'campaigns_created': 0,
                'challenges_submitted': 0,
                'features_used': [],
                
                # Streaks
                'daily_streak': 0,
                'last_login_date': datetime.now().date().isoformat(),
                
                # Achievements
                'achievements': [],
                'achievement_count': 0
            }
            
            # Initialize tasks
            user_tasks = self._initialize_user_tasks(user_id, role)
            
            # Save to Firebase
            self.main_db.collection('user_stats').document(user_id).set(user_stats)
            self.main_db.collection('user_tasks').document(user_id).set(user_tasks)
            
            logger.info(f"Initialized gamification for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing user gamification: {str(e)}")
            return False
    
    def _initialize_user_tasks(self, user_id: str, role: str) -> Dict:
        """Initialize task tracking for user"""
        today = datetime.now().date().isoformat()
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date().isoformat()
        
        tasks = {
            'user_id': user_id,
            'last_updated': firestore.SERVER_TIMESTAMP,
            'current_date': today,
            'current_week': week_start,
            
            # Daily tasks
            'daily_tasks': {
                'date': today,
                'tasks': {task['id']: {'completed': False, 'progress': 0, 'target': task['target']} 
                         for task in TASK_CATEGORIES['daily']['tasks']}
            },
            
            # Weekly tasks
            'weekly_tasks': {
                'week': week_start,
                'tasks': {task['id']: {'completed': False, 'progress': 0, 'target': task['target']} 
                         for task in TASK_CATEGORIES['weekly']['tasks']}
            },
            
            # Role-specific tasks
            'role_tasks': {}
        }
        
        # Add role-specific tasks
        if role in TASK_CATEGORIES['role_specific']:
            for task in TASK_CATEGORIES['role_specific'][role]:
                period = task.get('period', 'weekly')
                if period not in tasks['role_tasks']:
                    tasks['role_tasks'][period] = {}
                tasks['role_tasks'][period][task['id']] = {
                    'completed': False, 
                    'progress': 0, 
                    'target': task['target']
                }
        
        return tasks
    
    def award_xp(self, user_id: str, activity: str, amount: Optional[int] = None, 
                 context: Dict = None) -> Tuple[int, bool, List[str]]:
        """
        Award XP for an activity and check for achievements
        Returns: (xp_awarded, level_up, new_achievements)
        """
        try:
            if not self.main_db:
                return 0, False, []
            
            # Get XP amount
            xp_amount = amount or XP_REWARDS.get(activity, 0)
            if xp_amount <= 0:
                return 0, False, []
            
            # Get current user stats
            user_ref = self.main_db.collection('user_stats').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                logger.warning(f"User stats not found for {user_id}")
                return 0, False, []
            
            current_stats = user_doc.to_dict()
            old_level = current_stats.get('level', 1)
            old_xp = current_stats.get('total_xp', 0)
            
            # Calculate new values
            new_xp = old_xp + xp_amount
            new_level = self._calculate_level(new_xp)
            level_up = new_level > old_level
            
            # Update activity counters based on activity type
            updates = {
                'total_xp': new_xp,
                'level': new_level,
                'last_activity': firestore.SERVER_TIMESTAMP
            }
            
            # Update specific counters
            if activity in ['recipe_generation', 'leftover_recipe_creation']:
                updates['recipes_generated'] = current_stats.get('recipes_generated', 0) + 1
            elif activity in ['quiz_completion_base', 'quiz_perfect_score_bonus']:
                updates['quizzes_completed'] = current_stats.get('quizzes_completed', 0) + 1
                if activity == 'quiz_perfect_score_bonus':
                    updates['perfect_scores'] = current_stats.get('perfect_scores', 0) + 1
            elif activity == 'dish_like':
                updates['dishes_liked'] = current_stats.get('dishes_liked', 0) + 1
            elif activity.startswith('campaign_creation'):
                updates['campaigns_created'] = current_stats.get('campaigns_created', 0) + 1
            elif activity == 'challenge_submission':
                updates['challenges_submitted'] = current_stats.get('challenges_submitted', 0) + 1
            
            # Track feature usage
            if context and 'feature' in context:
                features_used = current_stats.get('features_used', [])
                if context['feature'] not in features_used:
                    features_used.append(context['feature'])
                    updates['features_used'] = features_used
            
            # Update user stats
            user_ref.update(updates)
            
            # Update tasks
            self._update_task_progress(user_id, activity, context)
            
            # Check for new achievements
            new_achievements = self._check_achievements(user_id, {**current_stats, **updates})
            
            logger.info(f"Awarded {xp_amount} XP to user {user_id} for {activity}")
            return xp_amount, level_up, new_achievements
            
        except Exception as e:
            logger.error(f"Error awarding XP: {str(e)}")
            return 0, False, []
    
    def _calculate_level(self, total_xp: int) -> int:
        """Calculate level based on total XP"""
        # Level formula: Level = floor(sqrt(XP / 100)) + 1
        import math
        return max(1, int(math.sqrt(total_xp / 100)) + 1)
    
    def _update_task_progress(self, user_id: str, activity: str, context: Dict = None):
        """Update task progress based on activity"""
        try:
            tasks_ref = self.main_db.collection('user_tasks').document(user_id)
            tasks_doc = tasks_ref.get()
            
            if not tasks_doc.exists:
                return
            
            tasks_data = tasks_doc.to_dict()
            today = datetime.now().date().isoformat()
            week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).date().isoformat()
            
            # Reset tasks if needed
            if tasks_data.get('daily_tasks', {}).get('date') != today:
                tasks_data['daily_tasks'] = {
                    'date': today,
                    'tasks': {task['id']: {'completed': False, 'progress': 0, 'target': task['target']} 
                             for task in TASK_CATEGORIES['daily']['tasks']}
                }
            
            if tasks_data.get('weekly_tasks', {}).get('week') != week_start:
                tasks_data['weekly_tasks'] = {
                    'week': week_start,
                    'tasks': {task['id']: {'completed': False, 'progress': 0, 'target': task['target']} 
                             for task in TASK_CATEGORIES['weekly']['tasks']}
                }
            
            # Update task progress based on activity
            task_updates = {}
            
            # Daily task updates
            if activity in ['recipe_generation', 'leftover_recipe_creation']:
                task_updates['daily_tasks.tasks.generate_recipe.progress'] = 1
                task_updates['daily_tasks.tasks.generate_recipe.completed'] = True
                
                # Weekly task
                current_progress = tasks_data.get('weekly_tasks', {}).get('tasks', {}).get('recipe_master', {}).get('progress', 0)
                new_progress = min(current_progress + 1, 5)
                task_updates['weekly_tasks.tasks.recipe_master.progress'] = new_progress
                if new_progress >= 5:
                    task_updates['weekly_tasks.tasks.recipe_master.completed'] = True
            
            elif activity in ['quiz_completion_base', 'quiz_perfect_score_bonus']:
                task_updates['daily_tasks.tasks.take_quiz.progress'] = 1
                task_updates['daily_tasks.tasks.take_quiz.completed'] = True
                
                # Weekly quiz challenge (if score >= 80%)
                if context and context.get('score_percentage', 0) >= 80:
                    current_progress = tasks_data.get('weekly_tasks', {}).get('tasks', {}).get('quiz_champion', {}).get('progress', 0)
                    new_progress = min(current_progress + 1, 3)
                    task_updates['weekly_tasks.tasks.quiz_champion.progress'] = new_progress
                    if new_progress >= 3:
                        task_updates['weekly_tasks.tasks.quiz_champion.completed'] = True
            
            elif activity == 'dish_detection':
                task_updates['daily_tasks.tasks.use_visual_menu.progress'] = 1
                task_updates['daily_tasks.tasks.use_visual_menu.completed'] = True
            
            elif activity in ['dish_like', 'challenge_vote']:
                current_progress = tasks_data.get('weekly_tasks', {}).get('tasks', {}).get('social_contributor', {}).get('progress', 0)
                new_progress = min(current_progress + 1, 10)
                task_updates['weekly_tasks.tasks.social_contributor.progress'] = new_progress
                if new_progress >= 10:
                    task_updates['weekly_tasks.tasks.social_contributor.completed'] = True
            
            # Feature exploration tracking
            if context and 'feature' in context:
                # This would need more complex logic to track unique features used
                pass
            
            # Apply updates
            if task_updates:
                tasks_ref.update(task_updates)
                
        except Exception as e:
            logger.error(f"Error updating task progress: {str(e)}")
    
    def _check_achievements(self, user_id: str, user_stats: Dict) -> List[str]:
        """Check for new achievements"""
        try:
            current_achievements = user_stats.get('achievements', [])
            new_achievements = []
            
            # Check XP milestones
            total_xp = user_stats.get('total_xp', 0)
            for milestone in ACHIEVEMENTS['xp_milestones']:
                if total_xp >= milestone['threshold'] and milestone['name'] not in current_achievements:
                    new_achievements.append(milestone['name'])
            
            # Check activity-based achievements
            for achievement in ACHIEVEMENTS['activity_based']:
                if achievement['name'] not in current_achievements:
                    requirements_met = True
                    for req_key, req_value in achievement['requirement'].items():
                        if user_stats.get(req_key, 0) < req_value:
                            requirements_met = False
                            break
                    
                    if requirements_met:
                        new_achievements.append(achievement['name'])
            
            # Update achievements if any new ones
            if new_achievements:
                all_achievements = current_achievements + new_achievements
                self.main_db.collection('user_stats').document(user_id).update({
                    'achievements': all_achievements,
                    'achievement_count': len(all_achievements)
                })
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking achievements: {str(e)}")
            return []
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get comprehensive user stats"""
        try:
            if not self.main_db:
                return self._get_default_stats(user_id)
            
            user_ref = self.main_db.collection('user_stats').document(user_id)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                return user_doc.to_dict()
            else:
                return self._get_default_stats(user_id)
                
        except Exception as e:
            logger.error(f"Error getting user stats: {str(e)}")
            return self._get_default_stats(user_id)
    
    def _get_default_stats(self, user_id: str) -> Dict:
        """Get default stats for user"""
        return {
            'user_id': user_id,
            'total_xp': 0,
            'level': 1,
            'recipes_generated': 0,
            'quizzes_completed': 0,
            'perfect_scores': 0,
            'dishes_liked': 0,
            'campaigns_created': 0,
            'challenges_submitted': 0,
            'features_used': [],
            'daily_streak': 0,
            'achievements': [],
            'achievement_count': 0
        }
    
    def get_user_tasks(self, user_id: str) -> Dict:
        """Get user's current tasks"""
        try:
            if not self.main_db:
                return {}
            
            tasks_ref = self.main_db.collection('user_tasks').document(user_id)
            tasks_doc = tasks_ref.get()
            
            if tasks_doc.exists:
                return tasks_doc.to_dict()
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting user tasks: {str(e)}")
            return {}
    
    def get_leaderboard(self, limit: int = 10, period: str = 'all_time') -> List[Dict]:
        """Get leaderboard data"""
        try:
            if not self.main_db:
                return []
            
            # For now, just return all-time leaderboard
            # Could be extended to support weekly/monthly periods
            query = self.main_db.collection('user_stats').order_by('total_xp', direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.stream()
            
            leaderboard = []
            for i, doc in enumerate(docs):
                data = doc.to_dict()
                leaderboard.append({
                    'rank': i + 1,
                    'username': data.get('username', 'Unknown'),
                    'total_xp': data.get('total_xp', 0),
                    'level': data.get('level', 1),
                    'achievement_count': data.get('achievement_count', 0)
                })
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {str(e)}")
            return []

# Global gamification manager instance
gamification_manager = GamificationManager()

# Convenience functions for easy integration
def award_xp(user_id: str, activity: str, amount: Optional[int] = None, context: Dict = None) -> Tuple[int, bool, List[str]]:
    """Award XP to user"""
    return gamification_manager.award_xp(user_id, activity, amount, context)

def get_user_stats(user_id: str) -> Dict:
    """Get user stats"""
    return gamification_manager.get_user_stats(user_id)

def get_user_tasks(user_id: str) -> Dict:
    """Get user tasks"""
    return gamification_manager.get_user_tasks(user_id)

def get_leaderboard(limit: int = 10) -> List[Dict]:
    """Get leaderboard"""
    return gamification_manager.get_leaderboard(limit)

def initialize_user_gamification(user_id: str, username: str, role: str) -> bool:
    """Initialize gamification for new user"""
    return gamification_manager.initialize_user_gamification(user_id, username, role)
