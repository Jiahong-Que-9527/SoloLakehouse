import unittest

from silver_m1 import fresh, split


class FragmentBoundaries(unittest.TestCase):
    @staticmethod
    def points(times, lons=None):
        return [dict(position_epoch_s=t, latitude=50.0, longitude=lon)
                for t, lon in zip(times, lons or [8.5]*len(times))]

    def test_timing_threshold_and_isolated_point(self):
        fragments, gaps, deltas = split({}, self.points([3, 33, 64]), [], [])
        self.assertEqual(deltas, [30, 31])
        self.assertEqual([f["point_count"] for f in fragments], [2, 1])
        self.assertEqual(gaps[0]["reason"], "time_gap")
        self.assertEqual((gaps[0]["left_fragment_no"], gaps[0]["right_fragment_no"]), (1, 2))

    def test_airborne_partition_and_jump(self):
        _, gaps, _ = split({}, self.points([3590, 3605]), [3598], [(3600, "source_gap")])
        self.assertEqual(gaps[0]["reason"], "source_partition")
        _, gaps, _ = split({}, self.points([10, 20, 21], [8.5, 8.5, 8.505]), [15], [])
        self.assertEqual([gap["reason"] for gap in gaps],
                         ["airborne_observation", "implausible_displacement"])

    def test_position_freshness(self):
        self.assertTrue(fresh(100, 85))
        self.assertFalse(fresh(100, 84))
        self.assertFalse(fresh(100, None))
        self.assertFalse(fresh(100, 103))


if __name__ == "__main__":
    unittest.main()
