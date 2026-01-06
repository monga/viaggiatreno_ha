This package is designed to query the
[http://www.viaggiatreno.it/infomobilita/index.jsp](Trenitalia ViaggiaTreno) API
(that are mostly undocumented, but see
[https://github.com/roughconsensusandrunningcode/TrainMonitor/wiki/API-del-sistema-Viaggiatreno](here,
in Italian)) in a
[https://www.home-assistant.io/integrations/viaggiatreno/](Home Assistant
integration).

```python
from viaggiatreno_ha.trainline import (Viaggiatreno,
                                       TrainLine,
                                       TrainLineStatus)
from aiohttp import ClientSession


async def main():
    async with ClientSession() as session:
        vt = Viaggiatreno(session)
        tl = TrainLine('S01765', '136')
        await vt.query_if_running(tl)
        ts = TrainLineStatus(vt.json[tl])
        print(ts)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
