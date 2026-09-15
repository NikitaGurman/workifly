from aiogram.fsm.state import State, StatesGroup


class AddOrder(StatesGroup):
    choosing_category = State()
    entering_text = State()
    confirming = State()


class NewCategory(StatesGroup):
    entering_name = State()
