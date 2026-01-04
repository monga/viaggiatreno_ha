from viaggiatreno_ha.trainline import Viaggiatreno, TrainLine, TrainLineStatus
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import json
import datetime
from zoneinfo import ZoneInfo
from unittest import TestCase
from unittest.mock import patch
# import logging

# logging.basicConfig(level=logging.INFO)


class ViaggiatrenoTestCase(AioHTTPTestCase):

    async def get_application(self):

        async def train(request):
            day = request.url.parts[-1]
            with open(f'{day}.json') as r:
                return web.json_response(r.read())

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

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_query_connection(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 2,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 2,
                              tzinfo=Viaggiatreno.TZ)
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '136')
        await vt.query(tl)
        data = json.loads(vt.json[tl])
        self.assertEqual(data['origine'], 'COMO LAGO')

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_past_date_error(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=Viaggiatreno.TZ)
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '136')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_204_error(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=Viaggiatreno.TZ)
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('S01765', '666')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_404_error(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=Viaggiatreno.TZ)
        vt = Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = TrainLine('666', '666')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)


class TrainLineStatusTestCase(TestCase):

    def test_json_parsing1(self):
        ts: TrainLineStatus

        expected = {
            '1767308400000.json': {
                'train': TrainLine('S01765', '136'),
                'train_type': 'PG',
                'suppressed_stops': [],
                'day': datetime.datetime(2026, 1, 2,
                                         tzinfo=Viaggiatreno.TZ),
                lambda t: len(t.stops): 15,
                lambda t: t.stops[-1].name: 'MILANO CADORNA',
                'delay': 1,
                'origin': 'COMO LAGO',
                'destination': 'MILANO CADORNA',
                'running': True,
                'arrived': False,
                'scheduled_start': datetime.datetime(2026, 1, 2, 10, 16,
                                                     tzinfo=Viaggiatreno.TZ),
                'scheduled_end': datetime.datetime(2026, 1, 2, 11, 18,
                                                   tzinfo=Viaggiatreno.TZ),
                'actual_start': datetime.datetime(2026, 1, 2, 10, 17,
                                                  tzinfo=Viaggiatreno.TZ),
                'actual_end': datetime.datetime(2026, 1, 2, 11, 19,
                                                tzinfo=Viaggiatreno.TZ),
                'status': None,
                'in_station': False,
                'not_started': False
            },
            '1767394800000.json': {
                'train': TrainLine('S01765', '136'),
                'train_type': 'PG',
                'suppressed_stops': [],
                'day': datetime.datetime(2026, 1, 3,
                                         tzinfo=Viaggiatreno.TZ),
                lambda t: len(t.stops): 15,
                lambda t: t.stops[-2].name: 'MILANO DOMODOSSOLA',
                'delay': 0,
                'origin': 'COMO LAGO',
                'destination': 'MILANO CADORNA',
                'running': True,
                'arrived': False,
                'scheduled_start': datetime.datetime(2026, 1, 3, 10, 16,
                                                     tzinfo=Viaggiatreno.TZ),
                'scheduled_end': datetime.datetime(2026, 1, 3, 11, 18,
                                                   tzinfo=Viaggiatreno.TZ),
                'actual_start': datetime.datetime(2026, 1, 3, 10, 16,
                                                  tzinfo=Viaggiatreno.TZ),
                'actual_end': datetime.datetime(2026, 1, 3, 11, 18,
                                                tzinfo=Viaggiatreno.TZ),
                'status': None,
                'in_station': False,
                'not_started': True
            },
            '1767481200000.json': {
                'train': TrainLine('S01700', '9600'),
                'train_type': 'PG',
                'suppressed_stops': [],
                'day': datetime.datetime(2026, 1, 4,
                                         tzinfo=Viaggiatreno.TZ),
                lambda t: len(t.stops): 4,
                lambda t: t.stops[1].name: 'RHO FIERA',
                'delay': 15,
                'origin': 'MILANO CENTRALE',
                'destination': 'TORINO PORTA NUOVA',
                'running': True,
                'arrived': False,
                'scheduled_start': datetime.datetime(2026, 1, 4, 7, 53,
                                                     tzinfo=Viaggiatreno.TZ),
                'scheduled_end': datetime.datetime(2026, 1, 4, 8, 55,
                                                   tzinfo=Viaggiatreno.TZ),
                'actual_start': datetime.datetime(2026, 1, 4, 8, 8,
                                                  tzinfo=Viaggiatreno.TZ),
                'actual_end': datetime.datetime(2026, 1, 4, 9, 10,
                                                tzinfo=Viaggiatreno.TZ),
                'status': None,
                'in_station': False,
                'not_started': False
            },
        }

        for j in expected:
            with self.subTest(f'Subtest: {j}'):
                with open(j) as js:
                    ts = TrainLineStatus(js.read())
                for k, value in expected[j].items():
                    if isinstance(k, str):
                        self.assertEqual(getattr(ts, k), value, f'wrong {k}')
                    elif callable(k):
                        self.assertEqual(k(ts), value, f'wrong {k}')
                    else:
                        assert False, f"{k} not expected"
