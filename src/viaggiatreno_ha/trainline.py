from datetime import datetime, timedelta
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

    @classmethod
    def ms_ts_to_dt(cls, timestamp: int) -> datetime:
        return datetime.fromtimestamp(timestamp/1000,
                                      tz=cls.TZ)

    async def query(self, line: TrainLine,
                    get_current_time=lambda:
                    datetime.now(tz=Viaggiatreno.TZ)):
        current_time = get_current_time()
        midnight = datetime(current_time.year,
                            current_time.month,
                            current_time.day,
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

    async def query_if_running(self, line: TrainLine,
                               get_current_time=lambda:
                               datetime.now(tz=Viaggiatreno.TZ)):
        if line not in self.json:
            await self.query(line)
        else:
            data = json.loads(self.json[line])
            now = get_current_time()
            start = (Viaggiatreno.ms_ts_to_dt(data['orarioPartenza'])
                     - timedelta(minutes=30))
            end = (Viaggiatreno.ms_ts_to_dt(data['orarioArrivo'])
                   + timedelta(hours=3))
            if start <= now <= end:
                await self.query(line)


@dataclass
class TrainStop:
    name: str
    station_id: str
    scheduled: datetime
    actual: datetime | None
    delay: int
    actual_track: str | None


class TrainLineStatus:
    train: TrainLine
    train_type: str
    suppressed_stops: list[int]
    day: datetime
    stops: list[TrainStop]
    last_update: datetime | None
    delay: int
    origin: str
    destination: str
    running: bool
    arrived: bool
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    status: str | None
    in_station: bool
    not_started: bool

    def __init__(self, json_data: str):
        data = json.loads(json_data)

        self.train = TrainLine(str(data['idOrigine']),
                               str(data['numeroTreno']))
        self.train_type = data["tipoTreno"]
        self.suppressed_stops = data["fermateSoppresse"]
        y, m, d = map(int, data["dataPartenzaTrenoAsDate"].split("-"))
        self.day = datetime(y, m, d,
                            tzinfo=Viaggiatreno.TZ)
        if data['ultimoRilev'] is not None:
            self.last_update = Viaggiatreno.ms_ts_to_dt(data['ultimoRilev'])
        else:
            self.last_update = None
        self.stops = []
        for stop in data['fermate']:
            scheduled = Viaggiatreno.ms_ts_to_dt(stop['programmata'])
            if stop['effettiva'] is not None:
                actual = Viaggiatreno.ms_ts_to_dt(stop['effettiva'])
            else:
                actual = None
            if stop['binarioEffettivoArrivoDescrizione'] is not None:
                track = stop['binarioEffettivoArrivoDescrizione']
            else:
                track = None

            s = TrainStop(stop['stazione'],
                          stop['id'],
                          scheduled,
                          actual,
                          stop['ritardo'],
                          track)
            self.stops.append(s)
        self.delay = data['ritardo']
        self.origin = data['origine']
        self.destination = data['destinazione']
        self.running = data['circolante']
        self.arrived = data['arrivato']
        self.scheduled_start = Viaggiatreno.ms_ts_to_dt(data['orarioPartenza'])
        self.scheduled_end = Viaggiatreno.ms_ts_to_dt(data['orarioArrivo'])
        if data["compOrarioPartenzaZeroEffettivo"] is not None:
            h, m = map(int, data["compOrarioPartenzaZeroEffettivo"].split(':'))
            self.actual_start = datetime(self.scheduled_start.year,
                                         self.scheduled_start.month,
                                         self.scheduled_start.day,
                                         h, m,
                                         tzinfo=Viaggiatreno.TZ)
        else:
            self.actual_start = None
        if data["compOrarioArrivoZeroEffettivo"] is not None:
            h, m = map(int, data["compOrarioArrivoZeroEffettivo"].split(':'))
            self.actual_end = datetime(self.scheduled_end.year,
                                       self.scheduled_end.month,
                                       self.scheduled_end.day,
                                       h, m,
                                       tzinfo=Viaggiatreno.TZ)
        else:
            self.actual_end = None

        self.status = data['statoTreno']
        self.in_station = data['inStazione']
        self.not_started = data['nonPartito']


async def main():
    async with aiohttp.ClientSession() as session:
        vt = Viaggiatreno(session)
        tl = TrainLine('S01765', '136')
        await vt.query(tl)
        print(vt.json[tl])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
