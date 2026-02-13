from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    course       = State()   # Q1  — курс 3 слова
    role_outer   = State()   # Q2  — роль (одно слово)
    role_inner   = State()   # Q3  — ядро (одно слово)
    gap          = State()   # Q4  — разрыв (кнопки)
    gap_other    = State()   # Q4  — разрыв "другое" (текст)
    cost         = State()   # Q5  — цена (кнопки)
    family       = State()   # Q6  — семья (кнопки)
    anchor       = State()   # Q7  — якорь (кнопки)
    anchor_other = State()   # Q7  — якорь "другое" (текст)
    stop_action  = State()   # Q8  — поворот (текст)
    first_step   = State()   # Q9  — первый шаг (текст)
    final        = State()   # Q10 — главный вопрос (текст)

class AdminBroadcast(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()

class AdminAdd(StatesGroup):
    waiting_user_id = State()
