from viaggiatreno_ha import trainline
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web
import json
import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
import logging

logging.basicConfig(level=logging.INFO)


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
                              tzinfo=trainline.Viaggiatreno.TZ)
        vt = trainline.Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = trainline.TrainLine('S01765', '136')
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
                              tzinfo=trainline.Viaggiatreno.TZ)
        vt = trainline.Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = trainline.TrainLine('S01765', '136')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_204_error(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=trainline.Viaggiatreno.TZ)
        vt = trainline.Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = trainline.TrainLine('S01765', '666')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)

    @patch('viaggiatreno_ha.trainline.datetime')
    async def test_404_error(self, mock_datetime):
        mock_datetime.now.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=ZoneInfo("America/Los_Angeles"))
        mock_datetime.datetime.return_value = \
            datetime.datetime(2026, 1, 1,
                              tzinfo=trainline.Viaggiatreno.TZ)
        vt = trainline.Viaggiatreno(self.client)
        vt.ENDPOINT = '/{station_id}/{train_id}/{timestamp}'

        tl = trainline.TrainLine('666', '666')
        await vt.query(tl)
        self.assertNotIn(tl, vt.json)
