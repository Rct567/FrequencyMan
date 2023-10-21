import anki
from aqt import mw # type: ignore
from typing import List

def get_card_review_history(card_id: int) -> List[int]:

    # Define ease level mappings
    ease_mapping = {
        1: "failed",  # Corresponds to ease level 1 in Anki
        2: "hard",    # Corresponds to ease level 2 in Anki
        3: "good",    # Corresponds to ease level 3 in Anki
        4: "easy"     # Corresponds to ease level 4 in Anki
    }

    # Retrieve the review history using mw.col.db
    #review_history = mw.col.db.all("SELECT ease FROM revlog WHERE cid = ?", card_id)
    # entries = self.mw.col.db.all("select id/1000.0, ease, ivl, factor, time/1000.0, type from revlog where cid = ?", card_id)
    review_history = mw.col.db.list("SELECT factor FROM revlog where cid = ?", card_id)
    
    # Extract ease values from the review history, mapping them to strings
    #ease_values = [ease_mapping.get(ease[0], "unknown") for ease in review_history]
    
    return review_history	


def calculate_problematic_score(review_history: List[int]) -> int:
    # Initialize variables to track the score and a deque to store the recent history.
    score: float = 0
    recent_history: List[int] = []

    for index, action in enumerate(review_history):
        recent_history.append(action)

        # Weighted decay factor based on recency
        weight = 1 / (1 + index)  # Weights decrease as actions become more distant

        # Analyze recent history to calculate the score.
        if 1 in recent_history:  # "relapse" corresponds to ease level 3 in Anki
            score += 4 * weight
        elif 2 in recent_history:  # "hard" corresponds to ease level 2 in Anki
            score += 2 * weight
        elif 3 in recent_history:  # "good" corresponds to ease level 1 in Anki
            score -= 1 * weight
        elif 4 in recent_history:  # "easy" corresponds to ease level 4 in Anki
            score -= 0.6 * weight

    return max(0, round(score/len(review_history)))  # Ensure the score is non-negative.

# Example usage:
review_history = [1, 4, 3, 2, 1]
problematic_score = calculate_problematic_score(review_history)
print("Problematic Score:", problematic_score)