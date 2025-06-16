"""
XP and leveling utilities for the gamification system.
Implements a progressive XP system where each level requires more XP than the previous.
Includes comprehensive utilities for XP calculations, level management, and gamification features.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# XP Constants
BASE_XP_PER_LEVEL = 100
XP_MULTIPLIER = 1.5  # Each level requires 50% more XP than the previous
MAX_LEVEL = 100
MIN_LEVEL = 1

# XP Rewards for different activities
XP_REWARDS = {
    # Recipe and cooking activities
    'recipe_generation': 15,
    'recipe_generation_bonus': 5,  # Bonus for multiple recipes
    'cooking_quiz_correct': 10,
    'cooking_quiz_perfect': 25,  # All questions correct
    'daily_challenge_complete': 30,
    'weekly_challenge_complete': 100,
    
    # Campaign and promotion activities
    'campaign_creation_basic': 20,
    'campaign_creation_good': 30,
    'campaign_creation_excellent': 50,
    'campaign_like_received': 10,
    'campaign_dislike_received': 2,
    
    # Management activities
    'ingredient_added': 5,
    'ingredient_updated': 3,
    'inventory_management': 10,
    'waste_reduction': 20,
    
    # Event planning activities
    'event_planned': 25,
    'event_executed': 40,
    'event_feedback_positive': 15,
    
    # Social activities
    'helping_colleague': 15,
    'knowledge_sharing': 20,
    'mentoring': 30,
    
    # Achievement bonuses
    'first_recipe': 50,
    'first_campaign': 50,
    'streak_bonus': 10,  # Per day in streak
    'milestone_bonus': 100,  # Every 10 levels
}

# Level titles/badges
LEVEL_TITLES = {
    1: "Kitchen Novice",
    5: "Prep Cook",
    10: "Line Cook",
    15: "Cook",
    20: "Senior Cook",
    25: "Sous Chef Assistant",
    30: "Sous Chef",
    35: "Head Cook",
    40: "Kitchen Manager",
    45: "Executive Chef Assistant",
    50: "Executive Chef",
    60: "Culinary Master",
    70: "Kitchen Legend",
    80: "Culinary Genius",
    90: "Master Chef",
    100: "Culinary Grandmaster"
}

def calculate_level_from_xp(total_xp: int) -> int:
    """
    Calculate level from total XP using progressive system.
    Each level requires more XP than the previous one.
    
    Args:
        total_xp (int): Total XP earned by the user
        
    Returns:
        int: Current level (minimum 1, maximum MAX_LEVEL)
    """
    if total_xp < 0:
        return MIN_LEVEL
    
    if total_xp == 0:
        return MIN_LEVEL
    
    level = MIN_LEVEL
    xp_required = 0
    
    # Calculate level using progressive XP requirements
    while level < MAX_LEVEL:
        next_level_xp = get_xp_required_for_level(level + 1)
        if total_xp >= next_level_xp:
            level += 1
        else:
            break
    
    return min(level, MAX_LEVEL)

def get_xp_required_for_level(level: int) -> int:
    """
    Get total XP required to reach a specific level.
    Uses progressive scaling: each level requires more XP.
    
    Args:
        level (int): Target level
        
    Returns:
        int: Total XP required to reach that level
    """
    if level <= MIN_LEVEL:
        return 0
    
    total_xp = 0
    for l in range(MIN_LEVEL + 1, level + 1):
        # Progressive XP requirement: base * (level - 1) * multiplier^(level/10)
        level_xp = int(BASE_XP_PER_LEVEL * (l - 1) * (XP_MULTIPLIER ** ((l - 1) // 10)))
        total_xp += level_xp
    
    return total_xp

def get_xp_for_next_level(current_level: int) -> int:
    """
    Get XP required for the next level from current level.
    
    Args:
        current_level (int): Current level
        
    Returns:
        int: XP required for next level
    """
    if current_level >= MAX_LEVEL:
        return 0
    
    next_level = current_level + 1
    current_level_total_xp = get_xp_required_for_level(current_level)
    next_level_total_xp = get_xp_required_for_level(next_level)
    
    return next_level_total_xp - current_level_total_xp

def get_xp_progress(total_xp: int, current_level: int) -> Tuple[int, int, float]:
    """
    Get progress information for current level.
    Returns tuple for backward compatibility.
    
    Args:
        total_xp (int): Total XP earned
        current_level (int): Current level
        
    Returns:
        Tuple[int, int, float]: (current_level_xp, xp_needed_for_next, progress_percentage)
    """
    # XP required to reach current level
    current_level_start_xp = get_xp_required_for_level(current_level)
    
    # XP required to reach next level
    if current_level >= MAX_LEVEL:
        next_level_start_xp = current_level_start_xp
        xp_needed_for_next = 0
        progress_percentage = 100.0
        current_level_xp = total_xp - current_level_start_xp
    else:
        next_level_start_xp = get_xp_required_for_level(current_level + 1)
        # XP earned in current level
        current_level_xp = total_xp - current_level_start_xp
        # XP needed for next level
        xp_needed_for_next = next_level_start_xp - total_xp
        # Progress percentage within current level
        level_xp_requirement = next_level_start_xp - current_level_start_xp
        progress_percentage = (current_level_xp / level_xp_requirement) * 100 if level_xp_requirement > 0 else 100.0
    
    return (
        max(0, current_level_xp),
        max(0, xp_needed_for_next), 
        min(100.0, max(0.0, progress_percentage))
    )

def get_xp_progress_detailed(total_xp: int, current_level: int) -> Dict:
    """
    Get detailed progress information for current level.
    Returns dictionary with comprehensive information.
    
    Args:
        total_xp (int): Total XP earned
        current_level (int): Current level
        
    Returns:
        Dict: Progress information including current level XP, XP needed, and percentage
    """
    # XP required to reach current level
    current_level_start_xp = get_xp_required_for_level(current_level)
    
    # XP required to reach next level
    next_level_start_xp = get_xp_required_for_level(current_level + 1)
    
    # XP earned in current level
    current_level_xp = total_xp - current_level_start_xp
    
    # XP needed for next level
    xp_needed_for_next = next_level_start_xp - total_xp
    
    # Progress percentage within current level
    level_xp_requirement = next_level_start_xp - current_level_start_xp
    progress_percentage = (current_level_xp / level_xp_requirement) * 100 if level_xp_requirement > 0 else 100
    
    return {
        'current_level_xp': max(0, current_level_xp),
        'xp_needed_for_next': max(0, xp_needed_for_next),
        'progress_percentage': min(100, max(0, progress_percentage)),
        'level_xp_requirement': level_xp_requirement,
        'is_max_level': current_level >= MAX_LEVEL
    }

def get_level_title(level: int) -> str:
    """
    Get the title/badge for a specific level.
    
    Args:
        level (int): Level number
        
    Returns:
        str: Level title/badge
    """
    # Find the highest title that the level qualifies for
    applicable_titles = {k: v for k, v in LEVEL_TITLES.items() if k <= level}
    
    if applicable_titles:
        highest_level = max(applicable_titles.keys())
        return applicable_titles[highest_level]
    
    return "Kitchen Novice"

def get_xp_breakdown_for_levels(max_level: int = 20) -> List[Tuple[int, int, int, str]]:
    """
    Get XP breakdown for levels up to max_level.
    
    Args:
        max_level (int): Maximum level to calculate for
        
    Returns:
        List[Tuple]: List of (level, xp_for_level, total_xp_required, title)
    """
    breakdown = []
    
    for level in range(MIN_LEVEL, min(max_level + 1, MAX_LEVEL + 1)):
        if level == MIN_LEVEL:
            xp_for_level = 0
            total_xp_required = 0
        else:
            total_xp_required = get_xp_required_for_level(level)
            prev_total_xp = get_xp_required_for_level(level - 1)
            xp_for_level = total_xp_required - prev_total_xp
        
        title = get_level_title(level)
        breakdown.append((level, xp_for_level, total_xp_required, title))
    
    return breakdown

def calculate_xp_reward(activity: str, bonus_multiplier: float = 1.0, **kwargs) -> int:
    """
    Calculate XP reward for a specific activity.
    
    Args:
        activity (str): Activity name (key from XP_REWARDS)
        bonus_multiplier (float): Multiplier for bonus XP
        **kwargs: Additional parameters for specific activities
        
    Returns:
        int: XP reward amount
    """
    base_xp = XP_REWARDS.get(activity, 0)
    
    # Apply bonus multiplier
    total_xp = int(base_xp * bonus_multiplier)
    
    # Special cases for specific activities
    if activity == 'recipe_generation' and kwargs.get('recipe_count', 1) > 1:
        # Bonus XP for generating multiple recipes
        bonus_recipes = kwargs.get('recipe_count', 1) - 1
        total_xp += bonus_recipes * XP_REWARDS.get('recipe_generation_bonus', 5)
    
    elif activity == 'streak_bonus' and kwargs.get('streak_days', 0) > 0:
        # Streak bonus increases with streak length
        streak_days = kwargs.get('streak_days', 0)
        total_xp = min(streak_days * XP_REWARDS.get('streak_bonus', 10), 100)  # Cap at 100 XP
    
    elif activity == 'milestone_bonus' and kwargs.get('level', 0) > 0:
        # Milestone bonus every 10 levels
        level = kwargs.get('level', 0)
        if level % 10 == 0:
            total_xp = XP_REWARDS.get('milestone_bonus', 100)
        else:
            total_xp = 0
    
    return max(0, total_xp)

def get_daily_xp_limit() -> int:
    """
    Get daily XP earning limit to prevent abuse.
    
    Returns:
        int: Daily XP limit
    """
    return 500  # Reasonable daily limit

def get_weekly_xp_limit() -> int:
    """
    Get weekly XP earning limit.
    
    Returns:
        int: Weekly XP limit
    """
    return 2000  # Reasonable weekly limit

def calculate_level_up_rewards(old_level: int, new_level: int) -> Dict:
    """
    Calculate rewards for leveling up.
    
    Args:
        old_level (int): Previous level
        new_level (int): New level
        
    Returns:
        Dict: Level up rewards information
    """
    rewards = {
        'levels_gained': new_level - old_level,
        'milestone_bonuses': 0,
        'new_title': get_level_title(new_level),
        'title_changed': get_level_title(old_level) != get_level_title(new_level),
        'special_rewards': []
    }
    
    # Check for milestone bonuses (every 10 levels)
    for level in range(old_level + 1, new_level + 1):
        if level % 10 == 0:
            rewards['milestone_bonuses'] += XP_REWARDS.get('milestone_bonus', 100)
            rewards['special_rewards'].append(f"Level {level} Milestone Bonus!")
    
    # Special rewards for significant levels
    if new_level >= 50 and old_level < 50:
        rewards['special_rewards'].append("Executive Chef Achievement Unlocked!")
    elif new_level >= 25 and old_level < 25:
        rewards['special_rewards'].append("Sous Chef Achievement Unlocked!")
    elif new_level >= 10 and old_level < 10:
        rewards['special_rewards'].append("Line Cook Achievement Unlocked!")
    
    return rewards

def get_leaderboard_position(user_xp: int, all_user_xp: List[int]) -> Dict:
    """
    Calculate user's position in leaderboard.
    
    Args:
        user_xp (int): User's total XP
        all_user_xp (List[int]): List of all users' XP
        
    Returns:
        Dict: Leaderboard position information
    """
    if not all_user_xp:
        return {'position': 1, 'total_users': 1, 'percentile': 100}
    
    sorted_xp = sorted(all_user_xp, reverse=True)
    
    try:
        position = sorted_xp.index(user_xp) + 1
    except ValueError:
        # User XP not in list, find position
        position = len([xp for xp in sorted_xp if xp > user_xp]) + 1
    
    total_users = len(sorted_xp)
    percentile = ((total_users - position + 1) / total_users) * 100
    
    return {
        'position': position,
        'total_users': total_users,
        'percentile': round(percentile, 1)
    }

def calculate_activity_streak(activity_dates: List[datetime]) -> Dict:
    """
    Calculate activity streak information.
    
    Args:
        activity_dates (List[datetime]): List of activity dates
        
    Returns:
        Dict: Streak information
    """
    if not activity_dates:
        return {'current_streak': 0, 'longest_streak': 0, 'last_activity': None}
    
    # Sort dates
    sorted_dates = sorted(set(date.date() for date in activity_dates))
    
    current_streak = 0
    longest_streak = 0
    temp_streak = 1
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Calculate current streak
    if sorted_dates and (sorted_dates[-1] == today or sorted_dates[-1] == yesterday):
        current_streak = 1
        for i in range(len(sorted_dates) - 2, -1, -1):
            if (sorted_dates[i + 1] - sorted_dates[i]).days == 1:
                current_streak += 1
            else:
                break
    
    # Calculate longest streak
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 1
    
    longest_streak = max(longest_streak, temp_streak)
    
    return {
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'last_activity': sorted_dates[-1] if sorted_dates else None
    }

def get_achievement_progress(user_stats: Dict) -> Dict:
    """
    Calculate achievement progress based on user stats.
    
    Args:
        user_stats (Dict): User statistics
        
    Returns:
        Dict: Achievement progress information
    """
    achievements = {
        'recipe_master': {
            'name': 'Recipe Master',
            'description': 'Generate 100 recipes',
            'progress': min(user_stats.get('recipes_generated', 0), 100),
            'target': 100,
            'completed': user_stats.get('recipes_generated', 0) >= 100
        },
        'campaign_creator': {
            'name': 'Campaign Creator',
            'description': 'Create 50 marketing campaigns',
            'progress': min(user_stats.get('campaigns_created', 0), 50),
            'target': 50,
            'completed': user_stats.get('campaigns_created', 0) >= 50
        },
        'quiz_champion': {
            'name': 'Quiz Champion',
            'description': 'Score perfect on 25 cooking quizzes',
            'progress': min(user_stats.get('perfect_quizzes', 0), 25),
            'target': 25,
            'completed': user_stats.get('perfect_quizzes', 0) >= 25
        },
        'streak_warrior': {
            'name': 'Streak Warrior',
            'description': 'Maintain a 30-day activity streak',
            'progress': min(user_stats.get('longest_streak', 0), 30),
            'target': 30,
            'completed': user_stats.get('longest_streak', 0) >= 30
        },
        'level_climber': {
            'name': 'Level Climber',
            'description': 'Reach level 50',
            'progress': min(user_stats.get('level', 1), 50),
            'target': 50,
            'completed': user_stats.get('level', 1) >= 50
        }
    }
    
    return achievements

def format_xp_display(xp: int) -> str:
    """
    Format XP for display with appropriate suffixes.
    
    Args:
        xp (int): XP amount
        
    Returns:
        str: Formatted XP string
    """
    if xp >= 1000000:
        return f"{xp / 1000000:.1f}M XP"
    elif xp >= 1000:
        return f"{xp / 1000:.1f}K XP"
    else:
        return f"{xp:,} XP"

def get_next_milestone(current_level: int) -> Dict:
    """
    Get information about the next milestone level.
    
    Args:
        current_level (int): Current level
        
    Returns:
        Dict: Next milestone information
    """
    # Find next milestone (every 10 levels or special levels)
    special_levels = [5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]
    
    next_milestone = None
    for level in special_levels:
        if level > current_level:
            next_milestone = level
            break
    
    if next_milestone:
        xp_needed = get_xp_required_for_level(next_milestone)
        title = get_level_title(next_milestone)
        
        return {
            'level': next_milestone,
            'title': title,
            'xp_required': xp_needed,
            'is_milestone': next_milestone % 10 == 0
        }
    
    return {
        'level': MAX_LEVEL,
        'title': get_level_title(MAX_LEVEL),
        'xp_required': get_xp_required_for_level(MAX_LEVEL),
        'is_milestone': True
    }

def validate_xp_award(activity: str, user_id: str, daily_xp: int = 0) -> Tuple[bool, str]:
    """
    Validate if XP can be awarded for an activity.
    
    Args:
        activity (str): Activity name
        user_id (str): User ID
        daily_xp (int): XP already earned today
        
    Returns:
        Tuple[bool, str]: (is_valid, reason)
    """
    # Check if activity exists
    if activity not in XP_REWARDS:
        return False, f"Unknown activity: {activity}"
    
    # Check daily limit
    daily_limit = get_daily_xp_limit()
    activity_xp = XP_REWARDS[activity]
    
    if daily_xp + activity_xp > daily_limit:
        return False, f"Daily XP limit ({daily_limit}) would be exceeded"
    
    return True, "Valid"

# Export all utility functions
__all__ = [
    'calculate_level_from_xp',
    'get_xp_required_for_level', 
    'get_xp_for_next_level',
    'get_xp_progress',
    'get_level_title',
    'get_xp_breakdown_for_levels',
    'calculate_xp_reward',
    'get_daily_xp_limit',
    'get_weekly_xp_limit',
    'calculate_level_up_rewards',
    'get_leaderboard_position',
    'calculate_activity_streak',
    'get_achievement_progress',
    'format_xp_display',
    'get_next_milestone',
    'validate_xp_award',
    'XP_REWARDS',
    'LEVEL_TITLES',
    'BASE_XP_PER_LEVEL',
    'MAX_LEVEL',
    'MIN_LEVEL'
]
