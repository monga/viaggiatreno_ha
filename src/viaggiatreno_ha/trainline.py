"""
Data model for Trenitalia Viaggiatreno API
for the needs of Home Assistant.
"""

import logging
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from aiohttp import ClientTimeout, ClientSession  # type: ignore

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainLine:
    """
        A train line is defined by its departing (first) station code
        and the train line id.

        For example: `TrainLine('S01765', '136')`

        Use
        http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/autocompletaStazione/PREFIX
        to get the station codes for PREFIX* stations
        (change the prefix for others).
    """
    starting_station: str
    train_id: str


class Viaggiatreno:
    """
       Query ViaggiaTreno API with `query_if_running(TrainLine('S01765', '136'))`.
       The query result is cached and queried again only if possibly needed,
       assuming train line changes can happen only 30' min before departure and 3h
       after the scheduled arrive.

    """
    ENDPOINT = (
        "http://www.viaggiatreno.it/infomobilita/"
        "resteasy/viaggiatreno/andamentoTreno/"
        "{station_id}/{train_id}/{timestamp}"
    )
    TIMEOUT = ClientTimeout(total=15, connect=5)  # seconds
    TZ = ZoneInfo('Europe/Rome')

    def __init__(self, session: ClientSession):
        self.session = session
        self.json: dict[TrainLine, str] = {}

    @classmethod
    def ms_ts_to_dt(cls, timestamp: int) -> datetime:
        """Convert a UNIX timestamp (in ms) to a datetime in ViaggiaTreno timezone."""
        return datetime.fromtimestamp(timestamp/1000,
                                      tz=cls.TZ)

    async def query(self, line: TrainLine,
                    get_current_time=lambda:
                    datetime.now(tz=Viaggiatreno.TZ)):
        """
           Query the ViaggiaTreno API about a TrainLine.
           ViaggiaTreno gives data only for trains departing today
           (according to Europe/Rome timezone).
        """
        current_time = get_current_time()
        midnight = datetime(current_time.year,
                            current_time.month,
                            current_time.day,
                            tzinfo=self.TZ)
        midnight_ms = 1000 * int(midnight.timestamp())
        uri = self.ENDPOINT.format(station_id=line.starting_station,
                                   train_id=line.train_id,
                                   timestamp=midnight_ms)

        _LOGGER.info("I'm going to query: %s", uri)
        async with self.session.get(uri,
                                    timeout=self.TIMEOUT) as response:
            if response.status == 200:
                js = await response.json()
                assert isinstance(js, dict), f"Not a dict, but a {type(js)}"
                self.json[line] = js

    async def query_if_useful(self, line: TrainLine,
                               before: timedelta = timedelta(minutes=30),
                               after: timedelta = timedelta(hours=3),
                               get_current_time=lambda:
                               datetime.now(tz=Viaggiatreno.TZ)):
        """
           Query the ViaggiaTreno API about a TrainLine, assuming train line
           changes can happen only 30' min before departure and 3h
           after the scheduled arrive.
           ViaggiaTreno gives data only for trains departing today
           (according to Europe/Rome timezone).
        """
        if line not in self.json:
            await self.query(line)
        else:
            data = json.loads(self.json[line])
            trainline_date = Viaggiatreno.ms_ts_to_dt(
                data['dataPartenzaTreno'])
            now = get_current_time()
            start = (Viaggiatreno.ms_ts_to_dt(data['orarioPartenza'])
                     - before)
            end = (Viaggiatreno.ms_ts_to_dt(data['orarioArrivo'])
                   + after)
            if (now.date() != trainline_date.date() or start <= now <= end):
                await self.query(line)


@dataclass
class TrainStop:
    """A train stop in the train line.
    """
    name: str
    station_id: str
    scheduled: datetime
    actual: datetime | None
    delay: int
    actual_track: str | None


@dataclass
class TrainLineStatus:
    """Status of a train line.
    """
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

    def __init__(self, data: dict):
        """Create TrainLineStatus from json parsed data.
        """
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
    """Example of use."""
    async with ClientSession() as session:
        vt = Viaggiatreno(session)
        tl = TrainLine('S01765', '136')
        await vt.query_if_useful(tl)
        print(vt.json[tl])

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
