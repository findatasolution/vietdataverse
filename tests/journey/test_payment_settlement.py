"""PayOS callback/return-page regression tests; no external requests or DB writes."""
import asyncio
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from test_public_plans import load_definitions

ROOT = Path(__file__).resolve().parents[2]


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.order = [7, 'pro_monthly', 'pending', 'subscription', None, 45000, 'link-test']
        self.lock = threading.Lock()
        self.commits = 0
        self.activations = []
        self.queries = []
        owner = self

        class Session:
            locked = False
            def execute(self, sql, params):
                owner.queries.append(sql)
                if 'SELECT user_id, plan' in sql:
                    if 'FOR UPDATE' not in sql:
                        raise AssertionError('Settlement must lock the order before reading its status')
                    owner.lock.acquire()
                    self.locked = True
                    return SimpleNamespace(fetchone=lambda: tuple(owner.order) if owner.order else None)
                if "SET status = 'paid'" in sql:
                    owner.order[2] = 'paid'
                return SimpleNamespace(fetchone=lambda: None)
            def commit(self):
                owner.commits += 1
            def close(self):
                if self.locked:
                    self.locked = False
                    owner.lock.release()

        def activate(session, uid, plan):
            self.activations.append((uid, plan))
            return datetime(2026, 10, 22)

        self.ns = {'text': lambda sql: sql, 'HTTPException': HTTPException, 'Request': object, 'hashlib': hashlib,
                   '_hmac': hmac, 'json': json, '_session': Session,
                   '_activate_premium': activate, 'PAYOS_CHECKSUM_KEY': 'fixture-only-key',
                   'PAYOS_CLIENT_ID': 'fixture', 'PAYOS_API_KEY': 'fixture'}
        load_definitions(ROOT / 'be/payment.py', {'SUBSCRIPTION_PLANS', '_verify_payos_webhook',
                         '_settle_paid_order', 'verify_order', 'payos_webhook'}, self.ns)
        self.ns['_query_payos_order'] = Mock(return_value={'code':'00','data':{
            'orderCode':123, 'id':'link-test', 'status':'PAID', 'amount':45000, 'amountPaid':45000}})

    def webhook(self, **changes):
        data = {'orderCode':123, 'amount':45000, 'currency':'VND', 'code':'00',
                'paymentLinkId':'link-test', 'reference':'fixture-reference'}
        data.update(changes)
        signature = hmac.new(b'fixture-only-key', '&'.join(f'{k}={data[k]}' for k in sorted(data)).encode(), hashlib.sha256).hexdigest()
        body = {'code':'00','success':True,'data':data,'signature':signature}
        async def read(): return body
        return SimpleNamespace(json=read), body

    def test_official_callback_without_status_activates(self):
        request, _ = self.webhook()
        self.assertEqual(asyncio.run(self.ns['payos_webhook'](request)), {'success':True})
        self.assertEqual(self.order[2], 'paid')
        self.assertEqual(self.activations, [(7,'pro_monthly')])

    def test_webhook_then_return_then_replay_only_activates_once(self):
        request, _ = self.webhook()
        asyncio.run(self.ns['payos_webhook'](request))
        result = asyncio.run(self.ns['verify_order'](123))
        asyncio.run(self.ns['payos_webhook'](request))
        self.assertTrue(result['already_paid'])
        self.assertEqual(result['amount'], 45000)
        self.assertEqual(len(self.activations), 1)

    def test_concurrent_confirmations_only_activate_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.ns['_settle_paid_order'](123,45000,'link-test'), range(2)))
        self.assertEqual(sum(r['activated'] for r in results), 1)
        self.assertEqual(len(self.activations), 1)

    def test_mismatched_amount_or_link_rejected(self):
        for changes in ({'amount':22500}, {'paymentLinkId':'different'}):
            request, _ = self.webhook(**changes)
            with self.assertRaises(HTTPException) as err:
                asyncio.run(self.ns['payos_webhook'](request))
            self.assertEqual(err.exception.status_code,409)
        self.assertFalse(self.activations)
        self.assertEqual(self.commits,0)

    def test_student_order_uses_stored_discounted_amount(self):
        self.order[5] = 22500
        request, _ = self.webhook(amount=22500)
        asyncio.run(self.ns['payos_webhook'](request))
        self.assertEqual(len(self.activations),1)

    def test_invalid_signature_and_missing_configuration_fail_closed(self):
        request, body = self.webhook()
        body['data']['amount'] = 1
        with self.assertRaises(HTTPException): asyncio.run(self.ns['payos_webhook'](request))
        request, _ = self.webhook()
        self.ns['PAYOS_CHECKSUM_KEY'] = ''
        with self.assertRaises(HTTPException) as err: asyncio.run(self.ns['payos_webhook'](request))
        self.assertEqual(err.exception.status_code,503)
        self.assertFalse(self.activations)

    def test_unsuccessful_callback_ignored(self):
        request, _ = self.webhook(code='01')
        asyncio.run(self.ns['payos_webhook'](request))
        self.assertFalse(self.activations)

    def test_topup_never_activates_api_subscription(self):
        self.order[1], self.order[3], self.order[4] = 'credit_topup', 'credit_topup', 45
        topup = Mock()
        with patch.dict(sys.modules, {'services.credit':SimpleNamespace(credit_topup=topup)}):
            result = asyncio.run(self.ns['verify_order'](123))
        self.assertEqual(result['order_type'],'credit_topup')
        self.assertFalse(result['activated'])
        self.assertFalse(self.activations)
        topup.assert_called_once()

    def test_unknown_order_acknowledged_for_payos_setup_probe(self):
        self.order = None
        request, _ = self.webhook()
        self.assertEqual(asyncio.run(self.ns['payos_webhook'](request)), {'success':True})
        self.assertFalse(self.activations)

    def test_pending_and_wrong_gateway_order_do_not_activate(self):
        response = self.ns['_query_payos_order'].return_value
        response['data']['status'] = 'PENDING'
        self.assertFalse(asyncio.run(self.ns['verify_order'](123))['activated'])
        response['data']['orderCode'] = 999
        with self.assertRaises(HTTPException): asyncio.run(self.ns['verify_order'](123))
        self.assertFalse(self.activations)


if __name__ == '__main__': unittest.main()
