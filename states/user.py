from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choosing_ui_language = State()
    choosing_timezone = State()
    choosing_timezone_manual = State()


class ProfileStates(StatesGroup):
    editing_timezone_manual = State()
    editing_digest_time = State()
    editing_quiet_hours = State()


class SearchStates(StatesGroup):
    waiting_query = State()
