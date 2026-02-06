"""Тестовая генерация PDF для проверки дизайна"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pdf_gen import create_pdf

# Тестовые данные
test_data = {
    'full_name': 'Александр Упадышев',
    'role_outer': 'Предприниматель',
    'role_inner': 'Искатель',
    'nav_score': 'Переход (Transition)',
    'family_presence': 'В телефоне и мыслях о сделках',
    'anchor_word': 'Спокойствие',
    'cost_of_delay': 'Здоровье',
    'final_question': 'Как найти баланс между бизнесом и семьей?'
}

print("Generating test PDF...")
try:
    filename = "Test_Strategy.pdf"
    result = create_pdf(test_data, filename)
    if result:
        print(f"[OK] PDF created: {result}")
        # Get file size
        size = os.path.getsize(result)
        print(f"     Size: {size} bytes ({size/1024:.1f} KB)")
    else:
        print("[ERROR] PDF not created")
except Exception as e:
    print(f"[ERROR] Generation failed: {e}")
    import traceback
    traceback.print_exc()
