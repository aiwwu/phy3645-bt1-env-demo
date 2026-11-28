"""Giữ yêu cầu mỗi cặp chỉ thay đổi đúng mệnh đề đích."""

import unittest
from unittest.mock import patch

from benchmark import ROOT, read_queries


class QueryPairTest(unittest.TestCase):
    def test_all_three_pairs_pass_clause_check(self):
        self.assertEqual(set(read_queries()), {"where", "group_by", "having"})

    def test_change_outside_where_is_rejected(self):
        original_read = type(ROOT).read_text

        def changed_read(path, *args, **kwargs):
            text = original_read(path, *args, **kwargs)
            if path.name == "where_after.sql":
                return text.replace("COUNT(*)", "COUNT(provider_id)")
            return text

        with patch.object(type(ROOT), "read_text", changed_read):
            with self.assertRaisesRegex(ValueError, "ngoài WHERE"):
                read_queries()


if __name__ == "__main__":
    unittest.main()
