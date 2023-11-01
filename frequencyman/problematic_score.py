import anki
from aqt import mw # type: ignore
from typing import TypedDict

from .lib.utilities import chunked_list

#var_dump([mw.col.card_stats_data(card.id).revlog, mw.col.db.all("SELECT id, ease, ivl,  lastIvl, factor, type FROM revlog WHERE cid = ?", card.id)])



    
ReviewEntry = TypedDict('ReviewEntry', {"id": int, "ease": int, "ivl": int, "lastIvl": int, "factor": int, "type": int})

def get_cards_review_history(card_ids: list[int]) -> dict[int, list[ReviewEntry]]:
    
    cards_review_history: dict[int, list[ReviewEntry]] = {}

    for chunk in chunked_list(card_ids, 400):

        card_ids_str = ','.join(map(str, chunk))
        query = f"SELECT cid, id, ease, ivl, lastIvl, factor, type FROM revlog WHERE cid IN ({card_ids_str})"
        results = mw.col.db.all(query)

        # Iterate through the results and organize them into the dictionary
        for row in results:
            card_id = row[0]
            review_entry: ReviewEntry = {
                "id": row[1],         # Unique identifier for the review entry, timestamp
                "ease": row[2],       # Ease level chosen by the user (1: Wrong/relapse, 2: Hard, 3: Good, 4: Easy)
                "ivl": row[3],        # Interval until the next review (in seconds)
                "lastIvl": row[4],    # Last interval before the current one (in seconds)
                "factor": row[5],     # Ease factor used in the spaced repetition algorithm
                "type": row[6]        # Type of review event (e.g., '0' for regular reviews, '1' for learning reviews)
            }

            # Check if the card ID is already in the dictionary; if not, create a new list
            if card_id not in cards_review_history:
                cards_review_history[card_id] = []

            # Append the review entry to the corresponding card's list
            cards_review_history[card_id].append(review_entry)
            

    return cards_review_history

""" def get_card_review_history(card_id:int) -> list[ReviewEntry]:

    results = mw.col.db.all("SELECT id, ease, ivl, lastIvl, factor, type FROM revlog WHERE cid = ?", card_id)

    review_history = []
    for row in results:  
        review_entry: ReviewEntry = {
            "id": row[0],         # Unique identifier for the review entry, timestamp
            "ease": row[1],       # Ease level chosen by the user (1: Wrong/relapse, 2: Hard, 3: Good, 4: Easy)
            "ivl": row[2],        # Interval until the next review (in seconds)
            "lastIvl": row[3],    # Last interval before the current one (in seconds)
            "factor": row[4],     # Ease factor used in the spaced repetition algorithm
            "type": row[5]        # Type of review event (e.g., '0' for regular reviews, '1' for learning reviews)
        }

        review_history.append(review_entry)

    return review_history """


def calculate_problematic_score(review_history: list[ReviewEntry]) -> int:
    # Initialize variables to track the score and a deque to store the recent history.
    score: float = 0
    recent_history: list[int] = []
    # Sort the review history by 'id' in ascending order
    review_history.sort(key=lambda x: x['id'])

    for index, entry in enumerate(review_history):
        action = entry['ease'] 
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

