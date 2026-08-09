import unittest

from migrate_articles_to_supabase import normalize_article


class ArticleMigrationTests(unittest.TestCase):
    def test_jsonb_columns_fall_back_to_complete_raw_data(self):
        expected = {
            "contents": {"zh": "中文正文", "en": "English body"},
            "titles": {"zh": "中文标题", "en": "English title"},
            "translations": {"zh": "中文全文", "fr": "Texte français"},
            "translated_titles": {"zh": "中文标题", "fr": "Titre français"},
            "summaries": {"fr": "Résumé"},
            "translation_jobs": {"fr": {"status": "completed"}},
        }
        article = {
            "id": "article-1",
            "url": "https://example.com/article-1",
            **{key: {} for key in expected},
            "raw_data": {
                **expected,
                "translation_instruction": "Use British English",
            },
        }

        row = normalize_article(article)

        for key, value in expected.items():
            self.assertEqual(row[key], value)
        self.assertEqual(row["translation_instruction"], "Use British English")

    def test_populated_top_level_jsonb_columns_take_precedence(self):
        article = {
            "id": "article-2",
            "url": "https://example.com/article-2",
            "contents": {"zh": "current"},
            "raw_data": {"contents": {"zh": "stale"}},
        }

        self.assertEqual(normalize_article(article)["contents"], {"zh": "current"})


if __name__ == "__main__":
    unittest.main()
