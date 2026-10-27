"""Offline compatibility checks: python -m unittest discover -s tests -v."""
import base64
import hashlib
import hmac
import importlib
import io
import json
import os
from pathlib import Path
import random
import socket
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class DependencyCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden in offline tests'))
        cls.network.start()
        cls.environment = patch.dict(os.environ, {
            'PYTHON_DOTENV_DISABLED': '1',
            'CHANNEL_ACCESS_TOKEN': 'offline-test-token',
            'CHANNEL_SECRET': 'offline-test-secret',
            'GEMINI_API_KEY': '',
            'HOST_URL': 'https://example.invalid',
        })
        cls.environment.start()
        cls.previous_cwd = Path.cwd()
        cls.directory = tempfile.TemporaryDirectory()
        os.chdir(cls.directory.name)
        cls.bot = importlib.import_module('app')
        cls.bot.img_svc.font_path = str(ROOT / 'static/fonts/Yomogi-Regular.ttf')
        cls.bot.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.previous_cwd)
        cls.directory.cleanup()
        cls.environment.stop()
        cls.network.stop()

    def setUp(self):
        self.bot.sessions.clear()
        self.client = self.bot.app.test_client()
        line_patch = patch.object(self.bot, 'line_bot_api', autospec=True)
        self.line = line_patch.start()
        self.addCleanup(line_patch.stop)

    def post_events(self, events, valid=True):
        body = json.dumps({'destination': 'offline-destination', 'events': events})
        signature = base64.b64encode(hmac.new(b'offline-test-secret', body.encode(), hashlib.sha256).digest()).decode()
        return self.client.post('/callback', data=body, headers={
            'Content-Type': 'application/json', 'X-Line-Signature': signature if valid else 'invalid',
        })

    def event(self, message):
        return {'type': 'message', 'replyToken': 'offline-reply', 'timestamp': 0,
                'source': {'type': 'user', 'userId': 'offline-user'}, 'message': message}

    def photo(self, index):
        from PIL import Image
        generator = random.Random(index)
        pixels = bytes(generator.randrange(256) for _ in range(64 * 64 * 3))
        picture = Image.frombytes('RGB', (64, 64), pixels).resize((320, 320))
        path = Path('tmp') / f'photo-{index}.jpg'
        picture.save(path)
        return str(path)

    def test_signature_and_routes(self):
        self.assertEqual(self.client.get('/').status_code, 404)
        self.assertEqual(self.post_events([]).status_code, 200)
        self.assertEqual(self.post_events([], valid=False).status_code, 400)
        response = self.client.get('/static/fonts/Yomogi-Regular.ttf')
        self.assertEqual(response.status_code, 200)
        response.close()
        self.line.reply_message.assert_not_called()
        self.line.push_message.assert_not_called()

    def test_text_webhook_and_reset(self):
        event = self.event({'id': '1', 'type': 'text', 'text': '渋谷, 2026秋'})
        self.assertEqual(self.post_events([event]).status_code, 200)
        session = self.bot.sessions['offline-user']
        self.assertEqual((session['status'], session['location'], session['date']), ('collecting', '渋谷', '2026秋'))
        reply = self.line.reply_message.call_args.args[1]
        self.assertEqual(reply.as_json_dict()['type'], 'text')
        event['message']['text'] = 'reset'
        self.assertEqual(self.post_events([event]).status_code, 200)
        self.assertEqual(self.bot.sessions['offline-user']['status'], 'idle')

    def test_image_webhook_and_completion_dispatch(self):
        from PIL import Image
        data = io.BytesIO()
        Image.new('RGB', (64, 64), 'red').save(data, format='JPEG')
        self.line.get_message_content.return_value.iter_content.return_value = [data.getvalue()]
        self.bot.sessions['offline-user'] = {'status': 'collecting', 'location': 'Tokyo', 'date': '2026秋', 'images': []}
        event = self.event({'id': '2', 'type': 'image', 'contentProvider': {'type': 'line'}})
        self.assertEqual(self.post_events([event]).status_code, 200)
        paths = self.bot.sessions['offline-user']['images'][:]
        self.assertEqual(len(paths), 1)
        with Image.open(paths[0]) as photo:
            self.assertEqual(photo.size, (64, 64))
        with patch.object(self.bot.threading, 'Thread') as thread:
            event['message'] = {'id': '3', 'type': 'text', 'text': '完了'}
            self.assertEqual(self.post_events([event]).status_code, 200)
            thread.return_value.start.assert_called_once()
            self.assertEqual(thread.call_args.kwargs['args'][1]['images'], paths)
        self.assertEqual(self.bot.sessions['offline-user']['status'], 'idle')

    def test_album_generation_and_message_serialization(self):
        from PIL import Image
        paths = [self.photo(i) for i in range(3)]
        unique = self.bot.img_svc._deduplicate_images(paths + [paths[0]])
        self.assertEqual(len(unique), 3)
        captions = {'title': '旅の思い出', 'location_romaji': 'Tokyo', 'comment': 'テスト'}
        with patch.object(self.bot.gemini, 'generate_captions', return_value=captions):
            self.bot.generate_album_task('offline-user', {'location': '東京', 'date': '2026秋', 'images': paths})
        self.line.push_message.assert_called_once()
        messages = self.line.push_message.call_args.args[1]
        self.assertEqual([m.as_json_dict()['type'] for m in messages], ['text', 'image'])
        image = messages[1].as_json_dict()
        self.assertTrue(image['originalContentUrl'].startswith('https://example.invalid/static/images/'))
        output = Path('static/images') / image['originalContentUrl'].rsplit('/', 1)[-1]
        with Image.open(output) as photo:
            self.assertEqual(photo.size, (1080, 1920))
        # Generated files live only in the temporary test directory.
        with patch.object(self.bot.app, 'root_path', str(Path.cwd())):
            response = self.client.get('/static/images/' + output.name)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_gemini_response_parsing_and_fallback(self):
        model = Mock()
        model.generate_content.return_value = SimpleNamespace(text='```json\n{"title":"Test","location_romaji":"Tokyo","comment":"OK"}\n```')
        with patch.object(self.bot.gemini, 'model', model, create=True):
            self.assertEqual(self.bot.gemini.generate_captions('東京', '2026')['title'], 'Test')
            model.generate_content.side_effect = RuntimeError('offline simulated error')
            self.assertEqual(self.bot.gemini.generate_captions('東京', '2026')['title'], 'Travel Memoz')

    def test_requests_uses_patched_certifi(self):
        import certifi
        import requests
        self.assertEqual(certifi.__version__, '2026.10.19')
        self.assertEqual(requests.certs.where(), certifi.where())


if __name__ == '__main__':
    unittest.main()
