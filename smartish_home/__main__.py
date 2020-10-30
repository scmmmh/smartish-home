import asyncio
import json
import signal
import websockets

#import json
#import requests

TOKEN = ''
#HEADERS = {
#    "Authorization": f"Bearer {TOKEN}",
#    "content-type": "application/json",
#}
#
#response = requests.get('http://10.42.8.5:8123/api/states', headers=HEADERS)
#for state in response.json():
#    print(state['entity_id'])
#print(json.dumps(response.json(), indent=2))

def id_seq():
    nid = 1
    while True:
        yield nid
        nid = nid + 1


ids = iter(id_seq())
messages = {}
running = True


async def send_message(ws, message_type, payload=None):
    identifier = next(ids)
    msg = {
        'id': identifier,
        'type': message_type,
    }
    if payload:
        msg.update(payload)
    await ws.send(json.dumps(msg))
    messages[identifier] = message_type


async def shutdown(signl):
    global running

    print('Shutting down')
    running = False


async def main():
    global running

    print('Connecting')
    async with websockets.connect('ws://10.42.8.5:8123/api/websocket') as websocket:
        print('Connected')
        while running:
            msg = json.loads(await websocket.recv())
            if msg['type'] == 'auth_required':
                print('Authenticating')
                await websocket.send(json.dumps({
                    "type": "auth",
                    "access_token": TOKEN
                }))
            elif msg['type'] == 'auth_ok':
                print('Authenticated')
                await send_message(websocket, 'config/area_registry/list')
                #await send_message(websocket, 'config/device_registry/list')
                #await websocket.send(json.dumps({
                #    'id': next(ids),
                #    'type': 'subscribe_events',
                #    'event_type': 'state_changed'
                #}))
                #await websocket.send(json.dumps({
                #    'id': next(ids),
                #    'type': 'subscribe_events',
                #    'event_type': 'area_registry_updated'
                #}))
                #await websocket.send(json.dumps({
                #    'id': next(ids),
                #    'type': 'subscribe_events',
                #    'event_type': 'device_registry_updated'
                #}))
            elif msg['type'] == 'auth_invalid':
                print('Authentication failed')
                running = False
            else:
                if messages[msg['id']] == 'config/area_registry/list':
                    print('Area list received')
                    del messages[msg['id']]
                else:
                    print(json.dumps(msg, indent=2))


asyncio.get_event_loop().run_until_complete(main())
