"""
XP and leveling utilities for the gamification system.
Implements progressive XP requirements where each level needs more XP.
"""

def calculate_xp_for_level(level):
    """
    Calculate total XP required to reach a specific level.
    Uses progressive scaling: Level 1=100, Level 2=250, Level 3=450, etc.
    
    Formula: XP = sum of (base_xp * level * multiplier) for each level
    """
    if level <= 1:
        return 0
    
    total_xp = 0
    base_xp = 100
    
    for current_level in range(1, level):
        # Progressive multiplier: 1.0, 1.2, 1.4, 1.6, etc.
        multiplier = 1.0 + (current_level - 1) * 0.2
        level_xp = int(base_xp * multiplier)
        total_xp += level_xp
    
    return total_xp

def calculate_level_from_xp(total_xp):
    """
    Calculate what level a user should be based on their total XP.
    """
    if total_xp < 0:
        return 1
    
    level = 1
    accumulated_xp = 0
    
    while True:
        xp_for_next_level = calculate_xp_for_level(level + 1)
        if total_xp < xp_for_next_level:
            break
        level += 1
        
        # Safety check to prevent infinite loops
        if level > 100:
            break
    
    return level

def get_current_level_progress(total_xp):
    """
    Get progress information for the current level.
    Returns: (current_level, current_level_xp, xp_needed_for_next, progress_percentage)
    """
    current_level = calculate_level_from_xp(total_xp)
    
    # XP required to reach current level
    xp_for_current_level = calculate_xp_for_level(current_level)
    
    # XP required to reach next level
    xp_for_next_level = calculate_xp_for_level(current_level + 1)
    
    # XP earned in current level
    current_level_xp = total_xp - xp_for_current_level
    
    # XP needed for next level
    xp_needed_for_next = xp_for_next_level - total_xp
    
    # Progress percentage (0-100)
    level_xp_requirement = xp_for_next_level - xp_for_current_level
    if level_xp_requirement > 0:
        progress_percentage = (current_level_xp / level_xp_requirement) * 100
    else:
        progress_percentage = 100
    
    return current_level, current_level_xp, xp_needed_for_next, min(progress_percentage, 100)

def get_xp_breakdown_for_levels(max_level=10):
    """
    Get XP breakdown for multiple levels for display purposes.
    Returns list of tuples: (level, xp_for_this_level, total_xp_required)
    """
    breakdown = []
    base_xp = 100
    
    for level in range(1, max_level + 1):
        if level == 1:
            xp_for_this_level = base_xp
            total_xp_required = base_xp
        else:
            multiplier = 1.0 + (level - 2) * 0.2
            xp_for_this_level = int(base_xp * multiplier)
            total_xp_required = calculate_xp_for_level(level + 1)
        
        breakdown.append((level, xp_for_this_level, total_xp_required))
    
    return breakdown
