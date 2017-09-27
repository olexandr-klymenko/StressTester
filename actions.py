import asyncio
import json
from logging import getLogger
from typing import Dict, Union

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError, ClientOSError, ClientResponseError
from concurrent.futures._base import TimeoutError

from constants import MAX_RETRY, RETRY_DELAY
from counter import StatsCounter
from actions_registry import register_action_decorator
from codes_description import HTTPCodesDescription
from utils import async_timeit_decorator


logger = getLogger('asyncio')


@register_action_decorator('rest')
async def async_rest_call(name, **kwargs) -> Union[str, bytes]:
    if kwargs.get('raw'):
        kwargs['data'] = json.dumps(kwargs['data'])
    attempts_left = MAX_RETRY
    while attempts_left:
        async with ClientSession() as session:
            try:
                resp_data = await async_http_request(name, session, **kwargs)
            except (ClientConnectorError, ClientOSError, ClientResponseError, TimeoutError) as err:
                logger.warning(str(err))
                StatsCounter.append_error_metric(action_name=name)
                attempts_left -= 1
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                return resp_data
    raise Exception("Max number of retries exceeded")


@async_timeit_decorator
async def async_http_request(name, session: ClientSession, **kwargs) -> str:
    print(json.loads(kwargs.get('data')))
    async with session.request(method=kwargs['method'],
                               url=kwargs['url'],
                               data=json.loads(kwargs.get('data')),
                               headers=kwargs.get('headers'),
                               params=kwargs.get('params')) as resp:
        resp_data = await resp.text()
        description = HTTPCodesDescription.get_description(resp.status, **kwargs)
        logger.info("'%s' %s %s, status: %s, description: %s\n\tpayload: %s\n\tparams: %s\n\tresponse data: %s" %
                    (name,
                     kwargs['url'],
                     kwargs['method'].upper(),
                     resp.status,
                     description,
                     kwargs.get('data'),
                     kwargs.get('params'),
                     resp_data))
        return resp_data


@register_action_decorator('sleep')
async def async_sleep(sec):
    await asyncio.sleep(sec)


@register_action_decorator('get')
async def get_value(info: Union[str, Dict], key: str):
    assert info != "", 'Incorrect dictionary'
    try:
        if isinstance(info, dict):
            info = json.dumps(info)
        return json.loads(info)[key]
    except TypeError:
        logger.error("Unexpected value of 'info'. Expected: dict(), got: %s" % info)
        raise