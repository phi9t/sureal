import unittest
from advanced.auth_keepalive import refresh_once
class KeepaliveTests(unittest.TestCase):
 def test_valid_renewable_ticket_refreshes_without_interactive_kinit(self):
  calls=[]
  def run(command,label):calls.append((command,label));return 0
  result=refresh_once('/tools/waystone',run)
  self.assertTrue(result['ok']);self.assertTrue(result['ticket_renewed']);self.assertFalse(result['interactive_login_required']);self.assertIn(('/usr/bin/kinit','-R'),[tuple(c) for c,l in calls]);self.assertFalse(any(c==['/usr/bin/kinit'] for c,l in calls))
 def test_expired_unrenewable_ticket_stops_before_token_refresh(self):
  calls=[]
  def run(command,label):calls.append(label);return 1
  result=refresh_once('/tools/waystone',run)
  self.assertFalse(result['ok']);self.assertTrue(result['interactive_login_required']);self.assertNotIn('token-refresh',calls)
 def test_renewal_limit_does_not_discard_still_valid_ticket(self):
  def run(command,label):return 1 if label=='ticket-renewal' else 0
  result=refresh_once('/tools/waystone',run)
  self.assertTrue(result['ok']);self.assertFalse(result['ticket_renewed']);self.assertTrue(result['renewal_window_warning'])
 def test_refresh_failure_reports_actionable_status(self):
  def run(command,label):return 10 if label=='token-refresh' else 0
  result=refresh_once('/tools/waystone',run)
  self.assertFalse(result['ok']);self.assertTrue(result['interactive_login_required'])
if __name__=='__main__':unittest.main()
