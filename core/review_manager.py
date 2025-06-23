import os
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fsrs import Scheduler, Card as FSRSCard, Rating, ReviewLog as FSRSReviewLog

# --- Pydantic Models for Review System ---

class Flashcard(BaseModel):
    """
    Represents a single flashcard, combining our application's data
    with the scheduling data from the py-fsrs library.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    concept_id: str = Field(..., description="The original concept this card is derived from.")
    question: str = Field(..., description="The question side of the card.")
    answer: str = Field(..., description="The answer side of the card.")
    
    # Stores the state of the FSRS card object as a dictionary
    fsrs_data: Dict[str, Any] = Field(default_factory=lambda: FSRSCard().to_dict())
    
    # We no longer store review history here, as FSRS manages it internally
    # and we are not using the log for any logic at the moment.

class FlashcardDeck(BaseModel):
    """Represents a user's entire collection of flashcards."""
    user_id: str
    cards: Dict[str, Flashcard] = Field(default_factory=dict)
    # The scheduler state can also be saved if we use custom parameters
    scheduler_data: Optional[Dict[str, Any]] = None

# --- Review System Manager ---

class ReviewManager:
    """
    Manages the lifecycle of flashcards using the py-fsrs library.
    """
    def __init__(self, user_profile, deck_storage_path: str = "reviews"):
        self.user_id = user_profile.user_id
        self.storage_path = deck_storage_path
        self.deck_file_path = os.path.join(self.storage_path, f"{self.user_id}_deck.json")
        self.deck = self._load_deck()
        
        # Initialize scheduler, loading its state if it exists
        if self.deck.scheduler_data:
            self.scheduler = Scheduler.from_dict(self.deck.scheduler_data)
        else:
            self.scheduler = Scheduler()

    def _load_deck(self) -> FlashcardDeck:
        """Loads the user's flashcard deck from a JSON file."""
        os.makedirs(self.storage_path, exist_ok=True)
        if os.path.exists(self.deck_file_path):
            with open(self.deck_file_path, 'r', encoding='utf-8') as f:
                try:
                    deck_data = json.load(f)
                    # Removed problematic data migration logic that was nullifying valid date strings.
                    return FlashcardDeck.model_validate(deck_data)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"[ReviewManager] Error loading deck, creating a new one. Error: {e}")
                    # If there's an error (e.g., old format), start fresh.
                    os.remove(self.deck_file_path)
                    return FlashcardDeck(user_id=self.user_id)
        return FlashcardDeck(user_id=self.user_id)

    def _save_deck(self):
        """Saves the user's flashcard deck and scheduler state to a JSON file."""
        self.deck.scheduler_data = self.scheduler.to_dict()
        with open(self.deck_file_path, 'w', encoding='utf-8') as f:
            f.write(self.deck.model_dump_json(indent=4))
        print(f"[ReviewManager] Deck for user '{self.user_id}' saved to {self.deck_file_path}")

    def add_card(self, concept_id: str, question: str, answer: str) -> Optional[Flashcard]:
        """Creates a new flashcard and adds it to the deck."""
        for card in self.deck.cards.values():
            if card.question == question:
                print(f"[ReviewManager] Flashcard with same question already exists. Skipping.")
                return None

        card = Flashcard(concept_id=concept_id, question=question, answer=answer)
        
        # Ensure the initial fsrs_data is JSON compatible (dates as strings)
        fsrs_dict = card.fsrs_data
        json_str = json.dumps(fsrs_dict, default=str)
        card.fsrs_data = json.loads(json_str)

        self.deck.cards[card.id] = card
        self._save_deck()
        print(f"[ReviewManager] New flashcard created for concept '{concept_id}'.")
        return card

    def delete_card(self, card_id: str):
        """Deletes a flashcard from the deck."""
        if card_id in self.deck.cards:
            del self.deck.cards[card_id]
            self._save_deck()
            print(f"[ReviewManager] Deleted flashcard with ID '{card_id}'.")
            return True
        else:
            print(f"[ReviewManager] Error: Card with ID '{card_id}' not found for deletion.")
            return False

    def get_due_cards(self) -> List[Flashcard]:
        """Returns a list of all cards that are due for review."""
        now = datetime.now(timezone.utc)
        due_cards = []
        for card in self.deck.cards.values():
            # Hotfix: Ensure date fields are strings before passing to fsrs lib,
            # as it expects ISO strings and might receive datetime objects.
            fsrs_data = card.fsrs_data.copy()
            if isinstance(fsrs_data.get("due"), datetime):
                fsrs_data["due"] = fsrs_data["due"].isoformat()
            if isinstance(fsrs_data.get("last_review"), datetime):
                fsrs_data["last_review"] = fsrs_data["last_review"].isoformat()

            fsrs_card = FSRSCard.from_dict(fsrs_data)
            if fsrs_card.due <= now:
                due_cards.append(card)
        return due_cards

    def update_card_review(self, card_id: str, user_rating: str):
        """
        Updates a card's SRS data based on the user's review using the py-fsrs library.
        """
        app_card = self.deck.cards.get(card_id)
        if not app_card:
            print(f"[ReviewManager] Error: Card with ID '{card_id}' not found.")
            return

        rating_map = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}
        rating = rating_map.get(user_rating)
        if not rating:
            print(f"[ReviewManager] Error: Invalid user rating '{user_rating}'.")
            return
        
        # Load the FSRS card state from our application's card
        fsrs_card = FSRSCard.from_dict(app_card.fsrs_data)

        # Let the scheduler review the card
        updated_fsrs_card, review_log = self.scheduler.review_card(fsrs_card, rating)

        # Save the updated FSRS card state back to our application's card.
        # We perform a JSON round-trip to ensure datetime objects are converted
        # to ISO strings, which is the format FSRSCard.from_dict expects.
        updated_dict = updated_fsrs_card.to_dict()
        json_str = json.dumps(updated_dict, default=str)
        app_card.fsrs_data = json.loads(json_str)

        self._save_deck()
        print(f"[ReviewManager] Card '{card_id}' reviewed with py-fsrs. New state: {updated_fsrs_card.state}. Next review: {updated_fsrs_card.due.strftime('%Y-%m-%d')}")