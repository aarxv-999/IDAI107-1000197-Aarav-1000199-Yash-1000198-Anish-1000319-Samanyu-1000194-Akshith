"""
XP and leveling utilities for the gamification system.
Implements progressive XP requirements where each level needs more XP.
"""

import logging

logger = logging.getLogger(__name__)

def calculate_xp_for_level(level):
    """
    Calculate total XP required to reach a specific level.
    Uses progressive scaling where each level requires more XP than the previous.
    
    Level 1: 0 XP (starting level)
    Level 2: 100 XP total
    Level 3: 220 XP total (100 + 120)
    Level 4: 360 XP total (100 + 120 + 140)
    And so on...
    
    Args:
        level (int): The target level
        
    Returns:
        int: Total XP required to reach that level
    """
    if level <= 1:
        return 0
    
    total_xp = 0
    base_xp = 100
    
    for current_level in range(1, level):
        # Progressive multiplier: 1.0, 1.2, 1.4, 1.6, etc.
        # Each level requires 20% more XP than the base amount
        multiplier = 1.0 + (current_level - 1) * 0.2
        level_xp = int(base_xp * multiplier)
        total_xp += level_xp
        
        logger.debug(f"Level {current_level} -> {current_level + 1}: {level_xp} XP (Total: {total_xp})")
    
    return total_xp

def calculate_level_from_xp(total_xp):
    """
    Calculate what level a user should be based on their total XP.
    
    Args:
        total_xp (int): User's total XP
        
    Returns:
        int: The user's current level
    """
    if total_xp < 0:
        return 1
    
    level = 1
    
    # Keep checking if user has enough XP for the next level
    while True:
        xp_for_next_level = calculate_xp_for_level(level + 1)
        if total_xp < xp_for_next_level:
            break
        level += 1
        
        # Safety check to prevent infinite loops
        if level > 100:
            logger.warning(f"User has extremely high XP ({total_xp}), capping at level 100")
            break
    
    logger.debug(f"User with {total_xp} XP is level {level}")
    return level

def get_xp_progress(total_xp, current_level):
    """
    Get progress information for the current level.
    
    Args:
        total_xp (int): User's total XP
        current_level (int): User's current level
        
    Returns:
        tuple: (current_level_xp, xp_needed_for_next, progress_percentage)
    """
    try:
        # XP required to reach current level
        xp_for_current_level = calculate_xp_for_level(current_level)
        
        # XP required to reach next level
        xp_for_next_level = calculate_xp_for_level(current_level + 1)
        
        # XP earned in current level
        current_level_xp = max(0, total_xp - xp_for_current_level)
        
        # XP needed for next level
        xp_needed_for_next = max(0, xp_for_next_level - total_xp)
        
        # Progress percentage (0-100)
        level_xp_requirement = xp_for_next_level - xp_for_current_level
        if level_xp_requirement > 0:
            progress_percentage = (current_level_xp / level_xp_requirement) * 100
        else:
            progress_percentage = 100
        
        # Ensure values are within expected ranges
        progress_percentage = max(0, min(100, progress_percentage))
        
        logger.debug(f"Level {current_level} progress: {current_level_xp}/{level_xp_requirement} XP ({progress_percentage:.1f}%)")
        
        return current_level_xp, xp_needed_for_next, progress_percentage
        
    except Exception as e:
        logger.error(f"Error calculating XP progress: {str(e)}")
        # Return safe defaults
        return 0, 100, 0

def get_xp_breakdown_for_levels(max_level=10):
    """
    Get XP breakdown for multiple levels for display purposes.
    
    Args:
        max_level (int): Maximum level to show in breakdown
        
    Returns:
        list: List of tuples (level, xp_for_this_level, total_xp_required)
    """
    breakdown = []
    base_xp = 100
    
    try:
        for level in range(1, max_level + 1):
            if level == 1:
                xp_for_this_level = 0  # Level 1 is the starting level
                total_xp_required = 0
            else:
                # Calculate XP needed for this specific level
                multiplier = 1.0 + (level - 2) * 0.2
                xp_for_this_level = int(base_xp * multiplier)
                total_xp_required = calculate_xp_for_level(level)
            
            breakdown.append((level, xp_for_this_level, total_xp_required))
            logger.debug(f"Level {level}: {xp_for_this_level} XP this level, {total_xp_required} total")
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Error generating XP breakdown: {str(e)}")
        return [(1, 0, 0)]  # Return safe default

