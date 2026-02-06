import asyncio
import logging
from bot import dp, bot
from database import init_db
from web import app
import uvicorn
import os

async def main():
    if not os.path.exists("assets"):
        os.makedirs("assets")
        print("Создана папка assets. Не забудьте положить туда yacht.jpg и font.ttf!")

    await init_db()
    logging.basicConfig(level=logging.INFO)
    
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
