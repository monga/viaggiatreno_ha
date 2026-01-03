import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
import logging
import aiohttp  # type: ignore
import json

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainLine:
    starting_station: str
    train_id: str


class Viaggiatreno:
    ENDPOINT = (
        "http://www.viaggiatreno.it/infomobilita/"
        "resteasy/viaggiatreno/andamentoTreno/"
        "{station_id}/{train_id}/{timestamp}"
    )
    TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)  # seconds
    TZ = ZoneInfo('Europe/Rome')

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.json: dict[TrainLine, str] = {}

    async def query(self, line: TrainLine):
        now = datetime.datetime.now(tz=self.TZ)
        midnight = datetime.datetime(now.year, now.month, now.day,
                                     tzinfo=self.TZ)
        midnight_ms = 1000 * int(midnight.timestamp())
        uri = self.ENDPOINT.format(station_id=line.starting_station,
                                   train_id=line.train_id,
                                   timestamp=midnight_ms)

        _LOGGER.info(f"I'm going to query: {uri}")
        async with self.session.get(uri,
                                    timeout=self.TIMEOUT) as response:
            if response.status == 200:
                js = await response.json()
                self.json[line] = js


@dataclass
class TrainStop:
    name: str
    station_id: str
    scheduled: int
    actual: int | None
    delay: int
    actual_track: str | None


class Treno:
    def __init__(self,
                 station_id: str,
                 train_id: str):
        pass

