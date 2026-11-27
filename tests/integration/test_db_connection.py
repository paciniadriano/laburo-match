from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


async def test_connects_to_the_test_database(session: AsyncSession):
    name = (await session.execute(text("SELECT current_database()"))).scalar_one()

    assert name == "laburo_test"


async def test_session_work_is_invisible_to_others_and_rolled_back(
    session: AsyncSession, engine: AsyncEngine
):
    """`commit()` inside the test only releases a savepoint; a second connection sees nothing."""
    await session.execute(text("CREATE TABLE scratch_isolation (id int)"))
    await session.execute(text("INSERT INTO scratch_isolation VALUES (1)"))
    await session.commit()

    assert (await session.execute(text("SELECT count(*) FROM scratch_isolation"))).scalar_one() == 1
    async with engine.connect() as other:
        exists = await other.execute(text("SELECT to_regclass('scratch_isolation')"))
        assert exists.scalar_one() is None
