from viaggiatreno_ha.trainline import (Viaggiatreno,
                                       TrainLine,
                                       TrainLineStatus,
                                       TrainState,
                                       Timetable,
                                       TrainPath)
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest import TestCase
from unittest.mock import AsyncMock
# import logging

# logging.basicConfig(level=logging.INFO)


class ViaggiatrenoTestCase(AioHTTPTestCase):

    async def get_application(self):

        async def train(request):
            day = request.url.parts[-1]
            with open(f'{day}.json') as r:
                return web.json_response(json.loads(r.read()))

        async def status204(request):
            return web.Response(status=204)

        async def error404(request):
            raise web.HTTPNotFound()

        app = web.Application()
        # Train COMO LAGO to MILANO CADORNA, 2026-01-02
        app.router.add_get('/S01765/136/1767308400000', train)
        # Train COMO LAGO to MILANO CADORNA, 2026-01-03
        app.router.add_get('/S01765/136/1767394800000', train)
        # Train MILANO CENTRALE to TORINO PORTA NUOVA, 2026-01-04
        app.router.add_get('/S01765/136/1767481200000', train)
        app.router.add_get('/S01765/666/*', status204)
        app.router.add_get('/666/*/*', error404)
        return app

    async def test_query_connection(self):
        mock_datetime = \
            datetime(2026, 1, 2,
                     tzinfo=ZoneInfo("America/Los_Angeles"))
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '136')
        await vt.query(tl, get_current_time=lambda: mock_datetime)
        self.assertIn(tl, vt.json)
        data = vt.json[tl]
        self.assertEqual(data['origine'], 'COMO LAGO')

    async def test_past_date_error(self):
        mock_datetime = \
            datetime(2026, 1, 1,
                     tzinfo=ZoneInfo("America/Los_Angeles"))
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '136')
        await vt.query(tl, get_current_time=lambda: mock_datetime)
        self.assertNotIn(tl, vt.json)

    async def test_204_error(self):
        mock_datetime = \
            datetime(2026, 1, 1,
                     tzinfo=ZoneInfo("America/Los_Angeles"))
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '666')
        await vt.query(tl, get_current_time=lambda: mock_datetime)
        self.assertNotIn(tl, vt.json)

    async def test_404_error(self):
        mock_datetime = \
            datetime(2026, 1, 1,
                     tzinfo=ZoneInfo("America/Los_Angeles"))
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('666', '666')
        await vt.query(tl, get_current_time=lambda: mock_datetime)
        self.assertNotIn(tl, vt.json)

    async def test_query_if_useful_first(self):
        mock_datetime = \
            datetime(2026, 1, 2,
                     tzinfo=Viaggiatreno.TZ)
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'
        vt.query = AsyncMock()

        tl = TrainLine('S01765', '136')
        await vt.query_if_useful(tl, get_current_time=lambda: mock_datetime)
        vt.query.assert_awaited_once()

    async def test_query_if_useful(self):
        expected = [{'delta_min': -15, 'awaitings': 1},
                    {'delta_min': -31, 'awaitings': 0},
                    {'delta_min': 62, 'awaitings': 1},
                    {'delta_min': 3*60+62, 'awaitings': 1},
                    {'delta_min': 3*60+63, 'awaitings': 0},
                    ]
        for tcase in expected:
            with self.subTest(f"Query: {tcase['delta_min']}' Δ from start"):
                mock_dt = datetime(2026, 1, 2, 10, 16,
                                   tzinfo=Viaggiatreno.TZ) \
                                   + timedelta(
                                       minutes=tcase['delta_min'])
                vt = Viaggiatreno(self.client)
                vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'
                vt.query = AsyncMock()

                tl = TrainLine('S01765', '136')
                with open('1767308400000.json') as js:
                    vt.json[tl] = json.loads(js.read())

                await vt.query_if_useful(tl,
                                         get_current_time=lambda: mock_dt)
                self.assertEqual(vt.query.await_count, tcase['awaitings'])


class TrainLineStatusTestCase(TestCase):

    def test_json_parsing1(self):
        ts: TrainLineStatus

        expected = {
            '1767308400000.json': {
                'date': datetime(2026, 1, 2,
                                 tzinfo=Viaggiatreno.TZ),
                'last_update': datetime(2026, 1, 2, 11, 10,
                                        tzinfo=Viaggiatreno.TZ),
                'path': TrainPath('COMO LAGO', 'MILANO CADORNA'),
                lambda t: len(t.stops): 15,
                lambda t: t.stops[-1].name: 'MILANO CADORNA',
                'state': TrainState.RUNNING,
                'timetable': Timetable(datetime(2026, 1, 2, 10, 16,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 2, 11, 18,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 2, 10, 17,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 2, 11, 19,
                                                tzinfo=Viaggiatreno.TZ),
                                       1)
            },
            '1767394800000.json': {
                'date': datetime(2026, 1, 3,
                                 tzinfo=Viaggiatreno.TZ),
                'last_update': None,
                'path': TrainPath('COMO LAGO', 'MILANO CADORNA'),
                lambda t: len(t.stops): 15,
                lambda t: t.stops[-2].name: 'MILANO DOMODOSSOLA',
                'state': TrainState.NOT_YET_DEPARTED,
                'timetable': Timetable(datetime(2026, 1, 3, 10, 16,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 3, 11, 18,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 3, 10, 16,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 3, 11, 18,
                                                tzinfo=Viaggiatreno.TZ),
                                       0)
            },
            '1767481200000.json': {
                'date': datetime(2026, 1, 4,
                                 tzinfo=Viaggiatreno.TZ),

                'last_update': datetime(2026, 1, 4, 8, 15,
                                        tzinfo=Viaggiatreno.TZ),
                'path': TrainPath('MILANO CENTRALE', 'TORINO PORTA NUOVA'),
                lambda t: len(t.stops): 4,
                lambda t: t.stops[1].name: 'RHO FIERA',
                'state': TrainState.RUNNING,
                'timetable': Timetable(datetime(2026, 1, 4, 7, 53,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 4, 8, 55,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 4, 8, 8,
                                                tzinfo=Viaggiatreno.TZ),
                                       datetime(2026, 1, 4, 9, 10,
                                                tzinfo=Viaggiatreno.TZ),
                                       15)
            },
        }

        for j in expected:
            with self.subTest(f'Subtest: {j}'):
                with open(j) as js:
                    ts = TrainLineStatus(json.loads(js.read()))
                for k, value in expected[j].items():
                    if isinstance(k, str):
                        self.assertEqual(getattr(ts, k), value, f'wrong {k}')
                    elif callable(k):
                        self.assertEqual(k(ts), value, f'wrong {k}')
                    else:
                        assert False, f"{k} not expected"
