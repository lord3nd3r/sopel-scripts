import sys
sys.path.insert(0, '/run/user/1000/gvfs/sftp:host=boston.3nd3r.net/home/ender/.sopel/scripts')

from trivia_game import TriviaGame


def test_check_answer_index():
    q = {"question": "2+2?", "choices": ["3", "4"], "answer_index": 1}
    g = TriviaGame([q])
    q1 = g.next_question()
    assert g.check_answer(q1, 1) is True
    assert g.score == 1


def test_check_answer_text():
    q = {"question": "Spell color (US)", "answer": "color"}
    g = TriviaGame([q])
    q1 = g.next_question()
    assert g.check_answer(q1, "color") is True
    assert g.score == 1


def test_category_support():
    questions = [
        {"category": "Geography", "question": "Capital of France?", "answer": "paris"},
        {"category": "Science", "question": "Chemical symbol for gold?", "answer": "au"}
    ]
    g = TriviaGame(questions)
    q1 = g.next_question()
    assert q1.get("category") == "Geography"


def test_generate_hints():
    g = TriviaGame([])
    hints = g.generate_hints("israel and jordan", num_hints=3)
    assert len(hints) == 3
    # First hint should have more masked characters
    assert "*" in hints[0]
    # Last hint should reveal more
    assert hints[2].count("*") < hints[0].count("*")


def test_streak_tracking():
    q = {"question": "Test?", "answer": "yes"}
    g = TriviaGame([q, q, q])
    
    g.next_question()
    g.check_answer({"answer": "yes"}, "yes", winner_name="Player1")
    assert g.streak == 1
    
    g.next_question()
    g.check_answer({"answer": "yes"}, "yes", winner_name="Player1")
    assert g.streak == 2
    
    g.next_question()
    g.check_answer({"answer": "yes"}, "yes", winner_name="Player2")
    assert g.streak == 1  # Streak resets for different winner


if __name__ == "__main__":
    print("Running tests...")
    test_check_answer_index()
    print("✓ test_check_answer_index")
    test_check_answer_text()
    print("✓ test_check_answer_text")
    test_category_support()
    print("✓ test_category_support")
    test_generate_hints()
    print("✓ test_generate_hints")
    test_streak_tracking()
    print("✓ test_streak_tracking")
    print("\nAll tests passed!")
