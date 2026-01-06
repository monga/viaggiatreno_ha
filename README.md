This package is designed to query the [Trenitalia
ViaggiaTreno](http://www.viaggiatreno.it/infomobilita/index.jsp) API (that are
mostly undocumented, but see [here, in
Italian](https://github.com/roughconsensusandrunningcode/TrainMonitor/wiki/API-del-sistema-Viaggiatreno))
in a [Home Assistant
integration](https://www.home-assistant.io/integrations/viaggiatreno/).

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
