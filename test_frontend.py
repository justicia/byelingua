import unittest
from pathlib import Path


class FrontendSubscriptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = Path(__file__).with_name("index.html").read_text(encoding="utf-8")

    def test_my_subscriptions_has_an_add_website_button(self):
        self.assertIn('id="personalAddButton"', self.index)
        self.assertIn('$("personalAddButton").onclick=openPersonalSubscriptionDialog', self.index)

    def test_personal_subscription_list_has_scoped_delete_action(self):
        self.assertIn('data-remove="${esc(x.id)}"', self.index)
        self.assertIn('action:"delete_my_subscription",id', self.index)

    def test_personal_add_dialog_uses_authenticated_subscription_action(self):
        self.assertIn('action:"save_my_subscription",subscription:sub', self.index)
        self.assertIn('function openPersonalSubscriptionDialog()', self.index)


if __name__ == "__main__":
    unittest.main()
