import streamlit as st
import random
import logging

logger = logging.getLogger(__name__)

def show_xp_notification(xp_amount, activity):
    """Displays a notification for XP earned."""
    st.success(f"You earned +{xp_amount} XP for {activity}!")

def render_cooking_quiz():
    """Renders a cooking quiz using Streamlit."""

    user_id = st.session_state.get("user_id")
    if not user_id:
        st.error("User ID not found. Please log in.")
        return

    if "quiz_questions" not in st.session_state:
        st.session_state.quiz_questions = [
            {
                "question": "What is the Maillard reaction?",
                "options": [
                    "A reaction between amino acids and reducing sugars",
                    "A type of food poisoning",
                    "The process of freezing food",
                    "A chemical reaction that causes food to spoil"
                ],
                "correct_answer": "A reaction between amino acids and reducing sugars"
            },
            {
                "question": "What is the best way to cook a steak?",
                "options": [
                    "Pan-sear it",
                    "Boil it",
                    "Microwave it",
                    "Deep fry it"
                ],
                "correct_answer": "Pan-sear it"
            },
            {
                "question": "What is the best way to cook pasta?",
                "options": [
                    "Boil it in salted water",
                    "Boil it in unsalted water",
                    "Microwave it",
                    "Deep fry it"
                ],
                "correct_answer": "Boil it in salted water"
            },
            {
                "question": "What is the best way to cook rice?",
                "options": [
                    "Steam it",
                    "Boil it",
                    "Microwave it",
                    "Deep fry it"
                ],
                "correct_answer": "Steam it"
            },
            {
                "question": "What is the best way to cook vegetables?",
                "options": [
                    "Steam them",
                    "Boil them",
                    "Microwave them",
                    "Deep fry them"
                ],
                "correct_answer": "Steam them"
            }
        ]
        random.shuffle(st.session_state.quiz_questions)

    st.header("Cooking Quiz")

    st.info("""
**Cooking Quiz:**
- Complete quiz: +2 XP per question
- Perfect score: +5 bonus XP
- Daily streak: +2 bonus XP
""")

    if "quiz_answers" not in st.session_state:
        st.session_state.quiz_answers = {}

    for i, question_data in enumerate(st.session_state.quiz_questions):
        question = question_data["question"]
        options = question_data["options"]
        correct_answer = question_data["correct_answer"]

        st.subheader(f"Question {i + 1}:")
        user_answer = st.radio(question, options, key=f"question_{i}")
        st.session_state.quiz_answers[question] = user_answer

    if st.button("Submit Quiz"):
        correct_count = 0
        for question_data in st.session_state.quiz_questions:
            question = question_data["question"]
            correct_answer = question_data["correct_answer"]
            if st.session_state.quiz_answers.get(question) == correct_answer:
                correct_count += 1

        score_percentage = (correct_count / len(st.session_state.quiz_questions)) * 100
        st.write(f"You got {correct_count} out of {len(st.session_state.quiz_questions)} questions correct!")
        st.write(f"Your score: {score_percentage:.2f}%")

        # Award XP - more reasonable amounts
        base_xp_per_question = 2  # 2 XP per question instead of 3
        base_xp = base_xp_per_question * len(st.session_state.quiz_questions)
        bonus_xp = 5 if score_percentage == 100 else 0  # 5 bonus XP for perfect score instead of 10
        total_xp = base_xp + bonus_xp

        try:
            from modules.leftover import update_user_stats
            update_user_stats(user_id, total_xp, quizzes_completed=1)
            show_xp_notification(total_xp, "completing cooking quiz")
        except Exception as e:
            logger.error(f"Error awarding quiz XP: {str(e)}")
