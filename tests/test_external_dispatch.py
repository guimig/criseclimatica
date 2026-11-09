import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from dispatch_update import dispatch, ENDPOINT


class ExternalDispatchTests(unittest.TestCase):
    def test_requires_private_token_before_network_call(self):
        for value in [None, '', 'with space']:
            with patch('dispatch_update.build_opener') as opener:
                with self.assertRaisesRegex(RuntimeError, 'Configure'):
                    dispatch(value)
                opener.assert_not_called()

    def test_fixed_repository_and_main_branch_are_dispatched(self):
        opener=MagicMock();opener.open.return_value.__enter__.return_value.status=204
        with patch('dispatch_update.build_opener',return_value=opener):dispatch('test-token')
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,ENDPOINT)
        self.assertEqual(request.method,'POST')
        self.assertEqual(json.loads(request.data),{'ref':'main'})
        self.assertEqual(request.get_header('Authorization'),'Bearer test-token')

    def test_errors_do_not_expose_token_or_response_body(self):
        for error in [HTTPError(ENDPOINT,401,'secret-body',{},None),URLError('secret-body')]:
            opener=MagicMock();opener.open.side_effect=error
            with patch('dispatch_update.build_opener',return_value=opener):
                with self.assertRaises(RuntimeError) as caught:dispatch('test-token')
            self.assertNotIn('test-token',str(caught.exception))
            self.assertNotIn('secret-body',str(caught.exception))
