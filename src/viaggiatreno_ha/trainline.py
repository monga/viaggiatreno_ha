"""
Data model for Trenitalia Viaggiatreno API
for the needs of Home Assistant.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from enum import Enum, auto
from aiohttp import ClientTimeout, ClientSession  # type: ignore

_LOGGER = logging.getLogger(__name__)

VIAGGIATRENO_TZ = ZoneInfo('Europe/Rome')


def ms_ts_to_dt(timestamp: int) -> datetime:
    """Convert a UNIX timestamp (in ms) to a datetime
       in ViaggiaTreno timezone."""
    return datetime.fromtimestamp(timestamp/1000, tz=VIAGGIATRENO_TZ)


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


@dataclass
class TrainStop:
    """A train scheduled stop in the train line.
    """
    name: str
    station_id: str
    scheduled: datetime
    actual: datetime | None
    delay: int
    actual_track: str | None


class TrainState(Enum):
    """
    States for train lines.
    """
    NOT_YET_DEPARTED = auto()
    RUNNING = auto()
    PARTIALLY_CANCELLED = auto()
    CANCELLED = auto()
    ARRIVED = auto()
    UNKNOWN = auto()


@dataclass
class TrainPath:
    """
    Actual path of a train line.
    """
    origin: str
    destination: str


@dataclass
class Timetable:
    """
    Scheduled and actual times for a train.
    """
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start: datetime | None
    actual_end: datetime | None
    delay: int


@dataclass
class TrainLineStatus:
    """
    Status of a train line.
    """
    date: datetime
    last_update: datetime | None
    path: TrainPath
    stops: list[TrainStop]
    state: TrainState
    timetable: Timetable

    def __init__(self, data: dict):
        """Create TrainLineStatus from json parsed data.
        """
        self.date = ms_ts_to_dt(data["dataPartenzaTreno"])
        self.state = TrainState.UNKNOWN

        def comp_to_dt(field: str) -> datetime | None:
            assert field in data
            if data[field] is not None and data[field] != '--':
                h, m = map(int, data[field].split(':'))
                return datetime(self.date.year,
                                self.date.month,
                                self.date.day,
                                h, m,
                                tzinfo=VIAGGIATRENO_TZ)
            return None

        self.last_update = comp_to_dt('compOraUltimoRilevamento')

        self.stops = []
        for stop in data['fermate']:
            scheduled = ms_ts_to_dt(stop['programmata'])
            if stop['effettiva'] is not None:
                actual = ms_ts_to_dt(stop['effettiva'])
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

        if data['tipoTreno'] == 'PG' and data['provvedimento'] == 0:
            if data['nonPartito']:
                self.state = TrainState.NOT_YET_DEPARTED
            else:
                self.state = TrainState.RUNNING
        elif data['tipoTreno'] == 'ST' and data['provvedimento'] == 1:
            self.state = TrainState.CANCELLED
        elif data['tipoTreno'] in ('PP', 'SI', 'SF'):
            self.state = TrainState.PARTIALLY_CANCELLED
        elif data['arrivato']:
            self.state = TrainState.ARRIVED
        else:
            # Unknown state (a deviation?)
            assert data['provvedimento'] != 0

        self.path = TrainPath(data['origine'], data['destinazione'])

        scheduled_start = ms_ts_to_dt(data['orarioPartenza'])
        scheduled_end = ms_ts_to_dt(data['orarioArrivo'])
        actual_start = comp_to_dt("compOrarioPartenzaZeroEffettivo")
        actual_end = comp_to_dt("compOrarioArrivoZeroEffettivo")
        self.timetable = Timetable(scheduled_start, scheduled_end,
                                   actual_start, actual_end,
                                   data['ritardo'])


class Viaggiatreno:
    """
       Query ViaggiaTreno API with
       `query_if_useful(TrainLine('S01765', '136'))`.
    """
    ENDPOINT = (
        "http://www.viaggiatreno.it/infomobilita/"
        "resteasy/viaggiatreno/andamentoTreno/"
        "{station_id}/{train_id}/{timestamp}"
    )
    TIMEOUT = ClientTimeout(total=15, connect=5)  # seconds

    def __init__(self, session: ClientSession):
        self.session = session
        self.json: dict[TrainLine, dict] = {}

    def get_line_status(self, line: TrainLine) -> TrainLineStatus | None:
        """Return the status of the train line, if already queried..
        """
        if line in self.json:
            return TrainLineStatus(self.json[line])
        return None

    async def query(self, line: TrainLine,
                    get_current_time=lambda:
                    datetime.now(tz=VIAGGIATRENO_TZ)):
        """
           Query the ViaggiaTreno API about a TrainLine.
           ViaggiaTreno gives data only for trains departing today
           (according to Europe/Rome timezone).
        """
        current_time = get_current_time()
        midnight = datetime(current_time.year,
                            current_time.month,
                            current_time.day,
                            tzinfo=VIAGGIATRENO_TZ)
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
            elif response.status == 204:
                _LOGGER.info("No content: check query parameters")
            else:
                _LOGGER.info("Server response not OK: %s", response)

    async def query_if_useful(self, line: TrainLine,
                              before: timedelta = timedelta(minutes=30),
                              after: timedelta = timedelta(hours=3),
                              get_current_time=lambda:
                              datetime.now(tz=VIAGGIATRENO_TZ)):
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
            data = self.json[line]
            trainline_date = ms_ts_to_dt(
                data['dataPartenzaTreno'])
            now = get_current_time()
            start = ms_ts_to_dt(data['orarioPartenza']) - before
            end = ms_ts_to_dt(data['orarioArrivo']) + after
            if (now.date() != trainline_date.date() or start <= now <= end):
                await self.query(line)


async def main():
    """Example of use."""
    async with ClientSession() as session:
        vt = Viaggiatreno(session)
        tl = TrainLine('S01765', '136')
        await vt.query_if_useful(tl)
        print(vt.get_line_status(tl))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
