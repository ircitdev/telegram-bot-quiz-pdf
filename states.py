from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    role_outer = State()
    role_inner = State()
    quiz = State()
    family = State()
    anchor = State()
    cost = State()
    final = State()
