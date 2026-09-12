import json
import random
import re
from typing import List, Dict, Optional, Any, Set


def normalize_alnum(text: str) -> str:
    """Lowercase and strip all non-alphanumeric characters."""
    return re.sub(r'[^a-z0-9]', '', (text or '').lower())


def strip_article(text: str) -> str:
    """Strip leading English articles ('the', 'a', 'an')."""
    t = (text or '').strip().lower()
    for art in ('the ', 'a ', 'an '):
        if t.startswith(art):
            return t[len(art):].strip()
    return t


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
    def load_from_file(cls, path: str, category: Optional[str] = None) -> "TriviaGame":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if category:
            cat_lower = category.strip().lower()
            data = [q for q in data if q.get("category", "").strip().lower() == cat_lower]
        return cls(data)

    @classmethod
    def get_categories(cls, path: str) -> List[str]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cats = sorted({q.get("category", "").strip() for q in data if q.get("category")})
        return cats

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
        """Get the primary canonical answer as a display string."""
        if "choices" in question and "answer_index" in question:
            idx = question["answer_index"]
            if 0 <= idx < len(question["choices"]):
                return question["choices"][idx]
        return question.get("answer", "")

    def get_acceptable_answers(self, question: Dict[str, Any]) -> List[str]:
        """Return all acceptable answer strings and option aliases for a question."""
        answers: Set[str] = set()

        if "choices" in question and "answer_index" in question:
            idx = question["answer_index"]
            choices = question.get("choices", [])
            if 0 <= idx < len(choices):
                choice_text = choices[idx]
                answers.add(choice_text)
                # Allow letter option: A, B, C, D
                if idx < 26:
                    answers.add(chr(ord('a') + idx))
                # Allow number option: 1, 2, 3, 4
                answers.add(str(idx + 1))
            return list(answers)

        raw = question.get("answer", "")
        if not raw:
            return []

        raw_str = str(raw).strip()
        answers.add(raw_str)

        # Handle slash alternatives (e.g. "Margaret Court / Novak Djokovic")
        if " / " in raw_str:
            for part in raw_str.split(" / "):
                part_clean = part.strip()
                if part_clean:
                    answers.add(part_clean)

        # Handle 'or' alternatives (e.g. "Kitten or Kit", "Corn or Wheat")
        if re.search(r'\b or \b', raw_str, re.IGNORECASE):
            for part in re.split(r'\b or \b', raw_str, flags=re.IGNORECASE):
                part_clean = part.strip()
                if part_clean:
                    answers.add(part_clean)

        # Handle parenthetical notes (e.g. "Jawbone (Mandible)", "John Lennon (solo)")
        if '(' in raw_str and ')' in raw_str:
            # Without parentheses
            without_parens = re.sub(r'\s*\([^)]*\)', '', raw_str).strip()
            if without_parens:
                answers.add(without_parens)
            # Inside parentheses
            for inside in re.findall(r'\(([^)]+)\)', raw_str):
                inside_clean = inside.strip()
                # Ignore notes like "(first one)" or "(executive)" unless it's a substantive name
                if inside_clean and not any(k in inside_clean.lower() for k in ['first one', 'executive', 'legislative', 'judicial', 'solo']):
                    answers.add(inside_clean)

        return [a for a in answers if a]

    def is_correct(self, question: Dict[str, Any], given: Any) -> bool:
        """Check if user input matches any acceptable answer."""
        if given is None:
            return False

        given_s = str(given).strip()
        if not given_s:
            return False

        given_lower = given_s.lower()
        given_no_art = strip_article(given_lower)
        given_alnum = normalize_alnum(given_lower)
        given_alnum_no_art = normalize_alnum(given_no_art)

        acceptable = self.get_acceptable_answers(question)
        for variant in acceptable:
            var_lower = variant.strip().lower()
            var_no_art = strip_article(var_lower)
            var_alnum = normalize_alnum(var_lower)
            var_alnum_no_art = normalize_alnum(var_no_art)

            # 1. Exact string match (case-insensitive)
            if given_lower == var_lower:
                return True

            # 2. String match with leading 'the/a/an' stripped
            if given_no_art and given_no_art == var_no_art:
                return True

            # 3. Alphanumeric match (ignores punctuation, dashes, spaces, quotes)
            if given_alnum and given_alnum == var_alnum:
                return True

            # 4. Alphanumeric match with leading articles stripped
            if given_alnum_no_art and given_alnum_no_art == var_alnum_no_art:
                return True

        return False

    def check_answer(self, question: Dict[str, Any], given: Any, winner_name: str = None) -> bool:
        """Check if the given answer is correct. Updates score and streak."""
        if given is None or str(given).strip() == "":
            # Timeout / reset
            self.streak = 0
            self.last_winner = None
            return False

        correct = self.is_correct(question, given)

        if correct:
            self.score += 1
            if winner_name and winner_name == self.last_winner:
                self.streak += 1
            else:
                self.streak = 1
                self.last_winner = winner_name

        return correct

    def generate_hints(self, answer: str, num_hints: int = 3) -> List[str]:
        """Generate progressive masked hints for an answer.
        
        Example: "israel and jordan" -> ["isra** *** ******", "israel a** ******", "israel a** ***dan"]
        """
        if not answer:
            return []
        
        # Replace special chars with spaces for hint generation,
        # but preserve decimal points within numbers (e.g. "26.2" stays as one token)
        clean = re.sub(r'(?<=\d)\.(?=\d)', 'DECPT', answer.lower())
        clean = re.sub(r'[^\w\s]', ' ', clean)
        clean = clean.replace('DECPT', '.')
        words = clean.split()

        # Purely numeric answers (years, counts) can't reveal digits without
        # giving the answer away — give escalating meta-hints instead.
        if words and all(w.isdigit() or re.match(r'^\d+\.\d+$', w) for w in words):
            hints = []
            try:
                val = float(''.join(words)) if len(words) == 1 else None
            except ValueError:
                val = None
            for hint_num in range(1, num_hints + 1):
                masked = ' '.join('*' * len(w) for w in words)
                if val is None:
                    hints.append(masked)
                    continue
                if hint_num == 1:
                    hints.append(f"{masked} (it's a number)")
                elif hint_num == 2:
                    lo = 10 ** (len(str(int(val))) - 1)
                    hints.append(f"{masked} (between {lo} and {lo * 10 - 1})")
                else:
                    if val >= 1000:  # year-like: narrow to the decade
                        decade = int(val) // 10 * 10
                        hints.append(f"{masked} (in the {decade}s)")
                    else:
                        half = 10 ** (len(str(int(val))) - 1) * 5
                        lo = 10 ** (len(str(int(val))) - 1)
                        side = f"under {half}" if val < half else f"{half} or higher"
                        hints.append(f"{masked} ({side})")
            return hints

        # Single-character answers can't be progressively revealed.
        if len(words) == 1 and len(words[0]) == 1:
            return ['* (single letter)', '* (single letter)', '* (single letter)']
        
        hints = []
        
        for hint_num in range(1, num_hints + 1):
            hint_words = []
            
            for word in words:
                word_len = len(word)

                # Fully mask numeric words (including decimals) so hints
                # do not reveal digits
                if word.isdigit() or re.match(r'^\d+\.\d+$', word):
                    hint_words.append('*' * word_len)
                    continue
                
                if word_len == 1:
                    # Single char: only reveal on last hint
                    hint_words.append('*')
                elif word_len == 2:
                    # Two chars: reveal 1 char per hint
                    if hint_num == 1:
                        hint_words.append('**')
                    else:
                        hint_words.append(word[0] + '*')
                elif word_len <= 4:
                    # Short words (3-4 chars): reveal gradually
                    chars_to_reveal = min(hint_num, max(1, word_len - 1))
                    revealed = word[:chars_to_reveal]
                    masked = '*' * (word_len - chars_to_reveal)
                    hint_words.append(revealed + masked)
                else:
                    # Longer words: progressive reveal based on ratio
                    reveal_ratio = hint_num / (num_hints + 1)
                    chars_to_reveal = max(1, int(word_len * reveal_ratio))
                    chars_to_reveal = min(chars_to_reveal, word_len - 1)
                    revealed = word[:chars_to_reveal]
                    masked = '*' * (word_len - chars_to_reveal)
                    hint_words.append(revealed + masked)
            
            hints.append(' '.join(hint_words))
        
        return hints


if __name__ == "__main__":
    print("trivia_game.py: library module — import TriviaGame from your code.")
