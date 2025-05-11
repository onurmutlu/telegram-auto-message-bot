import asyncio
from database.user_db import UserDatabase

async def run_migration():
    db = UserDatabase()
    await db.connect()
    print('Bağlantı kuruldu, migrasyonlar çalıştırılıyor...')
    await db.run_migrations()
    print('Migrasyonlar tamamlandı')

if __name__ == "__main__":
    asyncio.run(run_migration()) 