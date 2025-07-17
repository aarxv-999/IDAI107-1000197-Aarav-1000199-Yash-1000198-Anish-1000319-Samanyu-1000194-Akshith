import logging

logger = logging.getLogger(__name__)

def calculate_xp_for_level(level):
    if level <= 1:
        return 0
    
    total_xp = 0
    base_xp = 100
    
    for current_level in range(1, level):
        multiplier = 1.0 + (current_level - 1) * 0.2
        level_xp = int(base_xp * multiplier)
        total_xp += level_xp
        
        logger.debug(f"Level {current_level} -> {current_level + 1}: {level_xp} XP (Total: {total_xp})")
    
    return total_xp

def calculate_level_from_xp(total_xp):
    if total_xp < 0:
        return 1
    
    level = 1
    
    while True:
        xp_for_next_level = calculate_xp_for_level(level + 1)
        if total_xp < xp_for_next_level:
            break
        level += 1
        
        if level > 100:
            logger.warning(f"User has extremely high XP ({total_xp}), capping at level 100")
            break
    
    logger.debug(f"User with {total_xp} XP is level {level}")
    return level

def get_xp_progress(total_xp, current_level):
    try:
        xp_for_current_level = calculate_xp_for_level(current_level)
        
        xp_for_next_level = calculate_xp_for_level(current_level + 1)
        
        current_level_xp = max(0, total_xp - xp_for_current_level)
        
        xp_needed_for_next = max(0, xp_for_next_level - total_xp)
        
        level_xp_requirement = xp_for_next_level - xp_for_current_level
        if level_xp_requirement > 0:
            progress_percentage = (current_level_xp / level_xp_requirement) * 100
        else:
            progress_percentage = 100
        
        progress_percentage = max(0, min(100, progress_percentage))
        
        logger.debug(f"Level {current_level} progress: {current_level_xp}/{level_xp_requirement} XP ({progress_percentage:.1f}%)")
        
        return current_level_xp, xp_needed_for_next, progress_percentage
        
    except Exception as e:
        logger.error(f"Error calculating XP progress: {str(e)}")
        return 0, 100, 0

def get_xp_breakdown_for_levels(max_level=10):
    breakdown = []
    base_xp = 100
    
    try:
        for level in range(1, max_level + 1):
            if level == 1:
                xp_for_this_level = 0
                total_xp_required = 0
            else:
                multiplier = 1.0 + (level - 2) * 0.2
                xp_for_this_level = int(base_xp * multiplier)
                total_xp_required = calculate_xp_for_level(level)
            
            breakdown.append((level, xp_for_this_level, total_xp_required))
            logger.debug(f"Level {level}: {xp_for_this_level} XP this level, {total_xp_required} total")
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Error generating XP breakdown: {str(e)}")
        return [(1, 0, 0)]

def get_xp_for_next_levels(current_level, num_levels=5):
    future_levels = []
    
    try:
        for i in range(1, num_levels + 1):
            target_level = current_level + i
            if target_level > 100:
                break
                
            total_xp_required = calculate_xp_for_level(target_level)
            
            prev_level_xp = calculate_xp_for_level(target_level - 1)
            xp_for_this_level = total_xp_required - prev_level_xp
            
            future_levels.append((target_level, xp_for_this_level, total_xp_required))
        
        return future_levels
        
    except Exception as e:
        logger.error(f"Error calculating future levels: {str(e)}")
        return []

def validate_xp_system():
    try:
        assert calculate_xp_for_level(1) == 0
        assert calculate_xp_for_level(2) == 100
        assert calculate_xp_for_level(3) == 220
        
        assert calculate_level_from_xp(0) == 1
        assert calculate_level_from_xp(50) == 1
        assert calculate_level_from_xp(100) == 2
        assert calculate_level_from_xp(220) == 3
        
        current_level_xp, xp_needed, progress = get_xp_progress(150, 2)
        assert current_level_xp == 50
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
    milestones = {
        5: "Rising Star - First major milestone",
        10: "Culinary Expert - Serious dedication",
        15: "Master Chef - Advanced knowledge",
        20: "Legendary Cook - Elite status",
        25: "Grandmaster - Ultimate achievement"
    }
    
    return milestones

def calculate_daily_xp_goal(current_level):
    base_daily_goal = 20
    level_multiplier = 1 + (current_level - 1) * 0.1
    
    daily_goal = int(base_daily_goal * level_multiplier)
    
    return min(daily_goal, 100)

if __name__ == "__main__":
    if validate_xp_system():
        print("XP system is working correctly!")
        
        print("\nExample XP Requirements:")
        for level in range(1, 11):
            total_xp = calculate_xp_for_level(level)
            if level > 1:
                prev_xp = calculate_xp_for_level(level - 1)
                level_xp = total_xp - prev_xp
                print(f"Level {level}: {level_xp} XP (Total: {total_xp})")
            else:
                print(f"Level {level}: Starting level (Total: {total_xp})")
    else:
        print("XP system validation failed!")
