import json
import random
import re
from typing import List, Dict, Optional, Any


class TriviaGame:
    """Core trivia game logic with category support and hint generation.
    
    Questions are expected as a list of dicts with keys:
      - "question": str
      - "category": str (optional)
      - "choices": [str, ...]  (optional)
      - "answer_index": int (index into choices) OR "answer": str
    """

    def __init__(self, questions: List[Dict[str, Any]]):
        self.questions = list(questions)
        self.current = 0
        self.score = 0
        self.streak = 0
        self.last_winner = None

    @classmethod
    def load_from_file(cls, path: str) -> "TriviaGame":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    def shuffle(self) -> None:
        random.shuffle(self.questions)

    def reset(self) -> None:
        self.current = 0
        self.score = 0
        self.streak = 0
        self.last_winner = None

    def remaining(self) -> int:
        return max(0, len(self.questions) - self.current)

    def next_question(self) -> Optional[Dict[str, Any]]:
        if self.current >= len(self.questions):
            return None
        q = self.questions[self.current]
        self.current += 1
        return q

    def get_answer_text(self, question: Dict[str, Any]) -> str:
        """Get the correct answer as a string."""
        if "choices" in question and "answer_index" in question:
            return question["choices"][question["answer_index"]]
        return question.get("answer", "")

    def check_answer(self, question: Dict[str, Any], given: Any, winner_name: str = None) -> bool:
        """Check if the given answer is correct. Updates score and streak."""
        correct = False
        if "answer_index" in question and isinstance(given, int):
            correct = (given == question["answer_index"])
        else:
            expected = str(self.get_answer_text(question)).strip().lower()
            given_s = str(given).strip().lower()
            correct = expected != "" and given_s == expected

        if correct:
            self.score += 1
            if winner_name and winner_name == self.last_winner:
                self.streak += 1
            else:
                self.streak = 1
                self.last_winner = winner_name
        else:
            # Reset streak if no one answered correctly
            if given is None or given == "":
                self.streak = 0
                self.last_winner = None

        return correct

    def generate_hints(self, answer: str, num_hints: int = 3) -> List[str]:
        """Generate progressive masked hints for an answer.
        
        Example: "israel and jordan" -> ["isra** *** ******", "israel a** ******", "israel a** ***dan"]
        """
        if not answer:
            return []
        
        # Replace special chars with spaces for hint generation
        clean = re.sub(r'[^\w\s]', ' ', answer.lower())
        words = clean.split()
        
        hints = []
        
        for hint_num in range(1, num_hints + 1):
            hint_words = []
            
            for word in words:
                word_len = len(word)

                # Fully mask purely-numeric words so hints do not reveal digits
                if word.isdigit():
                    hint_words.append('*' * word_len)
                    continue
                
                if word_len == 1:
                    # Single char: only reveal on last hint
                    # Never reveal single-char words in progressive hints;
                    # they will be revealed only on timeout by the caller.
                    hint_words.append('*')
                elif word_len == 2:
                    # Two chars: reveal 1 char per hint (never fully reveal until last)
                    if hint_num == 1:
                        hint_words.append('**')
                    else:
                        # For hint 2+ reveal first char only; never reveal both in hints
                        hint_words.append(word[0] + '*')
                elif word_len <= 4:
                    # Short words (3-4 chars): reveal gradually
                    # Never fully reveal the word in progressive hints; allow up to
                    # word_len-1 characters to be shown.
                    chars_to_reveal = min(hint_num, max(1, word_len - 1))
                    revealed = word[:chars_to_reveal]
                    masked = '*' * (word_len - chars_to_reveal)
                    hint_words.append(revealed + masked)
                else:
                    # Longer words: progressive reveal based on ratio
                    reveal_ratio = hint_num / (num_hints + 1)
                    chars_to_reveal = max(1, int(word_len * reveal_ratio))
                    # Cap reveal to word_len-1 so hints never show the full word
                    chars_to_reveal = min(chars_to_reveal, word_len - 1)
                    revealed = word[:chars_to_reveal]
                    masked = '*' * (word_len - chars_to_reveal)
                    hint_words.append(revealed + masked)
            
            hints.append(' '.join(hint_words))
        
        return hints


if __name__ == "__main__":
    print("trivia_game.py: library module — import TriviaGame from your code.")
