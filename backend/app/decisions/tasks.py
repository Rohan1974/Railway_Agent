"""Classification tasks shared by both modes.

Each task maps to one Jev question type (choice or noulli), and the Claude classifier gets the
same options and descriptions, so both models answer exactly the same question.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionTask:
    name: str
    jev_type: str                 # "choice" | "noulli"
    question: str
    options: dict[str, str]       # label -> description
    uses_context: bool = False    # True: the last assistant message is part of the input


TASKS: dict[str, DecisionTask] = {t.name: t for t in [
    DecisionTask(
        name="intent",
        jev_type="choice",
        question="What does the user want from the railway booking assistant in this message?",
        options={
            "search_trains": "Find trains between two places or on a date",
            "check_availability": "Check seats or berths left on a specific train",
            "get_fare": "Ask the ticket price or fare",
            "book_ticket": "Book or reserve a ticket",
            "pnr_status": "Check the status of an existing booking or PNR",
            "cancel_ticket": "Cancel an existing booking or get a refund for it",
            "provide_details": "Give details the assistant asked for (passenger names, ages, a choice, a station)",
            "greeting": "Greeting, thanks or small talk with no request",
            "off_topic": "Anything that is not about Indian Railways train travel (flights, buses, cabs, hotels, general questions)",
        },
    ),
    DecisionTask(
        name="travel_class",
        jev_type="choice",
        question="Which travel class does the user ask for?",
        options={
            "SL": "Sleeper",
            "3A": "AC 3 Tier / third AC / 3AC",
            "2A": "AC 2 Tier / second AC / 2AC",
            "1A": "AC First Class / first AC",
            "CC": "AC Chair Car",
            "EC": "Executive Chair Car / executive class",
            "none": "No specific class is mentioned (including a generic 'AC')",
        },
    ),
    DecisionTask(
        name="quota",
        jev_type="choice",
        question="Which booking quota does the user ask for?",
        options={
            "GN": "General quota, or no quota mentioned",
            "TQ": "Tatkal",
            "LD": "Ladies quota",
            "SS": "Senior citizen quota",
        },
    ),
    DecisionTask(
        name="confirmation",
        jev_type="choice",
        question="The assistant asked the user to confirm an action. How did the user answer?",
        options={
            "yes": "Confirms the action exactly as proposed",
            "no": "Rejects it, wants to wait, or wants changes first",
            "unclear": "Asks a question or has not decided",
        },
        uses_context=True,
    ),
    DecisionTask(
        name="frustration",
        jev_type="noulli",
        question="Is the user frustrated or annoyed with the assistant?",
        options={
            "frustrated": "The user is frustrated, annoyed or angry",
            "not_frustrated": "The user is neutral or happy",
        },
    ),
]}
