import os
from pip.download import PipSession
from pip.index import PackageFinder
from pip.locations import USER_CACHE_DIR


class Index:
    def __init__(self, url):
        self.session = PipSession(cache=os.path.join(USER_CACHE_DIR, 'http'))
        self.finder = PackageFinder(
            [],
            [url],
            session=self.session
        )

    def candidates_for(self, dep, source=False):
        candidates = self.finder.find_all_candidates(dep.name)
        if source:
            candidates = [x for x in candidates if not x.location.is_wheel]
        return candidates

    def best_candidate_of(self, dep, candidates):
        if dep:
            compatible_versions = set(
                dep.req.specifier.filter(
                    [str(c.version) for c in candidates],
                    prereleases=False
                )
            )

            if len(compatible_versions) == 0:
                compatible_versions = set(
                    dep.req.specifier.filter(
                        [str(c.version) for c in candidates],
                        prereleases=True
                    )
                )

            applicable_candidates = [
                c for c in candidates if str(c.version) in compatible_versions
            ]
        else:
            applicable_candidates = candidates

        if not len(applicable_candidates):
            return None

        return max(applicable_candidates, key=self.finder._candidate_sort_key)
