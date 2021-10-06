import asyncio
import logging
from typing import List
from datetime import datetime, timezone

import aiohttp
from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from tortoise.transactions import in_transaction
from tortoise.contrib.fastapi import register_tortoise

from config import BACKEND_URL, DATABASE_URL, SYNC_TIMEOUT_SECONDS
from app.models import User
from app.serializers import User_Pydantic


app = FastAPI()
db_lock = asyncio.Lock()


@app.on_event("startup")
@repeat_every(seconds=SYNC_TIMEOUT_SECONDS)
async def sync_users_data() -> None:
    # ensure that only one instance of job is running, other instances will be discarded
    if not db_lock.locked():
        await db_lock.acquire()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(BACKEND_URL) as response:  # noqa: E501
                    async with in_transaction():
                        update_data = await response.json()
                        fetched_ids = [_["id"] for _ in update_data]
                        # split update data on already existing and new ones
                        if not fetched_ids:
                            return None
                        existing_users = await User.filter(id__in=fetched_ids)
                        for user in existing_users:
                            user_data = [_ for _ in update_data if _["id"] == user.id][0]
                            user.name = user_data["name"]
                            user.kills = user_data["kills"]
                            user.deaths = user_data["deaths"]
                            user.score = user_data["score"]
                            user.flag = user_data["flag"]
                            user.last_played = datetime.utcfromtimestamp(user_data["lastMove"] / 1000).replace(
                                tzinfo=timezone.utc
                            )  # noqa: E501
                        existing_users_ids = [_.id for _ in existing_users]
                        # detect new users
                        new_users_ids = list(set(fetched_ids) - set(existing_users_ids))
                        new_users_data = [_ for _ in update_data if _["id"] in new_users_ids]
                        new_users = [
                            User(
                                id=_["id"],
                                name=_["name"],
                                kills=_["kills"],
                                deaths=_["deaths"],
                                score=_["score"],
                                flag=_["flag"],
                                last_played=datetime.utcfromtimestamp(_["lastMove"] / 1000).replace(
                                    tzinfo=timezone.utc
                                ),
                            )
                            for _ in new_users_data
                        ]
                        if existing_users:
                            await User.bulk_update(
                                existing_users,
                                fields=["name", "kills", "deaths", "score", "flag", "last_played"],
                            )
                        await User.bulk_create(new_users)
        except Exception as e:
            logging.debug(f":::sync_users_cron: {e}")
        finally:
            db_lock.release()


@app.get("/users", response_model=List[User_Pydantic])
async def get_users():
    return await User_Pydantic.from_queryset(User.all().order_by("-score"))


register_tortoise(
    app,
    db_url=DATABASE_URL,
    modules={"models": ["app.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)