def get_xp_for_next_levels(current_level, num_levels=5):
    """
    Get XP requirements for the next few levels.
    Useful for showing users what they're working towards.
    
    Args:
        current_level (int): User's current level
        num_levels (int): Number of future levels to show
        
    Returns:
        list: List of tuples (level, xp_needed_for_level, total_xp_required)
    """
    future_levels = []
    
    try:
        for i in range(1, num_levels + 1):
            target_level = current_level + i
            if target_level > 100:  # Cap at level 100
                break
                
            total_xp_required = calculate_xp_for_level(target_level)
            
            # XP needed just for this level (not total)
            prev_level_xp = calculate_xp_for_level(target_level - 1)
            xp_for_this_level = total_xp_required - prev_level_xp
            
            future_levels.append((target_level, xp_for_this_level, total_xp_required))
        
        return future_levels
        
    except Exception as e:
        logger.error(f"Error calculating future levels: {str(e)}")
        return []

def validate_xp_system():
    """
    Validate that the XP system is working correctly.
    Useful for debugging and testing.
    
    Returns:
        bool: True if system is working correctly
    """
    try:
        # Test basic level calculations
        assert calculate_xp_for_level(1) == 0
        assert calculate_xp_for_level(2) == 100
        assert calculate_xp_for_level(3) == 220  # 100 + 120
        
        # Test level from XP calculations
        assert calculate_level_from_xp(0) == 1
        assert calculate_level_from_xp(50) == 1
        assert calculate_level_from_xp(100) == 2
        assert calculate_level_from_xp(220) == 3
        
        # Test progress calculations
        current_level_xp, xp_needed, progress = get_xp_progress(150, 2)
        assert current_level_xp == 50  # 150 - 100 (XP for level 2)
        assert progress > 0 and progress <= 100
        
        logger.info("XP system validation passed")
        return True
        
    except AssertionError as e:
        logger.error(f"XP system validation failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error during XP system validation: {str(e)}")
        return False

def get_level_milestones():
    """
    Get important level milestones for achievements and rewards.
    
    Returns:
        dict: Dictionary of milestone levels and their descriptions
    """
    milestones = {
        5: "Rising Star - First major milestone",
        10: "Culinary Expert - Serious dedication",
        15: "Master Chef - Advanced knowledge",
        20: "Legendary Cook - Elite status",
        25: "Grandmaster - Ultimate achievement"
    }
    
    return milestones

def calculate_daily_xp_goal(current_level):
    """
    Calculate a reasonable daily XP goal based on current level.
    Higher level players need more XP, so their daily goals should be higher.
    
    Args:
        current_level (int): User's current level
        
    Returns:
        int: Suggested daily XP goal
    """
    base_daily_goal = 20  # Base daily XP goal
    level_multiplier = 1 + (current_level - 1) * 0.1  # 10% increase per level
    
    daily_goal = int(base_daily_goal * level_multiplier)
    
    # Cap the daily goal at a reasonable amount
    return min(daily_goal, 100)

# Run validation when module is imported (optional)
if __name__ == "__main__":
    # Only run validation if this file is executed directly
    if validate_xp_system():
        print("✅ XP system is working correctly!")
        
        # Show some example calculations
        print("\n📊 Example XP Requirements:")
        for level in range(1, 11):
            total_xp = calculate_xp_for_level(level)
            if level > 1:
                prev_xp = calculate_xp_for_level(level - 1)
                level_xp = total_xp - prev_xp
                print(f"Level {level}: {level_xp} XP (Total: {total_xp})")
            else:
                print(f"Level {level}: Starting level (Total: {total_xp})")
    else:
        print("❌ XP system validation failed!")
