import asyncio
import uuid
from sqlalchemy import select
from app.database import async_session
from app.models.user import User

async def seed():
    async with async_session() as db:
        uid = uuid.UUID('5dc41bda-2383-4e56-8f37-661cf313163d')
        user = await db.scalar(select(User).where(User.id == uid))
        if not user:
            user = User(id=uid, email='test@example.com', display_name='Test User')
            db.add(user)
            await db.commit()
            print('User seeded')
        else:
            print('User exists')

if __name__ == '__main__':
    asyncio.run(seed())
